# backend/app/api/routes/_task.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas._task import TaskCreate, TaskRead, TaskUpdateStatus
from app.services._task_service import create_task, assign_agent, update_status, get_tasks
from app.core._deps import get_db, get_current_user

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.post("/", response_model=TaskRead)
def route_create_task(task: TaskCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return create_task(db, task)

@router.get("/", response_model=list[TaskRead])
def route_get_tasks(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return get_tasks(db)

@router.patch("/{task_id}/status", response_model=TaskRead)
def route_update_status(task_id: int, status_update: TaskUpdateStatus, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    task = update_status(db, task_id, status_update.status)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/{task_id}/assign/{agent_id}", response_model=TaskRead)
def route_assign_agent(task_id: int, agent_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    task = assign_agent(db, task_id, agent_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task