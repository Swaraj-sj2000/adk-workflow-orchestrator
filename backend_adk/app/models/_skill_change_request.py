from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from app.db._database import Base
from datetime import datetime


class SkillChangeRequest(Base):
    __tablename__ = "skill_change_requests"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    employee_profile_id = Column(Integer, ForeignKey("employee_profiles.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    skill_name = Column(String, nullable=False)
    current_value = Column(Float, nullable=False)
    requested_value = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending / approved / rejected / suggested
    admin_message = Column(Text, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
