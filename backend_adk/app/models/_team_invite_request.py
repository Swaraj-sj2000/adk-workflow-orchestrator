from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from app.db._database import Base


class TeamInviteRequest(Base):
    __tablename__ = "team_invite_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    requester_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=False)
    proposed_role = Column(String, nullable=True)
    # pending_ceo | pending_manager | pending_employee | accepted
    # rejected_by_ceo | rejected_by_manager | rejected_by_employee
    status = Column(String, nullable=False, default="pending_ceo")
    current_manager_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
