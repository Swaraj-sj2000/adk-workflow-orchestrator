# app/schemas/_employee_profile.py
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional, Dict, List


class EmployeeProfileCreate(BaseModel):
    user_id: int
    skills: Dict[str, float] = {}
    max_capacity: float = 8.0
    department: Optional[str] = None
    duty_start_hour: Optional[float] = Field(default=9.0, ge=0, le=23.75)
    duty_end_hour: Optional[float] = Field(default=18.0, ge=0, le=23.75)


class EmployeeProfileUpdate(BaseModel):
    skills: Optional[Dict[str, float]] = None
    max_capacity: Optional[float] = None
    current_load: Optional[float] = None
    availability_status: Optional[str] = None
    department: Optional[str] = None
    duty_start_hour: Optional[float] = Field(default=None, ge=0, le=23.75)
    duty_end_hour: Optional[float] = Field(default=None, ge=0, le=23.75)

    @field_validator("skills")
    @classmethod
    def normalize_skills(cls, value: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        if value is None:
            return value

        cleaned: Dict[str, float] = {}
        for key, score in value.items():
            normalized_key = str(key or "").strip().lower()
            if not normalized_key:
                continue
            cleaned[normalized_key] = round(max(0.0, min(float(score), 1.0)), 2)
        return cleaned

    @field_validator("availability_status")
    @classmethod
    def normalize_availability(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip().lower()
        allowed = {"available", "busy", "on-leave"}
        if normalized not in allowed:
            raise ValueError("availability_status must be available, busy, or on-leave")
        return normalized


class EmployeeProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    skills: Dict[str, float]
    max_capacity: float
    current_load: float
    department: Optional[str]
    availability_status: str
    duty_start_hour: Optional[float]
    duty_end_hour: Optional[float]
