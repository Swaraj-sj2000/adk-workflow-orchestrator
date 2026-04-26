# backend/app/services/_project_service.py

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core._security import hash_password
from app.models._client_profile import ClientProfile
from app.models._checkpoint import Checkpoint
from app.models._blocker import Blocker
from app.models._communication import Communication
from app.models._decision_log import DecisionLog
from app.models._employee_metrics import EmployeeMetrics
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
EXPERIENCE_GRADE_THRESHOLDS = (
    (0, "Starter"),
    (120, "Contributor"),
    (300, "Specialist"),
    (600, "Lead"),
    (1000, "Principal"),
)
logger = get_logger(__name__)


ROLE_SKILL_MAP = {
    "Solution Architect": ("architecture", "delivery"),
    "AI Engineer": ("llm", "modeling"),
    "Backend Engineer": ("backend", "api"),
    "Frontend Engineer": ("frontend", "react"),
    "QA Automation Engineer": ("qa", "testing", "automation"),
    "Delivery Lead": ("project-management",),
    "Client Success Manager": ("client-success", "reporting"),
    "DevOps Engineer": ("devops", "cloud", "security"),
    "Data Engineer": ("data", "analytics"),
    "Prompt Engineer": ("prompting", "research"),
}

DEFAULT_PROJECT_TEAM_ORDER = [
    "Solution Architect",
    "Delivery Lead",
    "AI Engineer",
    "Backend Engineer",
    "Client Success Manager",
]


def _dedupe_recommended_team(recommended_team: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen_ids = set()
    for member in recommended_team or []:
        employee_id = member.get("employee_id")
        if not employee_id or employee_id in seen_ids:
            continue
        seen_ids.add(employee_id)
        deduped.append(member)
    return deduped


def _available_role_members(
    db: Session,
    tenant_id: int,
    role_title: Optional[str],
    *,
    exclude_ids: Optional[List[int]] = None,
) -> List[Dict[str, Any]]:
    if not role_title:
        return []

    excluded = set(exclude_ids or [])
    employees = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.tenant_id == tenant_id)
        .all()
    )

    candidates: List[Dict[str, Any]] = []
    for employee in employees:
        if employee.id in excluded:
            continue
        if _title_from_employee(employee) != role_title:
            continue
        candidates.append(
            {
                "employee_id": employee.id,
                "name": employee.user.full_name if employee.user else f"Employee {employee.id}",
                "title": role_title,
                "availability_status": _effective_availability_status(employee),
                "shift_status": _shift_status(employee),
                "workload_percent": _workload_percent(employee.current_load, employee.max_capacity),
                "duty_window": _duty_window_label(employee),
            }
        )

    return sorted(candidates, key=lambda item: (item["workload_percent"], item["name"]))


