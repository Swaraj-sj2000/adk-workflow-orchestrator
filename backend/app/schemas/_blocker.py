# app/schemas/_blocker.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class BlockerCreate(BaseModel):
    task_id: int
    blocker_type: str
    severity: str = "medium"
    description: str


class BlockerUpdate(BaseModel):
    status: Optional[str] = None
    resolution_notes: Optional[str] = None


class BlockerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: int
    blocker_type: str
    severity: str
    description: str
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
