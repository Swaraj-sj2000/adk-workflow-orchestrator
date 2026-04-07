# app/schemas/_blocker.py
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional
from datetime import datetime


class BlockerCreate(BaseModel):
    task_id: int
    blocker_type: str = Field(min_length=3, max_length=40)
    severity: str = "medium"
    description: str = Field(min_length=5, max_length=1000)

    @field_validator("blocker_type", "severity")
    @classmethod
    def normalize_small_fields(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


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
    raised_by_user_id: Optional[int]
    ai_response: Optional[str]
    next_action: Optional[str]
    escalation_recommended: int
    created_at: datetime
    resolved_at: Optional[datetime]
    resolution_notes: Optional[str]
