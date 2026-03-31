# app/schemas/_meeting.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime


class MeetingCreate(BaseModel):
    project_id: int
    title: str
    description: Optional[str] = None
    meeting_type: str = "status"
    scheduled_at: Optional[datetime] = None
    attendees: List[int] = []


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    decisions_made: Optional[List[Dict[str, Any]]] = None


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    created_by: int
    title: str
    description: Optional[str]
    meeting_type: str
    scheduled_at: Optional[datetime]
    completed_at: Optional[datetime]
    attendees: List[int]
    decisions_made: Optional[List[Dict[str, Any]]]
    created_at: datetime
