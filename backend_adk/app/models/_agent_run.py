# app/models/_agent_run.py

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db._database import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_run_id = Column(Integer, ForeignKey("workflow_runs.id"), nullable=False, index=True)
    agent_name = Column(String, nullable=False, index=True)
    role = Column(String, nullable=False)
    stage = Column(String, nullable=False)
    status = Column(String, nullable=False, default="completed")
    confidence = Column(Float, nullable=True)
    requires_human_review = Column(Boolean, nullable=False, default=False)
    reasoning = Column(Text, nullable=True)
    input_payload = Column(JSON, nullable=False, default={})
    output_payload = Column(JSON, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    workflow_run = relationship("WorkflowRun", back_populates="agent_runs")
