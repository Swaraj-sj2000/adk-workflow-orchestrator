# app/models/_change_request.py
from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db._database import Base
from datetime import datetime


class ChangeRequest(Base):
    __tablename__ = "change_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    requested_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    status = Column(String, default="pending")  # pending / approved / rejected / implemented

    # Populated by scope-change agent (Feature 6)
    agent_analysis = Column(Text, nullable=True)
    change_order_doc = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    project = relationship("Project", backref="change_requests")
    requested_by = relationship("User", foreign_keys=[requested_by_user_id])
