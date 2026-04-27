# app/services/_task_service.py
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import List, Optional

from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._task_progress import TaskProgress
from app.models._user import User
from app.schemas._task import TaskCreate, TaskStatus
from app.services._skill_service import update_skill_confidence


def _ensure_progress(db: Session, task: Task) -> TaskProgress:
    progress = db.query(TaskProgress).filter(TaskProgress.task_id == task.id).first()
    if progress:
        return progress
    progress = TaskProgress(
        task_id=task.id,
        completion_percentage=100.0 if task.status == "done" else 0.0,
        estimated_hours_remaining=0.0 if task.status == "done" else task.estimated_time,
        status_notes="Completed" if task.status == "done" else "Not started",
        is_on_track=1,
    )
    db.add(progress)
    db.flush()
    return progress


def _is_employee_authorized_for_task(db: Session, task: Task, actor: User) -> bool:
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == actor.id).first()
    if not profile:
        return False
    direct_assignment = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.task_id == task.id, TaskAssignment.employee_id == profile.id)
        .first()
    )
    if direct_assignment:
        return True
    if task.parent_task_id is None:
        return False
    parent_assignment = (
        db.query(TaskAssignment)
        .filter(TaskAssignment.task_id == task.parent_task_id, TaskAssignment.employee_id == profile.id)
        .first()
    )
    return bool(parent_assignment)


def _sync_parent_task_from_children(db: Session, task: Task) -> None:
    if task.parent_task_id is None:
        return
    parent = db.query(Task).filter(Task.id == task.parent_task_id).first()
    if not parent:
        return
    children = db.query(Task).filter(Task.parent_task_id == parent.id).all()
    if not children:
        return

    completed = len([child for child in children if child.status == "done"])
    parent_progress = _ensure_progress(db, parent)
    parent_progress.completion_percentage = round((completed / len(children)) * 100, 1)
    parent_progress.estimated_hours_remaining = max((parent.estimated_time or 0) * (1 - parent_progress.completion_percentage / 100), 0)
    parent_progress.status_notes = f"{completed} of {len(children)} subtasks completed"
    db.add(parent_progress)

    if completed == len(children):
        parent.status = "done"
    elif completed > 0:
        parent.status = "running"
    else:
        parent.status = "pending"
    db.add(parent)


def _sync_children_from_parent(db: Session, task: Task) -> None:
    children = db.query(Task).filter(Task.parent_task_id == task.id).all()
    if not children:
        return
    completed = task.status == "done"
    for child in children:
        child.status = "done" if completed else "pending"
        progress = _ensure_progress(db, child)
        progress.completion_percentage = 100.0 if completed else 0.0
        progress.estimated_hours_remaining = 0.0 if completed else child.estimated_time
        progress.status_notes = "Completed via parent task" if completed else "Reset from parent task"
        db.add(progress)
        db.add(child)


def _sync_project_progress(db: Session, project_id: int) -> None:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return
    top_level_tasks = db.query(Task).filter(Task.project_id == project_id, Task.parent_task_id.is_(None)).all()
    if not top_level_tasks:
        project.progress = 0
        db.add(project)
        return
    done_count = len([task for task in top_level_tasks if task.status == "done"])
    project.progress = round((done_count / len(top_level_tasks)) * 100)
    if project.progress >= 100:
        project.status = "completed"
    elif done_count > 0 and project.status != "on-hold":
        project.status = "in-progress"
    db.add(project)


def _sync_assignment_status(db: Session, task: Task) -> None:
    assignment_task_id = task.parent_task_id if task.parent_task_id is not None else task.id
    assignments = db.query(TaskAssignment).filter(TaskAssignment.task_id == assignment_task_id).all()
    for assignment in assignments:
        if task.status == "done":
            if assignment.status != "completed":
                # Release the load this task held on the employee
                employee = db.query(EmployeeProfile).filter(EmployeeProfile.id == assignment.employee_id).first()
                if employee:
                    hours = float(assignment.estimated_hours or task.estimated_time or 0.0)
                    employee.current_load = max(0.0, round((employee.current_load or 0.0) - hours, 1))
                    employee.availability_status = "busy" if employee.current_load > 0 else "available"
                    db.add(employee)
                # Update demonstrated skills based on completed task
                update_skill_confidence(db, task)
            assignment.status = "completed"
            assignment.completed_at = assignment.completed_at or datetime.now(timezone.utc)
        elif task.status in {"running", "blocked", "delayed"}:
            assignment.status = "in-progress"
            assignment.started_at = assignment.started_at or datetime.now(timezone.utc)
        else:
            assignment.status = "assigned"
            assignment.completed_at = None
        db.add(assignment)


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

    if actor.role == "employee" and not _is_employee_authorized_for_task(db, task, actor):
        raise HTTPException(status_code=403, detail="Employees can only update assigned tasks")

    task.status = status.value  # store the string in DB
    progress = _ensure_progress(db, task)
    progress.completion_percentage = 100.0 if status.value == "done" else 0.0
    progress.estimated_hours_remaining = 0.0 if status.value == "done" else task.estimated_time
    progress.status_notes = "Completed manually" if status.value == "done" else "Reset manually"
    db.add(progress)
    db.add(task)
    if task.parent_task_id is None:
        _sync_children_from_parent(db, task)
        _sync_assignment_status(db, task)
    else:
        _sync_parent_task_from_children(db, task)
        parent = db.query(Task).filter(Task.id == task.parent_task_id).first()
        if parent:
            _sync_assignment_status(db, parent)
    _sync_project_progress(db, task.project_id)
    db.commit()
    db.refresh(task)
    return task


def get_tasks(db: Session, actor: User, project_id: Optional[int] = None, agent_id: Optional[int] = None) -> List[Task]:
    query = db.query(Task).filter(Task.tenant_id == actor.tenant_id, Task.deleted_at.is_(None))
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
