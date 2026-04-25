from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String

from app.db._database import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    theme = Column(String, nullable=False, default="light")
    language = Column(String, nullable=False, default="en")
    ceo_mode = Column(Boolean, nullable=False, default=False)
    notification_density = Column(String, nullable=False, default="all")
    default_landing_page = Column(String, nullable=False, default="dashboard")
    email_notifications = Column(Boolean, nullable=False, default=True)
    weekly_digest = Column(Boolean, nullable=False, default=True)
    # Google integrations
    google_calendar_connected = Column(Boolean, nullable=False, default=False)
    google_calendar_token = Column(JSON, nullable=True)
    google_calendar_email = Column(String, nullable=True)
    onboarding_complete = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
