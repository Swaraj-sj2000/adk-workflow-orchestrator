# app/models/_decision_log.py
from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, Text, ForeignKey
from app.db._database import Base
from datetime import datetime


class DecisionLog(Base):
    __tablename__ = "decision_logs"

    id = Column(Integer, primary_key=True, index=True)
    decision_type = Column(String, nullable=False)  # assignment / reassignment / deadline_change / rebalance / escalation
    entity_type = Column(String, nullable=False)  # task / project / employee
    entity_id = Column(Integer, nullable=False)
    input_data = Column(JSON, nullable=False)  # what factors were considered
    decision_taken = Column(Text, nullable=False)  # what was decided
    confidence = Column(Float, nullable=False)  # 0-1 scale
    reasoning = Column(Text, nullable=True)  # explanation for the decision
    override_by_admin = Column(Integer, ForeignKey("users.id"), nullable=True)  # if admin overrode it
    created_at = Column(DateTime, default=datetime.utcnow)
