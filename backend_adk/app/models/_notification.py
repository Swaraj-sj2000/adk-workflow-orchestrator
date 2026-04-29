from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from app.db._database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    # approval_needed | fyi | escalation | invite_received | accepted | rejection_record
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=True)
    reference_type = Column(String, nullable=True)
    reference_id = Column(Integer, nullable=True)
    read_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
