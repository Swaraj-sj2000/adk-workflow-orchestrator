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


class SkillEntry(BaseModel):
    name: str
    rating: float = Field(ge=0.0, le=1.0)


class DirectAddMemberRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=100)
    role: str = Field(default="employee")
    role_title: str | None = None
    skills: list[SkillEntry] = []
    reliability: float = Field(default=0.5, ge=0.0, le=1.0)
    years_experience: float = Field(default=0.0, ge=0.0)
    joining_date: str | None = None  # ISO date string YYYY-MM-DD


class LLMBriefRequest(BaseModel):
    brief: str = Field(min_length=10, max_length=2000)
    company_domain: str  # e.g. "goldmine.ai"


def _generate_temp_password() -> str:
    chars = string.ascii_letters + string.digits
    suffix = ''.join(secrets.choice(chars) for _ in range(6))
    return f"Welcome@{suffix}"


@router.post("/invite/llm-brief")
def parse_employee_brief(
    payload: LLMBriefRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    """Use LLM to parse a free-text employee brief into a structured profile suggestion."""
    import json as _json
    import re

    try:
        from app.services._llm_service import LLMService, HumanMessage, SystemMessage

        llm = LLMService()
        if not llm.enabled:
            raise ValueError("LLM not available")

        temp_pw = _generate_temp_password()
        messages = [
            SystemMessage(content=(
                "You extract structured employee profile data from a free-text brief. "
                "Reply ONLY with valid JSON, no markdown, no explanation.\n"
                "Format:\n"
                '{"full_name":"string","email":"firstname.lastname@DOMAIN","role":"employee|admin|client",'
                '"role_title":"string","years_experience":float,"skills":[{"name":"string","rating":float 0-1}],'
                '"joining_date":"YYYY-MM-DD or null"}\n'
                f"Use domain: {payload.company_domain}. "
                "Skills rating 0-1 (e.g. 0.8 = strong, 0.5 = intermediate). "
                "joining_date: use today if not mentioned. "
                "Generate a realistic email from the person's name and the given domain."
            )),
            HumanMessage(content=payload.brief),
        ]

        raw = llm._invoke_text(messages)
        cleaned = re.sub(r"```[a-z]*\n?|```", "", raw).strip()
        data = _json.loads(cleaned)

        return {
            "full_name": data.get("full_name", ""),
            "email": data.get("email", ""),
            "role": data.get("role", "employee"),
            "role_title": data.get("role_title", ""),
            "years_experience": float(data.get("years_experience", 0)),
            "skills": data.get("skills", []),
            "joining_date": data.get("joining_date"),
            "suggested_password": temp_pw,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"LLM parse failed: {exc}")


@router.get("/invite/check-email")
def check_email_available(
    email: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    exists = db.query(User).filter(User.email == email).first() is not None
    return {"available": not exists, "email": email}


@router.post("/invite/direct-add")
def direct_add_member(
    payload: DirectAddMemberRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    """Create a user account directly with full profile. Returns credentials for sharing."""
    from datetime import date as _date
    from app.models._employee_profile import EmployeeProfile
    from app.models._employee_metrics import EmployeeMetrics
    from app.models._team import TeamMember

    allowed_roles = {"employee", "admin", "client"}
    if payload.role not in allowed_roles:
        raise HTTPException(status_code=400, detail=f"Role must be one of: {', '.join(allowed_roles)}")

    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="This email is already in use, please choose a different one.")

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

    # Parse joining date
    joining_date = None
    if payload.joining_date:
        try:
            joining_date = _date.fromisoformat(payload.joining_date)
        except ValueError:
            pass

    # Build skills dict
    skills_dict = {s.name: s.rating for s in payload.skills}

    # Create employee profile with XP/level/skills
    profile = EmployeeProfile(
        tenant_id=current_user.tenant_id,
        user_id=user.id,
        skills=skills_dict,
        xp=0,
        level=1,
        joining_date=joining_date,
        years_experience=payload.years_experience,
        pending_skills={},
    )
    db.add(profile)
    db.flush()

    # Create metrics with initial reliability set by CEO
    metrics = EmployeeMetrics(
        employee_id=profile.id,
        reliability_score=payload.reliability,
        efficiency_score=0.5,
    )
    db.add(metrics)

    # Add to org talent pool team
    team = get_or_create_org_pool_team(db, current_user.tenant_id, current_user.id)
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
        "skills": skills_dict,
        "reliability": payload.reliability,
        "years_experience": payload.years_experience,
    }


@router.delete("/invite/direct-add/{user_id}")
def delete_member(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    """Remove an employee/admin added by CEO. Cannot delete yourself."""
    from app.models._employee_profile import EmployeeProfile
    from datetime import datetime

    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot remove yourself.")

    user = db.query(User).filter(
        User.id == user_id,
        User.tenant_id == current_user.tenant_id,
        User.role.in_(["employee", "admin", "client"]),
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="Member not found in your organisation.")

    # Soft-delete employee profile
    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user_id).first()
    if profile:
        profile.deleted_at = datetime.utcnow()
        db.add(profile)

    # Remove team memberships
    from sqlalchemy import text
    db.execute(text("DELETE FROM team_members WHERE user_id = :uid"), {"uid": user_id})

    # Soft-delete user
    user.deleted_at = datetime.utcnow() if hasattr(user, "deleted_at") else None
    db.delete(user)

    db.commit()
    return {"deleted": True, "user_id": user_id}


# ── Skill change request flow ──────────────────────────────────────────────────

class SkillChangeRequestPayload(BaseModel):
    skill_name: str
    requested_value: float = Field(ge=0.0, le=1.0)


class SkillActionPayload(BaseModel):
    action: str  # approve / reject / suggest
    message: str | None = None


@router.post("/skills/request-change")
def request_skill_change(
    payload: SkillChangeRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Employee requests a skill rating change — goes to admin for approval."""
    from app.models._employee_profile import EmployeeProfile
    from app.models._skill_change_request import SkillChangeRequest

    profile = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == current_user.id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Employee profile not found.")

    current_val = (profile.skills or {}).get(payload.skill_name)
    if current_val is None:
        raise HTTPException(status_code=404, detail=f"Skill '{payload.skill_name}' not found in your profile.")

    # Check no pending request exists for this skill
    pending = db.query(SkillChangeRequest).filter(
        SkillChangeRequest.employee_profile_id == profile.id,
        SkillChangeRequest.skill_name == payload.skill_name,
        SkillChangeRequest.status == "pending",
    ).first()
    if pending:
        raise HTTPException(status_code=409, detail="A pending request for this skill already exists.")

    req = SkillChangeRequest(
        tenant_id=current_user.tenant_id,
        employee_profile_id=profile.id,
        user_id=current_user.id,
        skill_name=payload.skill_name,
        current_value=current_val,
        requested_value=payload.requested_value,
        status="pending",
    )
    db.add(req)

    # Mark in pending_skills on profile
    pending_skills = dict(profile.pending_skills or {})
    pending_skills[payload.skill_name] = {
        "current": current_val,
        "requested": payload.requested_value,
    }
    profile.pending_skills = pending_skills
    db.add(profile)
    db.commit()
    db.refresh(req)

    return {"request_id": req.id, "skill": payload.skill_name, "status": "pending"}


@router.get("/skills/approvals")
def list_skill_approvals(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    """List all pending skill change requests for the tenant."""
    from app.models._skill_change_request import SkillChangeRequest
    from app.models._employee_profile import EmployeeProfile

    rows = (
        db.query(SkillChangeRequest, User, EmployeeProfile)
        .join(User, User.id == SkillChangeRequest.user_id)
        .join(EmployeeProfile, EmployeeProfile.id == SkillChangeRequest.employee_profile_id)
        .filter(
            SkillChangeRequest.tenant_id == current_user.tenant_id,
            SkillChangeRequest.status == "pending",
        )
        .order_by(SkillChangeRequest.created_at.desc())
        .all()
    )

    return [
        {
            "id": req.id,
            "employee_name": user.full_name or user.email,
            "employee_email": user.email,
            "skill_name": req.skill_name,
            "current_value": req.current_value,
            "requested_value": req.requested_value,
            "status": req.status,
            "created_at": req.created_at.isoformat() if req.created_at else None,
        }
        for req, user, profile in rows
    ]


@router.post("/skills/approvals/{request_id}/action")
def action_skill_request(
    request_id: int,
    payload: SkillActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    """Approve, reject, or suggest changes on a skill change request."""
    from datetime import datetime
    from app.models._skill_change_request import SkillChangeRequest
    from app.models._employee_profile import EmployeeProfile

    if payload.action not in ("approve", "reject", "suggest"):
        raise HTTPException(status_code=400, detail="Action must be approve, reject, or suggest.")

    req = db.query(SkillChangeRequest).filter(
        SkillChangeRequest.id == request_id,
        SkillChangeRequest.tenant_id == current_user.tenant_id,
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    if req.status != "pending":
        raise HTTPException(status_code=409, detail="Request already resolved.")

    profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == req.employee_profile_id).first()

    req.status = payload.action
    req.admin_message = payload.message
    req.resolved_by = current_user.id
    req.resolved_at = datetime.utcnow()

    if payload.action == "approve" and profile:
        skills = dict(profile.skills or {})
        skills[req.skill_name] = req.requested_value
        profile.skills = skills
        db.add(profile)

    # Remove from pending_skills on profile
    if profile:
        pending = dict(profile.pending_skills or {})
        pending.pop(req.skill_name, None)
        profile.pending_skills = pending
        db.add(profile)

    db.add(req)
    db.commit()

    return {
        "request_id": req.id,
        "action": payload.action,
        "skill": req.skill_name,
        "message": payload.message,
    }
