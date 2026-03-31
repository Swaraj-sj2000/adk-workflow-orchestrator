# app/models/_audit_log.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from app.db._database import Base
from datetime import datetime


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)
    entity_type = Column(String, nullable=False)
    entity_id = Column(Integer, nullable=False)
    decision_reason = Column(Text, nullable=True)
    performed_by = Column(String, nullable=False, default="agent")  # agent / human
    context_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
