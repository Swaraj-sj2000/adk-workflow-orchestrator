# app/models/_agent.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship
from app.db._database import Base

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    capability = Column(String, nullable=True)
    tasks = relationship("Task", back_populates="agent")