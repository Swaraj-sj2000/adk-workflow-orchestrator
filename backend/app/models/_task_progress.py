# app/models/_task_progress.py
from sqlalchemy import Column, Integer, Float, ForeignKey, DateTime, Text
from app.db._database import Base
from datetime import datetime


class TaskProgress(Base):
    __tablename__ = "task_progress"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), unique=True, nullable=False)
    completion_percentage = Column(Float, default=0.0)  # 0-100
    last_updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    actual_hours_spent = Column(Float, default=0.0)
    estimated_hours_remaining = Column(Float, nullable=True)
    status_notes = Column(Text, nullable=True)
    is_on_track = Column(Integer, default=1)  # 1 = yes, 0 = no (for early detection of delays)
