#backend/app/services/_project_service.py

from sqlalchemy.orm import Session
from app.models._project import Project


def create_project(db: Session, name: str, description: str, budget: int, owner_id: int):
    project = Project(
        name=name,
        description=description,
        budget=budget,
        owner_id=owner_id
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def get_projects(db: Session):
    return db.query(Project).all()