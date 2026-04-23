# backend/app/api/routes/_task.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.schemas._task import TaskCreate, TaskRead, TaskUpdateStatus
from app.services._task_service import create_task, assign_agent, update_status, get_tasks
from app.core._deps import get_db, get_current_user
from app.models._task import Task

router = APIRouter(prefix="/tasks", tags=["Tasks"])

@router.post("/", response_model=TaskRead)
def route_create_task(task: TaskCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create tasks")
    return create_task(db, task, current_user)

@router.get("/")
def route_get_tasks(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    tasks = get_tasks(db, current_user)
    items = tasks[skip : skip + limit]
    return {
        "items": items,
        "total": len(tasks),
        "skip": skip,
        "limit": limit,
    }

@router.get("/{task_id}", response_model=TaskRead)
def route_get_task(task_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    task = db.query(Task).filter(Task.id == task_id, Task.tenant_id == current_user.tenant_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.patch("/{task_id}/status", response_model=TaskRead)
def route_update_status(task_id: int, status_update: TaskUpdateStatus, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    task = update_status(db, task_id, status_update.status, current_user)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/{task_id}/assign/{agent_id}", response_model=TaskRead)
def route_assign_agent(task_id: int, agent_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign agents")
    task = assign_agent(db, task_id, agent_id, current_user)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
