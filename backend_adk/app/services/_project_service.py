# backend/app/services/_project_service.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core._security import hash_password
from app.models._client_profile import ClientProfile
from app.models._checkpoint import Checkpoint
from app.models._blocker import Blocker
from app.models._communication import Communication
from app.models._decision_log import DecisionLog
from app.models._employee_profile import EmployeeProfile
from app.models._event_queue import EventQueue
from app.models._meeting import Meeting
from app.models._performance_point import PerformancePoint
from app.models._project import Project
from app.models._team import Team, TeamMember
from app.models._team_invite import TeamInvite
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._task_dependency import TaskDependency
from app.models._task_progress import TaskProgress
from app.models._user import User
from app.models._workflow_run import WorkflowRun
from app.core._logging import get_logger
from app.services._invite_service import (
    apply_invite_response,
    create_team_invite,
    find_project_invite_for_actor,
    get_invite_for_actor,
    get_or_create_project_team,
    normalize_email,
)
from app.services._llm_service import LLMService
from app.schemas._project import ProjectCreate


DEFAULT_APPROVAL_WINDOW_MINUTES = 5
logger = get_logger(__name__)


ROLE_SKILL_MAP = {
    "Solution Architect": ("architecture", "delivery"),
    "AI Engineer": ("llm", "modeling"),
    "Backend Engineer": ("backend", "api"),
    "Frontend Engineer": ("frontend", "react"),
    "QA Automation Engineer": ("qa", "testing", "automation"),
    "Project Coordinator": ("project-management",),
    "Client Success Manager": ("client-success", "reporting"),
    "DevOps Engineer": ("devops", "cloud", "security"),
    "Data Engineer": ("data", "analytics"),
    "Prompt Engineer": ("prompting", "research"),
}

DEFAULT_PROJECT_TEAM_ORDER = [
    "Project Coordinator",
    "Solution Architect",
    "AI Engineer",
    "Backend Engineer",
    "Client Success Manager",
]


def _utcnow() -> datetime:
    return datetime.utcnow()


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def create_project(db: Session, payload: ProjectCreate, admin: User):
    if admin.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create projects")

    duplicate = (
        db.query(Project)
        .filter(
            Project.tenant_id == admin.tenant_id,
            func.lower(Project.name) == payload.name.strip().lower(),
            Project.status != "completed",
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=409, detail="A project with this name already exists in your tenant")

    llm_service = LLMService()
    client, client_report = _resolve_client(db, payload, admin.tenant_id)
    planning_packet = llm_service.parse_project_intake(payload.description or payload.name)
    role_clusters = _build_role_clusters(planning_packet)
    recommended_team = _recommend_team(db, admin.tenant_id, role_clusters)
    approval_deadline = _utcnow() + timedelta(minutes=DEFAULT_APPROVAL_WINDOW_MINUTES)
    project_deadline = _normalize_datetime(payload.deadline)
    guidance_context = {
        "project_name": payload.name,
        "project_summary": planning_packet.get("project_summary", payload.description),
        "client_company_name": client.company_name if client else None,
        "recommended_team": recommended_team,
        "task_titles": [task["title"] for task in planning_packet.get("tasks", [])],
        "role_clusters": role_clusters,
    }

    project = Project(
        tenant_id=admin.tenant_id,
        name=payload.name,
        description=payload.description,
        budget=payload.budget,
        admin_id=admin.id,
        client_id=client.id if client else None,
        priority=payload.priority,
        deadline=project_deadline,
        status=payload.status,
        payment_status=payload.payment_status,
        progress=8,
        custom_fields={
            "current_phase": "intake",
            "client_status": "registered" if client else "pending",
            "client_response_status": "awaiting-brief-confirmation",
            "approval_status": "awaiting-admin-approval",
            "approval_deadline": approval_deadline.isoformat(),
            "approval_window_minutes": DEFAULT_APPROVAL_WINDOW_MINUTES,
            "admin_requirements": payload.description,
            "next_decision": "Admin approval required for the AI-generated team draft and role plan",
            "recommended_team": recommended_team,
            "role_clusters": role_clusters,
            "team_invites": [],
            "team_join_deadline": None,
            "team_join_window_minutes": 240,
            "team_join_status": "pending-admin-approval",
            "replacement_suggestions": [],
            "emp_involved_ids": [],
            "report_text": None,
            "planning_packet": {
                "project_complexity": planning_packet.get("project_complexity"),
                "project_summary": planning_packet.get("project_summary"),
                "project_structure": planning_packet.get("project_structure"),
                "tasks": planning_packet.get("tasks", []),
            },
            "stage_briefs": {
                "admin": llm_service.generate_stage_brief("planning", "admin", guidance_context),
                "employee": llm_service.generate_stage_brief("planning", "employee", guidance_context),
                "client": llm_service.generate_stage_brief("planning", "client", guidance_context),
            },
            "decision_support": {
                "admin": llm_service.generate_decision_support("team_approval", "admin", guidance_context),
                "employee": llm_service.generate_decision_support("team_approval", "employee", guidance_context),
            },
            "presentation_status": "txt draft for now; designed PPT later",
            "deadline_policy": "Escalate to admin meeting if team response misses approval window",
        },
    )
    db.add(project)
    db.flush()
    team = get_or_create_project_team(db, project, admin.id)
    project.custom_fields["team_id"] = team.id

    _seed_project_plan(db, project, planning_packet, role_clusters)
    _log_project_intake(db, project, client_report, recommended_team)
    _notify_client_on_project_start(db, project, client)

    db.commit()
    db.refresh(project)
    return build_project_status(db, project.id)


def get_projects(db: Session, viewer: Optional[User] = None):
    ensure_deadline_escalations(db)
    query = db.query(Project).options(joinedload(Project.client)).order_by(Project.created_at.desc())
    if viewer and viewer.tenant_id is not None:
        query = query.filter(Project.tenant_id == viewer.tenant_id)

    if viewer and viewer.role == "employee":
        employee_profile = (
            db.query(EmployeeProfile)
            .filter(EmployeeProfile.user_id == viewer.id, EmployeeProfile.tenant_id == viewer.tenant_id)
            .first()
        )
        if not employee_profile:
            return []
        projects = query.all()
        visible = []
        for project in projects:
            meta = _project_meta(project)
            has_assignment = (
                db.query(TaskAssignment)
                .join(Task, Task.id == TaskAssignment.task_id)
                .filter(Task.project_id == project.id, TaskAssignment.employee_id == employee_profile.id)
                .first()
            )
            has_invite = any(
                normalize_email(invite.get("email", "")) == normalize_email(viewer.email)
                or invite.get("employee_id") == employee_profile.id
                for invite in meta.get("team_invites", [])
            )
            if has_assignment or has_invite:
                visible.append(project)
        return [_serialize_project_summary(db, project, viewer) for project in visible]
    elif viewer and viewer.role == "client":
        client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == viewer.id).first()
        if not client_profile:
            return []
        query = query.filter(Project.client_id == client_profile.id)

    projects = query.all()
    return [_serialize_project_summary(db, project, viewer) for project in projects]


def get_clients(db: Session, viewer: Optional[User] = None):
    query = db.query(ClientProfile).options(joinedload(ClientProfile.user))
    if viewer and viewer.tenant_id is not None:
        query = query.filter(ClientProfile.tenant_id == viewer.tenant_id)
    clients = query.order_by(ClientProfile.company_name.asc()).all()
    results = []
    for client in clients:
        results.append(
            {
                "id": client.id,
                "company_name": client.company_name,
                "contact_person": client.contact_person,
                "email": client.user.email if client.user else None,
                "full_name": client.user.full_name if client.user else None,
                "phone": client.phone,
                "address": client.address,
            }
        )
    return results


def build_admin_dashboard(db: Session, admin: User):
    ensure_deadline_escalations(db)
    projects = (
        db.query(Project)
        .options(joinedload(Project.client))
        .filter(Project.tenant_id == admin.tenant_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    employees = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.tenant_id == admin.tenant_id)
        .all()
    )
    decisions = db.query(DecisionLog).order_by(DecisionLog.created_at.desc()).limit(8).all()

    active_projects = [_serialize_project_summary(db, project) for project in projects if project.status != "completed"]
    completed_projects = [_serialize_completed_project(project) for project in projects if project.status == "completed"]

    team_size = len(employees)
    available_count = len([employee for employee in employees if employee.current_load == 0 and employee.availability_status != "on-leave"])
    avg_workload = round(
        sum(_workload_percent(employee.current_load, employee.max_capacity) for employee in employees) / team_size,
        1,
    ) if team_size else 0.0

    return {
        "summary": {
            "active_projects": len(active_projects),
            "completed_projects": len(completed_projects),
            "clients": len({project.client_id for project in projects if project.client_id}),
            "team_size": team_size,
            "employees_available_now": available_count,
            "average_team_workload": avg_workload,
            "projects_waiting_approval": len(
                [
                    project
                    for project in projects
                    if _project_meta(project).get("approval_status") in {"awaiting-admin-approval", "awaiting-team-join"}
                ]
            ),
        },
        "active_projects": active_projects,
        "completed_projects": completed_projects,
        "recent_decisions": [
            {
                "id": decision.id,
                "decision_type": decision.decision_type,
                "decision_taken": decision.decision_taken,
                "confidence": decision.confidence,
                "created_at": decision.created_at.isoformat(),
            }
            for decision in decisions
        ],
        "clients": get_clients(db, admin),
    }


