# app/api/routes/_task_assignment.py
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core._deps import get_db, get_current_user
from app.models._task_assignment import TaskAssignment
from app.models._user import User
from app.schemas._task_assignment import TaskAssignmentRead

router = APIRouter(prefix="/task-assignments", tags=["Task Assignments"])


@router.get("", response_model=List[TaskAssignmentRead])
def list_task_assignments(
    task_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(TaskAssignment)
    if task_id is not None:
        query = query.filter(TaskAssignment.task_id == task_id)
    if employee_id is not None:
        query = query.filter(TaskAssignment.employee_id == employee_id)
    return query.order_by(TaskAssignment.assigned_at.desc()).all()
