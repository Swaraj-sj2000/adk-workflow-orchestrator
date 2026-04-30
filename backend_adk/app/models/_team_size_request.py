from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.sql import func

from app.db._database import Base


class TeamSizeRequest(Base):
    __tablename__ = "team_size_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    admin_profile_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=False)
    requested_size = Column(Integer, nullable=False)
    current_limit = Column(Integer, nullable=False)
    reason = Column(Text, nullable=True)
    status = Column(String, default="pending", nullable=False)  # pending | approved | rejected | expired
    approved_size = Column(Integer, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, nullable=True)
