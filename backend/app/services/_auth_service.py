# backend/app/services/_auth_service.py
import re
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models._client_profile import ClientProfile
from app.models._employee_metrics import EmployeeMetrics
from app.models._employee_profile import EmployeeProfile
from app.models._team_invite import TeamInvite
from app.models._tenant import Tenant
from app.models._user import User
from app.core._security import hash_password, verify_password, create_access_token
from app.services._invite_service import link_pending_invites_for_user, normalize_email


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return cleaned or "tenant"


def ensure_default_tenant(db: Session) -> Tenant:
    tenant = db.query(Tenant).filter(Tenant.slug == "default").first()
    if tenant:
        return tenant

    tenant = Tenant(name="Default Organization", slug="default")
    db.add(tenant)
    db.flush()
    return tenant


def bootstrap_tenant_data(db: Session) -> Tenant:
    default_tenant = ensure_default_tenant(db)

    users = db.query(User).filter(User.tenant_id.is_(None)).all()
    for user in users:
        user.tenant_id = default_tenant.id
        db.add(user)

    employee_profiles = db.query(EmployeeProfile).filter(EmployeeProfile.tenant_id.is_(None)).all()
    for profile in employee_profiles:
        profile.tenant_id = profile.user.tenant_id if profile.user else default_tenant.id
        db.add(profile)

    client_profiles = db.query(ClientProfile).filter(ClientProfile.tenant_id.is_(None)).all()
    for profile in client_profiles:
        profile.tenant_id = profile.user.tenant_id if profile.user else default_tenant.id
        db.add(profile)

    from app.models._project import Project
    from app.models._task import Task

    projects = db.query(Project).filter(Project.tenant_id.is_(None)).all()
    for project in projects:
        admin = db.query(User).filter(User.id == project.admin_id).first()
        project.tenant_id = admin.tenant_id if admin and admin.tenant_id else default_tenant.id
        db.add(project)

    tasks = db.query(Task).filter(Task.tenant_id.is_(None)).all()
    for task in tasks:
        task.tenant_id = task.project.tenant_id if task.project else default_tenant.id
        db.add(task)

    db.flush()
    return default_tenant


def _resolve_registration_tenant(
    db: Session,
    *,
    email: str,
    role: str,
    tenant_name: str | None = None,
    tenant_slug: str | None = None,
) -> Tenant:
    pending_invites = db.query(TeamInvite).filter(TeamInvite.email == email, TeamInvite.status == "pending").all()
    invite_tenant_ids = {invite.tenant_id for invite in pending_invites}
    if invite_tenant_ids:
        if len(invite_tenant_ids) > 1:
            raise HTTPException(status_code=409, detail="This email has pending invites across multiple tenants")
        tenant = db.query(Tenant).filter(Tenant.id == next(iter(invite_tenant_ids))).first()
        if not tenant:
            raise HTTPException(status_code=404, detail="Invite tenant not found")
        return tenant

    if tenant_slug:
        tenant = db.query(Tenant).filter(Tenant.slug == _slugify(tenant_slug)).first()
        if tenant:
            return tenant
        if role != "admin":
            raise HTTPException(status_code=404, detail="Requested tenant not found")
        tenant = Tenant(name=tenant_name or tenant_slug.strip(), slug=_slugify(tenant_slug))
        db.add(tenant)
        db.flush()
        return tenant

    if role == "admin":
        domain = email.split("@", 1)[1]
        slug = _slugify(domain.replace(".", "-"))
        tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        if tenant:
            return tenant
        tenant = Tenant(name=tenant_name or domain.title(), slug=slug)
        db.add(tenant)
        db.flush()
        return tenant

    return ensure_default_tenant(db)


def _ensure_employee_profile(db: Session, user: User) -> None:
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user.id).first()
    if profile:
        return

    profile = EmployeeProfile(
        tenant_id=user.tenant_id,
        user_id=user.id,
        skills={},
        max_capacity=8.0,
        current_load=0.0,
        department="General Delivery",
        availability_status="available",
    )
    db.add(profile)
    db.flush()

    metrics = db.query(EmployeeMetrics).filter(EmployeeMetrics.employee_id == profile.id).first()
    if not metrics:
        db.add(
            EmployeeMetrics(
                employee_id=profile.id,
                efficiency_score=0.8,
                reliability_score=0.8,
                avg_completion_time=0.0,
                total_tasks_completed=0,
                total_tasks_failed=0,
                total_tasks_delayed=0,
            )
        )


def _ensure_client_profile(db: Session, user: User) -> None:
    profile = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    if profile:
        return

    db.add(
        ClientProfile(
            tenant_id=user.tenant_id,
            user_id=user.id,
            company_name=user.full_name or user.email,
            contact_person=user.full_name,
        )
    )


def register_user(
    db: Session,
    email: str,
    password: str,
    full_name: str,
    role: str,
    tenant_name: str | None = None,
    tenant_slug: str | None = None,
):
    email = normalize_email(email)
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    bootstrap_tenant_data(db)
    tenant = _resolve_registration_tenant(
        db,
        email=email,
        role=role,
        tenant_name=tenant_name,
        tenant_slug=tenant_slug,
    )

    pending_invites = db.query(TeamInvite).filter(TeamInvite.email == email, TeamInvite.status == "pending").count()
    effective_role = "employee" if pending_invites and role != "admin" else role

    user = User(
        email=email,
        password=hash_password(password),
        full_name=full_name.strip(),
        role=effective_role,
        tenant_id=tenant.id,
    )
    db.add(user)
    db.flush()

    if user.role == "employee":
        _ensure_employee_profile(db, user)
    elif user.role == "client":
        _ensure_client_profile(db, user)

    link_pending_invites_for_user(db, user)

    db.commit()
    db.refresh(user)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "tenant_slug": tenant.slug,
        "tenant_name": tenant.name,
    }


def login_user(db: Session, email: str, password: str):
    bootstrap_tenant_data(db)
    email = normalize_email(email)
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password):
        return None

    tenant = db.query(Tenant).filter(Tenant.id == user.tenant_id).first() if user.tenant_id else None
    token = create_access_token({"user_id": user.id, "role": user.role, "tenant_id": user.tenant_id, "email": user.email})
    user_data = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "tenant_id": user.tenant_id,
        "tenant_slug": tenant.slug if tenant else None,
        "tenant_name": tenant.name if tenant else None,
    }
    return token, user_data
