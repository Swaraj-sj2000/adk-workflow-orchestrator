# backend/app/schemas/_project.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client_id: Optional[int] = None
    budget: float = 0.0
    priority: str = "medium"
    deadline: Optional[datetime] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    progress: Optional[int] = None
    priority: Optional[str] = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # ✅ Pydantic v2

    id: int
    name: str
    description: Optional[str]
    admin_id: int
    client_id: Optional[int]
    status: str
    progress: int
    budget: float
    spent: float
    payment_status: str
    created_at: datetime
    deadline: Optional[datetime]
    priority: str
