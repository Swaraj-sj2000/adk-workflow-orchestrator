# backend/app/models/_tenant.py

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text  # noqa: F401 (Integer used for founded_year)

from app.db._database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    slug = Column(String, nullable=False, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    logo_url = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    industry = Column(String, nullable=True)
    website_url = Column(Text, nullable=True)
    headquarters = Column(String, nullable=True)
    employee_count_range = Column(String, nullable=True)
    founded_year = Column(Integer, nullable=True)
    contact_email = Column(String, nullable=True)
    contact_phone = Column(String, nullable=True)
