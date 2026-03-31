#backend/app/models/_project.py

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, JSON
from sqlalchemy.orm import relationship 
from app.db._database import Base
from datetime import datetime

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    description = Column(String)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    client_id = Column(Integer, ForeignKey("client_profiles.id"), nullable=True)
    
    # Project status and progress
    status = Column(String, default="planning")  # planning / in-progress / on-hold / completed / cancelled
    progress = Column(Integer, default=0)  # 0-100
    
    # Budget and payment
    budget = Column(Float, nullable=False, default=0.0)
    spent = Column(Float, default=0.0)
    payment_status = Column(String, default="pending")  # pending / partial / completed
    
    # Timeline
    created_at = Column(DateTime, default=datetime.utcnow)
    start_date = Column(DateTime, nullable=True)
    deadline = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Priority and metadata
    priority = Column(String, default="medium")  # low / medium / high / critical
    custom_fields = Column(JSON, nullable=True)  # custom fields (renamed from metadata)
    
    # Relationships
    tasks = relationship("Task", back_populates="project")
    meetings = relationship("Meeting", backref="project")
    client = relationship("ClientProfile", backref="projects")