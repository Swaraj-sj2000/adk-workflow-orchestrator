from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core._deps import get_current_user, require_admin, require_ceo_or_admin
from app.db._database import get_db
from app.models._project import Project
from app.models._team import Team
from app.models._user import User
from app.schemas._invite import TeamInviteAction, TeamInviteCreate
from app.services import _project_service
from app.services._invite_service import (
    create_team_invite,
    get_or_create_org_pool_team,
    get_or_create_project_team,
    list_pending_org_invites,
    list_talent_pool,
    list_user_invites,
)

router = APIRouter(tags=["Invites"])


@router.post("/invite")
def create_invite(
    payload: TeamInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    team = None
    if payload.team_id is not None:
        team = db.query(Team).filter(Team.id == payload.team_id, Team.tenant_id == current_user.tenant_id).first()
    elif payload.project_id is not None:
        project = db.query(Project).filter(Project.id == payload.project_id, Project.tenant_id == current_user.tenant_id).first()
        if not project:
            raise HTTPException(status_code=404, detail="Project not found")
        team = get_or_create_project_team(db, project, current_user.id)

    if not team:
        raise HTTPException(status_code=400, detail="A valid project_id or team_id is required")

    invite, existing_user = create_team_invite(
        db,
        team=team,
        tenant_id=current_user.tenant_id,
        email=payload.email,
        invited_by_user_id=current_user.id,
        role_title=payload.role_title,
        note=payload.note,
    )
    db.commit()

    return {
        "invite_id": invite.id,
        "team_id": invite.team_id,
        "email": invite.email,
        "status": invite.status,
        "token": invite.token,
        "existing_user": bool(existing_user),
    }


@router.post("/invite/org")
def create_org_invite(
    payload: TeamInviteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    """Invite someone to join the company talent pool — no project needed."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="You must belong to a tenant to invite members")

    team = get_or_create_org_pool_team(db, current_user.tenant_id, current_user.id)
    invite, existing_user = create_team_invite(
        db,
        team=team,
        tenant_id=current_user.tenant_id,
        email=payload.email,
        invited_by_user_id=current_user.id,
        role_title=payload.role_title,
        note=payload.note,
    )
    db.commit()

    return {
        "invite_id": invite.id,
        "team_id": invite.team_id,
        "email": invite.email,
        "status": invite.status,
        "token": invite.token,
        "existing_user": bool(existing_user),
    }


@router.get("/invite/talent-pool")
def get_talent_pool(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    """List all accepted members in the org talent pool."""
    return {
        "members": list_talent_pool(db, current_user.tenant_id),
        "pending_invites": list_pending_org_invites(db, current_user.tenant_id),
    }


@router.get("/my-invites")
def my_invites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invites = list_user_invites(db, current_user)
    return [
        {
            "id": invite.id,
            "team_id": invite.team_id,
            "email": invite.email,
            "status": invite.status,
            "token": invite.token,
            "role_title": invite.role_title,
            "note": invite.note,
            "created_at": invite.created_at.isoformat() if invite.created_at else None,
        }
        for invite in invites
    ]


@router.post("/accept-invite")
def accept_invite(
    payload: TeamInviteAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _project_service.handle_team_invite_action(
        db=db,
        actor=current_user,
        invite_id=payload.invite_id,
        token=payload.token,
        accepted=payload.accepted,
        note=payload.note,
    )
