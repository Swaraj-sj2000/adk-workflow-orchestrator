# app/models/_task_assignment.py
from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, Float, Text
from sqlalchemy.orm import relationship
from app.db._database import Base
from datetime import datetime


class TaskAssignment(Base):
    __tablename__ = "task_assignments"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=False)
    assigned_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    status = Column(String, default="assigned")  # assigned / in-progress / completed / failed
    estimated_hours = Column(Float, nullable=True)
    actual_hours = Column(Float, nullable=True)
    assignment_confidence = Column(Float, nullable=True)  # 0-1 scale, from assignment engine
    notes = Column(Text, nullable=True)

    # Relationships
    task = relationship("Task", back_populates="assignments")
    employee = relationship("EmployeeProfile", back_populates="assignments")
