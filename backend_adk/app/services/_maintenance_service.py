from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models._project import Project
from app.models._team import Team
from app.models._team_invite import TeamInvite


def list_stale_project_team_invites(
    db: Session,
    *,
    tenant_id: Optional[int] = None,
    project_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    query = (
        db.query(TeamInvite, Team, Project)
        .join(Team, Team.id == TeamInvite.team_id)
        .join(Project, Project.id == Team.project_id)
        .filter(TeamInvite.status == "pending", Project.deleted_at.is_not(None))
        .order_by(Project.deleted_at.desc(), TeamInvite.created_at.asc())
    )
    if tenant_id is not None:
        query = query.filter(TeamInvite.tenant_id == tenant_id)
    if project_id is not None:
        query = query.filter(Project.id == project_id)
    if limit is not None:
        query = query.limit(limit)

    rows = query.all()
    return [
        {
            "invite_id": invite.id,
            "tenant_id": invite.tenant_id,
            "team_id": invite.team_id,
            "project_id": project.id,
            "project_name": project.name,
            "project_deleted_at": project.deleted_at.isoformat() if project.deleted_at else None,
            "email": invite.email,
            "role_title": invite.role_title,
            "status": invite.status,
            "created_at": invite.created_at.isoformat() if invite.created_at else None,
        }
        for invite, _team, project in rows
    ]


def cancel_stale_project_team_invites(
    db: Session,
    *,
    tenant_id: Optional[int] = None,
    project_id: Optional[int] = None,
    limit: Optional[int] = None,
    apply: bool = False,
) -> Dict[str, Any]:
    stale_invites = list_stale_project_team_invites(
        db,
        tenant_id=tenant_id,
        project_id=project_id,
        limit=limit,
    )

    updated = 0
    if apply and stale_invites:
        invite_ids = [row["invite_id"] for row in stale_invites]
        invites = db.query(TeamInvite).filter(TeamInvite.id.in_(invite_ids)).all()
        for invite in invites:
            invite.status = "cancelled"
            db.add(invite)
            updated += 1

    return {
        "matched": len(stale_invites),
        "updated": updated,
        "dry_run": not apply,
        "invites": stale_invites,
    }
