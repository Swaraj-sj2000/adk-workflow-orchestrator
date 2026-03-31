#backend/app/models/_project.py

from sqlalchemy import Column, Integer, String, ForeignKey
from app.db._database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)

    owner_id = Column(Integer, ForeignKey("users.id"))

    progress = Column(Integer, default=0)  # 0-100
    budget = Column(Integer)
    profit = Column(Integer, default=0)