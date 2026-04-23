# backend/app/schemas/_user.py

from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    role: Literal["platform_owner", "ceo", "admin", "employee", "client"]
    tenant_name: Optional[str] = Field(default=None, max_length=120)
    tenant_slug: Optional[str] = Field(default=None, max_length=120)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return value.strip()


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.strip().lower()


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=8, max_length=255)
    new_password: str = Field(min_length=8, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)
