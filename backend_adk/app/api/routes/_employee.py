# app/api/routes/_employee.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core._deps import get_db, get_current_user
from app.models._user import User
from app.models._employee_profile import EmployeeProfile
from app.models._employee_metrics import EmployeeMetrics
from app.schemas._employee_profile import EmployeeProfileCreate, EmployeeProfileUpdate, EmployeeProfileRead
from app.schemas._employee_metrics import EmployeeMetricsRead
from app.services._project_service import build_client_workspace, build_employee_workspace, update_checkpoint_status
from typing import List

router = APIRouter(prefix="/employees", tags=["Employees"])


class CheckpointToggleRequest(BaseModel):
    completed: bool


@router.post("/profile", response_model=EmployeeProfileRead)
def route_create_employee_profile(
    profile: EmployeeProfileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create employee profile."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create profiles")
    
    # Check if profile already exists
    existing = db.query(EmployeeProfile).filter(
        EmployeeProfile.user_id == profile.user_id,
        EmployeeProfile.tenant_id == current_user.tenant_id,
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="Profile already exists for this user")
    
    new_profile = EmployeeProfile(**profile.dict(), tenant_id=current_user.tenant_id)
    db.add(new_profile)
    db.flush()
    
    # Create associated metrics
    metrics = EmployeeMetrics(employee_id=new_profile.id)
    db.add(metrics)

    db.commit()
    db.refresh(new_profile)
    
    return new_profile


@router.get("/{employee_id}/profile", response_model=EmployeeProfileRead)
def route_get_employee_profile(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get employee profile."""
    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.id == employee_id,
        EmployeeProfile.tenant_id == current_user.tenant_id,
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    # Employees can only see their own profile (unless admin)
    if current_user.role != "admin" and current_user.id != profile.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return profile


@router.patch("/{employee_id}/profile", response_model=EmployeeProfileRead)
def route_update_employee_profile(
    employee_id: int,
    profile_update: EmployeeProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update employee profile."""
    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.id == employee_id,
        EmployeeProfile.tenant_id == current_user.tenant_id,
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    
    if current_user.role != "admin" and current_user.id != profile.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    update_data = profile_update.dict(exclude_unset=True)
    if current_user.role != "admin":
        allowed_fields = {"skills", "availability_status", "duty_start_hour", "duty_end_hour"}
        forbidden = set(update_data.keys()) - allowed_fields
        if forbidden:
            raise HTTPException(status_code=403, detail="Employees can only update skills, leave status, and duty hours")
        if update_data.get("availability_status") == "busy":
            raise HTTPException(status_code=400, detail="Busy status is managed automatically from assignments")

    for key, value in update_data.items():
        setattr(profile, key, value)

    if profile.availability_status != "on-leave":
        profile.availability_status = "busy" if (profile.current_load or 0) > 0 else "available"
    
    db.merge(profile)
    db.commit()
    db.refresh(profile)
    
    return profile


@router.get("/{employee_id}/metrics", response_model=EmployeeMetricsRead)
def route_get_employee_metrics(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get employee performance metrics."""
    profile = db.query(EmployeeProfile).filter(
        EmployeeProfile.id == employee_id,
        EmployeeProfile.tenant_id == current_user.tenant_id,
    ).first()
    
    if not profile:
        raise HTTPException(status_code=404, detail="Employee not found")

    if current_user.role != "admin" and current_user.id != profile.user_id:
        raise HTTPException(status_code=403, detail="Not authorized")
    
    metrics = db.query(EmployeeMetrics).filter(
        EmployeeMetrics.employee_id == employee_id
    ).first()
    
    if not metrics:
        raise HTTPException(status_code=404, detail="Metrics not found")
    
    return metrics


@router.get("", response_model=List[EmployeeProfileRead])
def route_list_employees(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all employees (admin/CEO see full list; others see only available)."""
    query = db.query(EmployeeProfile).filter(EmployeeProfile.tenant_id == current_user.tenant_id)

    if current_user.role not in ("admin", "ceo", "platform_owner"):
        query = query.filter(EmployeeProfile.availability_status.in_(["available", "on-duty"]))

    employees = query.offset(skip).limit(limit).all()
    return employees


@router.get("/directory")
def route_employee_directory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Rich employee directory for admin/CEO: name, role, department, skills, load, team."""
    if current_user.role not in ("admin", "ceo", "platform_owner"):
        raise HTTPException(status_code=403, detail="Not authorized")

    from app.models._team import Team, TeamMember
    from sqlalchemy.orm import joinedload

    profiles = (
        db.query(EmployeeProfile)
        .options(joinedload(EmployeeProfile.user), joinedload(EmployeeProfile.metrics))
        .filter(EmployeeProfile.tenant_id == current_user.tenant_id)
        .order_by(EmployeeProfile.department, EmployeeProfile.id)
        .all()
    )

    # Build team membership lookup
    teams = db.query(Team).filter(Team.tenant_id == current_user.tenant_id).all()
    team_name_map = {t.id: t.name for t in teams}
    memberships = db.query(TeamMember).filter(TeamMember.tenant_id == current_user.tenant_id).all()
    emp_teams: dict = {}
    for m in memberships:
        if m.employee_profile_id:
            emp_teams.setdefault(m.employee_profile_id, []).append(team_name_map.get(m.team_id, "Unknown"))

    result = []
    for p in profiles:
        cap = p.max_capacity or 8.0
        load = p.current_load or 0.0
        result.append({
            "employee_profile_id": p.id,
            "user_id": p.user_id,
            "name": p.user.full_name if p.user else f"Employee {p.id}",
            "email": p.user.email if p.user else None,
            "department": p.department,
            "skills": p.skills or {},
            "availability_status": p.availability_status,
            "current_load": load,
            "max_capacity": cap,
            "workload_percent": round((load / cap) * 100) if cap > 0 else 0,
            "teams": emp_teams.get(p.id, []),
            "efficiency_score": p.metrics.efficiency_score if p.metrics else None,
            "reliability_score": p.metrics.reliability_score if p.metrics else None,
            "total_tasks_completed": p.metrics.total_tasks_completed if p.metrics else 0,
        })
    return {"employees": result, "total": len(result)}


@router.get("/my-work")
def route_my_work(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "employee":
        raise HTTPException(status_code=403, detail="Only employees can view this workspace")

    return build_employee_workspace(db, current_user)


@router.patch("/checkpoints/{checkpoint_id}")
def route_update_checkpoint(
    checkpoint_id: int,
    payload: CheckpointToggleRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_checkpoint_status(db, checkpoint_id, payload.completed, current_user)


@router.get("/client-workspace")
def route_client_workspace(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "client":
        raise HTTPException(status_code=403, detail="Only clients can view this workspace")

    return build_client_workspace(db, current_user)
