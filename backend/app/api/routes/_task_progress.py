# app/api/routes/_task_progress.py
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core._deps import get_db, get_current_user
from app.models._user import User
from app.models._task import Task
from app.models._employee_profile import EmployeeProfile
from app.models._task_assignment import TaskAssignment
from app.models._task_progress import TaskProgress
from app.schemas._task_progress import TaskProgressRead, TaskProgressUpdate
from app.services._event_service import EventService, process_event_queue_batch_async

router = APIRouter(prefix="/task-progress", tags=["Task Progress"])


@router.get("", response_model=Optional[TaskProgressRead])
def get_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.tenant_id == current_user.tenant_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if current_user.role == "employee":
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()
        assignment = db.query(TaskAssignment).filter(TaskAssignment.task_id == task_id, TaskAssignment.employee_id == (profile.id if profile else -1)).first()
        if not assignment:
            raise HTTPException(status_code=403, detail="Not authorized to view this task progress")
    progress = db.query(TaskProgress).filter(TaskProgress.task_id == task_id).first()
    return progress


@router.patch("/{task_id}", response_model=TaskProgressRead)
def update_task_progress(
    task_id: int,
    payload: TaskProgressUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = db.query(Task).filter(Task.id == task_id, Task.tenant_id == current_user.tenant_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if current_user.role == "employee":
        profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()
        assignment = db.query(TaskAssignment).filter(TaskAssignment.task_id == task_id, TaskAssignment.employee_id == (profile.id if profile else -1)).first()
        if not assignment:
            raise HTTPException(status_code=403, detail="Not authorized to update this task progress")

    progress = db.query(TaskProgress).filter(TaskProgress.task_id == task_id).first()
    if not progress:
        progress = TaskProgress(task_id=task_id)
        db.add(progress)
        db.flush()

    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(progress, key, value)

    db.merge(progress)
    db.commit()
    db.refresh(progress)

    event_service = EventService(db)
    event_service.publish_event(
        event_type="PROJECT_EXECUTION_SIGNAL",
        entity_type="project",
        entity_id=task.project_id,
        payload={
            "triggered_by": current_user.id,
            "source": "task_progress_update",
            "task_id": task_id,
            "persist_followup_messages": True,
        },
    )
    background_tasks.add_task(process_event_queue_batch_async, 1)

    return progress