def build_team_dashboard(db: Session, admin: User):
    employees = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user), joinedload(EmployeeProfile.assignments).joinedload(TaskAssignment.task))
        .filter(EmployeeProfile.tenant_id == admin.tenant_id)
        .order_by(EmployeeProfile.department.asc(), EmployeeProfile.id.asc())
        .all()
    )

    members = []
    for employee in employees:
        active_assignments = [
            assignment
            for assignment in employee.assignments
            if assignment.task and assignment.task.project and assignment.task.project.status != "completed"
        ]
        members.append(
            {
                "employee_id": employee.id,
                "name": employee.user.full_name if employee.user else f"Employee {employee.id}",
                "email": employee.user.email if employee.user else None,
                "title": _title_from_employee(employee),
                "department": employee.department,
                "shift_status": "On Leave" if employee.availability_status == "on-leave" else "On Duty",
                "availability_status": employee.availability_status,
                "workload_percent": _workload_percent(employee.current_load, employee.max_capacity),
                "current_load": employee.current_load,
                "max_capacity": employee.max_capacity,
                "skills": employee.skills,
                "active_assignment_count": len(active_assignments),
                "active_projects": sorted(
                    {assignment.task.project.name for assignment in active_assignments if assignment.task and assignment.task.project}
                ),
            }
        )

    return {
        "team_size": len(members),
        "members": members,
        "summary": {
            "free_now": len([member for member in members if member["workload_percent"] == 0 and member["availability_status"] != "on-leave"]),
            "on_leave": len([member for member in members if member["availability_status"] == "on-leave"]),
            "busy": len([member for member in members if member["workload_percent"] >= 70]),
        },
    }


def build_agentic_dashboard(db: Session, admin: User):
    ensure_deadline_escalations(db)
    llm_service = LLMService()
    projects = (
        db.query(Project)
        .options(joinedload(Project.client))
        .filter(Project.tenant_id == admin.tenant_id)
        .order_by(Project.created_at.desc())
        .all()
    )
    low_confidence = (
        db.query(DecisionLog)
        .filter(DecisionLog.confidence < 0.7)
        .order_by(DecisionLog.created_at.desc())
        .limit(10)
        .all()
    )
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).limit(10).all()

    approvals = []
    suggestions = []
    for project in projects:
        meta = _project_meta(project)
        approvals.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "approval_status": meta.get("approval_status"),
                "approval_deadline": meta.get("approval_deadline"),
                "team_join_deadline": meta.get("team_join_deadline"),
                "current_phase": meta.get("current_phase"),
                "next_decision": meta.get("next_decision"),
                "recommended_team": meta.get("recommended_team", []),
            }
        )
        suggestions.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "requires_admin_attention": meta.get("approval_status") in {"escalated", "rejected"},
                "suggestion": _suggestion_for_project(project),
            }
        )

    return {
        "approvals": approvals,
        "suggestions": suggestions,
        "llm_status": {
            "enabled": llm_service.enabled,
            "model_id": llm_service.model_id,
            "init_error": llm_service.init_error,
        },
        "low_confidence_decisions": [
            {
                "id": decision.id,
                "decision_type": decision.decision_type,
                "entity_type": decision.entity_type,
                "entity_id": decision.entity_id,
                "decision_taken": decision.decision_taken,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "created_at": decision.created_at.isoformat(),
            }
            for decision in low_confidence
        ],
        "escalation_meetings": [
            {
                "meeting_id": meeting.id,
                "project_id": meeting.project_id,
                "title": meeting.title,
                "meeting_type": meeting.meeting_type,
                "scheduled_at": meeting.scheduled_at.isoformat() if meeting.scheduled_at else None,
            }
            for meeting in meetings
        ],
    }


def build_project_status(db: Session, project_id: int, viewer: Optional[User] = None):
    ensure_deadline_escalations(db)
    project = (
        db.query(Project)
        .options(joinedload(Project.client).joinedload(ClientProfile.user), joinedload(Project.tasks).joinedload(Task.assignments))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if viewer and viewer.tenant_id != project.tenant_id:
        raise HTTPException(status_code=403, detail="Not authorized to view this project")

    if viewer and viewer.role == "employee":
        employee_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == viewer.id).first()
        employee_task_ids = {
            assignment.task_id
            for assignment in db.query(TaskAssignment).filter(
                TaskAssignment.employee_id == employee_profile.id if employee_profile else -1
            ).all()
        }
        project_task_ids = {task.id for task in project.tasks}
        pending_invite = any(
            invite.get("employee_id") == (employee_profile.id if employee_profile else None)
            for invite in _project_meta(project).get("team_invites", [])
        )
        if not employee_profile or (not employee_task_ids.intersection(project_task_ids) and not pending_invite):
            raise HTTPException(status_code=403, detail="Not authorized to view this project")

    if viewer and viewer.role == "client":
        client_profile = db.query(ClientProfile).filter(ClientProfile.user_id == viewer.id).first()
        if not client_profile or project.client_id != client_profile.id:
            raise HTTPException(status_code=403, detail="Not authorized to view this project")

    tasks = project.tasks
    assignments = [assignment for task in tasks for assignment in task.assignments]
    involved_employees = _collect_involved_employees(db, assignments, project)
    completed_tasks = len([task for task in tasks if task.status == "done"])
    blocked_tasks = len([task for task in tasks if task.status == "blocked"])
    in_progress_tasks = len([task for task in tasks if task.status in {"running", "in-progress"}])
    top_level_tasks = [task for task in tasks if task.parent_task_id is None]
    meta = _refresh_project_team_metadata(db, project)
    visible_client_id = project.client_id if not viewer or viewer.role == "admin" else None
    public_status_label = _client_business_summary(project, top_level_tasks, meta)

    return {
        "id": project.id,
        "project_id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "progress": project.progress,
        "priority": project.priority,
        "budget": project.budget,
        "spent": project.spent,
        "payment_status": project.payment_status,
        "client_id": visible_client_id,
        "client_name": project.client.company_name if project.client else None,
        "client_email": project.client.user.email if project.client and project.client.user else None,
        "client_status": meta.get("client_status"),
        "client_response_status": meta.get("client_response_status"),
        "approval_status": meta.get("approval_status"),
        "approval_deadline": meta.get("approval_deadline"),
        "team_join_deadline": meta.get("team_join_deadline"),
        "team_join_status": meta.get("team_join_status"),
        "current_phase": meta.get("current_phase"),
        "next_decision": meta.get("next_decision"),
        "public_status_label": public_status_label,
        "viewer_guidance": _guidance_for_viewer(meta, viewer),
        "decision_support": _decision_support_for_viewer(meta, viewer),
        "planning_summary": meta.get("planning_packet", {}).get("project_summary"),
        "role_clusters": meta.get("role_clusters", []),
        "team_invites": _visible_team_invites(meta, viewer),
        "replacement_suggestions": meta.get("replacement_suggestions", []),
        "emp_involved": involved_employees,
        "task_summary": {
            "total": len(top_level_tasks),
            "completed": completed_tasks,
            "in_progress": in_progress_tasks,
            "blocked": blocked_tasks,
        },
        "tasks": [
            {
                "id": task.id,
                "description": task.description,
                "status": task.status,
                "difficulty": task.difficulty,
                "urgency": task.urgency,
                "estimated_time": task.estimated_time,
                "required_role": meta.get("task_role_map", {}).get(str(task.id)),
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "assignments": [
                    {
                        "employee_id": assignment.employee_id,
                        "employee_name": assignment.employee.user.full_name if assignment.employee and assignment.employee.user else None,
                        "status": assignment.status,
                        "estimated_hours": assignment.estimated_hours,
                    }
                    for assignment in task.assignments
                ],
            }
            for task in top_level_tasks
        ],
        "report_text": meta.get("report_text"),
        "presentation_status": meta.get("presentation_status"),
    }


