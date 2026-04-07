# app/services/_task_service.py
from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional

from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._user import User
from app.schemas._task import TaskCreate, TaskStatus


def create_task(db: Session, task_in: TaskCreate, actor: User) -> Task:
    project = db.query(Project).filter(Project.id == task_in.project_id, Project.tenant_id == actor.tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    task = Task(**task_in.model_dump(), tenant_id=actor.tenant_id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def assign_agent(db: Session, task_id: int, agent_id: int, actor: User) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.tenant_id == actor.tenant_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.agent_id = agent_id
    db.commit()
    db.refresh(task)
    return task


def update_status(db: Session, task_id: int, status: TaskStatus, actor: User) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.tenant_id == actor.tenant_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if actor.role == "employee":
        employee_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == actor.id).first()
        assignment = (
            db.query(TaskAssignment)
            .filter(TaskAssignment.task_id == task.id, TaskAssignment.employee_id == (employee_profile.id if employee_profile else -1))
            .first()
        )
        if not assignment:
            raise HTTPException(status_code=403, detail="Employees can only update assigned tasks")

    task.status = status.value  # store the string in DB
    db.commit()
    db.refresh(task)
    return task


def get_tasks(db: Session, actor: User, project_id: Optional[int] = None, agent_id: Optional[int] = None) -> List[Task]:
    query = db.query(Task).filter(Task.tenant_id == actor.tenant_id)
    if project_id:
        query = query.filter(Task.project_id == project_id)
    if agent_id:
        query = query.filter(Task.agent_id == agent_id)

    if actor.role == "employee":
        employee_profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == actor.id).first()
        assigned_ids = (
            db.query(TaskAssignment.task_id)
            .filter(TaskAssignment.employee_id == (employee_profile.id if employee_profile else -1))
            .all()
        )
        query = query.filter(Task.id.in_([task_id for (task_id,) in assigned_ids]) if assigned_ids else False)

    return query.all()
