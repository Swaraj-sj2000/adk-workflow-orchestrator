# app/schemas/_task_progress.py
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime


class TaskProgressUpdate(BaseModel):
    completion_percentage: Optional[float] = Field(default=None, ge=0, le=100)
    actual_hours_spent: Optional[float] = Field(default=None, ge=0)
    estimated_hours_remaining: Optional[float] = Field(default=None, ge=0)
    status_notes: Optional[str] = None
    is_on_track: Optional[int] = Field(default=None, ge=0, le=1)


class ProofOfWorkSubmit(BaseModel):
    proof_note: Optional[str] = None
    proof_url: Optional[str] = None


class TaskProgressRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    completion_percentage: float
    last_updated_at: datetime
    actual_hours_spent: float
    estimated_hours_remaining: Optional[float]
    status_notes: Optional[str]
    proof_note: Optional[str]
    proof_url: Optional[str]
    is_on_track: int
