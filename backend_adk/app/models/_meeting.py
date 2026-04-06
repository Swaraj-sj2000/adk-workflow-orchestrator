# app/models/_meeting.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, JSON, Text
from app.db._database import Base
from datetime import datetime


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    meeting_type = Column(String, default="status")  # status / emergency / review / planning
    scheduled_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    attendees = Column(JSON, nullable=False)  # [user_id, ...]
    decisions_made = Column(JSON, nullable=True)  # [{decision: str, owner: user_id, deadline: date}, ...]
    created_at = Column(DateTime, default=datetime.utcnow)
