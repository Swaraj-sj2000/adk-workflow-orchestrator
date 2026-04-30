from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core._deps import get_current_user, require_ceo_or_admin
from app.db._database import get_db
from app.models._employee_profile import EmployeeProfile
from app.models._notification import Notification
from app.models._team_invite_request import TeamInviteRequest
from app.models._team_size_request import TeamSizeRequest
from app.models._user import User
from app.services._llm_service import LLMService, HumanMessage, SystemMessage

router = APIRouter(tags=["Company"])

_llm = LLMService()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _notify(db, tenant_id, user_id, ntype, title, body, ref_type=None, ref_id=None):
    annotation = None
    try:
        if _llm.enabled:
            annotation = _llm._invoke_text([
                SystemMessage(content="You are a concise notification assistant. In one short sentence, tell the recipient what they should focus on or do next based on this notification. No headers, no bullet points."),
                HumanMessage(content=f"Type: {ntype}\nTitle: {title}\nBody: {body}"),
            ]) or None
    except Exception:
        pass
    db.add(Notification(
        tenant_id=tenant_id, user_id=user_id,
        type=ntype, title=title, body=body,
        llm_annotation=annotation,
        reference_type=ref_type, reference_id=ref_id,
    ))


def _get_ceo(db: Session, tenant_id: int) -> Optional[User]:
    return db.query(User).filter(
        User.tenant_id == tenant_id,
        User.role == "ceo",
        User.deleted_at.is_(None),
    ).first()


def _profile_of(db: Session, user_id: int, tenant_id: int) -> Optional[EmployeeProfile]:
    return db.query(EmployeeProfile).filter(
        EmployeeProfile.user_id == user_id,
        EmployeeProfile.tenant_id == tenant_id,
        EmployeeProfile.deleted_at.is_(None),
    ).first()


def _user_of(db: Session, profile: EmployeeProfile) -> Optional[User]:
    if not profile:
        return None
    return db.query(User).filter(User.id == profile.user_id).first()


def _name(user: Optional[User]) -> str:
    if not user:
        return "Unknown"
    return user.full_name or user.email


def _invite_summary(db: Session, inv: TeamInviteRequest) -> dict:
    emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == inv.employee_id).first()
    req_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == inv.requester_id).first()
    emp_user = _user_of(db, emp_profile)
    req_user = _user_of(db, req_profile)
    return {
        "id": inv.id,
        "status": inv.status,
        "proposed_role": inv.proposed_role,
        "rejection_reason": inv.rejection_reason,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "employee": {
            "profile_id": inv.employee_id,
            "name": _name(emp_user),
            "email": emp_user.email if emp_user else "",
            "role_title": emp_user.position if emp_user else "",
        },
        "requester": {
            "profile_id": inv.requester_id,
            "name": _name(req_user),
            "email": req_user.email if req_user else "",
        },
    }


# ── Company directory ─────────────────────────────────────────────────────────

@router.get("/company/directory")
def company_directory(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    users = (
        db.query(User)
        .filter(
            User.tenant_id == current_user.tenant_id,
            User.deleted_at.is_(None),
            User.role.in_(["employee", "admin"]),
        )
        .all()
    )

    # Requester's own profile (for pending invite detection)
    my_profile = _profile_of(db, current_user.id, current_user.tenant_id)

    result = []
    for u in users:
        profile = db.query(EmployeeProfile).filter(
            EmployeeProfile.user_id == u.id,
            EmployeeProfile.deleted_at.is_(None),
        ).first()

        manager_info = None
        if profile and profile.manager_id:
            mgr_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == profile.manager_id).first()
            mgr_user = _user_of(db, mgr_profile)
            if mgr_user:
                manager_info = {
                    "profile_id": profile.manager_id,
                    "name": _name(mgr_user),
                    "email": mgr_user.email,
                }

        # Check if I already have a pending invite for this person
        pending_invite = None
        if my_profile and profile:
            req = db.query(TeamInviteRequest).filter(
                TeamInviteRequest.employee_id == profile.id,
                TeamInviteRequest.requester_id == my_profile.id,
                TeamInviteRequest.status.in_(["pending_ceo", "pending_manager", "pending_employee"]),
                TeamInviteRequest.tenant_id == current_user.tenant_id,
            ).first()
            if req:
                pending_invite = {"id": req.id, "status": req.status}

        result.append({
            "user_id": u.id,
            "profile_id": profile.id if profile else None,
            "name": u.full_name or u.email,
            "email": u.email,
            "role": u.role,
            "role_title": u.position,
            "availability_status": profile.availability_status if profile else "unknown",
            "manager": manager_info,
            "pending_invite": pending_invite,
        })

    return result


