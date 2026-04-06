# app/schemas/_task.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, List
from enum import Enum
from datetime import datetime


class TaskStatus(str, Enum):
    pending = "pending"
    running = "running"
    done = "done"
    blocked = "blocked"
    delayed = "delayed"


class TaskCreate(BaseModel):
    project_id: int
    parent_task_id: Optional[int] = None
    agent_id: Optional[int] = None
    description: str
    difficulty: str = "medium"
    urgency: str = "medium"
    estimated_time: Optional[float] = None
    required_skills: Dict[str, float] = {}
    deadline: Optional[datetime] = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    project_id: int
    agent_id: Optional[int]
    parent_task_id: Optional[int]
    description: str
    status: str
    difficulty: str
    urgency: str
    estimated_time: Optional[float]
    required_skills: Dict[str, float]
    deadline: Optional[datetime]
    created_at: datetime


class TaskUpdateStatus(BaseModel):
    status: TaskStatus


class TaskUpdate(BaseModel):
    description: Optional[str] = None
    difficulty: Optional[str] = None
    urgency: Optional[str] = None
    estimated_time: Optional[float] = None
    deadline: Optional[datetime] = None
