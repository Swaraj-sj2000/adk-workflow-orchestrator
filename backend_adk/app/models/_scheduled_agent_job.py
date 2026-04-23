from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db._database import Base


class ScheduledAgentJob(Base):
    __tablename__ = "scheduled_agent_jobs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    job_type = Column(String, nullable=False)
    cron_expr = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    enabled = Column(Boolean, nullable=False, default=True)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)
    last_status = Column(String, nullable=True)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
