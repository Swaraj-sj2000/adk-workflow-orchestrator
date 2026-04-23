from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String

from app.db._database import Base


class EmailDeliveryLog(Base):
    __tablename__ = "email_delivery_logs"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    to_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    template_name = Column(String, nullable=False)
    sendgrid_message_id = Column(String, nullable=True)
    status = Column(String, nullable=False, default="queued")
    error_message = Column(String, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
