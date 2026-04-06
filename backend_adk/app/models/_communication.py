# app/models/_communication.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from app.db._database import Base
from datetime import datetime


class Communication(Base):
    __tablename__ = "communications"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False, default="ticket")  # email / ticket / meeting / call
    from_actor = Column(String, nullable=False)  # agent / admin / employee / client
    to_actor = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)
    sent_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="sent")  # sent / queued / failed / acknowledged
