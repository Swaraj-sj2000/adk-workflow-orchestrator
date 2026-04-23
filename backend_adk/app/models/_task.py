# app/models/_task.py
from sqlalchemy import Column, Integer, String, ForeignKey, Enum, Float, DateTime, JSON, Text
from sqlalchemy.orm import relationship
from app.db._database import Base
import enum
from datetime import datetime

class TaskStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    blocked = "blocked"
    delayed = "delayed"
    
class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True)
    parent_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=True)  # for subtasks
    description = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    
    # Task details
    difficulty = Column(String, default="medium")  # easy / medium / hard
    urgency = Column(String, default="medium")  # low / medium / high / critical
    estimated_time = Column(Float, nullable=True)  # hours
    required_skills = Column(JSON, nullable=False, default={})  # {skill: proficiency_level}
    
    # Deadlines
    created_at = Column(DateTime, default=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    # Soft delete
    deleted_at = Column(DateTime, nullable=True)
    
    # Subtasks relationship
    subtasks = relationship("Task", remote_side=[id], backref="parent_task")
    
    # Relationships
    project = relationship("Project", back_populates="tasks")
    agent = relationship("Agent", back_populates="tasks")
    assignments = relationship("TaskAssignment", back_populates="task")
