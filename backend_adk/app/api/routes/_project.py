# app/api/routes/_project.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db._database import get_db
from app.schemas._project import ProjectCreate, ProjectInviteResponse, TeamApprovalAction
from app.services._project_service import (
    build_project_status,
    create_project,
    delete_project_atomic,
    get_clients,
    get_projects,
    handle_team_approval,
    handle_project_invite_response,
)
from app.core._deps import get_current_user
from app.models._project import Project
from app.core._logging import get_logger

router = APIRouter(prefix="/projects", tags=["Projects"])
logger = get_logger(__name__)


@router.post("/")
def create(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    logger.info(f"Creating project: name={project.name}, user_id={user.id}")
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create projects")
    try:
        result = create_project(db, project, admin=user)
        logger.info(f"Project created successfully: project_id={result.id if hasattr(result, 'id') else 'unknown'}")
        return result
    except Exception as e:
        logger.error(f"Failed to create project: {e}", exc_info=True)
        raise


@router.get("/")
def read_all(
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return get_projects(db, viewer=user)


@router.get("/clients")
def read_clients(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view clients")
    return get_clients(db, user)


@router.get("/{project_id}/status")
def read_project_status(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return build_project_status(db, project_id, viewer=user)


@router.post("/{project_id}/team-approval")
def act_on_team_approval(
    project_id: int,
    payload: TeamApprovalAction,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can confirm project team approval")

    return handle_team_approval(
        db=db,
        project_id=project_id,
        approved=payload.approved,
        note=payload.note,
        actor_id=user.id,
    )


@router.post("/{project_id}/invite-response")
def respond_to_project_invite(
    project_id: int,
    payload: ProjectInviteResponse,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return handle_project_invite_response(
        db=db,
        project_id=project_id,
        accepted=payload.accepted,
        note=payload.note,
        actor=user,
    )


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    return delete_project_atomic(db, project_id, user)
