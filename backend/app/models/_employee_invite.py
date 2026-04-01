# backend/app/models/_employee_invite.py

from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.db._database import Base
from datetime import datetime, timedelta
import uuid
import secrets


class EmployeeInvite(Base):
    """
    Invitation link for employees to join an organization.
    Admin generates these and shares them with employees.
    """
    __tablename__ = "employee_invites"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Invite details
    email = Column(String(255), nullable=False)
    invite_code = Column(String(100), unique=True, nullable=False, index=True)  # Unique link token
    role = Column(String(50), default="employee")  # Pre-assigned role
    
    # Status
    status = Column(String(50), default="pending")  # pending / accepted / expired / cancelled
    
    # Timeline
    expires_at = Column(DateTime, nullable=False)
    created_by = Column(String(36), nullable=True)  # admin user_id who sent invite
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Who accepted this invite
    accepted_by_user_id = Column(String(36), ForeignKey("auth_users.id"), nullable=True)
    
    # Relationships
    organization = relationship("Organization")
    accepted_by_user = relationship("AuthUser", foreign_keys=[accepted_by_user_id])
    
    @classmethod
    def generate_invite_code(cls):
        """Generate a secure, URL-safe invite code"""
        return secrets.token_urlsafe(24)
    
    @classmethod
    def create_invite(cls, organization_id, email, created_by, role="employee", expires_in_days=7):
        """Factory method to create invitation"""
        return cls(
            organization_id=organization_id,
            email=email,
            invite_code=cls.generate_invite_code(),
            role=role,
            created_by=created_by,
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days),
            status="pending"
        )
    
    def is_valid(self):
        """Check if invite is still valid"""
        return (
            self.status == "pending" and 
            self.expires_at > datetime.utcnow()
        )
    
    def __repr__(self):
        return f"<EmployeeInvite {self.email} in {self.organization_id}>"
