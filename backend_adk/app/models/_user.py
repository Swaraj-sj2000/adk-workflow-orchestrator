# backend/app/models/_user.py

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from app.db._database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    full_name = Column(String, nullable=True)
    role = Column(String)  # platform_owner / ceo / admin / employee / client
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    password_reset_token = Column(String, nullable=True)
    password_reset_expires = Column(DateTime, nullable=True)
    # Email verification
    email_verified = Column(Boolean, nullable=True)
    email_verify_token = Column(String, nullable=True)
    # 2FA / TOTP
    totp_secret = Column(String, nullable=True)
    totp_enabled = Column(Boolean, nullable=False, default=False)
    # Soft delete
    deleted_at = Column(DateTime, nullable=True)
