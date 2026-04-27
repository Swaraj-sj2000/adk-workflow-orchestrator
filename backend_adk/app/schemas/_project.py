# backend/app/schemas/_project.py
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Any, Dict, Optional, Literal
from datetime import datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=160)
    description: Optional[str] = Field(default=None, max_length=5000)
    status: str = "planning"
    client_id: Optional[int] = None
    client_email: Optional[str] = None
    client_company_name: Optional[str] = None
    client_contact_person: Optional[str] = None
    client_phone: Optional[str] = None
    client_address: Optional[str] = None
    client_user_full_name: Optional[str] = None
    client_user_password: Optional[str] = None
    client_mode: Literal["existing", "new"] = "existing"
    budget: float = 0.0
    payment_status: str = "pending"
    priority: str = "medium"
    deadline: Optional[datetime] = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


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
    custom_fields: Optional[Dict[str, Any]] = None


class TeamApprovalAction(BaseModel):
    approved: bool
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_approval_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class ProjectInviteResponse(BaseModel):
    accepted: bool
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_invite_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class DraftTeamReplacementAction(BaseModel):
    current_employee_id: int = Field(gt=0)
    replacement_employee_id: int = Field(gt=0)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_replacement_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class ProjectTaskReassignmentAction(BaseModel):
    replacement_employee_id: int = Field(gt=0)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_reassignment_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class TaskChangeRequestCreate(BaseModel):
    action: Literal["add", "delete"]
    target_type: Literal["task", "subtask"]
    target_task_id: Optional[int] = Field(default=None, gt=0)
    parent_task_id: Optional[int] = Field(default=None, gt=0)
    proposed_title: Optional[str] = Field(default=None, min_length=3, max_length=200)
    proposed_description: Optional[str] = Field(default=None, min_length=3, max_length=1000)
    note: str = Field(min_length=8, max_length=1200)

    @field_validator("proposed_title", "proposed_description", "note")
    @classmethod
    def normalize_change_request_text(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class TaskChangeRequestReview(BaseModel):
    approved: bool
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("note")
    @classmethod
    def normalize_review_note(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value else value


class ProjectPaymentUpdate(BaseModel):
    payment_status: str = Field(min_length=3, max_length=40)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("payment_status")
    @classmethod
    def normalize_payment_status(cls, value: str) -> str:
        return value.strip().lower()
