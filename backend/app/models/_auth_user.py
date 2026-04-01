# backend/app/models/_auth_user.py

from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.db._database import Base
from datetime import datetime
import uuid


class AuthUser(Base):
    """
    Authentication user model for multi-tenant support.
    Every user belongs to exactly one organization.
    Replaces the old User model gradually.
    """
    __tablename__ = "auth_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Authentication fields
    email = Column(String(255), nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Role and permissions
    role = Column(String(50), default="employee")  # admin / manager / employee
    
    # Account status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    
    # Metadata
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    organization = relationship("Organization")
    # Note: employee_profile relationship is defined in EmployeeProfile model
    
    __table_args__ = (
        # Unique email per organization (allow same email across orgs)
        # This will be added via migration if needed
    )
    
    def __repr__(self):
        return f"<AuthUser {self.email} in {self.organization_id}>"