# ── Send invite request ───────────────────────────────────────────────────────

class InviteRequestPayload(BaseModel):
    employee_profile_id: int
    proposed_role: Optional[str] = None


@router.post("/company/invite-request")
def send_invite_request(
    payload: InviteRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    my_profile = _profile_of(db, current_user.id, current_user.tenant_id)
    if not my_profile:
        raise HTTPException(status_code=400, detail="Your employee profile was not found.")

    emp_profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.id == payload.employee_profile_id,
        EmployeeProfile.tenant_id == current_user.tenant_id,
        EmployeeProfile.deleted_at.is_(None),
    ).first()
    if not emp_profile:
        raise HTTPException(status_code=404, detail="Employee not found.")

    if emp_profile.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot invite yourself.")

    existing = db.query(TeamInviteRequest).filter(
        TeamInviteRequest.employee_id == payload.employee_profile_id,
        TeamInviteRequest.requester_id == my_profile.id,
        TeamInviteRequest.status.in_(["pending_ceo", "pending_manager", "pending_employee"]),
        TeamInviteRequest.tenant_id == current_user.tenant_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A pending invite already exists for this person.")

    # Team size enforcement for admins
    if current_user.role == "admin":
        team_count = db.query(EmployeeProfile).filter(
            EmployeeProfile.tenant_id == current_user.tenant_id,
            EmployeeProfile.manager_id == my_profile.id,
            EmployeeProfile.deleted_at.is_(None),
        ).count()
        limit = my_profile.max_team_size if my_profile.max_team_size is not None else 10
        if team_count >= limit:
            raise HTTPException(
                status_code=400,
                detail=f"Your team is at its size limit ({limit} members). Submit a size increase request to your CEO.",
            )

    emp_user = _user_of(db, emp_profile)
    emp_name = _name(emp_user)
    req_name = _name(current_user)
    role_label = payload.proposed_role or "team member"

    if emp_profile.manager_id is None:
        # Flow A — unassigned: CEO must approve first
        invite = TeamInviteRequest(
            tenant_id=current_user.tenant_id,
            requester_id=my_profile.id,
            employee_id=payload.employee_profile_id,
            proposed_role=payload.proposed_role,
            status="pending_ceo",
        )
        db.add(invite)
        db.flush()

        ceo = _get_ceo(db, current_user.tenant_id)
        if ceo:
            _notify(db, current_user.tenant_id, ceo.id,
                "approval_needed",
                f"{req_name} wants to add {emp_name} to their team",
                f"{req_name} has requested to add {emp_name} (currently unassigned) as {role_label}. Please approve or reject.",
                "team_invite_request", invite.id)
    else:
        # Flow B — has manager: current manager approves first
        invite = TeamInviteRequest(
            tenant_id=current_user.tenant_id,
            requester_id=my_profile.id,
            employee_id=payload.employee_profile_id,
            proposed_role=payload.proposed_role,
            status="pending_manager",
            current_manager_id=emp_profile.manager_id,
        )
        db.add(invite)
        db.flush()

        mgr_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == emp_profile.manager_id).first()
        if mgr_profile:
            _notify(db, current_user.tenant_id, mgr_profile.user_id,
                "approval_needed",
                f"{req_name} wants to move {emp_name} from your team",
                f"{req_name} has requested to add {emp_name} to their team as {role_label}. Please approve or reject.",
                "team_invite_request", invite.id)

    db.commit()
    return {"invite_request_id": invite.id, "status": invite.status}


