import secrets
import string

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.core._deps import get_current_user, require_admin, require_ceo_or_admin
from app.core._security import hash_password
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


class DirectAddMemberRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    role: str = Field(default="employee")
    role_title: str | None = None


def _generate_temp_password() -> str:
    chars = string.ascii_letters + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f"Welcome@{suffix}"


@router.post("/invite/direct-add")
def direct_add_member(
    payload: DirectAddMemberRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    """Create a user account directly — no email invite needed. Returns temp password for sharing."""
    allowed_roles = {"employee", "admin", "client"}
    if payload.role not in allowed_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(allowed_roles)}")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="A user with this email already exists.")

    temp_password = _generate_temp_password()
    parts = payload.full_name.strip().split(None, 1)
    user = User(
        email=payload.email,
        password=hash_password(temp_password),
        full_name=payload.full_name.strip(),
        first_name=parts[0] if parts else '',
        last_name=parts[1] if len(parts) > 1 else '',
        role=payload.role,
        tenant_id=current_user.tenant_id,
        position=payload.role_title,
        email_verified=True,
    )
    db.add(user)
    db.flush()

    # Add to org talent pool team
    team = get_or_create_org_pool_team(db, current_user.tenant_id, current_user.id)
    from app.models._team import TeamMember
    existing_membership = db.query(TeamMember).filter(
        TeamMember.team_id == team.id, TeamMember.user_id == user.id
    ).first()
    if not existing_membership:
        db.add(TeamMember(team_id=team.id, user_id=user.id, role_title=payload.role_title or payload.role))

    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "role_title": payload.role_title,
        "temp_password": temp_password,
    }