def handle_team_approval(db: Session, project_id: int, approved: bool, note: Optional[str], actor_id: int):
    project = (
        db.query(Project)
        .options(joinedload(Project.tasks).joinedload(Task.assignments))
        .filter(Project.id == project_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    meta = _project_meta(project)
    meta["approval_response_note"] = note
    meta["approval_acted_at"] = _utcnow().isoformat()
    llm_service = LLMService()
    guidance_context = {
        "project_name": project.name,
        "project_summary": project.description,
        "recommended_team": meta.get("recommended_team", []),
        "project_id": project.id,
    }

    if approved:
        team = get_or_create_project_team(db, project, actor_id)
        _sync_project_team_invites(db, project, team, meta.get("recommended_team", []), meta.get("role_clusters", []), actor_id)
        meta["approval_status"] = "awaiting-team-join"
        meta["current_phase"] = "team-confirmation"
        meta["team_join_deadline"] = (_utcnow() + timedelta(hours=4)).isoformat()
        meta["team_join_status"] = "awaiting-responses"
        meta["team_invites"] = _load_team_invite_summaries(db, project)
        meta["next_decision"] = "Wait for every drafted team member to accept the project within four hours"
        meta["stage_briefs"] = {
            "admin": llm_service.generate_stage_brief("team-confirmation", "admin", guidance_context),
            "employee": llm_service.generate_stage_brief("team-confirmation", "employee", guidance_context),
            "client": llm_service.generate_stage_brief("team-confirmation", "client", guidance_context),
        }
        meta["decision_support"] = {
            "admin": llm_service.generate_decision_support("team_join", "admin", guidance_context),
            "employee": llm_service.generate_decision_support("project_invite", "employee", guidance_context),
        }
        project.status = "planning"
        project.progress = max(project.progress, 12)
        _log_decision(
            db,
            "team_approval",
            project.id,
            0.91,
            f"Admin approved the AI-generated team draft. {note or 'No additional note provided.'}",
        )
    else:
        meta["approval_status"] = "rejected"
        meta["current_phase"] = "admin-review"
        meta["next_decision"] = "Admin intervention required before restarting kickoff"
        meta["stage_briefs"] = {
            "admin": llm_service.generate_stage_brief("admin-review", "admin", guidance_context),
            "employee": llm_service.generate_stage_brief("admin-review", "employee", guidance_context),
            "client": llm_service.generate_stage_brief("admin-review", "client", guidance_context),
        }
        meta["decision_support"] = {
            "admin": llm_service.generate_decision_support("team_rejection", "admin", guidance_context),
            "employee": llm_service.generate_decision_support("team_rejection", "employee", guidance_context),
        }
        project.status = "on-hold"
        _create_admin_meeting(
            db,
            project,
            actor_id,
            "Admin review meeting for rejected kickoff plan",
            "review",
            note or "Team rejected the kickoff plan and requested admin intervention.",
        )
        _log_decision(
            db,
            "team_rejection",
            project.id,
            0.82,
            f"Team rejected kickoff plan. {note or 'No additional note provided.'}",
        )

    project.custom_fields = meta
    db.add(project)
    db.commit()
    db.refresh(project)
    return build_project_status(db, project.id)


def handle_project_invite_response(db: Session, project_id: int, accepted: bool, note: Optional[str], actor: User):
    if actor.role != "employee":
        raise HTTPException(status_code=403, detail="Only employees can respond to project invites")

    invite = find_project_invite_for_actor(db, project_id, actor)
    return handle_team_invite_action(db=db, actor=actor, invite_id=invite.id, token=None, accepted=accepted, note=note)

def handle_team_invite_action(
    db: Session,
    *,
    actor: User,
    invite_id: Optional[int],
    token: Optional[str],
    accepted: bool,
    note: Optional[str],
):
    if actor.role != "employee":
        raise HTTPException(status_code=403, detail="Only employees can respond to team invites")

    invite = get_invite_for_actor(db, invite_id=invite_id, token=token, actor=actor)
    team = db.query(Team).filter(Team.id == invite.team_id).first()
    project = db.query(Project).filter(Project.id == team.project_id).first() if team else None
    if not project:
        raise HTTPException(status_code=404, detail="Project not found for invite")

    employee_profile = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.user_id == actor.id, EmployeeProfile.tenant_id == actor.tenant_id)
        .first()
    )
    if not employee_profile:
        raise HTTPException(status_code=404, detail="Employee profile not found")

    member = apply_invite_response(db, invite=invite, actor=actor, accepted=accepted, note=note)
    meta = _project_meta(project)
    invite_summaries = _load_team_invite_summaries(db, project)
    guidance_context = {
        "project_name": project.name,
        "project_summary": project.description,
        "recommended_team": meta.get("recommended_team", []),
        "project_id": project.id,
        "invite_statuses": invite_summaries,
    }
    llm_service = LLMService()

    if accepted:
        _assign_role_tasks_to_employee(db, project, employee_profile, invite.role_title)
        meta["team_join_status"] = "accepted" if not any(item.get("status") == "pending" for item in invite_summaries) else "awaiting-responses"
        meta["approval_status"] = "approved" if meta["team_join_status"] == "accepted" else "awaiting-team-join"
        meta["current_phase"] = "execution"
        meta["next_decision"] = (
            "Monitor delivery and client feedback"
            if meta["team_join_status"] == "accepted"
            else "Continue execution for accepted members while waiting on remaining responses"
        )
        meta["stage_briefs"] = {
            "admin": llm_service.generate_stage_brief("execution", "admin", guidance_context),
            "employee": llm_service.generate_stage_brief("execution", "employee", guidance_context),
            "client": llm_service.generate_stage_brief("execution", "client", guidance_context),
        }
        meta["decision_support"] = {
            "admin": llm_service.generate_decision_support("execution_start", "admin", guidance_context),
            "employee": llm_service.generate_decision_support("execution_start", "employee", guidance_context),
        }
        project.status = "in-progress"
        project.progress = max(project.progress, 18)
    else:
        meta["team_join_status"] = "rejected"
        meta["approval_status"] = "rejected-by-team"
        meta["current_phase"] = "restaffing"
        meta["next_decision"] = f"Replace the rejected {invite.role_title or 'team slot'} role and resend the invite"
        meta["replacement_suggestions"] = _suggest_replacements(
            db,
            project.tenant_id,
            invite.role_title,
            exclude_employee_id=employee_profile.id,
        )
        meta["stage_briefs"] = {
            "admin": llm_service.generate_stage_brief("restaffing", "admin", guidance_context),
            "employee": llm_service.generate_stage_brief("restaffing", "employee", guidance_context),
            "client": llm_service.generate_stage_brief("restaffing", "client", guidance_context),
        }
        meta["decision_support"] = {
            "admin": llm_service.generate_decision_support("restaffing", "admin", guidance_context),
            "employee": llm_service.generate_decision_support("project_rejection", "employee", guidance_context),
        }
        project.status = "on-hold"
        _create_admin_meeting(
            db,
            project,
            project.admin_id,
            f"Restaffing meeting for {invite.role_title or 'team slot'}",
            "review",
            f"{employee_profile.user.full_name if employee_profile.user else actor.email} rejected the project invite. Review replacement suggestions.",
        )

    meta["team_invites"] = invite_summaries
    if member and member.employee_profile_id:
        emp_involved = set(meta.get("emp_involved_ids", []))
        emp_involved.add(member.employee_profile_id)
        meta["emp_involved_ids"] = sorted(emp_involved)

    project.custom_fields = meta
    db.add(project)
    db.commit()
    db.refresh(project)
    return build_project_status(db, project.id, viewer=actor)


def ensure_deadline_escalations(db: Session):
    projects = db.query(Project).filter(Project.status != "completed").all()
    changed = False
    now = _utcnow()

    for project in projects:
        meta = _project_meta(project)
        approval_status = meta.get("approval_status")

        if approval_status == "awaiting-admin-approval":
            deadline_value = meta.get("approval_deadline")
            if not deadline_value:
                continue
            deadline = _normalize_datetime(datetime.fromisoformat(deadline_value))
            if deadline < now and not meta.get("admin_followup_created"):
                meta["approval_status"] = "escalated"
                meta["current_phase"] = "escalation"
                meta["next_decision"] = "Admin follow-up required to either approve or rework the AI-generated draft"
                meta["admin_followup_created"] = True
                project.status = "on-hold"
                project.custom_fields = meta
                _create_admin_meeting(
                    db,
                    project,
                    project.admin_id,
                    "Admin follow-up for missed kickoff approval",
                    "review",
                    "The AI-generated team and role plan was not approved within the intake window.",
                )
                _log_decision(
                    db,
                    "admin_approval_deadline_missed",
                    project.id,
                    0.83,
                    "Admin approval window expired. System created a follow-up meeting.",
                )
                changed = True
            continue

        if approval_status != "awaiting-team-join":
            continue

        deadline_value = meta.get("team_join_deadline")
        if not deadline_value:
            continue

        deadline = _normalize_datetime(datetime.fromisoformat(deadline_value))
        if deadline >= now:
            continue

        if meta.get("team_join_escalation_created"):
            meta["team_join_status"] = "expired"
            project.custom_fields = meta
            changed = True
            continue

        pending_names = [
            invite.get("name")
            for invite in meta.get("team_invites", [])
            if invite.get("status") == "pending"
        ]
        meta["approval_status"] = "escalated"
        meta["current_phase"] = "escalation"
        meta["team_join_status"] = "expired"
        meta["next_decision"] = "Admin meet required with team members who missed the join window"
        meta["team_join_escalation_created"] = True
        project.status = "on-hold"
        project.custom_fields = meta

        _create_admin_meeting(
            db,
            project,
            project.admin_id,
            "Admin follow-up for missed team join deadline",
            "emergency",
            f"Project invite window expired. Pending responses: {', '.join(pending_names) if pending_names else 'none recorded'}.",
        )
        _log_decision(
            db,
            "team_join_deadline_missed",
            project.id,
            0.88,
            "Team join deadline expired. System escalated to an admin review meeting.",
        )
        changed = True

    if changed:
        db.commit()