# ── CEO action ────────────────────────────────────────────────────────────────

class ActionPayload(BaseModel):
    approved: bool
    reason: Optional[str] = None


@router.post("/company/invite-request/{request_id}/ceo-action")
def ceo_action(
    request_id: int,
    payload: ActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "ceo":
        raise HTTPException(status_code=403, detail="CEO only.")

    invite = db.query(TeamInviteRequest).filter(
        TeamInviteRequest.id == request_id,
        TeamInviteRequest.tenant_id == current_user.tenant_id,
        TeamInviteRequest.status == "pending_ceo",
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Request not found or already resolved.")

    emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == invite.employee_id).first()
    req_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == invite.requester_id).first()
    emp_user = _user_of(db, emp_profile)
    req_user = _user_of(db, req_profile)
    emp_name = _name(emp_user)
    req_name = _name(req_user)
    role_label = invite.proposed_role or "team member"

    if payload.approved:
        invite.status = "pending_employee"
        if emp_user:
            _notify(db, current_user.tenant_id, emp_user.id,
                "invite_received",
                f"{req_name} wants you to join their team",
                f"{req_name} has invited you to join their team as {role_label}. Approved by CEO.",
                "team_invite_request", invite.id)
    else:
        invite.status = "rejected_by_ceo"
        invite.rejection_reason = payload.reason
        if req_user:
            _notify(db, current_user.tenant_id, req_user.id,
                "rejection_record",
                f"Your request to add {emp_name} was rejected by CEO",
                payload.reason or "No reason provided.",
                "team_invite_request", invite.id)

    invite.updated_at = datetime.utcnow()
    db.add(invite)
    db.commit()
    return {"status": invite.status}


# ── Manager action ────────────────────────────────────────────────────────────

@router.post("/company/invite-request/{request_id}/manager-action")
def manager_action(
    request_id: int,
    payload: ActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    invite = db.query(TeamInviteRequest).filter(
        TeamInviteRequest.id == request_id,
        TeamInviteRequest.tenant_id == current_user.tenant_id,
        TeamInviteRequest.status == "pending_manager",
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Request not found or already resolved.")

    my_profile = _profile_of(db, current_user.id, current_user.tenant_id)
    if not my_profile or my_profile.id != invite.current_manager_id:
        raise HTTPException(status_code=403, detail="Only the employee's current manager can act on this.")

    emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == invite.employee_id).first()
    req_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == invite.requester_id).first()
    emp_user = _user_of(db, emp_profile)
    req_user = _user_of(db, req_profile)
    emp_name = _name(emp_user)
    req_name = _name(req_user)
    mgr_name = _name(current_user)
    role_label = invite.proposed_role or "team member"
    ceo = _get_ceo(db, current_user.tenant_id)

    if payload.approved:
        invite.status = "pending_employee"
        if ceo:
            _notify(db, current_user.tenant_id, ceo.id,
                "fyi",
                f"{emp_name} is being transferred to {req_name}'s team",
                f"{mgr_name} approved the transfer of {emp_name} to {req_name}'s team. No action needed.",
                "team_invite_request", invite.id)
        if emp_user:
            _notify(db, current_user.tenant_id, emp_user.id,
                "invite_received",
                f"{req_name} wants you to join their team",
                f"{req_name} has invited you to join their team as {role_label}. Already approved by your manager {mgr_name}.",
                "team_invite_request", invite.id)
    else:
        invite.status = "rejected_by_manager"
        invite.rejection_reason = payload.reason
        if ceo:
            _notify(db, current_user.tenant_id, ceo.id,
                "escalation",
                f"Transfer of {emp_name} blocked by their manager",
                f"{mgr_name} rejected {req_name}'s request to move {emp_name}. Reason: {payload.reason or 'None provided.'}",
                "team_invite_request", invite.id)

    invite.updated_at = datetime.utcnow()
    db.add(invite)
    db.commit()
    return {"status": invite.status}


# ── Employee action ───────────────────────────────────────────────────────────

