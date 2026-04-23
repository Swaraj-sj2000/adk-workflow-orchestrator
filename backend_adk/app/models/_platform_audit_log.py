from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String

from app.db._database import Base


class PlatformAuditLog(Base):
    __tablename__ = "platform_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String, nullable=False)
    tenant_id = Column(Integer, nullable=True, index=True)
    details = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
