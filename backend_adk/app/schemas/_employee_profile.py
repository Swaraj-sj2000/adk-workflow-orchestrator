# app/schemas/_employee_profile.py
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, List


class EmployeeProfileCreate(BaseModel):
    user_id: int
    skills: Dict[str, float] = {}
    max_capacity: float = 8.0
    department: Optional[str] = None


class EmployeeProfileUpdate(BaseModel):
    skills: Optional[Dict[str, float]] = None
    max_capacity: Optional[float] = None
    current_load: Optional[float] = None
    availability_status: Optional[str] = None


class EmployeeProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    skills: Dict[str, float]
    max_capacity: float
    current_load: float
    department: Optional[str]
    availability_status: str
