# backend/app/schemas/_invite.py

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class InviteStatus(str, Enum):
    """Invite status enumeration"""
    pending = "pending"
    accepted = "accepted"
    expired = "expired"
    cancelled = "cancelled"


class CreateInviteRequest(BaseModel):
    """Request to create new employee invite"""
    email: EmailStr
    role: str = Field(default="employee", description="employee|manager")
    expires_in_days: int = Field(default=7, ge=1, le=30, description="Days until invite expires")
    message: Optional[str] = Field(None, max_length=500, description="Custom message for invite")


class InviteResponse(BaseModel):
    """Single invite response"""
    id: str
    organization_id: str
    email: str
    invite_code: str
    role: str
    status: str
    expires_at: datetime
    created_at: datetime
    created_by: str
    accepted_at: Optional[datetime] = None
    accepted_by_user_id: Optional[str] = None
    
    class Config:
        from_attributes = True


class InviteListResponse(BaseModel):
    """List of invites with pagination"""
    items: List[InviteResponse]
    total: int
    pending_count: int
    accepted_count: int
    expired_count: int


class InviteLinkResponse(BaseModel):
    """Invite with shareable link"""
    invite_id: str
    email: str
    role: str
    status: str
    expires_at: datetime
    invite_link: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class RevokeInviteRequest(BaseModel):
    """Request to revoke/cancel invite"""
    reason: Optional[str] = Field(None, max_length=500)


class BulkInviteRequest(BaseModel):
    """Bulk invite creation"""
    emails: List[EmailStr]
    role: str = Field(default="employee")
    expires_in_days: int = Field(default=7, ge=1, le=30)


class BulkInviteResponse(BaseModel):
    """Bulk invite creation results"""
    created: int
    failed: int
    invites: List[InviteLinkResponse]
