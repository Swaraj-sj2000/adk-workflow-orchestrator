# app/models/_employee_profile.py
from sqlalchemy import Column, Integer, String, ForeignKey, Float, JSON, DateTime
from sqlalchemy.orm import relationship
from app.db._database import Base
from datetime import datetime


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    
    # Support both old user_id (Integer) and new auth_user_id (String UUID) during migration
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=True)
    auth_user_id = Column(String(36), ForeignKey("auth_users.id"), unique=True, nullable=True)
    
    # Profile data
    full_name = Column(String(255), nullable=True)
    role = Column(String(50), default="employee")  # employee / manager / team-lead
    skills = Column(JSON, nullable=False, default={})  # {"python": 0.9, "fastapi": 0.8, ...}
    experience_years = Column(Integer, nullable=True)
    
    # Capacity management
    max_capacity = Column(Float, default=8.0)  # hours per day
    current_load = Column(Float, default=0.0)  # hours currently assigned
    
    # Organization details
    department = Column(String, nullable=True)
    availability_status = Column(String, default="available")  # available / on-leave / busy
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    user = relationship("User", backref="employee_profile")
    auth_user = relationship("AuthUser", back_populates="employee_profile")
    metrics = relationship("EmployeeMetrics", back_populates="employee", uselist=False)
    assignments = relationship("TaskAssignment", back_populates="employee")