def _resolve_client(db: Session, payload: ProjectCreate, tenant_id: int) -> Tuple[Optional[ClientProfile], Dict]:
    if payload.client_mode == "existing":
        client = None
        if payload.client_id:
            client = (
                db.query(ClientProfile)
                .options(joinedload(ClientProfile.user))
                .filter(ClientProfile.id == payload.client_id, ClientProfile.tenant_id == tenant_id)
                .first()
            )
        elif payload.client_email:
            client = (
                db.query(ClientProfile)
                .join(User, User.id == ClientProfile.user_id)
                .options(joinedload(ClientProfile.user))
                .filter(User.email == payload.client_email, ClientProfile.tenant_id == tenant_id)
                .first()
            )
        if not client:
            raise HTTPException(status_code=404, detail="Existing client not found")

        _update_client_profile(client, payload)
        db.add(client)
        return client, {
            "type": "existing-client-update",
            "client_id": client.id,
            "client_company_name": client.company_name,
            "client_email": client.user.email if client.user else None,
            "message": "Existing client profile linked and refreshed for the new project.",
        }

    if not payload.client_email or not payload.client_user_password or not payload.client_company_name:
        raise HTTPException(
            status_code=400,
            detail="New client registration requires email, password, and company name",
        )

    existing_user = db.query(User).filter(User.email == payload.client_email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Client email already registered")

    user = User(
        email=payload.client_email,
        password=hash_password(payload.client_user_password),
        full_name=payload.client_user_full_name or payload.client_contact_person or payload.client_company_name,
        role="client",
        tenant_id=tenant_id,
    )
    db.add(user)
    db.flush()

    client = ClientProfile(
        tenant_id=tenant_id,
        user_id=user.id,
        company_name=payload.client_company_name,
        contact_person=payload.client_contact_person or user.full_name,
        phone=payload.client_phone,
        address=payload.client_address,
    )
    db.add(client)
    db.flush()

    return client, {
        "type": "new-client-registration",
        "client_id": client.id,
        "client_company_name": client.company_name,
        "client_email": user.email,
        "message": "Client account created and linked to the project.",
    }


def _update_client_profile(client: ClientProfile, payload: ProjectCreate):
    if payload.client_company_name:
        client.company_name = payload.client_company_name
    if payload.client_contact_person:
        client.contact_person = payload.client_contact_person
    if payload.client_phone:
        client.phone = payload.client_phone
    if payload.client_address:
        client.address = payload.client_address
    if client.user:
        if payload.client_user_full_name:
            client.user.full_name = payload.client_user_full_name
        if payload.client_user_password:
            client.user.password = hash_password(payload.client_user_password)


def _seed_project_plan(db: Session, project: Project, planning_packet: Dict, role_clusters: List[Dict[str, Any]]):
    now = _utcnow()
    deadline = _normalize_datetime(project.deadline) or (now + timedelta(days=21))
    llm_tasks = planning_packet.get("tasks") or []
    plan = []

    for index, item in enumerate(llm_tasks[:6], start=1):
        task_deadline = now + timedelta(days=min(index * 2, 10))
        plan.append(
            {
                "description": item.get("title") or item.get("description") or f"Task {index}",
                "difficulty": item.get("difficulty", "medium"),
                "urgency": item.get("urgency", "medium"),
                "estimated_time": max(2.0, min(float(item.get("estimated_time", 6.0)), 8.0)),
                "required_skills": item.get("required_skills", {"project-management": 0.6}),
                "required_role": item.get("required_role"),
                "deadline": min(deadline, task_deadline),
                "subtasks": [
                    *[
                        (
                            subtask.get("title"),
                            max(1.0, min(float(subtask.get("estimated_time", 2.0)), 4.0)),
                            subtask.get("required_skills", item.get("required_skills", {"communication": 0.6})),
                            subtask.get("details"),
                        )
                        for subtask in item.get("subtasks", [])
                    ],
                ],
            }
        )

    if not plan:
        plan = [
            {
                "description": f"Discovery and solution brief for {project.name}",
                "difficulty": "medium",
                "urgency": "high",
                "estimated_time": 4.0,
                "required_skills": {"project-management": 0.7, "communication": 0.7},
                "required_role": "Project Coordinator",
                "deadline": now + timedelta(days=2),
                "subtasks": [
                    ("Client expectation notes and risk register", 2.0, {"communication": 0.7}, "Capture scope, dependencies, and open assumptions."),
                ],
            },
            {
                "description": f"Architecture and delivery plan for {project.name}",
                "difficulty": "hard",
                "urgency": "high",
                "estimated_time": 6.0,
                "required_skills": {"architecture": 0.8, "backend": 0.6},
                "required_role": "Solution Architect",
                "deadline": min(deadline, now + timedelta(days=4)),
                "subtasks": [
                    ("Break down milestones, owners, and review gates", 3.0, {"delivery": 0.7}, "Define the implementation slices, review cadence, and ownership model."),
                ],
            },
        ]

    role_map = {}
    for item in plan:
        task = Task(
            tenant_id=project.tenant_id,
            project_id=project.id,
            description=item["description"],
            status="pending",
            difficulty=item["difficulty"],
            urgency=item["urgency"],
            estimated_time=item["estimated_time"],
            required_skills=item["required_skills"],
            deadline=item["deadline"],
        )
        db.add(task)
        db.flush()
        role_map[str(task.id)] = item.get("required_role") or _infer_role_from_skills(item["required_skills"])

        for description, estimated_time, skills, details in item["subtasks"] or []:
            db.add(
                Task(
                    tenant_id=project.tenant_id,
                    project_id=project.id,
                    parent_task_id=task.id,
                    description=f"{description}: {details}" if details else description,
                    status="pending",
                    difficulty="medium",
                    urgency=item["urgency"],
                    estimated_time=estimated_time,
                    required_skills=skills,
                    deadline=item["deadline"],
                )
            )

    meta = _project_meta(project)
    meta["task_role_map"] = role_map
    meta["role_clusters"] = role_clusters
    project.custom_fields = meta


def _log_project_intake(db: Session, project: Project, client_report: Dict, recommended_team: List[Dict]):
    db.add(
        DecisionLog(
            decision_type="project_intake",
            entity_type="project",
            entity_id=project.id,
            input_data=client_report,
            decision_taken="Registered project intake and prepared pre-execution plan.",
            confidence=0.93,
            reasoning="Initial intake converted into a planning packet, approval deadline, and recommended staffing shortlist.",
        )
    )
    db.add(
        DecisionLog(
            decision_type="team_preparation",
            entity_type="project",
            entity_id=project.id,
            input_data={"recommended_team": recommended_team},
            decision_taken="Prepared staffing shortlist and waiting for team approval.",
            confidence=0.79,
            reasoning="System selected currently available team members based on role-fit and zero-load priority.",
        )
    )


def _notify_client_on_project_start(db: Session, project: Project, client: Optional[ClientProfile]):
    subject = f"{project.name}: intake received"
    body = (
        f"Project '{project.name}' has been received. The team is preparing the kickoff plan, "
        "client report, and approval flow. First status packet is queued after team confirmation."
    )
    db.add(
        Communication(
            type="email",
            from_actor="system",
            to_actor="client" if client else "admin",
            subject=subject,
            body=body,
            project_id=project.id,
            status="queued",
        )
    )


def _assign_project_plan(db: Session, project: Project, recommended_team: List[Dict], role_clusters: List[Dict[str, Any]]):
    llm_service = LLMService()
    team_lookup = {member["employee_id"]: member for member in recommended_team}
    employees = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.tenant_id == project.tenant_id)
        .filter(EmployeeProfile.id.in_(team_lookup.keys()) if team_lookup else False)
        .all()
    )
    if not employees:
        employees = (
            db.query(EmployeeProfile)
            .options(joinedload(EmployeeProfile.user))
            .filter(EmployeeProfile.tenant_id == project.tenant_id)
            .all()
        )

    top_level_tasks = [task for task in project.tasks if task.parent_task_id is None]
    role_map = _project_meta(project).get("task_role_map", {})
    for index, task in enumerate(top_level_tasks):
        required_role = role_map.get(str(task.id))
        employee = _pick_employee_for_task(task, employees, index, required_role=required_role)
        if not employee:
            continue

        existing = (
            db.query(TaskAssignment)
            .filter(TaskAssignment.task_id == task.id, TaskAssignment.employee_id == employee.id)
            .first()
        )
        if existing:
            continue

        assignment = TaskAssignment(
            task_id=task.id,
            employee_id=employee.id,
            status="assigned",
            estimated_hours=task.estimated_time,
            assignment_confidence=0.84,
            notes="Assigned after team approval.",
        )
        db.add(assignment)
        employee.current_load = round((employee.current_load or 0) + (task.estimated_time or 0), 1)
        employee.availability_status = "busy" if employee.current_load > 0 else "available"
        task.status = "running" if index == 0 else "pending"
        db.flush()

        _apply_work_package_to_assignment(db, project, task, employee, assignment, llm_service)

    meta = _project_meta(project)
    meta["emp_involved_ids"] = sorted({assignment.employee_id for task in project.tasks for assignment in task.assignments})
    project.custom_fields = meta