def _serialize_draft_team(db: Session, project: Project, recommended_team: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    draft_team = _dedupe_recommended_team(recommended_team)
    selected_ids = [member["employee_id"] for member in draft_team if member.get("employee_id")]
    return [
        {
            **member,
            "replacement_options": _available_role_members(
                db,
                project.tenant_id,
                member.get("title"),
                exclude_ids=selected_ids,
            ),
        }
        for member in draft_team
    ]


def _utcnow() -> datetime:
    return datetime.utcnow()


def _normalize_datetime(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _format_hour_value(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None

    total_minutes = int(round(float(value) * 60))
    hours = (total_minutes // 60) % 24
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"


def _duty_window_label(employee: EmployeeProfile) -> str:
    if employee.duty_start_hour is None or employee.duty_end_hour is None:
        return "Not set"
    return f"{_format_hour_value(employee.duty_start_hour)} - {_format_hour_value(employee.duty_end_hour)}"


def _is_in_duty_window(employee: EmployeeProfile, when: Optional[datetime] = None) -> bool:
    if employee.duty_start_hour is None or employee.duty_end_hour is None:
        return True

    when = when or _utcnow()
    current_hour = when.hour + (when.minute / 60)
    start = float(employee.duty_start_hour)
    end = float(employee.duty_end_hour)

    if start <= end:
        return start <= current_hour <= end
    return current_hour >= start or current_hour <= end


def _effective_availability_status(employee: EmployeeProfile) -> str:
    if employee.availability_status == "on-leave":
        return "on-leave"
    if not _is_in_duty_window(employee):
        return "off-duty"
    return "busy" if (employee.current_load or 0) > 0 else "available"


def _shift_status(employee: EmployeeProfile) -> str:
    status = _effective_availability_status(employee)
    labels = {
        "available": "On Duty",
        "busy": "Busy",
        "on-leave": "On Leave",
        "off-duty": "Off Duty",
    }
    return labels.get(status, "On Duty")


def _sync_employee_capacity_state(employee: EmployeeProfile) -> None:
    if employee.availability_status == "on-leave":
        return
    employee.availability_status = "busy" if (employee.current_load or 0) > 0 else "available"


def _experience_grade(total_points: float) -> str:
    grade = EXPERIENCE_GRADE_THRESHOLDS[0][1]
    for threshold, label in EXPERIENCE_GRADE_THRESHOLDS:
        if total_points >= threshold:
            grade = label
    return grade


def _experience_points_map(db: Session, employee_ids: List[int]) -> Dict[int, float]:
    if not employee_ids:
        return {}

    rows = (
        db.query(PerformancePoint.employee_id, func.coalesce(func.sum(PerformancePoint.points), 0.0))
        .filter(PerformancePoint.employee_id.in_(employee_ids))
        .group_by(PerformancePoint.employee_id)
        .all()
    )
    return {employee_id: round(float(total_points or 0.0), 1) for employee_id, total_points in rows}


def _employee_metrics_map(db: Session, employee_ids: List[int]) -> Dict[int, EmployeeMetrics]:
    if not employee_ids:
        return {}
    metrics = db.query(EmployeeMetrics).filter(EmployeeMetrics.employee_id.in_(employee_ids)).all()
    return {metric.employee_id: metric for metric in metrics}


def _performance_snapshots(db: Session, employee_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    points_map = _experience_points_map(db, employee_ids)
    metrics_map = _employee_metrics_map(db, employee_ids)
    snapshots: Dict[int, Dict[str, Any]] = {}

    for employee_id in employee_ids:
        total_points = points_map.get(employee_id, 0.0)
        metrics = metrics_map.get(employee_id)
        level_progress = _experience_progress(total_points)
        snapshots[employee_id] = {
            "experience_points": total_points,
            "experience_grade": _experience_grade(total_points),
            "current_level": level_progress["current_level"],
            "current_level_points": level_progress["current_level_points"],
            "points_to_next_level": level_progress["points_to_next_level"],
            "level_progress_percent": level_progress["level_progress_percent"],
            "next_level_points": level_progress["next_level_points"],
            "efficiency_score": round(float(metrics.efficiency_score or 0.0), 2) if metrics else 0.0,
            "reliability_score": round(float(metrics.reliability_score or 0.0), 2) if metrics else 0.0,
            "tasks_completed": int(metrics.total_tasks_completed or 0) if metrics else 0,
            "tasks_delayed": int(metrics.total_tasks_delayed or 0) if metrics else 0,
        }

    return snapshots


def _ensure_employee_metrics(db: Session, employee: EmployeeProfile) -> EmployeeMetrics:
    metrics = db.query(EmployeeMetrics).filter(EmployeeMetrics.employee_id == employee.id).first()
    if metrics:
        return metrics

    metrics = EmployeeMetrics(
        employee_id=employee.id,
        efficiency_score=0.8,
        reliability_score=0.8,
        avg_completion_time=0.0,
        total_tasks_completed=0,
        total_tasks_failed=0,
        total_tasks_delayed=0,
    )
    db.add(metrics)
    db.flush()
    return metrics


def _experience_level(total_points: float) -> int:
    return max(1, int(float(total_points or 0.0) // 100) + 1)


def _experience_progress(total_points: float) -> Dict[str, Any]:
    normalized_points = round(float(total_points or 0.0), 1)
    level = _experience_level(normalized_points)
    level_points = round(normalized_points % 100, 1)
    return {
        "current_level": level,
        "current_level_points": level_points,
        "points_to_next_level": round(100.0 - level_points, 1),
        "level_progress_percent": round(level_points, 1),
        "next_level_points": 100,
    }


def _append_notification(meta: Dict[str, Any], *, kind: str, title: str, message: str, actor: Optional[str] = None) -> None:
    notifications = list(meta.get("notifications", []))
    notifications.insert(
        0,
        {
            "kind": kind,
            "title": title,
            "message": message,
            "actor": actor,
            "created_at": _utcnow().isoformat(),
        },
    )
    meta["notifications"] = notifications[:20]


def _recent_performance_notifications(db: Session, employee_id: int, limit: int = 8) -> List[Dict[str, Any]]:
    points = (
        db.query(PerformancePoint)
        .filter(PerformancePoint.employee_id == employee_id)
        .order_by(PerformancePoint.awarded_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "kind": "experience",
            "title": "Experience update",
            "message": f"{point.points:.1f} points {'added' if point.points >= 0 else 'deducted'} for {point.reason.lower()}",
            "points_delta": round(point.points, 1),
            "created_at": point.awarded_at.isoformat() if point.awarded_at else None,
        }
        for point in points
    ]


def _payment_activity(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(meta.get("payment_updates", []))


def _today_status_summary(project: Project, tasks: List[Task], meta: Dict[str, Any]) -> str:
    done_today = len(
        [
            task
            for task in tasks
            if task.deadline and task.deadline.date() == _utcnow().date() and task.status == "done"
        ]
    )
    running = len([task for task in tasks if task.status in {"running", "in-progress"}])
    if project.status == "completed":
        return "Delivery is complete. Final report, payment confirmation, and history are now available."
    if running:
        return f"{running} active workstreams are progressing today. {done_today} milestone items were closed today."
    if meta.get("approval_status") == "awaiting-team-join":
        return "Team confirmations are still being collected before full execution ramps up."
    return "The team is preparing the next delivery checkpoint and status update."


def _project_feature_highlights(project: Project) -> List[str]:
    packet = _project_meta(project).get("planning_packet", {})
    tasks = packet.get("tasks", []) or []
    return [task.get("title") for task in tasks[:5] if task.get("title")]


def _project_unique_value(project: Project) -> str:
    packet = _project_meta(project).get("planning_packet", {})
    structure = packet.get("project_structure") or "A structured delivery plan with AI-led execution guidance and traceable ownership."
    return f"The project is designed to deliver {structure.lower()} with clear role ownership and measurable progress."


def _client_plan_brief(project: Project) -> str:
    packet = _project_meta(project).get("planning_packet", {})
    summary = packet.get("project_summary") or project.description or project.name
    structure = packet.get("project_structure") or "a staged implementation plan"
    return f"{summary} Delivery will follow {structure.lower()} with visible checkpoints, ownership, and client-ready updates."


def _build_project_report(db: Session, project: Project) -> Dict[str, Any]:
    top_level_tasks = [task for task in project.tasks if task.parent_task_id is None]
    meta = _project_meta(project)
    assignments = [assignment for task in top_level_tasks for assignment in task.assignments]
    involved_employees = _collect_involved_employees(db, assignments, project)
    feature_highlights = _project_feature_highlights(project)
    today_status = _today_status_summary(project, top_level_tasks, meta)
    completed = len([task for task in top_level_tasks if task.status == "done"])
    running = len([task for task in top_level_tasks if task.status in {"running", "in-progress"}])
    blocked = len([task for task in top_level_tasks if task.status == "blocked"])

    lines = [
        f"Project: {project.name}",
        f"Status: {project.status}",
        f"Progress: {project.progress}%",
        f"Payment: {project.payment_status}",
        f"Budget: {project.budget}",
        f"Spent: {project.spent}",
        f"Completed workstreams: {completed}/{len(top_level_tasks) or 1}",
        f"Running workstreams: {running}",
        f"Blocked workstreams: {blocked}",
        f"Client summary: {_client_business_summary(project, top_level_tasks, meta)}",
        f"Today's status: {today_status}",
    ]
    if feature_highlights:
        lines.append("Feature highlights: " + ", ".join(feature_highlights))
    if involved_employees:
        lines.append("Core team: " + ", ".join(member["name"] for member in involved_employees))

    return {
        "executive_summary": _client_business_summary(project, top_level_tasks, meta),
        "plan_brief": _client_plan_brief(project),
        "usp": _project_unique_value(project),
        "feature_highlights": feature_highlights,
        "delivery_status": f"{completed} completed, {running} active, {blocked} blocked workstreams",
        "overall_status": project.status,
        "today_status": today_status,
        "team": involved_employees,
        "task_snapshot": [
            {
                "task_id": task.id,
                "name": task.description,
                "status": task.status,
                "estimated_time": task.estimated_time,
            }
            for task in top_level_tasks
        ],
        "payment_status": project.payment_status,
        "budget": project.budget,
        "spent": project.spent,
        "full_text": "\n".join(lines),
    }


def _recent_project_notifications(meta: Dict[str, Any], limit: int = 8) -> List[Dict[str, Any]]:
    return list(meta.get("notifications", []))[:limit]

def _task_experience_points(db: Session, task: Task, assignment: TaskAssignment) -> float:
    estimated_hours = float(task.estimated_time or assignment.estimated_hours or 0.0)
    complexity_bonus = {"easy": 8.0, "medium": 16.0, "hard": 24.0}.get(task.difficulty or "medium", 16.0)
    urgency_bonus = {"low": 4.0, "medium": 8.0, "high": 14.0, "critical": 20.0}.get(task.urgency or "medium", 8.0)
    timing_bonus = 12.0
    if task.deadline and assignment.completed_at and assignment.completed_at > task.deadline:
        timing_bonus = 4.0
    base_points = 25.0 + min(estimated_hours, 16.0) * 2.5 + complexity_bonus + urgency_bonus + timing_bonus
    existing_points = (
        db.query(func.coalesce(func.sum(PerformancePoint.points), 0.0))
        .filter(PerformancePoint.employee_id == assignment.employee_id)
        .scalar()
    )
    level = _experience_level(float(existing_points or 0.0))
    level_multiplier = max(0.45, 1.0 - ((level - 1) * 0.08))
    return round(base_points * level_multiplier, 1)


def _award_task_completion_points(db: Session, task: Task, assignment: TaskAssignment) -> Optional[PerformancePoint]:
    existing = (
        db.query(PerformancePoint)
        .filter(
            PerformancePoint.employee_id == assignment.employee_id,
            PerformancePoint.task_id == task.id,
            PerformancePoint.reason == "Automated task completion score",
        )
        .first()
    )
    if existing:
        return existing

    employee = db.query(EmployeeProfile).filter(EmployeeProfile.id == assignment.employee_id).first()
    if not employee:
        return None

    metrics = _ensure_employee_metrics(db, employee)
    assignment.completed_at = assignment.completed_at or _utcnow()
    assignment.actual_hours = assignment.actual_hours or assignment.estimated_hours or task.estimated_time or 0.0

    points = _task_experience_points(db, task, assignment)
    point_log = PerformancePoint(
        employee_id=assignment.employee_id,
        project_id=task.project_id,
        task_id=task.id,
        points=points,
        reason="Automated task completion score",
    )
    db.add(point_log)

    completed_before = metrics.total_tasks_completed or 0
    actual_hours = float(assignment.actual_hours or 0.0)
    metrics.total_tasks_completed = completed_before + 1
    if task.deadline and assignment.completed_at and assignment.completed_at > task.deadline:
        metrics.total_tasks_delayed = (metrics.total_tasks_delayed or 0) + 1
    metrics.avg_completion_time = round(
        (((metrics.avg_completion_time or 0.0) * completed_before) + actual_hours) / max(metrics.total_tasks_completed, 1),
        2,
    )

    estimated_hours = float(task.estimated_time or assignment.estimated_hours or actual_hours or 1.0)
    efficiency_sample = min(1.0, estimated_hours / max(actual_hours or estimated_hours, 1.0))
    metrics.efficiency_score = round(
        (((metrics.efficiency_score or 0.8) * completed_before) + efficiency_sample) / max(metrics.total_tasks_completed, 1),
        2,
    )
    metrics.reliability_score = round(
        max(
            0.5,
            min(
                0.99,
                0.7
                + min(metrics.total_tasks_completed, 12) * 0.02
                - (metrics.total_tasks_delayed or 0) * 0.03
                - (metrics.total_tasks_failed or 0) * 0.05,
            ),
        ),
        2,
    )
    db.add(metrics)
    return point_log


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
    recommended_team = _dedupe_recommended_team(_recommend_team(db, admin.tenant_id, role_clusters))
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
            "final_report": None,
            "payment_updates": [],
            "notifications": [],
            "client_plan_brief": None,
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
    project.custom_fields["client_plan_brief"] = _client_plan_brief(project)
    _append_notification(
        project.custom_fields,
        kind="project",
        title="Project created",
        message="The project intake is complete and waiting for admin approval on the staffing draft.",
        actor=admin.full_name or admin.email,
    )
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
    query = (
        db.query(Project)
        .options(joinedload(Project.client))
        .filter(Project.deleted_at.is_(None))
        .order_by(Project.created_at.desc())
    )
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
        .options(joinedload(Project.client), joinedload(Project.tasks))
        .filter(Project.tenant_id == admin.tenant_id, Project.deleted_at.is_(None))
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

    watch_notifications = []
    for project in projects:
        blocked = len([task for task in project.tasks if task.parent_task_id is None and task.status == "blocked"])
        delayed = len([task for task in project.tasks if task.parent_task_id is None and task.status == "delayed"])
        approval_status = _project_meta(project).get("approval_status")
        if blocked or delayed:
            watch_notifications.append(
                {
                    "kind": "watch",
                    "title": f"{project.name} needs attention",
                    "message": f"Blocked tasks: {blocked}. Delayed tasks: {delayed}.",
                    "actor": "system",
                    "created_at": _utcnow().isoformat(),
                }
            )
        elif approval_status in {"awaiting-admin-approval", "awaiting-team-join"}:
            watch_notifications.append(
                {
                    "kind": "watch",
                    "title": f"{project.name} awaiting action",
                    "message": f"Current approval state: {approval_status}.",
                    "actor": "system",
                    "created_at": _utcnow().isoformat(),
                }
            )

    return {
        "admin": {
            "user_id": admin.id,
            "full_name": admin.full_name,
            "email": admin.email,
            "role": admin.role,
            "tenant_id": admin.tenant_id,
        },
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
        "notifications": (watch_notifications + [
            notification
            for project in projects
            for notification in _recent_project_notifications(_project_meta(project), limit=4)
        ])[:8],
        "clients": get_clients(db, admin),
    }


PAYMENT_COLLECTED_STATUSES = {"client-confirmed", "admin-confirmed", "completed"}
PAYMENT_INVOICED_STATUSES = {"partial", "client-confirmed", "admin-confirmed", "completed", "disputed"}


def build_admin_analytics(db: Session, admin: User) -> dict:
    """Team-scoped analytics for admin: revenue, project health, task stats, member performance."""
    projects = (
        db.query(Project)
        .filter(Project.tenant_id == admin.tenant_id, Project.deleted_at.is_(None))
        .all()
    )
    employees = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.tenant_id == admin.tenant_id)
        .all()
    )
    tasks = (
        db.query(Task)
        .filter(Task.tenant_id == admin.tenant_id)
        .all()
    )
    metrics_rows = (
        db.query(EmployeeMetrics)
        .join(EmployeeProfile, EmployeeProfile.id == EmployeeMetrics.employee_id)
        .filter(EmployeeProfile.tenant_id == admin.tenant_id)
        .all()
    )
    blockers = (
        db.query(Blocker)
        .join(Task, Task.id == Blocker.task_id)
        .filter(Task.tenant_id == admin.tenant_id)
        .all()
    )

    total_budget = sum(float(p.budget or 0) for p in projects)
    total_spent = sum(float(p.spent or 0) for p in projects)
    total_collected = sum(float(p.budget or 0) for p in projects if p.payment_status in PAYMENT_COLLECTED_STATUSES)
    total_invoiced = sum(float(p.budget or 0) for p in projects if p.payment_status in PAYMENT_INVOICED_STATUSES)
    gross_profit = total_invoiced - total_spent
    profit_margin_pct = round(gross_profit / total_invoiced * 100 if total_invoiced else 0, 1)

    status_counts: dict = {}
    priority_counts: dict = {}
    for p in projects:
        status_counts[p.status or "unknown"] = status_counts.get(p.status or "unknown", 0) + 1
        priority_counts[p.priority or "medium"] = priority_counts.get(p.priority or "medium", 0) + 1

    done_tasks = [t for t in tasks if t.status in ("done", "completed")]
    blocked_tasks = [t for t in tasks if t.status == "blocked"]
    in_progress_tasks = [t for t in tasks if t.status == "in_progress"]
    open_blockers = [b for b in blockers if b.status == "open"]

    per_project = []
    for p in projects:
        b = float(p.budget or 0)
        s = float(p.spent or 0)
        pm = round((b - s) / b * 100, 1) if b else 0
        p_blockers = [bl for bl in open_blockers if any(t.id == bl.task_id and t.project_id == p.id for t in tasks)]
        per_project.append({
            "id": p.id,
            "name": p.name,
            "status": p.status,
            "priority": p.priority,
            "progress": float(p.progress or 0),
            "budget": round(b, 2),
            "spent": round(s, 2),
            "profit_margin": pm,
            "payment_status": p.payment_status,
            "open_blockers": len(p_blockers),
            "is_collected": p.payment_status in PAYMENT_COLLECTED_STATUSES,
        })
    per_project.sort(key=lambda x: -x["budget"])

    avg_efficiency = round(sum(m.efficiency_score or 0 for m in metrics_rows) / len(metrics_rows) * 100 if metrics_rows else 0, 1)
    avg_reliability = round(sum(m.reliability_score or 0 for m in metrics_rows) / len(metrics_rows) * 100 if metrics_rows else 0, 1)
    avg_utilization = round(
        sum(float(e.current_load or 0) / float(e.max_capacity or 1) * 100 for e in employees) / len(employees)
        if employees else 0, 1
    )
    top_performers = sorted(
        [
            {
                "name": (m.employee.user.full_name if m.employee and m.employee.user else f"Employee #{m.employee_id}"),
                "efficiency": round((m.efficiency_score or 0) * 100, 1),
                "reliability": round((m.reliability_score or 0) * 100, 1),
                "tasks_completed": m.total_tasks_completed or 0,
            }
            for m in metrics_rows
        ],
        key=lambda x: x["efficiency"] + x["reliability"],
        reverse=True,
    )[:5]

    return {
        "revenue": {
            "total_budget": round(total_budget, 2),
            "total_spent": round(total_spent, 2),
            "total_invoiced": round(total_invoiced, 2),
            "total_collected": round(total_collected, 2),
            "outstanding": round(total_invoiced - total_collected, 2),
            "gross_profit": round(gross_profit, 2),
            "profit_margin_pct": profit_margin_pct,
            "collection_rate_pct": round(total_collected / total_invoiced * 100 if total_invoiced else 0, 1),
        },
        "projects": {
            "total": len(projects),
            "active": len([p for p in projects if p.status not in ("completed", "cancelled")]),
            "completed": len([p for p in projects if p.status == "completed"]),
            "by_status": [{"label": k, "value": v} for k, v in sorted(status_counts.items())],
            "by_priority": [{"label": k, "value": v} for k, v in sorted(priority_counts.items())],
        },
        "tasks": {
            "total": len(tasks),
            "completed": len(done_tasks),
            "in_progress": len(in_progress_tasks),
            "blocked": len(blocked_tasks),
            "open_blockers": len(open_blockers),
            "completion_rate_pct": round(len(done_tasks) / len(tasks) * 100 if tasks else 0, 1),
        },
        "team": {
            "total_employees": len(employees),
            "avg_utilization_pct": avg_utilization,
            "avg_efficiency_pct": avg_efficiency,
            "avg_reliability_pct": avg_reliability,
            "top_performers": top_performers,
        },
        "per_project": per_project,
    }



def build_team_dashboard(db: Session, admin: User):
    employees = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user), joinedload(EmployeeProfile.assignments).joinedload(TaskAssignment.task))
        .filter(EmployeeProfile.tenant_id == admin.tenant_id)
        .order_by(EmployeeProfile.department.asc(), EmployeeProfile.id.asc())
        .all()
    )
    performance = _performance_snapshots(db, [employee.id for employee in employees])
    pending_invites = (
        db.query(TeamInvite, Team, Project)
        .join(Team, Team.id == TeamInvite.team_id)
        .join(Project, Project.id == Team.project_id)
        .filter(TeamInvite.tenant_id == admin.tenant_id, TeamInvite.status == "pending")
        .order_by(TeamInvite.created_at.desc())
        .all()
    )
    invite_targets = (
        db.query(Project)
        .filter(Project.tenant_id == admin.tenant_id, Project.status != "completed", Project.deleted_at.is_(None))
        .order_by(Project.created_at.desc())
        .all()
    )

    members = []
    for employee in employees:
        active_assignments = [
            assignment
            for assignment in employee.assignments
            if assignment.task and assignment.task.project and assignment.task.project.status != "completed"
        ]
        performance_entry = performance.get(employee.id, {})
        members.append(
            {
                "employee_id": employee.id,
                "name": employee.user.full_name if employee.user else f"Employee {employee.id}",
                "email": employee.user.email if employee.user else None,
                "title": _title_from_employee(employee),
                "department": employee.department,
                "shift_status": _shift_status(employee),
                "availability_status": _effective_availability_status(employee),
                "workload_percent": _workload_percent(employee.current_load, employee.max_capacity),
                "current_load": employee.current_load,
                "max_capacity": employee.max_capacity,
                "skills": employee.skills,
                "duty_start_hour": employee.duty_start_hour,
                "duty_end_hour": employee.duty_end_hour,
                "duty_window": _duty_window_label(employee),
                "on_leave": employee.availability_status == "on-leave",
                "active_assignment_count": len(active_assignments),
                "active_projects": sorted(
                    {assignment.task.project.name for assignment in active_assignments if assignment.task and assignment.task.project}
                ),
                "experience_points": performance_entry.get("experience_points", 0.0),
                "experience_grade": performance_entry.get("experience_grade", "Starter"),
                "current_level": performance_entry.get("current_level", 1),
                "current_level_points": performance_entry.get("current_level_points", 0.0),
                "points_to_next_level": performance_entry.get("points_to_next_level", 100.0),
                "level_progress_percent": performance_entry.get("level_progress_percent", 0.0),
                "next_level_points": performance_entry.get("next_level_points", 100),
                "efficiency_score": performance_entry.get("efficiency_score", 0.0),
                "reliability_score": performance_entry.get("reliability_score", 0.0),
                "tasks_completed": performance_entry.get("tasks_completed", 0),
                "tasks_delayed": performance_entry.get("tasks_delayed", 0),
            }
        )

    return {
        "team_size": len(members),
        "members": members,
        "invite_targets": [
            {
                "project_id": project.id,
                "name": project.name,
                "status": project.status,
            }
            for project in invite_targets
        ],
        "pending_invites": [
            {
                "invite_id": invite.id,
                "email": invite.email,
                "project_id": project.id,
                "project_name": project.name,
                "role_title": invite.role_title,
                "created_at": invite.created_at.isoformat() if invite.created_at else None,
            }
            for invite, _team, project in pending_invites
        ],
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
        .filter(Project.tenant_id == admin.tenant_id, Project.deleted_at.is_(None))
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
    top_level_tasks = [task for task in tasks if task.parent_task_id is None]
    completed_tasks = len([task for task in top_level_tasks if task.status == "done"])
    blocked_tasks = len([task for task in top_level_tasks if task.status == "blocked"])
    in_progress_tasks = len([task for task in top_level_tasks if task.status in {"running", "in-progress"}])
    meta = _refresh_project_team_metadata(db, project)
    visible_client_id = project.client_id if not viewer or viewer.role == "admin" else None
    public_status_label = _client_business_summary(project, top_level_tasks, meta)
    report = meta.get("final_report") or _build_project_report(db, project)

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
        "payment_updates": _payment_activity(meta),
        "client_id": visible_client_id,
        "client_name": project.client.company_name if project.client else None,
        "client_contact_person": project.client.contact_person if project.client else None,
        "client_user_name": project.client.user.full_name if project.client and project.client.user else None,
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
        "client_plan_brief": meta.get("client_plan_brief") or report["plan_brief"],
        "usp": report["usp"],
        "feature_highlights": report["feature_highlights"],
        "delivery_status": report["delivery_status"],
        "overall_status": report["overall_status"],
        "today_status": report["today_status"],
        "role_clusters": meta.get("role_clusters", []),
        "draft_team": _serialize_draft_team(db, project, meta.get("recommended_team", [])),
        "team_invites": _visible_team_invites(meta, viewer),
        "replacement_suggestions": meta.get("replacement_suggestions", []),
        "emp_involved": involved_employees,
        "task_change_requests": [
            _serialize_task_change_request(project, request)
            for request in sorted(
                _task_change_requests(meta),
                key=lambda item: item.get("created_at") or "",
                reverse=True,
            )
        ] if viewer and viewer.role == "admin" else [],
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
                "subtasks": [
                    {
                        "id": child.id,
                        "description": child.description,
                        "status": child.status,
                        "estimated_time": child.estimated_time,
                    }
                    for child in sorted(
                        [child for child in tasks if child.parent_task_id == task.id],
                        key=lambda child: child.created_at,
                    )
                ],
                "assignments": [
                    {
                        "employee_id": assignment.employee_id,
                        "employee_name": assignment.employee.user.full_name if assignment.employee and assignment.employee.user else None,
                        "status": assignment.status,
                        "estimated_hours": assignment.estimated_hours,
                    }
                    for assignment in task.assignments
                ],
                "replacement_options": (
                    _available_role_members(
                        db,
                        project.tenant_id,
                        meta.get("task_role_map", {}).get(str(task.id)),
                        exclude_ids=[assignment.employee_id for assignment in task.assignments],
                    )
                    if viewer and viewer.role == "admin"
                    else []
                ),
            }
            for task in top_level_tasks
        ],
        "report_text": meta.get("report_text") or report["full_text"],
        "final_report": meta.get("final_report") or report,
        "notifications": _recent_project_notifications(meta),
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
    actor = db.query(User).filter(User.id == actor_id).first()
    if approved and meta.get("approval_status") == "awaiting-team-join":
        return build_project_status(db, project.id, viewer=actor)
    if not approved and meta.get("approval_status") == "rejected":
        return build_project_status(db, project.id, viewer=actor)
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
        _append_notification(
            meta,
            kind="approval",
            title="Staffing draft approved",
            message="The project team plan was approved and invite responses are now pending.",
        )
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
        _append_notification(
            meta,
            kind="approval",
            title="Staffing draft rejected",
            message="The staffing draft was rejected and moved back to admin review.",
        )
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
    if invite.status != "pending":
        team = db.query(Team).filter(Team.id == invite.team_id).first()
        if not team:
            raise HTTPException(status_code=404, detail="Project team not found")
        return build_project_status(db, team.project_id, viewer=actor)
    return handle_team_invite_action(db=db, actor=actor, invite_id=invite.id, token=None, accepted=accepted, note=note)


def replace_draft_team_member(
    db: Session,
    *,
    project_id: int,
    current_employee_id: int,
    replacement_employee_id: int,
    note: Optional[str],
    actor: User,
):
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can edit the draft team")

    project = (
        db.query(Project)
        .options(joinedload(Project.tasks).joinedload(Task.assignments))
        .filter(Project.id == project_id, Project.tenant_id == actor.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    meta = _project_meta(project)
    if meta.get("approval_status") != "awaiting-admin-approval":
        raise HTTPException(status_code=409, detail="Draft team can only be changed before approval")

    recommended_team = _dedupe_recommended_team(meta.get("recommended_team", []))
    target_index = next((index for index, member in enumerate(recommended_team) if member.get("employee_id") == current_employee_id), None)
    if target_index is None:
        raise HTTPException(status_code=404, detail="Current draft team member not found")

    replacement = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.id == replacement_employee_id, EmployeeProfile.tenant_id == actor.tenant_id)
        .first()
    )
    if not replacement or not replacement.user:
        raise HTTPException(status_code=404, detail="Replacement employee not found")

    target_role = recommended_team[target_index].get("title")
    replacement_role = _title_from_employee(replacement)
    if replacement_role != target_role:
        raise HTTPException(status_code=400, detail=f"Replacement must match the required role: {target_role}")
    if any(member.get("employee_id") == replacement.id for member in recommended_team):
        raise HTTPException(status_code=409, detail="Replacement employee is already part of the draft team")

    recommended_team[target_index] = {
        "employee_id": replacement.id,
        "name": replacement.user.full_name,
        "title": replacement_role,
        "availability_status": _effective_availability_status(replacement),
        "shift_status": _shift_status(replacement),
        "workload_percent": _workload_percent(replacement.current_load, replacement.max_capacity),
        "duty_window": _duty_window_label(replacement),
    }

    meta["recommended_team"] = recommended_team
    meta["team_invites"] = _build_team_invites(recommended_team, meta.get("role_clusters", []))
    meta["replacement_suggestions"] = _available_role_members(
        db,
        actor.tenant_id,
        target_role,
        exclude_ids=[member["employee_id"] for member in recommended_team],
    )
    _append_notification(
        meta,
        kind="staffing",
        title="Draft team updated",
        message=f"Admin replaced the {target_role} draft recommendation.",
        actor=actor.full_name or actor.email,
    )
    _log_decision(
        db,
        "draft_team_replacement",
        project.id,
        0.88,
        note or f"Replaced draft {target_role} member {current_employee_id} with {replacement.id}.",
    )
    project.custom_fields = meta
    db.add(project)
    db.commit()
    db.refresh(project)
    return build_project_status(db, project.id, viewer=actor)


def reassign_project_task(
    db: Session,
    *,
    project_id: int,
    task_id: int,
    replacement_employee_id: int,
    note: Optional[str],
    actor: User,
):
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can reassign project tasks")

    project = (
        db.query(Project)
        .options(joinedload(Project.tasks).joinedload(Task.assignments))
        .filter(Project.id == project_id, Project.tenant_id == actor.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = next((project_task for project_task in project.tasks if project_task.id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    replacement = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user))
        .filter(EmployeeProfile.id == replacement_employee_id, EmployeeProfile.tenant_id == actor.tenant_id)
        .first()
    )
    if not replacement or not replacement.user:
        raise HTTPException(status_code=404, detail="Replacement employee not found")

    required_role = _project_meta(project).get("task_role_map", {}).get(str(task.id))
    if required_role and _title_from_employee(replacement) != required_role:
        raise HTTPException(status_code=400, detail=f"Replacement must match the required role: {required_role}")

    existing_assignment = next((assignment for assignment in task.assignments if assignment.employee_id == replacement.id), None)
    for assignment in task.assignments:
        if assignment.employee_id == replacement.id:
            continue
        previous_employee = assignment.employee
        if previous_employee:
            previous_employee.current_load = max(0.0, round((previous_employee.current_load or 0) - (assignment.estimated_hours or 0), 1))
            _sync_employee_capacity_state(previous_employee)
        assignment.status = "reassigned"
        assignment.notes = (assignment.notes or "") + f"\nReassigned by admin at {_utcnow().isoformat()}."
        db.add(assignment)

    if existing_assignment:
        existing_assignment.status = "assigned"
        existing_assignment.estimated_hours = task.estimated_time
        existing_assignment.notes = note or existing_assignment.notes or "Reassigned by admin."
        db.add(existing_assignment)
    else:
        db.add(
            TaskAssignment(
                task_id=task.id,
                employee_id=replacement.id,
                status="assigned",
                estimated_hours=task.estimated_time,
                assignment_confidence=1.0,
                notes=note or "Reassigned by admin.",
            )
        )

    replacement.current_load = round((replacement.current_load or 0) + (task.estimated_time or 0), 1)
    _sync_employee_capacity_state(replacement)

    meta = _project_meta(project)
    _append_notification(
        meta,
        kind="reassignment",
        title="Task reassigned",
        message=f"Task '{task.description}' was reassigned to {replacement.user.full_name}.",
        actor=actor.full_name or actor.email,
    )
    _log_decision(
        db,
        "task_reassignment",
        project.id,
        0.9,
        note or f"Task {task.id} reassigned to employee {replacement.id}.",
    )
    project.custom_fields = meta
    db.add(project)
    db.commit()
    db.refresh(project)
    return build_project_status(db, project.id, viewer=actor)


def update_project_payment_status(
    db: Session,
    *,
    project_id: int,
    payment_status: str,
    note: Optional[str],
    actor: User,
):
    project = (
        db.query(Project)
        .options(joinedload(Project.client).joinedload(ClientProfile.user))
        .filter(Project.id == project_id, Project.tenant_id == actor.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    client_user_id = project.client.user_id if project.client else None
    if actor.role not in {"admin", "client"}:
        raise HTTPException(status_code=403, detail="Only admins or the linked client can update payment status")
    if actor.role == "client" and actor.id != client_user_id:
        raise HTTPException(status_code=403, detail="Not authorized to update payment status for this project")

    allowed_statuses = {"pending", "partial", "completed", "client-confirmed", "admin-confirmed", "disputed"}
    normalized_status = payment_status.strip().lower()
    if normalized_status not in allowed_statuses:
        raise HTTPException(status_code=400, detail=f"Payment status must be one of: {', '.join(sorted(allowed_statuses))}")

    project.payment_status = normalized_status
    meta = _project_meta(project)
    updates = list(meta.get("payment_updates", []))
    updates.insert(
        0,
        {
            "status": normalized_status,
            "note": note,
            "updated_by": actor.full_name or actor.email,
            "actor_role": actor.role,
            "updated_at": _utcnow().isoformat(),
        },
    )
    meta["payment_updates"] = updates[:20]
    _append_notification(
        meta,
        kind="payment",
        title="Payment status updated",
        message=f"Payment status is now '{normalized_status}'.",
        actor=actor.full_name or actor.email,
    )
    project.custom_fields = meta
    db.add(project)
    db.commit()
    db.refresh(project)
    return build_project_status(db, project.id, viewer=actor)

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
        _append_notification(
            meta,
            kind="invite",
            title="Team member joined",
            message=f"{employee_profile.user.full_name if employee_profile.user else actor.email} accepted the invite and their task package is now active.",
            actor=actor.full_name or actor.email,
        )
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
        _append_notification(
            meta,
            kind="invite",
            title="Team invite rejected",
            message=f"{employee_profile.user.full_name if employee_profile.user else actor.email} declined the invite. Replacement suggestions were generated.",
            actor=actor.full_name or actor.email,
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
                "required_role": "Delivery Lead",
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
        _sync_employee_capacity_state(employee)
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
        _sync_employee_capacity_state(employee)
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

    summaries_by_email: Dict[str, Dict[str, Any]] = {}
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
        summaries_by_email[normalize_email(invite.email)] = {
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
    return list(summaries_by_email.values())


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
            "availability_status": _effective_availability_status(employee),
            "shift_status": _shift_status(employee),
            "workload_percent": _workload_percent(employee.current_load, employee.max_capacity),
            "duty_window": _duty_window_label(employee),
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
    top_level_tasks = db.query(Task).filter(Task.project_id == project.id, Task.parent_task_id.is_(None), Task.deleted_at.is_(None)).all()
    task_count = len(top_level_tasks)
    completed_count = len([task for task in top_level_tasks if task.status == "done"])
    visible_client_id = project.client_id if not viewer or viewer.role == "admin" else None
    team_invites = meta.get("team_invites", [])
    pending_invites = [invite for invite in team_invites if invite.get("status") == "pending"]
    report = meta.get("final_report") or _build_project_report(db, project)

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
        "client_contact_person": project.client.contact_person if project.client else None,
        "client_user_name": project.client.user.full_name if project.client and project.client.user else None,
        "budget": project.budget,
        "spent": project.spent,
        "payment_status": project.payment_status,
        "payment_updates": _payment_activity(meta),
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
        "today_status": report["today_status"],
        "feature_highlights": report["feature_highlights"],
        "report_text": meta.get("report_text") or report["full_text"],
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
        "final_report": meta.get("final_report"),
    }


def _project_meta(project: Project):
    return dict(project.custom_fields or {})


def _task_change_requests(meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    requests = meta.get("task_change_requests")
    return requests if isinstance(requests, list) else []


def _employee_can_access_task(db: Session, task: Optional[Task], actor: User) -> Tuple[bool, Optional[EmployeeProfile]]:
    if not task:
        return False, None
    profile = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.user_id == actor.id, EmployeeProfile.tenant_id == actor.tenant_id)
        .first()
    )
    if not profile:
        return False, None

    direct_assignment = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.task_id == task.id, TaskAssignment.employee_id == profile.id)
        .first()
    )
    if direct_assignment:
        return True, profile

    if task.parent_task_id:
        parent_assignment = (
            db.query(TaskAssignment)
            .filter(TaskAssignment.task_id == task.parent_task_id, TaskAssignment.employee_id == profile.id)
            .first()
        )
        if parent_assignment:
            return True, profile

    return False, profile


def _serialize_task_change_request(project: Project, request: Dict[str, Any]) -> Dict[str, Any]:
    tasks_by_id = {task.id: task for task in project.tasks}
    target_task = tasks_by_id.get(request.get("target_task_id"))
    parent_task = tasks_by_id.get(request.get("parent_task_id"))
    return {
        "request_id": request.get("request_id"),
        "status": request.get("status", "pending"),
        "action": request.get("action"),
        "target_type": request.get("target_type"),
        "target_task_id": request.get("target_task_id"),
        "target_task_title": target_task.description if target_task else request.get("target_task_title"),
        "parent_task_id": request.get("parent_task_id"),
        "parent_task_title": parent_task.description if parent_task else request.get("parent_task_title"),
        "proposed_title": request.get("proposed_title"),
        "proposed_description": request.get("proposed_description"),
        "note": request.get("note"),
        "role_title": request.get("role_title"),
        "requested_by_user_id": request.get("requested_by_user_id"),
        "requested_by_employee_id": request.get("requested_by_employee_id"),
        "requested_by_name": request.get("requested_by_name"),
        "agent_review": request.get("agent_review"),
        "admin_note": request.get("admin_note"),
        "created_at": request.get("created_at"),
        "reviewed_at": request.get("reviewed_at"),
        "reviewed_by_name": request.get("reviewed_by_name"),
        "applied_task_id": request.get("applied_task_id"),
    }


def _delete_task_tree(db: Session, project: Project, task: Task, meta: Dict[str, Any]) -> None:
    child_tasks = db.query(Task).filter(Task.parent_task_id == task.id).all()
    for child in child_tasks:
        _delete_task_tree(db, project, child, meta)

    assignments = db.query(TaskAssignment).filter(TaskAssignment.task_id == task.id).all()
    for assignment in assignments:
        employee = db.query(EmployeeProfile).filter(EmployeeProfile.id == assignment.employee_id).first()
        if employee:
            employee.current_load = max(
                0.0,
                round((employee.current_load or 0.0) - float(assignment.estimated_hours or task.estimated_time or 0.0), 1),
            )
            _sync_employee_capacity_state(employee)
            db.add(employee)
        db.delete(assignment)

    db.query(TaskDependency).filter(
        (TaskDependency.task_id == task.id) | (TaskDependency.depends_on_task_id == task.id)
    ).delete(synchronize_session=False)
    db.query(Checkpoint).filter(Checkpoint.task_id == task.id).delete(synchronize_session=False)
    db.query(TaskProgress).filter(TaskProgress.task_id == task.id).delete(synchronize_session=False)
    db.query(Blocker).filter(Blocker.task_id == task.id).delete(synchronize_session=False)
    db.query(PerformancePoint).filter(PerformancePoint.task_id == task.id).delete(synchronize_session=False)
    db.query(Communication).filter(Communication.task_id == task.id).delete(synchronize_session=False)
    db.query(EventQueue).filter(
        (EventQueue.entity_type == "task") & (EventQueue.entity_id == task.id)
    ).delete(synchronize_session=False)
    db.query(DecisionLog).filter(
        (DecisionLog.entity_type == "task") & (DecisionLog.entity_id == task.id)
    ).delete(synchronize_session=False)

    task_role_map = meta.get("task_role_map", {})
    task_role_map.pop(str(task.id), None)
    meta["task_role_map"] = task_role_map
    db.delete(task)


def create_task_change_request(
    db: Session,
    *,
    project_id: int,
    action: str,
    target_type: str,
    target_task_id: Optional[int],
    parent_task_id: Optional[int],
    proposed_title: Optional[str],
    proposed_description: Optional[str],
    note: str,
    actor: User,
):
    if actor.role != "employee":
        raise HTTPException(status_code=403, detail="Only employees can propose task list changes")

    project = (
        db.query(Project)
        .options(joinedload(Project.tasks).joinedload(Task.assignments))
        .filter(Project.id == project_id, Project.tenant_id == actor.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    tasks_by_id = {task.id: task for task in project.tasks}
    related_task = tasks_by_id.get(target_task_id) if target_task_id else None
    parent_task = tasks_by_id.get(parent_task_id) if parent_task_id else None

    if action == "add" and target_type == "task" and not related_task:
        raise HTTPException(status_code=400, detail="Choose one current task so the new task can inherit the correct project context")
    if action == "add" and target_type == "subtask" and not parent_task:
        raise HTTPException(status_code=400, detail="Choose the parent task for the new subtask")
    if action == "delete" and not related_task:
        raise HTTPException(status_code=400, detail="Choose the task or subtask you want to remove")
    if target_type == "subtask" and action == "delete" and related_task and related_task.parent_task_id is None:
        raise HTTPException(status_code=400, detail="Only subtasks can be removed through the subtask flow")
    if target_type == "task" and action == "delete" and related_task and related_task.parent_task_id is not None:
        raise HTTPException(status_code=400, detail="Choose the parent task instead of one of its subtasks")

    access_task = parent_task or related_task
    allowed, profile = _employee_can_access_task(db, access_task, actor)
    if not allowed or not profile:
        raise HTTPException(status_code=403, detail="You can only edit task lists that belong to your assigned work")

    meta = _project_meta(project)
    task_role_map = meta.get("task_role_map", {})
    role_anchor = parent_task or related_task
    role_title = (
        task_role_map.get(str(parent_task_id or 0))
        or task_role_map.get(str(target_task_id or 0))
        or (task_role_map.get(str(role_anchor.parent_task_id)) if role_anchor and role_anchor.parent_task_id else None)
        or _title_from_employee(profile)
    )

    context = {
        "project_name": project.name,
        "project_status": project.status,
        "employee_name": actor.full_name or actor.email,
        "employee_role": _title_from_employee(profile),
        "change_action": action,
        "target_type": target_type,
        "target_task": related_task.description if related_task else None,
        "parent_task": parent_task.description if parent_task else None,
        "proposed_title": proposed_title,
        "proposed_description": proposed_description,
        "employee_note": note,
        "current_project_progress": project.progress,
    }
    llm_service = LLMService()
    agent_review = llm_service.generate_decision_support("task_change_request", "admin", context)

    request = {
        "request_id": uuid4().hex,
        "status": "pending",
        "action": action,
        "target_type": target_type,
        "target_task_id": target_task_id,
        "target_task_title": related_task.description if related_task else None,
        "parent_task_id": parent_task_id if action == "add" and target_type == "subtask" else (related_task.parent_task_id if related_task else None),
        "parent_task_title": parent_task.description if parent_task else (tasks_by_id.get(related_task.parent_task_id).description if related_task and related_task.parent_task_id and tasks_by_id.get(related_task.parent_task_id) else None),
        "proposed_title": proposed_title,
        "proposed_description": proposed_description,
        "note": note,
        "role_title": role_title,
        "requested_by_user_id": actor.id,
        "requested_by_employee_id": profile.id,
        "requested_by_name": actor.full_name or actor.email,
        "created_at": _utcnow().isoformat(),
        "agent_review": agent_review,
    }
    requests = _task_change_requests(meta)
    requests.append(request)
    meta["task_change_requests"] = requests
    _append_notification(
        meta,
        kind="task-change",
        title="Task list change requested",
        message=f"{actor.full_name or actor.email} requested to {action} a {target_type}. Admin approval is now required.",
        actor=actor.full_name or actor.email,
    )
    project.custom_fields = meta
    db.add(project)
    db.commit()
    db.refresh(project)
    return _serialize_task_change_request(project, request)


def review_task_change_request(
    db: Session,
    *,
    project_id: int,
    request_id: str,
    approved: bool,
    note: Optional[str],
    actor: User,
):
    if actor.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can review task list changes")

    project = (
        db.query(Project)
        .options(joinedload(Project.tasks).joinedload(Task.assignments))
        .filter(Project.id == project_id, Project.tenant_id == actor.tenant_id)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    meta = _project_meta(project)
    requests = _task_change_requests(meta)
    request = next((item for item in requests if item.get("request_id") == request_id), None)
    if not request:
        raise HTTPException(status_code=404, detail="Task change request not found")
    if request.get("status") != "pending":
        return build_project_status(db, project.id, viewer=actor)

    tasks_by_id = {task.id: task for task in project.tasks}
    anchor_task = tasks_by_id.get(request.get("target_task_id"))
    parent_task = tasks_by_id.get(request.get("parent_task_id"))

    if approved:
        if request.get("action") == "add":
            anchor = parent_task or anchor_task
            role_title = request.get("role_title") or (meta.get("task_role_map", {}) or {}).get(str(anchor.id if anchor else 0))
            estimated_time = float(anchor.estimated_time or 4.0) if anchor else 4.0
            if request.get("target_type") == "subtask":
                estimated_time = max(1.0, round(estimated_time / 2, 1))
            description = request.get("proposed_title") or "Proposed task"
            if request.get("proposed_description"):
                description = f"{description}: {request['proposed_description']}"

            created_task = Task(
                project_id=project.id,
                parent_task_id=parent_task.id if request.get("target_type") == "subtask" and parent_task else None,
                description=description,
                difficulty=anchor.difficulty if anchor else "medium",
                urgency=anchor.urgency if anchor else "medium",
                estimated_time=estimated_time,
                required_skills=anchor.required_skills if anchor else {},
                deadline=anchor.deadline if anchor else None,
                tenant_id=project.tenant_id,
            )
            db.add(created_task)
            db.flush()
            _ensure_task_progress(db, created_task)

            task_role_map = meta.get("task_role_map", {})
            if role_title:
                task_role_map[str(created_task.id)] = role_title
                meta["task_role_map"] = task_role_map

            if request.get("target_type") == "task" and request.get("requested_by_employee_id"):
                assignment = TaskAssignment(
                    task_id=created_task.id,
                    employee_id=request["requested_by_employee_id"],
                    estimated_hours=estimated_time,
                    status="assigned",
                )
                db.add(assignment)
                employee = db.query(EmployeeProfile).filter(EmployeeProfile.id == request["requested_by_employee_id"]).first()
                if employee:
                    employee.current_load = round((employee.current_load or 0.0) + estimated_time, 1)
                    _sync_employee_capacity_state(employee)
                    db.add(employee)
                meta["emp_involved_ids"] = sorted(set(meta.get("emp_involved_ids", [])) | {request["requested_by_employee_id"]})

            request["applied_task_id"] = created_task.id
        else:
            target_task = tasks_by_id.get(request.get("target_task_id"))
            if not target_task:
                raise HTTPException(status_code=404, detail="The requested task is no longer available")
            _delete_task_tree(db, project, target_task, meta)

        request["status"] = "approved"
        status_message = "approved"
        _append_notification(
            meta,
            kind="task-change",
            title="Task list change approved",
            message=f"{actor.full_name or actor.email} approved a {request.get('target_type')} {request.get('action')} request.",
            actor=actor.full_name or actor.email,
        )
    else:
        request["status"] = "rejected"
        status_message = "rejected"
        _append_notification(
            meta,
            kind="task-change",
            title="Task list change rejected",
            message=f"{actor.full_name or actor.email} rejected a {request.get('target_type')} {request.get('action')} request.",
            actor=actor.full_name or actor.email,
        )

    request["admin_note"] = note
    request["reviewed_at"] = _utcnow().isoformat()
    request["reviewed_by_name"] = actor.full_name or actor.email
    meta["task_change_requests"] = requests
    project.custom_fields = meta
    db.add(project)
    _sync_project_progress(db, project.id)
    db.commit()
    db.refresh(project)
    _log_decision(
        db,
        "task_change_request",
        project.id,
        0.78 if approved else 0.62,
        f"Admin {status_message} task change request {request_id}. {note or 'No review note provided.'}",
    )
    return build_project_status(db, project.id, viewer=actor)


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
    performance = _performance_snapshots(db, [profile.id]).get(profile.id, {})

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
    completed_tasks = []
    project_invites = []
    planned_tracks = []
    project_history = []

    invite_projects = (
        db.query(Project)
        .options(joinedload(Project.tasks))
        .filter(Project.tenant_id == user.tenant_id, Project.deleted_at.is_(None), Project.status != "completed")
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
        child_tasks = sorted(
            [child for child in project.tasks if child.parent_task_id == task.id],
            key=lambda child: child.created_at,
        )
        child_progress_map = {
            progress.task_id: progress
            for progress in db.query(TaskProgress).filter(TaskProgress.task_id.in_([child.id for child in child_tasks]) if child_tasks else False).all()
        }
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

        task_completion = progress.completion_percentage if progress else 0
        task_is_done = (
            task.status in ("done", "completed", "cancelled")
            or task_completion >= 100
        )

        task_payload = {
                "assignment_id": assignment.id,
                "task_id": task.id,
                "project_id": project.id,
                "project_name": project.name,
                "task_name": task.description,
                "status": task.status,
                "assignment_status": assignment.status,
                "estimated_hours": assignment.estimated_hours,
                "completion_percentage": task_completion,
                "project_progress": project.progress,
                "notes": task_brief,
                "concern_path": "Raise a concern in this workspace first. The AI lead will respond before admin escalation is triggered.",
                "subtasks": [
                    {
                        "id": child.id,
                        "title": child.description,
                        "status": child.status,
                        "estimated_hours": child.estimated_time,
                        "completion_percentage": child_progress_map.get(child.id).completion_percentage if child_progress_map.get(child.id) else (100 if child.status == "done" else 0),
                    }
                    for child in child_tasks
                ],
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
                "task_change_requests": [
                    _serialize_task_change_request(project, request)
                    for request in sorted(
                        _task_change_requests(meta),
                        key=lambda item: item.get("created_at") or "",
                        reverse=True,
                    )
                    if request.get("requested_by_user_id") == user.id
                    and (
                        request.get("target_task_id") == task.id
                        or request.get("parent_task_id") == task.id
                        or request.get("target_task_id") in {child.id for child in child_tasks}
                    )
                ],
            }

        if task_is_done:
            completed_tasks.append(task_payload)
        else:
            my_tasks.append(task_payload)

        if project.id not in seen_projects:
            seen_projects.add(project.id)
            # Count personal task completion using task.status (same logic as task_is_done)
            # so orchestrator-created "pending" assignments don't undercount done work.
            proj_assignments = (
                db.query(TaskAssignment)
                .options(joinedload(TaskAssignment.task))
                .join(Task, Task.id == TaskAssignment.task_id)
                .filter(Task.project_id == project.id, TaskAssignment.employee_id == profile.id)
                .all()
            )
            total_mine = len(proj_assignments)
            done_mine = sum(
                1 for a in proj_assignments
                if a.status == "completed"
                or (a.task and a.task.status in ("done", "completed", "cancelled"))
            )
            my_completion_pct = round((done_mine / total_mine) * 100) if total_mine else 0
            payload = {
                "project_id": project.id,
                "name": project.name,
                "status": project.status,
                "progress": project.progress,
                "my_task_total": total_mine,
                "my_task_done": done_mine,
                "my_completion_pct": my_completion_pct,
                "public_status_label": _client_business_summary(project, [task for task in project.tasks if task.parent_task_id is None], meta),
                "viewer_guidance": _guidance_for_viewer(meta, user),
                "decision_support": _decision_support_for_viewer(meta, user),
                "report_text": meta.get("report_text"),
            }
            if project.status == "completed":
                project_history.append(payload)
            else:
                my_projects.append(payload)

    all_tasks = my_tasks + completed_tasks
    overall_personal_progress = round(
        (len(completed_tasks) / len(all_tasks)) * 100,
        1,
    ) if all_tasks else 0.0

    # Self-heal workload: recalculate current_load from non-completed assignments
    # so stale load values (e.g. from before the completion-fix was deployed) self-correct.
    active_load = sum(
        float(a.estimated_hours or (a.task.estimated_time if a.task else 0) or 0)
        for a in assignments
        if a.task and a.task.status not in ("done", "completed", "cancelled")
        and a.status not in ("completed", "cancelled")
    )
    active_load = round(active_load, 1)
    if profile.current_load != active_load:
        profile.current_load = max(0.0, active_load)
        _sync_employee_capacity_state(profile)
        db.add(profile)
        db.commit()
        db.refresh(profile)

    return {
        "employee": {
            "employee_id": profile.id,
            "name": profile.user.full_name if profile.user else user.email,
            "title": _title_from_employee(profile),
            "department": profile.department,
            "availability_status": _effective_availability_status(profile),
            "shift_status": _shift_status(profile),
            "workload_percent": _workload_percent(profile.current_load, profile.max_capacity),
            "skills": profile.skills or {},
            "duty_start_hour": profile.duty_start_hour,
            "duty_end_hour": profile.duty_end_hour,
            "duty_window": _duty_window_label(profile),
            "on_leave": profile.availability_status == "on-leave",
            "experience_points": performance.get("experience_points", 0.0),
            "experience_grade": performance.get("experience_grade", "Starter"),
            "current_level": performance.get("current_level", 1),
            "current_level_points": performance.get("current_level_points", 0.0),
            "points_to_next_level": performance.get("points_to_next_level", 100.0),
            "level_progress_percent": performance.get("level_progress_percent", 0.0),
            "next_level_points": performance.get("next_level_points", 100),
            "efficiency_score": performance.get("efficiency_score", 0.0),
            "reliability_score": performance.get("reliability_score", 0.0),
            "tasks_completed": performance.get("tasks_completed", 0),
        },
        "summary": {
            "active_projects": len(my_projects),
            "assigned_tasks": len(my_tasks),
            "completed_tasks": len(completed_tasks),
            "personal_progress_percent": overall_personal_progress,
            "pending_invites": len([invite for invite in project_invites if invite["status"] == "pending"]),
            "experience_points": performance.get("experience_points", 0.0),
        },
        "notifications": _recent_performance_notifications(db, profile.id),
        "project_invites": project_invites,
        "planned_tracks": planned_tracks,
        "projects": my_projects,
        "history": project_history,
        "tasks": my_tasks,
        "completed_tasks": completed_tasks,
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
    history = []
    for project in projects:
        meta = _refresh_project_team_metadata(db, project)
        top_level_tasks = [task for task in project.tasks if task.parent_task_id is None]
        report = _build_project_report(db, project)
        payload = {
            "project_id": project.id,
            "name": project.name,
            "status": project.status,
            "progress": project.progress,
            "client_status": meta.get("client_status"),
            "payment_status": project.payment_status,
            "payment_updates": _payment_activity(meta),
            "business_summary": _client_business_summary(project, top_level_tasks, meta),
            "plan_brief": report["plan_brief"],
            "usp": report["usp"],
            "feature_highlights": report["feature_highlights"],
            "delivery_status": report["delivery_status"],
            "overall_status": report["overall_status"],
            "today_status": report["today_status"],
            "final_report": meta.get("final_report") or report,
            "next_update": meta.get("client_response_status"),
            "viewer_guidance": _guidance_for_viewer(meta, user),
        }
        if project.status == "completed":
            history.append(payload)
        else:
            overview.append(payload)

    return {
        "client": {
            "client_id": client_profile.id,
            "company_name": client_profile.company_name,
            "contact_person": client_profile.contact_person,
            "full_name": client_profile.user.full_name if client_profile.user else client_profile.contact_person,
            "email": client_profile.user.email if client_profile.user else None,
            "role": "client",
        },
        "notifications": [notification for project in projects for notification in _recent_project_notifications(_project_meta(project), limit=3)][:8],
        "projects": overview,
        "history": history,
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
    child_tasks = db.query(Task).filter(Task.parent_task_id == task.id).all()
    total = len(checkpoints) or 1
    done = len([item for item in checkpoints if item.id == checkpoint.id and completed] + [item for item in checkpoints if item.id != checkpoint.id and item.status == "completed"])
    completion_percentage = round((done / total) * 100, 1)

    progress = _ensure_task_progress(db, task)
    if child_tasks:
        completion_percentage = progress.completion_percentage or 0.0
        progress.status_notes = f"{done} of {total} internal checkpoints completed"
        db.add(progress)
    else:
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

        if assignment:
            if completion_percentage >= 100:
                if assignment.status != "completed":
                    # Release the load this task held on the employee
                    emp = db.query(EmployeeProfile).filter(EmployeeProfile.id == assignment.employee_id).first()
                    if emp:
                        hours = float(assignment.estimated_hours or task.estimated_time or 0.0)
                        emp.current_load = max(0.0, round((emp.current_load or 0.0) - hours, 1))
                        _sync_employee_capacity_state(emp)
                        db.add(emp)
                assignment.status = "completed"
                assignment.completed_at = assignment.completed_at or _utcnow()
                assignment.actual_hours = assignment.actual_hours or assignment.estimated_hours or task.estimated_time or 0.0
                _award_task_completion_points(db, task, assignment)
            elif completion_percentage > 0:
                assignment.status = "in-progress"
                assignment.started_at = assignment.started_at or _utcnow()
            else:
                assignment.status = "assigned"
            db.add(assignment)

    _sync_project_progress(db, task.project_id)
    project = db.query(Project).filter(Project.id == task.project_id).first()
    if project:
        meta = _project_meta(project)
        actor_label = user.full_name or user.email
        _append_notification(
            meta,
            kind="progress",
            title="Checkpoint updated",
            message=f"{actor_label} marked '{checkpoint.title}' as {'completed' if completed else 'pending'}. Project progress is now {project.progress}%.",
            actor=actor_label,
        )
        project.custom_fields = meta
        db.add(project)
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
        # Free employee workloads before soft-deleting
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
            _sync_employee_capacity_state(employee)
            db.add(employee)

        # Soft-delete tasks and project (preserves audit trail)
        now = datetime.utcnow()
        if task_ids:
            db.query(Task).filter(Task.id.in_(task_ids)).update(
                {"deleted_at": now}, synchronize_session=False
            )
        project.deleted_at = now
        db.add(project)
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


def _release_completed_project_capacity(db: Session, project: Project) -> None:
    assignments = (
        db.query(TaskAssignment)
        .join(Task, Task.id == TaskAssignment.task_id)
        .filter(Task.project_id == project.id)
        .all()
    )
    employee_loads: Dict[int, float] = {}
    for assignment in assignments:
        employee_loads.setdefault(assignment.employee_id, 0.0)
        employee_loads[assignment.employee_id] += float(assignment.estimated_hours or assignment.actual_hours or 0.0)
        assignment.status = "completed"
        assignment.completed_at = assignment.completed_at or _utcnow()
        db.add(assignment)

    employees = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.id.in_(employee_loads.keys()) if employee_loads else False)
        .all()
    )
    for employee in employees:
        employee.current_load = max(0.0, round((employee.current_load or 0.0) - employee_loads.get(employee.id, 0.0), 1))
        _sync_employee_capacity_state(employee)
        db.add(employee)


def _finalize_completed_project(db: Session, project: Project) -> None:
    if project.status == "completed" and project.completed_at and (_project_meta(project).get("final_report") is not None):
        return

    _release_completed_project_capacity(db, project)
    meta = _project_meta(project)
    report = _build_project_report(db, project)
    meta["report_text"] = report["full_text"]
    meta["final_report"] = report
    meta["current_phase"] = "history"
    meta["client_status"] = "delivered"
    meta["client_response_status"] = "final-report-ready"
    meta["next_decision"] = "Await final payment confirmation and retain project in history"
    _append_notification(
        meta,
        kind="project",
        title="Project completed",
        message="Delivery is complete, resources were released, and the final report is now available in history.",
    )
    project.status = "completed"
    project.completed_at = project.completed_at or _utcnow()
    project.custom_fields = meta
    db.add(project)


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

    tasks = db.query(Task).filter(Task.project_id == project_id, Task.parent_task_id.is_(None), Task.deleted_at.is_(None)).all()
    if not tasks:
        project.progress = 0
        db.add(project)
        return

    for task in tasks:
        child_tasks = db.query(Task).filter(Task.parent_task_id == task.id, Task.deleted_at.is_(None)).all()
        if child_tasks:
            completed_children = len([child for child in child_tasks if child.status == "done"])
            progress = _ensure_task_progress(db, task)
            progress.completion_percentage = round((completed_children / len(child_tasks)) * 100, 1)
            progress.estimated_hours_remaining = max((task.estimated_time or 0) * (1 - progress.completion_percentage / 100), 0)
            progress.status_notes = f"{completed_children} of {len(child_tasks)} subtasks completed"
            db.add(progress)
            if completed_children == len(child_tasks):
                task.status = "done"
            elif completed_children > 0:
                task.status = "running"
            else:
                task.status = "pending"
            db.add(task)

    completed_tasks = len([task for task in tasks if task.status == "done"])
    project.progress = round((completed_tasks / len(tasks)) * 100)

    if project.progress >= 100:
        _finalize_completed_project(db, project)
    elif project.progress > 0 and project.status != "on-hold":
        project.status = "in-progress"
        project.completed_at = None
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
