from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String

from app.db._database import Base


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), unique=True, nullable=False)
    default_timezone = Column(String, nullable=False, default="UTC")
    data_region = Column(String, nullable=False, default="eu")
    plan_tier = Column(String, nullable=False, default="trial")
    suspended = Column(Boolean, nullable=False, default=False)
    suspension_reason = Column(String, nullable=True)
    suspended_at = Column(DateTime, nullable=True)
    grace_period_ends_at = Column(DateTime, nullable=True)
    stripe_customer_id = Column(String, nullable=True, unique=True)
    stripe_subscription_id = Column(String, nullable=True)
    stripe_plan_id = Column(String, nullable=True)
    next_billing_date = Column(DateTime, nullable=True)
    trial_ends_at = Column(DateTime, nullable=True)
    max_users = Column(Integer, nullable=False, default=5)
    max_projects = Column(Integer, nullable=False, default=3)
    max_teams = Column(Integer, nullable=False, default=1)
    max_ai_calls_per_month = Column(Integer, nullable=False, default=50)
    subscription_expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