def _apply_work_package_to_assignment(
    db: Session,
    project: Project,
    task: Task,
    employee: EmployeeProfile,
    assignment: TaskAssignment,
    llm_service: Optional[LLMService] = None,
):
    llm_service = llm_service or LLMService()
    work_package = _generate_task_execution_package(llm_service, project, task, employee)
    assignment.notes = work_package["summary"]
    _ensure_task_progress(db, task)
    _replace_checkpoints(db, task, work_package["checkpoints"])


def _assign_role_tasks_to_employee(db: Session, project: Project, employee: EmployeeProfile, role_title: Optional[str]):
    llm_service = LLMService()
    role_map = _project_meta(project).get("task_role_map", {})
    top_level_tasks = [task for task in project.tasks if task.parent_task_id is None]

    for index, task in enumerate(top_level_tasks):
        required_role = role_map.get(str(task.id))
        if role_title and required_role != role_title:
            continue

        existing = (
            db.query(TaskAssignment)
            .filter(TaskAssignment.task_id == task.id, TaskAssignment.employee_id == employee.id)
            .first()
        )
        if existing:
            continue

        assignment = TaskAssignment(
            task_id=task.id,
            employee_id=employee.id,
            status="assigned",
            estimated_hours=task.estimated_time,
            assignment_confidence=0.87,
            notes="Assigned after invite acceptance.",
        )
        db.add(assignment)
        employee.current_load = round((employee.current_load or 0) + (task.estimated_time or 0), 1)
        employee.availability_status = "busy" if employee.current_load > 0 else "available"
        task.status = "running" if index == 0 else task.status
        db.flush()
        _apply_work_package_to_assignment(db, project, task, employee, assignment, llm_service)

    _sync_project_progress(db, project.id)


def _load_team_invite_summaries(db: Session, project: Project) -> List[Dict[str, Any]]:
    meta = _project_meta(project)
    team = db.query(Team).filter(Team.project_id == project.id).first()
    if not team:
        return meta.get("team_invites", [])

    cluster_map = {cluster["role"]: cluster for cluster in meta.get("role_clusters", [])}
    invites = (
        db.query(TeamInvite)
        .filter(TeamInvite.team_id == team.id)
        .order_by(TeamInvite.created_at.asc())
        .all()
    )

    summaries = []
    for invite in invites:
        user = db.query(User).filter(User.id == invite.invited_user_id).first() if invite.invited_user_id else None
        employee = (
            db.query(EmployeeProfile)
            .options(joinedload(EmployeeProfile.user))
            .filter(EmployeeProfile.user_id == user.id, EmployeeProfile.tenant_id == project.tenant_id)
            .first()
            if user
            else None
        )
        cluster = cluster_map.get(invite.role_title or "", {})
        summaries.append(
            {
                "invite_id": invite.id,
                "employee_id": employee.id if employee else None,
                "email": invite.email,
                "name": employee.user.full_name if employee and employee.user else invite.email,
                "title": invite.role_title or cluster.get("role"),
                "status": invite.status,
                "note": invite.note,
                "responded_at": invite.responded_at.isoformat() if invite.responded_at else None,
                "token": invite.token,
                "role_focus": cluster.get("task_titles", []),
                "role_skills": cluster.get("skills", []),
                "capacity_reasoning": cluster.get("capacity_reasoning"),
            }
        )
    return summaries


def _refresh_project_team_metadata(db: Session, project: Project) -> Dict[str, Any]:
    meta = _project_meta(project)
    meta["team_invites"] = _load_team_invite_summaries(db, project)
    accepted_profile_ids = (
        db.query(TeamMember.employee_profile_id)
        .join(Team, Team.id == TeamMember.team_id)
        .filter(Team.project_id == project.id, TeamMember.employee_profile_id.isnot(None))
        .all()
    )
    accepted_ids = sorted({employee_profile_id for (employee_profile_id,) in accepted_profile_ids if employee_profile_id})
    if accepted_ids:
        meta["emp_involved_ids"] = sorted(set(meta.get("emp_involved_ids", [])) | set(accepted_ids))
    project.custom_fields = meta
    return meta


def _sync_project_team_invites(
    db: Session,
    project: Project,
    team: Team,
    recommended_team: List[Dict[str, Any]],
    role_clusters: List[Dict[str, Any]],
    actor_id: int,
) -> None:
    employee_profiles = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.id.in_([member["employee_id"] for member in recommended_team]) if recommended_team else False)
        .all()
    )
    employee_by_id = {profile.id: profile for profile in employee_profiles}

    for member in recommended_team:
        profile = employee_by_id.get(member["employee_id"])
        if not profile or not profile.user:
            continue
        role_title = member.get("title")
        try:
            create_team_invite(
                db,
                team=team,
                tenant_id=project.tenant_id,
                email=profile.user.email,
                invited_by_user_id=actor_id,
                role_title=role_title,
                note="System generated from approved staffing recommendation.",
            )
        except HTTPException as exc:
            if exc.status_code != 409:
                raise

    meta = _project_meta(project)
    meta["team_invites"] = _load_team_invite_summaries(db, project)
    project.custom_fields = meta


def _pick_employee_for_task(task: Task, employees: List[EmployeeProfile], index: int, required_role: Optional[str] = None):
    if not employees:
        return None

    required = task.required_skills or {}
    best_employee = None
    best_score = None

    for employee in employees:
        employee_skills = employee.skills or {}
        role_bonus = 1.0 if required_role and _title_from_employee(employee) == required_role else 0.0
        skill_score = sum(employee_skills.get(skill, 0) * weight for skill, weight in required.items())
        load_penalty = _workload_percent(employee.current_load, employee.max_capacity)
        score = (role_bonus, skill_score, -load_penalty, -employee.id)
        if best_score is None or score > best_score:
            best_score = score
            best_employee = employee

    return best_employee or employees[index % len(employees)]


def _collect_involved_employees(db: Session, assignments: List[TaskAssignment], project: Project):
    """
    Collect only employees who are actually involved in the project.
    - Includes those with active task assignments
    - Includes those who have accepted their team invite (stored in emp_involved_ids)
    - Does NOT include people who are only in pending invite status
    """
    employee_ids = {assignment.employee_id for assignment in assignments}
    employee_ids.update(_project_meta(project).get("emp_involved_ids", []))
    
    # Do NOT add recommended_team members - they only belong in "team_invites" until they accept

    employees = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.tenant_id == project.tenant_id)
        .filter(EmployeeProfile.id.in_(employee_ids) if employee_ids else False)
        .all()
    )
    return [
        {
            "employee_id": employee.id,
            "name": employee.user.full_name if employee.user else f"Employee {employee.id}",
            "title": _title_from_employee(employee),
            "availability_status": employee.availability_status,
            "workload_percent": _workload_percent(employee.current_load, employee.max_capacity),
        }
        for employee in employees
    ]


def _title_from_employee(employee: EmployeeProfile):
    skills = set((employee.skills or {}).keys())
    best_title = None
    best_score = 0

    for title, markers in ROLE_SKILL_MAP.items():
        score = len(skills.intersection(set(markers)))
        if score > best_score:
            best_title = title
            best_score = score

    return best_title or employee.department or "AI Services"


