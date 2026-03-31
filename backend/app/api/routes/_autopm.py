# app/api/routes/_autopm.py
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core._deps import get_db, get_current_user
from app.models._user import User
from app.services._autopm_service import AutoPMService

router = APIRouter(prefix="/autopm", tags=["AutoPM"])


class IntakeRequest(BaseModel):
    request_text: str
    budget: float = 0.0
    priority: str = "medium"
    deadline: Optional[datetime] = None


class AssignmentResponseRequest(BaseModel):
    response: str  # accepted / denied / negotiating
    negotiation_notes: Optional[str] = None


class SimulationRequest(BaseModel):
    seed: Optional[int] = None


@router.post("/intake")
def intake_project(
    payload: IntakeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can intake projects")

    service = AutoPMService(db)
    return service.intake_project(
        request_text=payload.request_text,
        admin_user_id=current_user.id,
        budget=payload.budget,
        priority=payload.priority,
        deadline=payload.deadline,
    )


@router.post("/projects/{project_id}/assign")
def assign_project_tasks(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign project tasks")

    service = AutoPMService(db)
    return service.assign_project_tasks(project_id)


@router.post("/assignments/{assignment_id}/respond")
def respond_to_assignment(
    assignment_id: int,
    payload: AssignmentResponseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AutoPMService(db)
    try:
        return service.handle_assignment_response(
            assignment_id=assignment_id,
            response=payload.response,
            negotiation_notes=payload.negotiation_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/projects/{project_id}/simulate")
def simulate_project(
    project_id: int,
    payload: SimulationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can run simulation")
    service = AutoPMService(db)
    return service.run_project_simulation(project_id, seed=payload.seed)


@router.get("/digest/daily")
def daily_digest(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view digest")
    service = AutoPMService(db)
    return service.generate_daily_digest()


@router.post("/projects/{project_id}/client-update")
def client_update(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can generate client updates")
    service = AutoPMService(db)
    try:
        return service.generate_client_update(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/projects/{project_id}/close")
def close_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can close project")
    service = AutoPMService(db)
    try:
        return service.close_project(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
