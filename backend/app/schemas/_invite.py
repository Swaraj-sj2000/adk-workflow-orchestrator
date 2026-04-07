from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class TeamInviteCreate(BaseModel):
    project_id: Optional[int] = None
    team_id: Optional[int] = None
    email: EmailStr
    role_title: Optional[str] = Field(default=None, max_length=120)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()


class TeamInviteAction(BaseModel):
    invite_id: Optional[int] = None
    token: Optional[str] = None
    accepted: bool = True
    note: Optional[str] = Field(default=None, max_length=500)


class TeamInviteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tenant_id: int
    team_id: int
    email: str
    status: str
    token: str
    role_title: Optional[str]
    note: Optional[str]
    created_at: datetime
    responded_at: Optional[datetime]
