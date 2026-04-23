# backend/app/models/_user.py

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
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
