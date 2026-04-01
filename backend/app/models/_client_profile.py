# app/models/_client_profile.py
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from app.db._database import Base
from datetime import datetime


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    company_name = Column(String, nullable=False)
    contact_person = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    address = Column(String, nullable=True)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization")
    user = relationship("User", backref="client_profile")
