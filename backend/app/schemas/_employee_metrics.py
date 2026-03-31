# app/schemas/_employee_metrics.py
from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class EmployeeMetricsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    efficiency_score: float
    reliability_score: float
    avg_completion_time: Optional[float]
    total_tasks_completed: int
    total_tasks_failed: int
    total_tasks_delayed: int
    updated_at: datetime


class EmployeeMetricsUpdate(BaseModel):
    efficiency_score: Optional[float] = None
    reliability_score: Optional[float] = None
    avg_completion_time: Optional[float] = None
