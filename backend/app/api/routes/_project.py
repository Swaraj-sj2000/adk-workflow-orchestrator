# app/api/routes/_project.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db._database import get_db
from app.schemas._project import ProjectCreate
from app.services._project_service import create_project, get_projects
from app.core._deps import get_current_user

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/")
def create(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return create_project(
        db,
        project.name,
        project.description,
        project.budget,
        owner_id=user.id
    )


@router.get("/")
def read_all(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return get_projects(db)