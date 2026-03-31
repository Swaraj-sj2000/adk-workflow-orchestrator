# app/api/routes/_blocker.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core._deps import get_db, get_current_user
from app.models._user import User
from app.models._blocker import Blocker
from app.models._task import Task
from app.schemas._blocker import BlockerCreate, BlockerUpdate, BlockerRead
from typing import List
from datetime import datetime

router = APIRouter(prefix="/blockers", tags=["Blockers"])


@router.post("/", response_model=BlockerRead)
def route_create_blocker(
    blocker: BlockerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a blocker for a task."""
    task = db.query(Task).filter(Task.id == blocker.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    new_blocker = Blocker(
        task_id=blocker.task_id,
        blocker_type=blocker.blocker_type,
        severity=blocker.severity,
        description=blocker.description,
        status="open"
    )
    
    db.add(new_blocker)
    db.commit()
    db.refresh(new_blocker)
    
    # Update task status if critical
    if blocker.severity == "critical":
        task.status = "blocked"
        db.merge(task)
        db.commit()
    
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
    
    return {"success": True, "blocker_id": blocker_id}
