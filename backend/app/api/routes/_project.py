#backend/app/api/routes/_project.py


from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db._database import get_db
from app.schemas._project import ProjectCreate
from app.services._project_service import create_project, get_projects

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/")
def create(project: ProjectCreate, db: Session = Depends(get_db)):
    # TEMP: hardcoded owner (we'll replace with JWT later)
    return create_project(db, project.name, project.description, project.budget, owner_id=1)


@router.get("/")
def read_all(db: Session = Depends(get_db)):
    return get_projects(db)