# app/api/routes/_system.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core._deps import get_db, get_current_user
from app.models._task import Task
from app.models._user import User
from app.services._assignment_engine import AssignmentEngine
from app.services._monitoring_service import MonitoringService
from app.services._decision_service import DecisionService
from app.services._event_service import EventService
from app.services._project_service import (
    build_admin_dashboard,
    build_agentic_dashboard,
    build_llm_status,
    build_project_status,
    build_team_dashboard,
)
from app.schemas._decision_log import DecisionLogRead
from app.schemas._event_queue import EventQueueRead
from typing import List

router = APIRouter(prefix="/system", tags=["System"])


@router.post("/assign-task/{task_id}")
def route_assign_task(
    task_id: int,
    override: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger automatic assignment for a task.
    Only admins can override confidence thresholds.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign tasks")
    
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    engine = AssignmentEngine(db)
    assignment, confidence, reasoning = engine.assign_task(task, override=override)
    
    if not assignment:
        raise HTTPException(
            status_code=400,
            detail=f"Could not assign task: {reasoning}"
        )
    
    return {
        "success": True,
        "assignment_id": assignment.id,
        "employee_id": assignment.employee_id,
        "confidence": confidence,
        "reasoning": reasoning
    }


@router.post("/rebalance/{project_id}")
def route_rebalance_workload(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger workload rebalancing for a project.
    Suggests and optionally applies reassignments.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can rebalance")
    
    engine = AssignmentEngine(db)
    suggestions = engine.suggest_reassignments(project_id)
    
    decision_service = DecisionService(db)
    decision_service.log_decision(
        decision_type="rebalance",
        entity_type="project",
        entity_id=project_id,
        input_data={"suggestion_count": len(suggestions)},
        decision_taken=f"Generated {len(suggestions)} reassignment suggestions",
        confidence=0.95,
        reasoning="Workload rebalancing triggered by admin"
    )
    
    return {
        "project_id": project_id,
        "suggestion_count": len(suggestions),
        "suggestions": suggestions
    }


@router.get("/health/{project_id}")
def route_project_health(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get project health status and risk assessment."""
    monitor = MonitoringService(db)
    health = monitor.check_project_health(project_id)
    
    return health


@router.get("/admin-dashboard")
def route_admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view the admin dashboard")

    return build_admin_dashboard(db)


@router.get("/team-dashboard")
def route_team_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view the team dashboard")

    return build_team_dashboard(db)


@router.get("/agentic-dashboard")
def route_agentic_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view the agentic dashboard")

    return build_agentic_dashboard(db)


@router.get("/project-status/{project_id}")
def route_project_status(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return build_project_status(db, project_id, viewer=current_user)


@router.get("/llm-status")
def route_llm_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view LLM status")
    return build_llm_status()


@router.get("/suggestions/{project_id}")
def route_get_suggestions(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get AI suggestions for project optimization.
    - task reassignments
    - resource rebalancing
    - escalation points
    """
    monitor = MonitoringService(db)
    risk_summary = monitor.get_risk_summary(project_id)
    
    engine = AssignmentEngine(db)
    reassignments = engine.suggest_reassignments(project_id)
    
    return {
        "project_id": project_id,
        "risk_summary": risk_summary,
        "reassignment_suggestions": reassignments,
        "requires_admin_attention": risk_summary["needs_intervention"]
    }


@router.get("/queue/status")
def route_queue_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view queue status")

    service = EventService(db)
    return service.get_queue_status()


@router.get("/queue/failed", response_model=List[EventQueueRead])
def route_failed_events(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view failed events")

    service = EventService(db)
    return service.get_failed_events(limit=limit)
