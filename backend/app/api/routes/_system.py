# app/api/routes/_system.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core._deps import get_db, get_current_user
from app.models._task import Task
from app.models._user import User
from app.services._assignment_engine import AssignmentEngine
from app.services._monitoring_service import MonitoringService
from app.services._decision_service import DecisionService
from app.schemas._decision_log import DecisionLogRead
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