def _serialize_project_summary(db: Session, project: Project, viewer: Optional[User] = None):
    meta = _refresh_project_team_metadata(db, project)
    top_level_tasks = db.query(Task).filter(Task.project_id == project.id, Task.parent_task_id.is_(None)).all()
    task_count = len(top_level_tasks)
    completed_count = len([task for task in top_level_tasks if task.status == "done"])
    visible_client_id = project.client_id if not viewer or viewer.role == "admin" else None
    team_invites = meta.get("team_invites", [])
    pending_invites = [invite for invite in team_invites if invite.get("status") == "pending"]

    return {
        "id": project.id,
        "project_id": project.id,
        "name": project.name,
        "description": project.description,
        "status": project.status,
        "progress": project.progress,
        "priority": project.priority,
        "client_id": visible_client_id,
        "client_name": project.client.company_name if project.client else None,
        "budget": project.budget,
        "spent": project.spent,
        "payment_status": project.payment_status,
        "current_phase": meta.get("current_phase"),
        "client_status": meta.get("client_status"),
        "client_response_status": meta.get("client_response_status"),
        "approval_status": meta.get("approval_status"),
        "approval_deadline": meta.get("approval_deadline"),
        "team_join_deadline": meta.get("team_join_deadline"),
        "team_join_status": meta.get("team_join_status"),
        "next_decision": meta.get("next_decision"),
        "public_status_label": _client_business_summary(project, top_level_tasks, meta),
        "viewer_guidance": _guidance_for_viewer(meta, viewer),
        "decision_support": _decision_support_for_viewer(meta, viewer),
        "task_count": task_count,
        "completed_task_count": completed_count,
        "report_text": meta.get("report_text"),
        "recommended_team": meta.get("recommended_team", []),
        "team_invites": _visible_team_invites(meta, viewer),
        "pending_team_invite_count": len(pending_invites),
        "pending_team_invite_names": [invite.get("name") for invite in pending_invites],
    }


def _serialize_completed_project(project: Project):
    meta = _project_meta(project)
    return {
        "project_id": project.id,
        "project_name": project.name,
        "client_id": project.client_id,
        "client_name": project.client.company_name if project.client else None,
        "payment_status": project.payment_status,
        "completed_at": project.completed_at.isoformat() if project.completed_at else None,
        "report_text": meta.get("report_text"),
    }


def _project_meta(project: Project):
    return dict(project.custom_fields or {})


def _workload_percent(current_load: float, max_capacity: float):
    if not max_capacity:
        return 0
    return round((current_load / max_capacity) * 100, 1)


def _infer_role_from_skills(skills: Dict[str, float]) -> str:
    best_title = "Backend Engineer"
    best_score = -1
    skill_keys = set((skills or {}).keys())
    for title, markers in ROLE_SKILL_MAP.items():
        score = len(skill_keys.intersection(set(markers)))
        if score > best_score:
            best_title = title
            best_score = score
    return best_title


def _build_role_clusters(planning_packet: Dict[str, Any]) -> List[Dict[str, Any]]:
    clusters: Dict[str, Dict[str, Any]] = {}
    for task in planning_packet.get("tasks", []):
        role = task.get("required_role") or _infer_role_from_skills(task.get("required_skills", {}))
        cluster = clusters.setdefault(
            role,
            {"role": role, "task_titles": [], "task_count": 0, "skills": set(), "total_hours": 0.0},
        )
        cluster["task_titles"].append(task.get("title"))
        cluster["task_count"] += 1
        cluster["skills"].update((task.get("required_skills") or {}).keys())
        cluster["total_hours"] += float(task.get("estimated_time") or 0)
        cluster["total_hours"] += sum(float(subtask.get("estimated_time") or 0) for subtask in task.get("subtasks", []))

    return [
        {
            "role": role,
            "task_titles": data["task_titles"],
            "task_count": data["task_count"],
            "skills": sorted(data["skills"]),
            "total_hours": round(data["total_hours"], 1),
            "suggested_headcount": max(1, min(2, int((data["total_hours"] - 1) // 10 + 1))),
            "capacity_reasoning": (
                "This role cluster owns concentrated delivery volume and may need backup capacity."
                if data["total_hours"] > 10
                else "One focused contributor should cover this role cluster for the current scope."
            ),
        }
        for role, data in clusters.items()
    ]


def _build_team_invites(recommended_team: List[Dict[str, Any]], role_clusters: List[Dict[str, Any]]):
    cluster_map = {cluster["role"]: cluster for cluster in role_clusters}
    invites = []
    for member in recommended_team:
        cluster = cluster_map.get(member.get("title"), {})
        invites.append(
            {
                "employee_id": member["employee_id"],
                "name": member["name"],
                "title": member["title"],
                "status": "pending",
                "note": None,
                "responded_at": None,
                "role_focus": cluster.get("task_titles", []),
                "role_skills": cluster.get("skills", []),
                "capacity_reasoning": cluster.get("capacity_reasoning"),
            }
        )
    return invites


def _visible_team_invites(meta: Dict[str, Any], viewer: Optional[User]):
    invites = meta.get("team_invites", [])
    if not viewer or viewer.role == "admin":
        return invites
    if viewer.role == "employee":
        return [invite for invite in invites if normalize_email(invite.get("email", "")) == normalize_email(viewer.email)]
    return []


def _suggest_replacements(
    db: Session,
    tenant_id: int,
    role_title: Optional[str],
    exclude_employee_id: Optional[int] = None,
):
    if not role_title:
        return []

    employees = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.tenant_id == tenant_id)
        .all()
    )
    suggestions = []
    for employee in employees:
        if exclude_employee_id and employee.id == exclude_employee_id:
            continue
        if _title_from_employee(employee) != role_title:
            continue
        suggestions.append(
            {
                "employee_id": employee.id,
                "name": employee.user.full_name if employee.user else f"Employee {employee.id}",
                "title": role_title,
                "workload_percent": _workload_percent(employee.current_load, employee.max_capacity),
                "availability_status": employee.availability_status,
            }
        )
    suggestions.sort(key=lambda item: (item["workload_percent"], item["employee_id"]))
    return suggestions[:3]


def _recommend_team(db: Session, tenant_id: int, role_clusters: Optional[List[Dict[str, Any]]] = None):
    employees = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.tenant_id == tenant_id)
        .filter(EmployeeProfile.availability_status.in_(["available", "on-duty"]))
        .order_by(EmployeeProfile.current_load.asc(), EmployeeProfile.id.asc())
        .all()
    )
    selected = []
    used_ids = set()

    desired_roles: List[str] = []
    for cluster in (role_clusters or []):
        copies = max(1, int(cluster.get("suggested_headcount", 1)))
        desired_roles.extend([cluster["role"]] * copies)
    if not desired_roles:
        desired_roles = DEFAULT_PROJECT_TEAM_ORDER

    for desired_title in desired_roles:
        match = next(
            (
                employee
                for employee in employees
                if employee.id not in used_ids and _title_from_employee(employee) == desired_title
            ),
            None,
        )
        if match:
            selected.append(match)
            used_ids.add(match.id)

    target_size = min(max(len(desired_roles), 4), 7)

    for employee in employees:
        if len(selected) >= target_size:
            break
        if employee.id in used_ids:
            continue
        selected.append(employee)
        used_ids.add(employee.id)

    return [
        {
            "employee_id": employee.id,
            "name": employee.user.full_name if employee.user else f"Employee {employee.id}",
            "title": _title_from_employee(employee),
            "workload_percent": _workload_percent(employee.current_load, employee.max_capacity),
        }
        for employee in selected
    ]


def _suggestion_for_project(project: Project):
    meta = _project_meta(project)
    approval_status = meta.get("approval_status")
    if approval_status == "awaiting-admin-approval":
        return "Review the AI-generated delivery breakdown, role clusters, and staffing draft before kickoff."
    if approval_status == "awaiting-team-join":
        return "Execution can start for accepted members. Track remaining invite responses and restaff any declined roles."
    if approval_status == "escalated":
        return "Run the admin sync, confirm the missed response or staffing gap, and relaunch only after owners commit."
    if approval_status in {"rejected", "rejected-by-team"}:
        return "Refine the delivery plan with the team’s feedback before restarting kickoff."
    return "Continue monitoring tasks, client responses, and payment updates."


def _guidance_for_viewer(meta: Dict, viewer: Optional[User]):
    stage_briefs = meta.get("stage_briefs", {})
    if not viewer:
        return stage_briefs.get("admin")
    if viewer.role == "admin":
        return stage_briefs.get("admin")
    if viewer.role == "client":
        return stage_briefs.get("client")
    return stage_briefs.get("employee")


def _decision_support_for_viewer(meta: Dict, viewer: Optional[User]):
    decision_support = meta.get("decision_support", {})
    if not viewer:
        return decision_support.get("admin")
    if viewer.role == "admin":
        return decision_support.get("admin")
    if viewer.role == "client":
        return decision_support.get("client") or meta.get("stage_briefs", {}).get("client")
    return decision_support.get("employee")


