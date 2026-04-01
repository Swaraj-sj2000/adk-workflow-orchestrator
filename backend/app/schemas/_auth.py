# backend/app/schemas/_auth.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "employee"


class UserCreate(UserBase):
    """Request model for user signup"""
    password: str = Field(..., min_length=8, description="Minimum 8 characters")
    organization_slug: Optional[str] = None


class UserLogin(BaseModel):
    """Request model for user login"""
    email: EmailStr
    password: str
    organization_slug: Optional[str] = None


class EmployeeInviteAccept(BaseModel):
    """Request model for accepting invite"""
    invite_code: str
    full_name: str
    email: EmailStr
    password: str = Field(..., min_length=8)
    skills: list[str] = []
    experience_years: Optional[int] = None


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    user_id: str
    organization_id: str
    role: str
    expires_in: int  # seconds


class AuthResponse(BaseModel):
    """Complete auth response with user and organization info"""
    user_id: str
    email: str
    full_name: Optional[str]
    organization_id: str
    organization_slug: str
    role: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class InviteCodeValidation(BaseModel):
    """Validate invite code before accepting"""
    valid: bool
    message: str
    email: Optional[str] = None
    organization_id: Optional[str] = None
    organization_name: Optional[str] = None
    expires_at: Optional[datetime] = None


class AuthError(BaseModel):
    """Standard auth error response"""
    detail: str
    error_code: Optional[str] = None


# Config for Pydantic models
class Config:
    json_schema_extra = {
        "example": {
            "email": "user@example.com",
            "password": "securepassword123"
        }
    }
