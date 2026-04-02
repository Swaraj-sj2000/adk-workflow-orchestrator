# app/api/routes/_project.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db._database import get_db
from app.schemas._project import ProjectCreate, ProjectInviteResponse, TeamApprovalAction
from app.services._project_service import (
    build_project_status,
    create_project,
    get_clients,
    get_projects,
    handle_team_approval,
    handle_project_invite_response,
)
from app.core._deps import get_current_user
from app.models._project import Project
from app.models._task import Task

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/")
def create(
    project: ProjectCreate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    return create_project(db, project, admin_id=user.id)


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
    return get_clients(db)


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
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if user.role != "admin" and user.id != project.admin_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this project")

    try:
        # Delete all related records first (cascade)
        # Delete task assignments
        from app.models._task_assignment import TaskAssignment
        db.query(TaskAssignment).filter(
            TaskAssignment.task_id.in_(
                db.query(Task.id).filter(Task.project_id == project_id)
            )
        ).delete(synchronize_session=False)
        
        # Delete task dependencies
        from app.models._task_dependency import TaskDependency
        db.query(TaskDependency).filter(
            TaskDependency.task_id.in_(
                db.query(Task.id).filter(Task.project_id == project_id)
            )
        ).delete(synchronize_session=False)
        
        # Delete tasks
        db.query(Task).filter(Task.project_id == project_id).delete(synchronize_session=False)
        
        # Delete project
        db.delete(project)
        db.commit()
        
        return {"success": True, "project_id": project_id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")