def build_employee_workspace(db: Session, user: User):
    profile = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.user_id == user.id, EmployeeProfile.tenant_id == user.tenant_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Employee profile not found")

    assignments = (
        db.query(TaskAssignment)
        .options(joinedload(TaskAssignment.task).joinedload(Task.project).joinedload(Project.client))
        .filter(TaskAssignment.employee_id == profile.id)
        .order_by(TaskAssignment.assigned_at.desc())
        .all()
    )

    llm_service = LLMService()
    my_projects = []
    seen_projects = set()
    my_tasks = []
    project_invites = []
    planned_tracks = []

    invite_projects = (
        db.query(Project)
        .options(joinedload(Project.tasks))
        .filter(Project.tenant_id == user.tenant_id)
        .filter(Project.status != "completed")
        .order_by(Project.created_at.desc())
        .all()
    )

    for project in invite_projects:
        meta = _refresh_project_team_metadata(db, project)
        invite = next(
            (
                item
                for item in meta.get("team_invites", [])
                if normalize_email(item.get("email", "")) == normalize_email(user.email)
            ),
            None,
        )
        if not invite:
            continue
        role_title = invite.get("title")
        role_tasks = []
        task_role_map = meta.get("task_role_map", {})
        for project_task in [task for task in project.tasks if task.parent_task_id is None]:
            required_role = task_role_map.get(str(project_task.id))
            if required_role != role_title:
                continue
            child_steps = [
                child.description
                for child in project.tasks
                if child.parent_task_id == project_task.id
            ]
            role_tasks.append(
                {
                    "task_id": project_task.id,
                    "task_name": project_task.description,
                    "status": project_task.status if invite.get("status") == "accepted" else "pending-invite-response",
                    "estimated_hours": project_task.estimated_time,
                    "required_role": required_role,
                    "delivery_steps": child_steps,
                    "project_progress": project.progress,
                }
            )

        project_invites.append(
            {
                "project_id": project.id,
                "project_name": project.name,
                "status": invite.get("status"),
                "title": invite.get("title"),
                "note": invite.get("note"),
                "responded_at": invite.get("responded_at"),
                "join_deadline": meta.get("team_join_deadline"),
                "role_focus": invite.get("role_focus", []),
                "role_skills": invite.get("role_skills", []),
                "capacity_reasoning": invite.get("capacity_reasoning"),
                "viewer_guidance": _guidance_for_viewer(meta, user),
                "decision_support": _decision_support_for_viewer(meta, user),
                "planned_tasks": role_tasks,
            }
        )
        if role_tasks:
            planned_tracks.append(
                {
                    "project_id": project.id,
                    "project_name": project.name,
                    "invite_status": invite.get("status"),
                    "role_title": role_title,
                    "tasks": role_tasks,
                }
            )

    for assignment in assignments:
        task = assignment.task
        if not task or not task.project:
            continue

        project = task.project
        if project.tenant_id != user.tenant_id:
            continue
        meta = _refresh_project_team_metadata(db, project)
        progress = db.query(TaskProgress).filter(TaskProgress.task_id == task.id).first()
        checkpoints = db.query(Checkpoint).filter(Checkpoint.task_id == task.id).order_by(Checkpoint.created_at.asc()).all()
        blockers = db.query(Blocker).filter(Blocker.task_id == task.id, Blocker.status != "resolved").order_by(Blocker.created_at.desc()).all()
        task_brief = assignment.notes or llm_service.generate_stage_brief(
            "execution",
            "employee",
            {
                "project_name": project.name,
                "task_name": task.description,
                "employee_name": user.full_name,
                "required_skills": task.required_skills,
            },
        )

        my_tasks.append(
            {
                "assignment_id": assignment.id,
                "task_id": task.id,
                "project_id": project.id,
                "project_name": project.name,
                "task_name": task.description,
                "status": task.status,
                "assignment_status": assignment.status,
                "estimated_hours": assignment.estimated_hours,
                "completion_percentage": progress.completion_percentage if progress else 0,
                "project_progress": project.progress,
                "notes": task_brief,
                "concern_path": "Raise a concern in this workspace first. The AI lead will respond before admin escalation is triggered.",
                "checkpoints": [
                    {
                        "id": checkpoint.id,
                        "title": checkpoint.title,
                        "status": checkpoint.status,
                        "notes": checkpoint.notes,
                        "completed_at": checkpoint.completed_at.isoformat() if checkpoint.completed_at else None,
                    }
                    for checkpoint in checkpoints
                ],
                "blockers": [
                    {
                        "id": blocker.id,
                        "severity": blocker.severity,
                        "description": blocker.description,
                        "status": blocker.status,
                        "ai_response": blocker.ai_response,
                        "next_action": blocker.next_action,
                    }
                    for blocker in blockers
                ],
            }
        )

        if project.id not in seen_projects:
            seen_projects.add(project.id)
            my_projects.append(
                {
                    "project_id": project.id,
                    "name": project.name,
                    "status": project.status,
                    "progress": project.progress,
                    "public_status_label": _client_business_summary(project, [task for task in project.tasks if task.parent_task_id is None], meta),
                    "viewer_guidance": _guidance_for_viewer(meta, user),
                    "decision_support": _decision_support_for_viewer(meta, user),
                }
            )

    overall_personal_progress = round(
        sum(task["completion_percentage"] for task in my_tasks) / len(my_tasks),
        1,
    ) if my_tasks else 0.0

    return {
        "employee": {
            "employee_id": profile.id,
            "name": profile.user.full_name if profile.user else user.email,
            "title": _title_from_employee(profile),
            "department": profile.department,
            "availability_status": profile.availability_status,
            "workload_percent": _workload_percent(profile.current_load, profile.max_capacity),
        },
        "summary": {
            "active_projects": len(my_projects),
            "assigned_tasks": len(my_tasks),
            "personal_progress_percent": overall_personal_progress,
            "pending_invites": len([invite for invite in project_invites if invite["status"] == "pending"]),
        },
        "project_invites": project_invites,
        "planned_tracks": planned_tracks,
        "projects": my_projects,
        "tasks": my_tasks,
    }


def build_client_workspace(db: Session, user: User):
    client_profile = (
        db.query(ClientProfile)
        .options(joinedload(ClientProfile.user))
        .filter(ClientProfile.user_id == user.id, ClientProfile.tenant_id == user.tenant_id)
        .first()
    )
    if not client_profile:
        raise HTTPException(status_code=404, detail="Client profile not found")

    projects = (
        db.query(Project)
        .options(joinedload(Project.tasks))
        .filter(Project.client_id == client_profile.id, Project.tenant_id == user.tenant_id)
        .order_by(Project.created_at.desc())
        .all()
    )

    overview = []
    for project in projects:
        meta = _refresh_project_team_metadata(db, project)
        top_level_tasks = [task for task in project.tasks if task.parent_task_id is None]
        overview.append(
            {
                "project_id": project.id,
                "name": project.name,
                "status": project.status,
                "progress": project.progress,
                "client_status": meta.get("client_status"),
                "payment_status": project.payment_status,
                "business_summary": _client_business_summary(project, top_level_tasks, meta),
                "next_update": meta.get("client_response_status"),
                "viewer_guidance": _guidance_for_viewer(meta, user),
            }
        )

    return {
        "client": {
            "client_id": client_profile.id,
            "company_name": client_profile.company_name,
            "contact_person": client_profile.contact_person,
        },
        "projects": overview,
    }


