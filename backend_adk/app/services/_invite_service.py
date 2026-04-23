import secrets
from datetime import datetime
from typing import List, Optional, Tuple

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
from app.models._team import Team, TeamMember
from app.models._team_invite import TeamInvite
from app.models._user import User
from app.services._email_service import EmailService


def normalize_email(email: str) -> str:
    return email.strip().lower()


def get_or_create_project_team(db: Session, project: Project, created_by_user_id: int) -> Team:
    team = db.query(Team).filter(Team.project_id == project.id).first()
    if team:
        return team

    team = Team(
        tenant_id=project.tenant_id,
        project_id=project.id,
        name=f"{project.name} Core Team",
        created_by_user_id=created_by_user_id,
    )
    db.add(team)
    db.flush()
    return team


def create_team_invite(
    db: Session,
    *,
    team: Team,
    tenant_id: int,
    email: str,
    invited_by_user_id: int,
    role_title: Optional[str] = None,
    note: Optional[str] = None,
) -> Tuple[TeamInvite, Optional[User]]:
    normalized_email = normalize_email(email)

    existing = (
        db.query(TeamInvite)
        .filter(
            TeamInvite.team_id == team.id,
            TeamInvite.email == normalized_email,
            TeamInvite.status.in_(["pending", "accepted"]),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="An active invite already exists for this email on the selected team")

    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user and existing_user.tenant_id != tenant_id:
        raise HTTPException(status_code=409, detail="This email already belongs to a different tenant")

    invite = TeamInvite(
        tenant_id=tenant_id,
        team_id=team.id,
        email=normalized_email,
        status="pending",
        token=secrets.token_urlsafe(24),
        role_title=role_title,
        invited_by_user_id=invited_by_user_id,
        invited_user_id=existing_user.id if existing_user else None,
        note=note,
    )
    db.add(invite)
    db.flush()

    inviter = db.query(User).filter(User.id == invited_by_user_id).first()
    project = db.query(Project).filter(Project.id == team.project_id, Project.tenant_id == tenant_id).first()
    EmailService.send_invite_email(
        to_email=normalized_email,
        inviter_name=inviter.full_name if inviter and inviter.full_name else (inviter.email if inviter else "A teammate"),
        project_name=project.name if project else team.name,
        role_title=role_title or "Contributor",
        invite_token=invite.token,
        tenant_id=tenant_id,
    )
    return invite, existing_user


def list_user_invites(db: Session, user: User) -> List[TeamInvite]:
    return (
        db.query(TeamInvite)
        .filter(
            TeamInvite.tenant_id == user.tenant_id,
            TeamInvite.status == "pending",
            TeamInvite.email == normalize_email(user.email),
        )
        .order_by(TeamInvite.created_at.desc())
        .all()
    )


def link_pending_invites_for_user(db: Session, user: User) -> List[TeamInvite]:
    invites = (
        db.query(TeamInvite)
        .filter(
            TeamInvite.email == normalize_email(user.email),
            TeamInvite.status == "pending",
        )
        .all()
    )

    for invite in invites:
        if invite.tenant_id != user.tenant_id:
            raise HTTPException(status_code=409, detail="Pending invites exist for a different tenant")
        invite.invited_user_id = user.id
        db.add(invite)

    return invites


def get_invite_for_actor(db: Session, *, invite_id: Optional[int], token: Optional[str], actor: User) -> TeamInvite:
    invite = None
    if invite_id is not None:
        invite = db.query(TeamInvite).filter(TeamInvite.id == invite_id).first()
    elif token:
        invite = db.query(TeamInvite).filter(TeamInvite.token == token).first()

    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    if invite.tenant_id != actor.tenant_id:
        raise HTTPException(status_code=403, detail="Invite does not belong to your tenant")
    if normalize_email(invite.email) != normalize_email(actor.email):
        raise HTTPException(status_code=403, detail="Invite email does not match the logged-in user")
    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="Invite has already been processed")

    return invite


def apply_invite_response(
    db: Session,
    *,
    invite: TeamInvite,
    actor: User,
    accepted: bool,
    note: Optional[str] = None,
) -> Optional[TeamMember]:
    invite.status = "accepted" if accepted else "rejected"
    invite.responded_by_user_id = actor.id
    invite.invited_user_id = actor.id
    invite.note = note or invite.note
    invite.responded_at = datetime.utcnow()
    db.add(invite)

    if not accepted:
        return None

    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == actor.id).first()
    member = (
        db.query(TeamMember)
        .filter(TeamMember.team_id == invite.team_id, TeamMember.user_id == actor.id)
        .first()
    )
    if member:
        return member

    member = TeamMember(
        tenant_id=invite.tenant_id,
        team_id=invite.team_id,
        user_id=actor.id,
        employee_profile_id=profile.id if profile else None,
        role_title=invite.role_title,
        status="active",
    )
    db.add(member)
    db.flush()
    return member


def find_project_invite_for_actor(db: Session, project_id: int, actor: User) -> TeamInvite:
    invite = (
        db.query(TeamInvite)
        .join(Team, Team.id == TeamInvite.team_id)
        .filter(
            Team.project_id == project_id,
            TeamInvite.tenant_id == actor.tenant_id,
            TeamInvite.email == normalize_email(actor.email),
        )
        .order_by(TeamInvite.created_at.desc())
        .first()
    )
    if not invite:
        raise HTTPException(status_code=404, detail="No invite found for this project")
    return invite
