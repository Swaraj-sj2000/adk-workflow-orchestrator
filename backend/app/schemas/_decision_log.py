# app/schemas/_decision_log.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class DecisionLogCreate(BaseModel):
    decision_type: str
    entity_type: str
    entity_id: int
    input_data: Dict[str, Any]
    decision_taken: str
    confidence: float
    reasoning: Optional[str] = None


class DecisionLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    decision_type: str
    entity_type: str
    entity_id: int
    input_data: Dict[str, Any]
    decision_taken: str
    confidence: float
    reasoning: Optional[str]
    created_at: datetime
