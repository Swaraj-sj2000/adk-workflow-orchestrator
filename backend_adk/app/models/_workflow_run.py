# app/models/_workflow_run.py

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db._database import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_type = Column(String, nullable=False, index=True)
    status = Column(String, nullable=False, default="running")
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    requires_human_review = Column(Boolean, nullable=False, default=False)
    input_payload = Column(JSON, nullable=False, default={})
    shared_context = Column(JSON, nullable=True)
    final_output = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    agent_runs = relationship(
        "AgentRun",
        back_populates="workflow_run",
        cascade="all, delete-orphan",
        order_by="AgentRun.id.asc()",
    )
