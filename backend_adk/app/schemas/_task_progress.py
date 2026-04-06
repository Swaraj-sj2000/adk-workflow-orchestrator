# app/schemas/_task_progress.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class TaskProgressUpdate(BaseModel):
    completion_percentage: Optional[float] = None
    actual_hours_spent: Optional[float] = None
    estimated_hours_remaining: Optional[float] = None
    status_notes: Optional[str] = None
    is_on_track: Optional[int] = None


class TaskProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    completion_percentage: float
    last_updated_at: datetime
    actual_hours_spent: float
    estimated_hours_remaining: Optional[float]
    status_notes: Optional[str]
    is_on_track: int
