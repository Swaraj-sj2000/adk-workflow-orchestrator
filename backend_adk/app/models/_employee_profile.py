# app/models/_employee_profile.py
from sqlalchemy import Column, Date, DateTime, Integer, String, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from app.db._database import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    skills = Column(JSON, nullable=False, default={})  # {"python": 0.9, "fastapi": 0.8, ...}
    max_capacity = Column(Float, default=40.0)
    current_load = Column(Float, default=0.0)
    department = Column(String, nullable=True)
    availability_status = Column(String, default="available")
    duty_start_hour = Column(Float, nullable=True, default=9.0)
    duty_end_hour = Column(Float, nullable=True, default=18.0)
    demonstrated_skills = Column(JSON, nullable=True, default={})

    # XP & levelling
    xp = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)

    # Joining date (set by CEO at registration — used for in-company tenure)
    joining_date = Column(Date, nullable=True)

    # Years of experience declared at registration
    years_experience = Column(Float, nullable=True, default=0.0)

    # Pending skill change requests from the employee
    # {"python": {"current": 0.8, "requested": 0.9, "request_id": 42}}
    pending_skills = Column(JSON, nullable=True, default={})

    # Manager assignment (set when employee accepts a team invite)
    manager_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=True)

    # Maximum direct reports allowed (CEO-controlled, default 10)
    max_team_size = Column(Integer, nullable=True, default=10)

    # Soft delete
    deleted_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", backref="employee_profile")
    metrics = relationship("EmployeeMetrics", back_populates="employee", uselist=False)
    assignments = relationship("TaskAssignment", back_populates="employee")
