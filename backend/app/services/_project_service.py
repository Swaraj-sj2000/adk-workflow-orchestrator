#backend/app/services/_project_service.py

from sqlalchemy.orm import Session
from app.models._project import Project
from typing import Optional
from datetime import datetime


def create_project(
    db: Session,
    name: str,
    description: Optional[str],
    budget: float,
    admin_id: int,
    client_id: Optional[int] = None,
    priority: str = "medium",
    deadline: Optional[datetime] = None,
):
    project = Project(
        name=name,
        description=description,
        budget=budget,
        admin_id=admin_id,
        client_id=client_id,
        priority=priority,
        deadline=deadline,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_projects(db: Session):
    return db.query(Project).all()
