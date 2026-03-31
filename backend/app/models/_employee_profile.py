# app/models/_employee_profile.py
from sqlalchemy import Column, Integer, String, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from app.db._database import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    skills = Column(JSON, nullable=False, default={})  # {"python": 0.9, "fastapi": 0.8, ...}
    max_capacity = Column(Float, default=8.0)  # hours per day
    current_load = Column(Float, default=0.0)  # hours currently assigned
    department = Column(String, nullable=True)
    availability_status = Column(String, default="available")  # available / on-leave / busy

    # Relationships
    user = relationship("User", backref="employee_profile")
    metrics = relationship("EmployeeMetrics", back_populates="employee", uselist=False)
    assignments = relationship("TaskAssignment", back_populates="employee")
