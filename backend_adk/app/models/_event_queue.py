# app/models/_event_queue.py
from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from app.db._database import Base
from datetime import datetime


class EventQueue(Base):
    __tablename__ = "event_queue"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String, nullable=False)  # TASK_CREATED / TASK_UPDATED / PROJECT_CREATED / etc.
    entity_type = Column(String, nullable=False)  # project / task / employee / etc.
    entity_id = Column(Integer, nullable=False)
    payload = Column(JSON, nullable=False)  # event data
    status = Column(String, default="pending")  # pending / processing / completed / failed
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)
