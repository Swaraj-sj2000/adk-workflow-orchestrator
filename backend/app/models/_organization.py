# backend/app/models/_organization.py

from sqlalchemy import Column, String, DateTime, Integer, Boolean
from sqlalchemy.orm import relationship
from app.db._database import Base
from datetime import datetime
import uuid


class Organization(Base):
    """
    Represents a tenant/workspace.
    Multiple users and projects belong to one organization.
    """
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(255), nullable=False)  # e.g., "Acme Corp"
    slug = Column(String(100), unique=True, nullable=False, index=True)  # e.g., "acme-corp"
    description = Column(String(500), nullable=True)
    
    # Subscription and limits
    subscription_tier = Column(String(50), default="free")  # free / pro / enterprise
    max_employees = Column(Integer, default=50)
    max_projects = Column(Integer, default=10)
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Metadata
    created_by = Column(String(36), nullable=True)  # user_id of creator
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships (defined as backref from child models)
    # - users (from AuthUser.organization)
    # - employee_profiles (from EmployeeProfile.organization)
    # - projects (from Project.organization)
    # - invites (from EmployeeInvite.organization)
    
    def __repr__(self):
        return f"<Organization {self.slug}>"
