# app/models/_employee_metrics.py
from sqlalchemy import Column, Integer, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from app.db._database import Base
from datetime import datetime


class EmployeeMetrics(Base):
    __tablename__ = "employee_metrics"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employee_profiles.id"), unique=True, nullable=False)
    efficiency_score = Column(Float, default=0.5)  # 0-1 scale
    reliability_score = Column(Float, default=0.5)  # 0-1 scale
    avg_completion_time = Column(Float, nullable=True)  # hours
    total_tasks_completed = Column(Integer, default=0)
    total_tasks_failed = Column(Integer, default=0)
    total_tasks_delayed = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("EmployeeProfile", back_populates="metrics")
