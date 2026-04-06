# app/models/_blocker.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from app.db._database import Base
from datetime import datetime


class Blocker(Base):
    __tablename__ = "blockers"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    blocker_type = Column(String, nullable=False)  # dependency / resource / external / ambiguity
    severity = Column(String, default="medium")  # low / medium / high / critical
    description = Column(Text, nullable=False)
    status = Column(String, default="open")  # open / in-progress / resolved / escalated
    raised_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    ai_response = Column(Text, nullable=True)
    next_action = Column(Text, nullable=True)
    escalation_recommended = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True)
