# app/schemas/_event_queue.py
from pydantic import BaseModel, ConfigDict
from typing import Dict, Any, Optional
from datetime import datetime


class EventQueueCreate(BaseModel):
    event_type: str
    entity_type: str
    entity_id: int
    payload: Dict[str, Any]


class EventQueueRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    event_type: str
    entity_type: str
    entity_id: int
    payload: Dict[str, Any]
    status: str
    retry_count: int
    created_at: datetime
    processed_at: Optional[datetime]
    error_message: Optional[str]
