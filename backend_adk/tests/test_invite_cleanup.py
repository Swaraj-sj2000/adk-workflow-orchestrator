from datetime import datetime

from sqlalchemy.orm import Session

from app.models._project import Project
from app.models._team import Team
from app.models._team_invite import TeamInvite
from app.models._tenant import Tenant
from app.models._user import User
from app.services._maintenance_service import cancel_stale_project_team_invites
from app.services._project_service import build_team_dashboard


def _make_tenant(db: Session, slug: str = "cleanupco") -> Tenant:
    tenant = Tenant(name=slug.title(), slug=slug)
    db.add(tenant)
    db.flush()
    return tenant


def _make_admin(db: Session, tenant_id: int, email: str = "admin@cleanupco.com") -> User:
    admin = User(
        email=email,
        password="x",
        full_name="Cleanup Admin",
        role="admin",
        tenant_id=tenant_id,
        email_verified=True,
    )
    db.add(admin)
    db.flush()
    return admin


def _make_project(db: Session, tenant_id: int, admin_id: int, *, deleted: bool) -> Project:
    project = Project(
        tenant_id=tenant_id,
        name="Cleanup Project",
        description="Cleanup test",
        admin_id=admin_id,
        status="planning",
        budget=1000.0,
        deleted_at=datetime.utcnow() if deleted else None,
    )
    db.add(project)
    db.flush()
    return project


def _make_team(db: Session, tenant_id: int, project_id: int, admin_id: int) -> Team:
    team = Team(
        tenant_id=tenant_id,
        project_id=project_id,
        name="Cleanup Team",
        created_by_user_id=admin_id,
    )
    db.add(team)
    db.flush()
    return team


def _make_invite(db: Session, tenant_id: int, team_id: int, admin_id: int, email: str) -> TeamInvite:
    invite = TeamInvite(
        tenant_id=tenant_id,
        team_id=team_id,
        email=email,
        status="pending",
        token=f"tok-{email}",
        role_title="Engineer",
        invited_by_user_id=admin_id,
    )
    db.add(invite)
    db.flush()
    return invite


def test_team_dashboard_hides_pending_invites_for_deleted_projects(db: Session):
    tenant = _make_tenant(db, "cleanupdash")
    admin = _make_admin(db, tenant.id, "dash-admin@cleanupco.com")
    project = _make_project(db, tenant.id, admin.id, deleted=True)
    team = _make_team(db, tenant.id, project.id, admin.id)
    _make_invite(db, tenant.id, team.id, admin.id, "hidden@cleanupco.com")
    db.commit()

    dashboard = build_team_dashboard(db, admin)

    assert dashboard["pending_invites"] == []


def test_cleanup_service_dry_run_then_apply(db: Session):
    tenant = _make_tenant(db, "cleanupapply")
    admin = _make_admin(db, tenant.id, "apply-admin@cleanupco.com")
    deleted_project = _make_project(db, tenant.id, admin.id, deleted=True)
    active_project = _make_project(db, tenant.id, admin.id, deleted=False)
    deleted_team = _make_team(db, tenant.id, deleted_project.id, admin.id)
    active_team = _make_team(db, tenant.id, active_project.id, admin.id)
    stale_invite = _make_invite(db, tenant.id, deleted_team.id, admin.id, "stale@cleanupco.com")
    active_invite = _make_invite(db, tenant.id, active_team.id, admin.id, "active@cleanupco.com")
    db.commit()

    dry_run = cancel_stale_project_team_invites(db, tenant_id=tenant.id, apply=False)

    assert dry_run["matched"] == 1
    assert dry_run["updated"] == 0
    assert dry_run["invites"][0]["invite_id"] == stale_invite.id

    db.refresh(stale_invite)
    db.refresh(active_invite)
    assert stale_invite.status == "pending"
    assert active_invite.status == "pending"

    applied = cancel_stale_project_team_invites(db, tenant_id=tenant.id, apply=True)
    db.commit()

    assert applied["matched"] == 1
    assert applied["updated"] == 1

    db.refresh(stale_invite)
    db.refresh(active_invite)
    assert stale_invite.status == "cancelled"
    assert active_invite.status == "pending"