class EmployeeActionPayload(BaseModel):
    accepted: bool
    reason: Optional[str] = None


@router.post("/company/invite-request/{request_id}/employee-action")
def employee_action(
    request_id: int,
    payload: EmployeeActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    invite = db.query(TeamInviteRequest).filter(
        TeamInviteRequest.id == request_id,
        TeamInviteRequest.tenant_id == current_user.tenant_id,
        TeamInviteRequest.status == "pending_employee",
    ).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found or already resolved.")

    emp_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == invite.employee_id).first()
    if not emp_profile or emp_profile.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="This invite is not for you.")

    req_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == invite.requester_id).first()
    req_user = _user_of(db, req_profile)
    req_name = _name(req_user)
    emp_name = _name(current_user)
    ceo = _get_ceo(db, current_user.tenant_id)

    if payload.accepted:
        invite.status = "accepted"
        emp_profile.manager_id = invite.requester_id
        db.add(emp_profile)
        if req_user:
            _notify(db, current_user.tenant_id, req_user.id,
                "accepted",
                f"{emp_name} accepted your team invite",
                f"{emp_name} has joined your team as {invite.proposed_role or 'team member'}.",
                "team_invite_request", invite.id)
    else:
        invite.status = "rejected_by_employee"
        invite.rejection_reason = payload.reason
        reason_text = payload.reason or "No reason provided."
        if req_user:
            _notify(db, current_user.tenant_id, req_user.id,
                "rejection_record",
                f"{emp_name} declined your team invite",
                f"{emp_name} declined to join your team. Reason: {reason_text}",
                "team_invite_request", invite.id)
        if ceo:
            _notify(db, current_user.tenant_id, ceo.id,
                "rejection_record",
                f"{emp_name} declined {req_name}'s team invite",
                f"{emp_name} declined to join {req_name}'s team. Reason: {reason_text}",
                "team_invite_request", invite.id)
        # Also notify previous manager if applicable
        if invite.current_manager_id:
            mgr_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == invite.current_manager_id).first()
            if mgr_profile:
                _notify(db, current_user.tenant_id, mgr_profile.user_id,
                    "rejection_record",
                    f"{emp_name} declined transfer to {req_name}'s team",
                    f"{emp_name} declined to move to {req_name}'s team. Reason: {reason_text}",
                    "team_invite_request", invite.id)

    invite.updated_at = datetime.utcnow()
    db.add(invite)
    db.commit()
    return {"status": invite.status}


# ── Pending requests for current user ─────────────────────────────────────────

@router.get("/company/invite-requests/pending")
def pending_invite_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    my_profile = _profile_of(db, current_user.id, current_user.tenant_id)

    if current_user.role == "ceo":
        invites = db.query(TeamInviteRequest).filter(
            TeamInviteRequest.tenant_id == current_user.tenant_id,
            TeamInviteRequest.status == "pending_ceo",
        ).order_by(TeamInviteRequest.created_at.desc()).all()
    elif current_user.role == "admin":
        if not my_profile:
            return []
        invites = db.query(TeamInviteRequest).filter(
            TeamInviteRequest.tenant_id == current_user.tenant_id,
            TeamInviteRequest.status == "pending_manager",
            TeamInviteRequest.current_manager_id == my_profile.id,
        ).order_by(TeamInviteRequest.created_at.desc()).all()
    else:
        if not my_profile:
            return []
        invites = db.query(TeamInviteRequest).filter(
            TeamInviteRequest.tenant_id == current_user.tenant_id,
            TeamInviteRequest.status == "pending_employee",
            TeamInviteRequest.employee_id == my_profile.id,
        ).order_by(TeamInviteRequest.created_at.desc()).all()

    return [_invite_summary(db, inv) for inv in invites]


# ── Notifications ─────────────────────────────────────────────────────────────

@router.get("/notifications")
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notifs = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.tenant_id == current_user.tenant_id,
        )
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "llm_annotation": n.llm_annotation,
            "reference_type": n.reference_type,
            "reference_id": n.reference_id,
            "read": n.read_at is not None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in notifs
    ]


