# app/api/routes/_task_progress.py
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core._deps import get_db, get_current_user
from app.models._user import User
from app.models._task_progress import TaskProgress
from app.schemas._task_progress import TaskProgressRead, TaskProgressUpdate

router = APIRouter(prefix="/task-progress", tags=["Task Progress"])


@router.get("", response_model=Optional[TaskProgressRead])
def get_task_progress(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    progress = db.query(TaskProgress).filter(TaskProgress.task_id == task_id).first()
    return progress


@router.patch("/{task_id}", response_model=TaskProgressRead)
def update_task_progress(
    task_id: int,
    payload: TaskProgressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
    return progress
