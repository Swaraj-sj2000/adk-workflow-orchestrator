# app/services/_task_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional

from app.models._task import Task
from app.schemas._task import TaskCreate, TaskStatus


def create_task(db: Session, task_in: TaskCreate) -> Task:
    task = Task(**task_in.model_dump())  # Pydantic v2: model_dump instead of dict
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def assign_agent(db: Session, task_id: int, agent_id: int) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.agent_id = agent_id
    db.commit()
    db.refresh(task)
    return task


def update_status(db: Session, task_id: int, status: TaskStatus) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.status = status.value  # store the string in DB
    db.commit()
    db.refresh(task)
    return task


def get_tasks(db: Session, project_id: Optional[int] = None, agent_id: Optional[int] = None) -> List[Task]:
    query = db.query(Task)
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if agent_id:
        query = query.filter(Task.agent_id == agent_id)
    return query.all()