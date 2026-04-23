from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserPreferencesUpdate(BaseModel):
    timezone: str | None = None
    theme: str | None = None
    language: str | None = None
    ceo_mode: bool | None = None
    notification_density: str | None = None
    default_landing_page: str | None = None
    email_notifications: bool | None = None
    weekly_digest: bool | None = None


class UserPreferencesRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    timezone: str
    theme: str
    language: str
    ceo_mode: bool
    notification_density: str
    default_landing_page: str
    email_notifications: bool
    weekly_digest: bool
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    timezone: str | None = None


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class SupportTicketCreate(BaseModel):
    subject: str = Field(max_length=200)
    body: str = Field(max_length=5000)
    priority: str = "medium"
