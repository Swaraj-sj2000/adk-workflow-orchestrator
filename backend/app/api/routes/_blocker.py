# app/api/routes/_blocker.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core._deps import get_db, get_current_user
from app.models._user import User
from app.models._blocker import Blocker
from app.models._employee_profile import EmployeeProfile
from app.models._meeting import Meeting
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._project import Project
from app.schemas._blocker import BlockerCreate, BlockerUpdate, BlockerRead
from app.services._event_service import EventService, process_event_queue_batch_async
from app.services._llm_service import LLMService
from typing import List
from datetime import datetime

router = APIRouter(prefix="/blockers", tags=["Blockers"])


@router.post("/", response_model=BlockerRead)
def route_create_blocker(
    blocker: BlockerCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a blocker for a task."""
    task = db.query(Task).filter(Task.id == blocker.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if current_user.role == "employee":
        employee_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()
        if not employee_profile:
            raise HTTPException(status_code=403, detail="Employee profile not found")
        assignment = (
            db.query(TaskAssignment)
            .filter(TaskAssignment.task_id == task.id, TaskAssignment.employee_id == employee_profile.id)
            .first()
        )
        if not assignment:
            raise HTTPException(status_code=403, detail="You can only raise concerns for your assigned tasks")
    
    new_blocker = Blocker(
        task_id=blocker.task_id,
        blocker_type=blocker.blocker_type,
        severity=blocker.severity,
        description=blocker.description,
        status="open",
        raised_by_user_id=current_user.id,
    )

    llm_service = LLMService()
    concern_response = llm_service.generate_concern_response(
        {
            "project_id": task.project_id,
            "task_id": task.id,
            "task_name": task.description,
            "severity": blocker.severity,
            "blocker_type": blocker.blocker_type,
            "description": blocker.description,
            "raised_by": current_user.full_name or current_user.email,
        }
    )
    new_blocker.ai_response = concern_response["response"]
    new_blocker.next_action = concern_response["action"]
    new_blocker.escalation_recommended = 1 if concern_response["escalate"] else 0
    
    db.add(new_blocker)
    db.commit()
    db.refresh(new_blocker)
    
    # Update task status if critical
    if blocker.severity == "critical":
        task.status = "blocked"
        db.merge(task)
        db.commit()

    if concern_response["meeting"]:
        project = db.query(Project).filter(Project.id == task.project_id).first()
        meeting = Meeting(
            project_id=task.project_id,
            created_by=project.admin_id if project else current_user.id,
            title=f"Concern triage for task #{task.id}",
            description=f"AI recommended a sync for blocker #{new_blocker.id}. {new_blocker.next_action}",
            meeting_type="review",
            scheduled_at=datetime.utcnow(),
            attendees=[project.admin_id, current_user.id] if project else [current_user.id],
            decisions_made=[
                {
                    "decision": "Review concern and decide whether admin escalation is needed",
                    "owner": project.admin_id if project else current_user.id,
                }
            ],
        )
        db.add(meeting)
        db.commit()

    event_service = EventService(db)
    event_service.publish_event(
        event_type="PROJECT_EXECUTION_SIGNAL",
        entity_type="project",
        entity_id=task.project_id,
        payload={
            "triggered_by": current_user.id,
            "source": "blocker_created",
            "task_id": task.id,
            "blocker_id": new_blocker.id,
            "persist_followup_messages": True,
        },
    )
    background_tasks.add_task(process_event_queue_batch_async, 1)
    
    return new_blocker


@router.get("/task/{task_id}", response_model=List[BlockerRead])
def route_get_task_blockers(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all blockers for a task."""
    blockers = db.query(Blocker).filter(
        Blocker.task_id == task_id,
        Blocker.status != "resolved"
    ).all()
    return blockers


@router.patch("/{blocker_id}", response_model=BlockerRead)
def route_update_blocker(
    blocker_id: int,
    blocker_update: BlockerUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update blocker status."""
    blocker = db.query(Blocker).filter(Blocker.id == blocker_id).first()
    if not blocker:
        raise HTTPException(status_code=404, detail="Blocker not found")
    
    if blocker_update.status:
        blocker.status = blocker_update.status
        
        if blocker_update.status == "resolved":
            blocker.resolved_at = datetime.utcnow()
    
    if blocker_update.resolution_notes:
        blocker.resolution_notes = blocker_update.resolution_notes
    
    db.merge(blocker)
    db.commit()
    db.refresh(blocker)

    task = db.query(Task).filter(Task.id == blocker.task_id).first()
    if task:
        event_service = EventService(db)
        event_service.publish_event(
            event_type="PROJECT_EXECUTION_SIGNAL",
            entity_type="project",
            entity_id=task.project_id,
            payload={
                "triggered_by": current_user.id,
                "source": "blocker_updated",
                "task_id": task.id,
                "blocker_id": blocker.id,
                "persist_followup_messages": True,
            },
        )
        background_tasks.add_task(process_event_queue_batch_async, 1)
    
    return blocker


@router.get("/{blocker_id}", response_model=BlockerRead)
def route_get_blocker(
    blocker_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get blocker details."""
    blocker = db.query(Blocker).filter(Blocker.id == blocker_id).first()
    if not blocker:
        raise HTTPException(status_code=404, detail="Blocker not found")
    return blocker


@router.delete("/{blocker_id}")
def route_delete_blocker(
    blocker_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a blocker (set as resolved)."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete blockers")
    
    blocker = db.query(Blocker).filter(Blocker.id == blocker_id).first()
    if not blocker:
        raise HTTPException(status_code=404, detail="Blocker not found")
    
    blocker.status = "resolved"
    blocker.resolved_at = datetime.utcnow()
    db.merge(blocker)
    db.commit()

    task = db.query(Task).filter(Task.id == blocker.task_id).first()
    if task:
        event_service = EventService(db)
        event_service.publish_event(
            event_type="PROJECT_EXECUTION_SIGNAL",
            entity_type="project",
            entity_id=task.project_id,
            payload={
                "triggered_by": current_user.id,
                "source": "blocker_deleted",
                "task_id": task.id,
                "blocker_id": blocker.id,
                "persist_followup_messages": True,
            },
        )
        background_tasks.add_task(process_event_queue_batch_async, 1)
    
    return {"success": True, "blocker_id": blocker_id}
