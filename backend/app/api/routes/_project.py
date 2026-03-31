# app/api/routes/_project.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db._database import get_db
from app.schemas._project import ProjectCreate
from app.services._project_service import create_project, get_projects
from app.core._deps import get_current_user
from app.models._project import Project

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
        admin_id=user.id,
        client_id=project.client_id,
        priority=project.priority,
        deadline=project.deadline,
    )


@router.get("/")
def read_all(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return get_projects(db)


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if user.role != "admin" and user.id != project.admin_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")

    db.delete(project)
    db.commit()
    return {"success": True, "project_id": project_id}