@router.get("/notifications/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        db.query(Notification)
        .filter(
            Notification.user_id == current_user.id,
            Notification.tenant_id == current_user.tenant_id,
            Notification.read_at.is_(None),
        )
        .count()
    )
    return {"count": count}


@router.patch("/notifications/{notification_id}/read")
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    n = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ).first()
    if not n:
        raise HTTPException(status_code=404, detail="Not found.")
    n.read_at = datetime.utcnow()
    db.add(n)
    db.commit()
    return {"read": True}


@router.patch("/notifications/read-all")
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(Notification).filter(
        Notification.user_id == current_user.id,
        Notification.tenant_id == current_user.tenant_id,
        Notification.read_at.is_(None),
    ).update({"read_at": datetime.utcnow()})
    db.commit()
    return {"ok": True}


# ── Team size limit ───────────────────────────────────────────────────────────

@router.get("/company/my-team-limit")
def my_team_limit(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    my_profile = _profile_of(db, current_user.id, current_user.tenant_id)
    if not my_profile:
        raise HTTPException(status_code=400, detail="Employee profile not found.")

    current_count = db.query(EmployeeProfile).filter(
        EmployeeProfile.tenant_id == current_user.tenant_id,
        EmployeeProfile.manager_id == my_profile.id,
        EmployeeProfile.deleted_at.is_(None),
    ).count()

    limit = my_profile.max_team_size if my_profile.max_team_size is not None else 10

    pending = db.query(TeamSizeRequest).filter(
        TeamSizeRequest.admin_profile_id == my_profile.id,
        TeamSizeRequest.status == "pending",
    ).order_by(TeamSizeRequest.created_at.desc()).first()

    return {
        "current_count": current_count,
        "limit": limit,
        "pending_request": {
            "id": pending.id,
            "requested_size": pending.requested_size,
            "status": pending.status,
        } if pending else None,
    }


class TeamSizeRequestPayload(BaseModel):
    requested_size: int
    reason: Optional[str] = None


@router.post("/company/team-size-request")
def request_team_size_increase(
    payload: TeamSizeRequestPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can request a team size increase.")

    my_profile = _profile_of(db, current_user.id, current_user.tenant_id)
    if not my_profile:
        raise HTTPException(status_code=400, detail="Employee profile not found.")

    current_limit = my_profile.max_team_size if my_profile.max_team_size is not None else 10

    if payload.requested_size <= current_limit:
        raise HTTPException(status_code=400, detail=f"Requested size must be greater than current limit ({current_limit}).")

    existing = db.query(TeamSizeRequest).filter(
        TeamSizeRequest.admin_profile_id == my_profile.id,
        TeamSizeRequest.status == "pending",
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="You already have a pending size increase request.")

    req = TeamSizeRequest(
        tenant_id=current_user.tenant_id,
        admin_profile_id=my_profile.id,
        requested_size=payload.requested_size,
        current_limit=current_limit,
        reason=payload.reason,
        status="pending",
    )
    db.add(req)
    db.flush()

    ceo = _get_ceo(db, current_user.tenant_id)
    if ceo:
        _notify(db, current_user.tenant_id, ceo.id,
            "approval_needed",
            f"{_name(current_user)} requests team size increase",
            f"{_name(current_user)} wants to grow their team from {current_limit} to {payload.requested_size} members."
            + (f" Reason: {payload.reason}" if payload.reason else ""),
            "team_size_request", req.id)

    db.commit()
    return {"id": req.id, "status": req.status}


@router.get("/company/team-size-requests")
def list_team_size_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "ceo":
        raise HTTPException(status_code=403, detail="CEO only.")

    requests = (
        db.query(TeamSizeRequest)
        .filter(
            TeamSizeRequest.tenant_id == current_user.tenant_id,
            TeamSizeRequest.status == "pending",
        )
        .order_by(TeamSizeRequest.created_at.desc())
        .all()
    )

    result = []
    for r in requests:
        admin_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == r.admin_profile_id).first()
        admin_user = _user_of(db, admin_profile)
        team_count = db.query(EmployeeProfile).filter(
            EmployeeProfile.manager_id == r.admin_profile_id,
            EmployeeProfile.deleted_at.is_(None),
        ).count() if admin_profile else 0
        result.append({
            "id": r.id,
            "admin_name": _name(admin_user),
            "admin_profile_id": r.admin_profile_id,
            "current_team_size": team_count,
            "current_limit": r.current_limit,
            "requested_size": r.requested_size,
            "reason": r.reason,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return result


@router.get("/company/admin-team-limits")
def admin_team_limits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "ceo":
        raise HTTPException(status_code=403, detail="CEO only.")

    admins = db.query(User).filter(
        User.tenant_id == current_user.tenant_id,
        User.role == "admin",
        User.deleted_at.is_(None),
    ).all()

    result = []
    for admin in admins:
        profile = _profile_of(db, admin.id, current_user.tenant_id)
        if not profile:
            continue
        team_count = db.query(EmployeeProfile).filter(
            EmployeeProfile.manager_id == profile.id,
            EmployeeProfile.deleted_at.is_(None),
        ).count()
        result.append({
            "admin_user_id": admin.id,
            "admin_profile_id": profile.id,
            "name": _name(admin),
            "email": admin.email,
            "current_team_size": team_count,
            "limit": profile.max_team_size if profile.max_team_size is not None else 10,
        })
    return result


class SizeRequestActionPayload(BaseModel):
    approved: bool
    approved_size: Optional[int] = None
    rejection_reason: Optional[str] = None


@router.post("/company/team-size-request/{request_id}/ceo-action")
def ceo_size_request_action(
    request_id: int,
    payload: SizeRequestActionPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "ceo":
        raise HTTPException(status_code=403, detail="CEO only.")

    req = db.query(TeamSizeRequest).filter(
        TeamSizeRequest.id == request_id,
        TeamSizeRequest.tenant_id == current_user.tenant_id,
        TeamSizeRequest.status == "pending",
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found or already resolved.")

    admin_profile = db.query(EmployeeProfile).filter(EmployeeProfile.id == req.admin_profile_id).first()
    admin_user = _user_of(db, admin_profile)
    admin_name = _name(admin_user)

    if payload.approved:
        new_size = payload.approved_size or req.requested_size
        req.status = "approved"
        req.approved_size = new_size
        if admin_profile:
            admin_profile.max_team_size = new_size
            db.add(admin_profile)
        if admin_user:
            _notify(db, current_user.tenant_id, admin_user.id,
                "accepted",
                "Your team size request was approved",
                f"CEO approved your request. Your team can now have up to {new_size} members.",
                "team_size_request", req.id)
    else:
        req.status = "rejected"
        req.rejection_reason = payload.rejection_reason
        if admin_user:
            _notify(db, current_user.tenant_id, admin_user.id,
                "rejection_record",
                "Your team size request was rejected",
                payload.rejection_reason or "No reason provided.",
                "team_size_request", req.id)

    req.updated_at = datetime.utcnow()
    db.add(req)
    db.commit()
    return {"status": req.status}


class AdminLimitPayload(BaseModel):
    max_team_size: int


@router.patch("/company/admin-team-limit/{admin_profile_id}")
def set_admin_team_limit(
    admin_profile_id: int,
    payload: AdminLimitPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "ceo":
        raise HTTPException(status_code=403, detail="CEO only.")

    if payload.max_team_size < 1:
        raise HTTPException(status_code=400, detail="Limit must be at least 1.")

    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.id == admin_profile_id,
        EmployeeProfile.tenant_id == current_user.tenant_id,
        EmployeeProfile.deleted_at.is_(None),
    ).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Admin profile not found.")

    admin_user = _user_of(db, profile)
    if not admin_user or admin_user.role != "admin":
        raise HTTPException(status_code=400, detail="Target must be an admin.")

    profile.max_team_size = payload.max_team_size
    db.add(profile)
    db.commit()
    return {"admin_profile_id": admin_profile_id, "max_team_size": payload.max_team_size}
