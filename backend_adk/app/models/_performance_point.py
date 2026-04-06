# app/models/_performance_point.py
from sqlalchemy import Column, Integer, ForeignKey, Float, String, DateTime
from app.db._database import Base
from datetime import datetime


class PerformancePoint(Base):
    __tablename__ = "performance_points"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False, index=True)
    points = Column(Float, nullable=False, default=0.0)
    reason = Column(String, nullable=False)
    awarded_at = Column(DateTime, default=datetime.utcnow)