def update_checkpoint_status(db: Session, checkpoint_id: int, completed: bool, user: User):
    checkpoint = db.query(Checkpoint).filter(Checkpoint.id == checkpoint_id).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")

    task = db.query(Task).filter(Task.id == checkpoint.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    assignment = (
        db.query(TaskAssignment)
        .join(EmployeeProfile, EmployeeProfile.id == TaskAssignment.employee_id)
        .filter(TaskAssignment.task_id == task.id, EmployeeProfile.user_id == user.id)
        .first()
    )
    if user.role != "admin" and not assignment:
        raise HTTPException(status_code=403, detail="Not authorized to update this checkpoint")

    checkpoint.status = "completed" if completed else "pending"
    checkpoint.completed_at = _utcnow() if completed else None
    db.add(checkpoint)

    checkpoints = db.query(Checkpoint).filter(Checkpoint.task_id == task.id).all()
    total = len(checkpoints) or 1
    done = len([item for item in checkpoints if item.id == checkpoint.id and completed] + [item for item in checkpoints if item.id != checkpoint.id and item.status == "completed"])
    completion_percentage = round((done / total) * 100, 1)

    progress = _ensure_task_progress(db, task)
    progress.completion_percentage = completion_percentage
    progress.status_notes = f"{done} of {total} checkpoints completed"
    progress.estimated_hours_remaining = max((task.estimated_time or 0) * (1 - completion_percentage / 100), 0)
    db.add(progress)

    if completion_percentage >= 100:
        task.status = "done"
    elif completion_percentage > 0:
        task.status = "running"
    else:
        task.status = "pending"
    db.add(task)

    _sync_project_progress(db, task.project_id)
    db.commit()

    return {
        "checkpoint_id": checkpoint.id,
        "task_id": task.id,
        "completion_percentage": completion_percentage,
        "task_status": task.status,
        "project_progress": db.query(Project).filter(Project.id == task.project_id).first().progress,
    }


def build_llm_status():
    llm_service = LLMService()
    return {
        "enabled": llm_service.enabled,
        "model_id": llm_service.model_id,
        "init_error": llm_service.init_error,
    }


def delete_project_atomic(db: Session, project_id: int, actor: User):
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete projects")

    project = (
        db.query(Project)
        .options(joinedload(Project.tasks).joinedload(Task.assignments))
        .filter(Project.id == project_id, Project.tenant_id == actor.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.admin_id != actor.id:
        raise HTTPException(status_code=403, detail="Only the owning admin can delete this project")

    task_ids = [task.id for task in project.tasks]
    logger.info("Deleting project %s for tenant %s by admin %s", project.id, actor.tenant_id, actor.id)

    try:
        employee_loads: Dict[int, float] = {}
        assignments = (
            db.query(TaskAssignment)
            .filter(TaskAssignment.task_id.in_(task_ids) if task_ids else False)
            .all()
        )
        for assignment in assignments:
            employee_loads.setdefault(assignment.employee_id, 0.0)
            employee_loads[assignment.employee_id] += assignment.estimated_hours or 0.0

        employees = (
            db.query(EmployeeProfile)
            .filter(EmployeeProfile.id.in_(employee_loads.keys()) if employee_loads else False)
            .all()
        )
        for employee in employees:
            reduction = employee_loads.get(employee.id, 0.0)
            employee.current_load = max(0.0, round((employee.current_load or 0.0) - reduction, 1))
            employee.availability_status = "available" if employee.current_load == 0 else "busy"
            db.add(employee)

        team_ids = [team.id for team in db.query(Team).filter(Team.project_id == project.id).all()]

        if task_ids:
            db.query(TaskDependency).filter(
                (TaskDependency.task_id.in_(task_ids)) | (TaskDependency.depends_on_task_id.in_(task_ids))
            ).delete(synchronize_session=False)
            db.query(Checkpoint).filter(Checkpoint.task_id.in_(task_ids)).delete(synchronize_session=False)
            db.query(TaskProgress).filter(TaskProgress.task_id.in_(task_ids)).delete(synchronize_session=False)
            db.query(Blocker).filter(Blocker.task_id.in_(task_ids)).delete(synchronize_session=False)
            db.query(PerformancePoint).filter(PerformancePoint.task_id.in_(task_ids)).delete(synchronize_session=False)
            db.query(Communication).filter(Communication.task_id.in_(task_ids)).delete(synchronize_session=False)
            db.query(EventQueue).filter(
                (EventQueue.entity_type == "task") & (EventQueue.entity_id.in_(task_ids))
            ).delete(synchronize_session=False)
            db.query(TaskAssignment).filter(TaskAssignment.task_id.in_(task_ids)).delete(synchronize_session=False)

        if team_ids:
            db.query(TeamInvite).filter(TeamInvite.team_id.in_(team_ids)).delete(synchronize_session=False)
            db.query(TeamMember).filter(TeamMember.team_id.in_(team_ids)).delete(synchronize_session=False)
            db.query(Team).filter(Team.id.in_(team_ids)).delete(synchronize_session=False)

        db.query(PerformancePoint).filter(PerformancePoint.project_id == project.id).delete(synchronize_session=False)
        db.query(Communication).filter(Communication.project_id == project.id).delete(synchronize_session=False)
        db.query(Meeting).filter(Meeting.project_id == project.id).delete(synchronize_session=False)
        db.query(WorkflowRun).filter(WorkflowRun.project_id == project.id).delete(synchronize_session=False)
        db.query(EventQueue).filter(
            (EventQueue.entity_type == "project") & (EventQueue.entity_id == project.id)
        ).delete(synchronize_session=False)
        db.query(DecisionLog).filter(
            ((DecisionLog.entity_type == "project") & (DecisionLog.entity_id == project.id))
            | ((DecisionLog.entity_type == "task") & (DecisionLog.entity_id.in_(task_ids) if task_ids else False))
        ).delete(synchronize_session=False)

        if task_ids:
            db.query(Task).filter(Task.id.in_(task_ids)).delete(synchronize_session=False)
        db.delete(project)
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Project deletion failed for project %s", project_id)
        raise HTTPException(status_code=500, detail="Project deletion failed and was rolled back")

    return {"success": True, "project_id": project_id}


def _client_business_summary(project: Project, tasks: List[Task], meta: Dict):
    total = len(tasks)
    done = len([task for task in tasks if task.status == "done"])
    running = len([task for task in tasks if task.status == "running"])

    if project.status == "planning":
        return "Your project is in the planning stage. We are structuring scope, delivery steps, and execution readiness."
    if project.status == "in-progress" and running:
        if done == 0:
            return "Core delivery has started. The project foundation is being built and the first workstream is actively moving."
        return "Delivery is progressing across active workstreams. Some parts are already completed while the remaining scope is moving through implementation."
    if project.status == "completed":
        return "The project has been completed and the final delivery package is ready."
    if meta.get("approval_status") == "rejected":
        return "The project plan is being refined before full execution continues."
    return "The project is active and the team is coordinating the next delivery checkpoint."


def _generate_task_execution_package(llm_service: LLMService, project: Project, task: Task, employee: EmployeeProfile):
    child_tasks = [child for child in project.tasks if child.parent_task_id == task.id]
    context = {
        "project_name": project.name,
        "task_name": task.description,
        "employee_name": employee.user.full_name if employee.user else f"Employee {employee.id}",
        "role": _title_from_employee(employee),
        "required_skills": task.required_skills,
        "estimated_time": task.estimated_time,
        "project_structure": _project_meta(project).get("planning_packet", {}).get("project_structure"),
        "subtask_hints": [
            {"title": child.description.split(":")[0], "notes": child.description}
            for child in child_tasks[:4]
        ],
    }
    return llm_service.generate_execution_package(context)


def _ensure_task_progress(db: Session, task: Task):
    progress = db.query(TaskProgress).filter(TaskProgress.task_id == task.id).first()
    if progress:
        return progress

    progress = TaskProgress(
        task_id=task.id,
        completion_percentage=0.0,
        actual_hours_spent=0.0,
        estimated_hours_remaining=task.estimated_time,
        status_notes="Not started",
        is_on_track=1,
    )
    db.add(progress)
    db.flush()
    return progress


def _replace_checkpoints(db: Session, task: Task, checkpoint_specs: List[Dict]):
    existing = db.query(Checkpoint).filter(Checkpoint.task_id == task.id).all()
    for checkpoint in existing:
        db.delete(checkpoint)
    db.flush()

    for index, spec in enumerate(checkpoint_specs, start=1):
        db.add(
            Checkpoint(
                task_id=task.id,
                title=spec.get("title") or f"Checkpoint {index}",
                due_date=(task.deadline - timedelta(days=max(0, len(checkpoint_specs) - index))) if task.deadline else None,
                status="pending",
                notes=spec.get("notes"),
            )
        )


def _sync_project_progress(db: Session, project_id: int):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return

    tasks = db.query(Task).filter(Task.project_id == project_id, Task.parent_task_id.is_(None)).all()
    if not tasks:
        project.progress = 0
        db.add(project)
        return

    progress_values = []
    for task in tasks:
        progress = db.query(TaskProgress).filter(TaskProgress.task_id == task.id).first()
        if progress:
            progress_values.append(progress.completion_percentage)
        elif task.status == "done":
            progress_values.append(100.0)
        else:
            progress_values.append(0.0)

    project.progress = round(sum(progress_values) / len(progress_values))
    db.add(project)


def _create_admin_meeting(
    db: Session,
    project: Project,
    created_by: int,
    title: str,
    meeting_type: str,
    description: str,
):
    existing = (
        db.query(Meeting)
        .filter(Meeting.project_id == project.id, Meeting.title == title)
        .first()
    )
    if existing:
        return existing

    recommended = _project_meta(project).get("recommended_team", [])
    attendees = [project.admin_id] + [member["employee_id"] for member in recommended]
    meeting = Meeting(
        project_id=project.id,
        created_by=created_by,
        title=title,
        description=description,
        meeting_type=meeting_type,
        scheduled_at=_utcnow() + timedelta(minutes=15),
        attendees=attendees,
        decisions_made=[{"decision": "Admin follow-up required", "owner": project.admin_id}],
    )
    db.add(meeting)
    return meeting


def _log_decision(db: Session, decision_type: str, project_id: int, confidence: float, decision_taken: str):
    db.add(
        DecisionLog(
            decision_type=decision_type,
            entity_type="project",
            entity_id=project_id,
            input_data={"project_id": project_id},
            decision_taken=decision_taken,
            confidence=confidence,
            reasoning="Captured as part of the project workflow lifecycle.",
        )
    )
