# app/api/routes/_project.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db._database import get_db
from app.schemas._project import (
    DraftTeamReplacementAction,
    ProjectCreate,
    ProjectInviteResponse,
    ProjectPaymentUpdate,
    ProjectTaskReassignmentAction,
    TaskChangeRequestCreate,
    TaskChangeRequestReview,
    TeamApprovalAction,
)
from app.services._project_service import (
    build_project_status,
    create_task_change_request,
    create_project,
    delete_project_atomic,
    get_clients,
    get_projects,
    handle_team_approval,
    handle_project_invite_response,
    reassign_project_task,
    review_task_change_request,
    replace_draft_team_member,
    update_project_payment_status,
)
from app.core._deps import get_current_user
from app.models._project import Project
from app.core._logging import get_logger

router = APIRouter(prefix="/projects", tags=["Projects"])
logger = get_logger(__name__)


@router.post("/")
def create(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    logger.info(f"Creating project: name={project.name}, user_id={user.id}")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create projects")
    try:
        result = create_project(db, project, admin=user)
        logger.info(f"Project created successfully: project_id={result.id if hasattr(result, 'id') else 'unknown'}")
        return result
    except Exception as e:
        logger.error(f"Failed to create project: {e}", exc_info=True)
        raise


@router.get("/")
def read_all(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    projects = get_projects(db, viewer=user)
    items = projects[skip : skip + limit]
    return {
        "items": items,
        "total": len(projects),
        "skip": skip,
        "limit": limit,
    }


@router.get("/clients")
def read_clients(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view clients")
    return get_clients(db, user)


@router.get("/{project_id}/status")
def read_project_status(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role == "client":
        project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == user.tenant_id).first()
        if project:
            project_meta = dict(project.custom_fields or {})
            if project.payment_status == "disputed" or project_meta.get("payment_hold_active"):
                raise HTTPException(
                    status_code=402,
                    detail="Project access restricted pending payment. Contact your project manager.",
                )
    return build_project_status(db, project_id, viewer=user)


@router.post("/{project_id}/team-approval")
def act_on_team_approval(
    project_id: int,
    payload: TeamApprovalAction,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can confirm project team approval")

    return handle_team_approval(
        db=db,
        project_id=project_id,
        approved=payload.approved,
        note=payload.note,
        actor_id=user.id,
    )


@router.patch("/{project_id}/draft-team")
def replace_draft_team(
    project_id: int,
    payload: DraftTeamReplacementAction,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return replace_draft_team_member(
        db=db,
        project_id=project_id,
        current_employee_id=payload.current_employee_id,
        replacement_employee_id=payload.replacement_employee_id,
        note=payload.note,
        actor=user,
    )


@router.post("/{project_id}/invite-response")
def respond_to_project_invite(
    project_id: int,
    payload: ProjectInviteResponse,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return handle_project_invite_response(
        db=db,
        project_id=project_id,
        accepted=payload.accepted,
        note=payload.note,
        actor=user,
    )


@router.post("/{project_id}/task-change-requests")
def submit_task_change_request(
    project_id: int,
    payload: TaskChangeRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return create_task_change_request(
        db=db,
        project_id=project_id,
        action=payload.action,
        target_type=payload.target_type,
        target_task_id=payload.target_task_id,
        parent_task_id=payload.parent_task_id,
        proposed_title=payload.proposed_title,
        proposed_description=payload.proposed_description,
        note=payload.note,
        actor=user,
    )


@router.patch("/{project_id}/task-change-requests/{request_id}")
def review_project_task_change_request(
    project_id: int,
    request_id: str,
    payload: TaskChangeRequestReview,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return review_task_change_request(
        db=db,
        project_id=project_id,
        request_id=request_id,
        approved=payload.approved,
        note=payload.note,
        actor=user,
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return delete_project_atomic(db, project_id, user)


@router.patch("/{project_id}/payment-status")
def update_payment_status(
    project_id: int,
    payload: ProjectPaymentUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return update_project_payment_status(
        db=db,
        project_id=project_id,
        payment_status=payload.payment_status,
        note=payload.note,
        actor=user,
    )


@router.patch("/{project_id}/tasks/{task_id}/reassign")
def reassign_task(
    project_id: int,
    task_id: int,
    payload: ProjectTaskReassignmentAction,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return reassign_project_task(
        db=db,
        project_id=project_id,
        task_id=task_id,
        replacement_employee_id=payload.replacement_employee_id,
        note=payload.note,
        actor=user,
    )


# ── Change Requests (Feature 4: Client Portal) ────────────────────────────────

from pydantic import BaseModel as _BaseModel
from typing import Optional as _Optional
from app.models._change_request import ChangeRequest as _ChangeRequest


class ChangeRequestCreate(_BaseModel):
    title: str
    description: str


class ChangeRequestResolve(_BaseModel):
    status: str  # approved / rejected / implemented
    agent_analysis: _Optional[str] = None


@router.post("/{project_id}/change-requests")
def submit_change_request(
    project_id: int,
    payload: ChangeRequestCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Client submits a change request; admin/CEO can also raise one."""
    from app.models._project import Project
    project = db.query(Project).filter(
        Project.id == project_id, Project.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if user.role == "client":
        from app.models._client_profile import ClientProfile
        profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
        if not profile or project.client_id != profile.id:
            raise HTTPException(status_code=403, detail="Not your project")

    cr = _ChangeRequest(
        tenant_id=user.tenant_id,
        project_id=project_id,
        requested_by_user_id=user.id,
        title=payload.title,
        description=payload.description,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)
    return {"id": cr.id, "status": cr.status, "message": "Change request submitted"}


@router.get("/{project_id}/change-requests")
def get_change_requests(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Admin/CEO views all change requests; client sees their own."""
    from app.models._project import Project
    project = db.query(Project).filter(
        Project.id == project_id, Project.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(_ChangeRequest).filter(_ChangeRequest.project_id == project_id)
    if user.role == "client":
        query = query.filter(_ChangeRequest.requested_by_user_id == user.id)

    requests = query.order_by(_ChangeRequest.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "status": r.status,
            "agent_analysis": r.agent_analysis,
            "change_order_doc": r.change_order_doc,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "resolved_at": r.resolved_at.isoformat() if r.resolved_at else None,
        }
        for r in requests
    ]


@router.patch("/{project_id}/change-requests/{cr_id}")
def resolve_change_request(
    project_id: int,
    cr_id: int,
    payload: ChangeRequestResolve,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Admin/CEO resolves (approve/reject/implement) a change request."""
    if user.role not in ("admin", "ceo"):
        raise HTTPException(status_code=403, detail="Only admins and CEOs can resolve change requests")

    cr = db.query(_ChangeRequest).filter(
        _ChangeRequest.id == cr_id, _ChangeRequest.project_id == project_id
    ).first()
    if not cr:
        raise HTTPException(status_code=404, detail="Change request not found")

    from datetime import datetime, timezone
    cr.status = payload.status
    if payload.agent_analysis:
        cr.agent_analysis = payload.agent_analysis
    cr.resolved_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": cr.id, "status": cr.status}


# ── Predictive Delivery Forecast (Feature 5) ──────────────────────────────────

@router.get("/{project_id}/delivery-forecast")
def delivery_forecast(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Returns a data-driven delivery risk forecast for a project.
    Computes velocity from completed tasks, estimates ETA, and flags risk.
    Available to admin and CEO only.
    """
    if user.role not in ("admin", "ceo"):
        raise HTTPException(status_code=403, detail="Only admins and CEOs can view forecasts")

    from app.models._project import Project
    from app.models._task import Task
    from app.models._task_progress import TaskProgress
    from datetime import datetime, timezone

    project = db.query(Project).filter(
        Project.id == project_id, Project.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    all_tasks = db.query(Task).filter(
        Task.project_id == project_id, Task.parent_task_id.is_(None)
    ).all()
    done_tasks = [t for t in all_tasks if t.status == "done"]
    pending_tasks = [t for t in all_tasks if t.status != "done"]

    total = len(all_tasks)
    done_count = len(done_tasks)
    pending_count = len(pending_tasks)

    # Velocity: how many tasks completed per day since project started
    now = datetime.now(timezone.utc)
    created = project.created_at
    if created and created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    days_elapsed = max(1, (now - created).days) if created else 1
    velocity = round(done_count / days_elapsed, 2)  # tasks/day

    # ETA estimate
    eta_days = round(pending_count / velocity) if velocity > 0 else None
    eta_date = (now.date().isoformat()) if pending_count == 0 else (
        (now + __import__("datetime").timedelta(days=eta_days)).date().isoformat() if eta_days else None
    )

    # Budget burn rate
    budget = float(project.budget or 0)
    spent = float(project.spent or 0)
    burn_pct = round((spent / budget * 100) if budget > 0 else 0, 1)
    progress_pct = project.progress or 0

    # Risk score (0-100)
    risk_score = 0
    risk_reasons = []

    # Budget overrun risk
    if budget > 0 and spent > 0:
        cost_efficiency = progress_pct / burn_pct if burn_pct > 0 else 1.0
        if cost_efficiency < 0.8:
            risk_score += 30
            risk_reasons.append(f"Budget burn ({burn_pct}%) outpacing progress ({progress_pct}%)")

    # Deadline risk
    if project.deadline:
        dl = project.deadline
        if dl.tzinfo is None:
            dl = dl.replace(tzinfo=timezone.utc)
        days_to_deadline = (dl - now).days
        if eta_days and eta_days > days_to_deadline:
            overshoot = eta_days - days_to_deadline
            risk_score += min(40, overshoot * 4)
            risk_reasons.append(f"Estimated completion {eta_days}d out vs {days_to_deadline}d to deadline")
        elif days_to_deadline < 7 and progress_pct < 70:
            risk_score += 25
            risk_reasons.append(f"Only {days_to_deadline} days left, {progress_pct}% complete")

    # Velocity risk
    if velocity < 0.3 and pending_count > 3:
        risk_score += 20
        risk_reasons.append(f"Low velocity ({velocity} tasks/day) with {pending_count} tasks remaining")

    # Stalled tasks
    blocked_count = len([t for t in all_tasks if t.status in ("blocked", "delayed")])
    if blocked_count > 0:
        risk_score += min(20, blocked_count * 5)
        risk_reasons.append(f"{blocked_count} task(s) blocked or delayed")

    risk_score = min(100, risk_score)
    risk_level = "critical" if risk_score >= 70 else "high" if risk_score >= 45 else "medium" if risk_score >= 20 else "low"

    forecast = {
        "project_id": project_id,
        "project_name": project.name,
        "total_tasks": total,
        "done_tasks": done_count,
        "pending_tasks": pending_count,
        "progress_pct": progress_pct,
        "velocity_tasks_per_day": velocity,
        "days_elapsed": days_elapsed,
        "estimated_days_remaining": eta_days,
        "estimated_completion_date": eta_date,
        "budget_total": budget,
        "budget_spent": spent,
        "budget_burn_pct": burn_pct,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "risk_reasons": risk_reasons,
        "blocked_tasks": blocked_count,
    }

    # Optionally enrich with LLM narrative
    try:
        from app.services._llm_service import LLMService
        llm = LLMService()
        if llm.enabled:
            prompt = (
                f"You are a delivery risk analyst. Given this project forecast data, write a 2-3 sentence "
                f"plain-English summary of delivery risk and the top recommended action:\n{forecast}"
            )
            narrative = llm.answer_user_question(
                message=prompt, role="admin", user_name="system",
                live_context="", platform_overview=""
            )
            if narrative:
                forecast["narrative"] = narrative
    except Exception:
        pass

    return forecast


# ── Scope Change Handler (Feature 6) ──────────────────────────────────────────

class ScopeChangeRequest(_BaseModel):
    new_brief: str
    reason: str = ""


@router.post("/{project_id}/scope-change")
def handle_scope_change(
    project_id: int,
    payload: ScopeChangeRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Admin submits an updated project brief.
    The agent analyses the diff vs existing tasks and generates a change order.
    """
    if user.role not in ("admin", "ceo"):
        raise HTTPException(status_code=403, detail="Only admins and CEOs can request scope changes")

    from app.models._project import Project
    from app.models._task import Task
    import json as _json

    project = db.query(Project).filter(
        Project.id == project_id, Project.tenant_id == user.tenant_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    existing_tasks = db.query(Task).filter(
        Task.project_id == project_id, Task.parent_task_id.is_(None)
    ).all()
    task_list = [{"id": t.id, "description": t.description, "status": t.status} for t in existing_tasks]

    change_order = None
    new_tasks_suggested = []

    try:
        from app.services._llm_service import LLMService
        llm = LLMService()
        if llm.enabled:
            analysis_prompt = f"""You are a project management AI. A scope change has been submitted.

Project: {project.name}
Original tasks: {_json.dumps(task_list, indent=2)}
New brief: {payload.new_brief}
Reason: {payload.reason}

Respond with a JSON object:
{{
  "change_order": "plain English change order document summarising what changes, what stays, what is new",
  "new_tasks": [{{"description": "...", "required_skills": {{}}, "estimated_hours": 0}}],
  "deprecated_task_ids": [],
  "risk_note": "any delivery risk from this change"
}}"""
            raw = llm.answer_user_question(
                message=analysis_prompt, role="admin", user_name="system",
                live_context="", platform_overview=""
            )
            if raw:
                import re as _re
                json_match = _re.search(r'\{.*\}', raw, _re.DOTALL)
                if json_match:
                    parsed = _json.loads(json_match.group())
                    change_order = parsed.get("change_order", "")
                    new_tasks_suggested = parsed.get("new_tasks", [])
    except Exception:
        pass

    if not change_order:
        change_order = (
            f"Scope change requested for '{project.name}'.\n"
            f"New brief: {payload.new_brief}\n"
            f"Reason: {payload.reason}\n"
            f"Existing tasks: {len(task_list)} (review each for continued relevance).\n"
            "Action required: admin to review and create/deprecate tasks as needed."
        )

    # Save as a change request with the agent's analysis
    cr = _ChangeRequest(
        tenant_id=user.tenant_id,
        project_id=project_id,
        requested_by_user_id=user.id,
        title=f"Scope Change: {payload.new_brief[:60]}",
        description=payload.new_brief,
        status="pending",
        agent_analysis=f"Reason: {payload.reason}",
        change_order_doc=change_order,
    )
    db.add(cr)
    db.commit()
    db.refresh(cr)

    return {
        "change_request_id": cr.id,
        "change_order": change_order,
        "suggested_new_tasks": new_tasks_suggested,
        "message": "Scope change analysed and logged. Review suggested tasks before applying.",
    }
