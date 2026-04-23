# app/api/routes/_decision.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core._deps import get_db, get_current_user
from app.models._user import User
from app.schemas._decision_log import DecisionLogRead
from app.services._decision_service import DecisionService
from typing import List

router = APIRouter(prefix="/decisions", tags=["Decisions"])


@router.get("/")
def route_get_decisions(
    entity_type: str = None,
    entity_id: int = None,
    decision_type: str = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get decision history with optional filters."""
    service = DecisionService(db)
    decisions = service.get_decision_history(
        entity_type=entity_type,
        entity_id=entity_id,
        decision_type=decision_type,
        skip=skip,
        limit=limit,
        tenant_id=current_user.tenant_id,
    )
    total = service.count_decision_history(
        entity_type=entity_type,
        entity_id=entity_id,
        decision_type=decision_type,
        tenant_id=current_user.tenant_id,
    )
    return {
        "items": decisions,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/risky", response_model=List[DecisionLogRead])
def route_get_risky_decisions(
    confidence_threshold: float = 0.6,
    hours: int = 24,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get low-confidence decisions that may need admin review.
    Admin dashboard can use this to focus on risky decisions.
    """
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view risky decisions")
    
    service = DecisionService(db)
    decisions = service.get_low_confidence_decisions(
        threshold=confidence_threshold,
        last_n_hours=hours,
        tenant_id=current_user.tenant_id,
    )
    return decisions


@router.post("/override/{decision_id}")
def route_override_decision(
    decision_id: int,
    override_reason: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin can override a system decision."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can override decisions")
    
    service = DecisionService(db)
    decision = service.override_decision(
        decision_id=decision_id,
        admin_id=current_user.id,
        override_reason=override_reason,
        tenant_id=current_user.tenant_id,
    )
    
    if not decision:
        raise HTTPException(status_code=404, detail="Decision not found")
    
    return {"success": True, "decision_id": decision_id, "overridden_by": current_user.id}


@router.get("/statistics")
def route_get_decision_statistics(
    days: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get system decision analytics."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view statistics")
    
    service = DecisionService(db)
    stats = service.get_decision_statistics(last_n_days=days, tenant_id=current_user.tenant_id)

    return {
        "period_days": days,
        "statistics": stats
    }
