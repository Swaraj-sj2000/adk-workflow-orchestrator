# app/schemas/_task_assignment.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class TaskAssignmentCreate(BaseModel):
    task_id: int
    employee_id: int
    estimated_hours: Optional[float] = None


class TaskAssignmentUpdate(BaseModel):
    status: Optional[str] = None
    actual_hours: Optional[float] = None
    notes: Optional[str] = None


class TaskAssignmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    employee_id: int
    assigned_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    status: str
    estimated_hours: Optional[float]
    actual_hours: Optional[float]
    assignment_confidence: Optional[float]
    notes: Optional[str]
