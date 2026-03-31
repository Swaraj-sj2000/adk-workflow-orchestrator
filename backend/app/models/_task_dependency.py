# app/models/_task_dependency.py
from sqlalchemy import Column, Integer, ForeignKey, String
from app.db._database import Base


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    depends_on_task_id = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    dependency_type = Column(String, default="blocking")  # blocking / weak / conditional
