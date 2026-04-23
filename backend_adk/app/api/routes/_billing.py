from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core._deps import get_db, require_ceo_or_admin
from app.models._user import User
from app.services._stripe_service import StripeService


router = APIRouter(tags=["Billing"])


class SubscribeRequest(BaseModel):
    plan_tier: str = Field(min_length=3, max_length=50)


class ProjectInvoiceRequest(BaseModel):
    amount: float = Field(gt=0)
    due_date: datetime


@router.post("/subscribe")
def subscribe(
    payload: SubscribeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant-scoped billing is not available for this account")
    try:
        return StripeService.create_tenant_subscription(
            db=db,
            tenant_id=current_user.tenant_id,
            plan_tier=payload.plan_tier.strip().lower(),
            admin_email=current_user.email,
            company_name=current_user.full_name or current_user.email,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/portal")
def billing_portal(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant-scoped billing is not available for this account")
    try:
        return {"url": StripeService.get_billing_portal_url(db, current_user.tenant_id)}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        StripeService.handle_stripe_webhook(payload, sig_header, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}


@router.post("/projects/{project_id}/invoice")
def create_invoice(
    project_id: int,
    payload: ProjectInvoiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant-scoped billing is not available for this account")
    try:
        return StripeService.create_project_invoice(db, project_id, payload.amount, payload.due_date, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/projects/{project_id}/hold")
def apply_hold(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant-scoped billing is not available for this account")
    try:
        return StripeService.apply_payment_hold(db, project_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/projects/{project_id}/lift-hold")
def lift_hold(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    if current_user.tenant_id is None:
        raise HTTPException(status_code=403, detail="Tenant-scoped billing is not available for this account")
    try:
        return StripeService.lift_payment_hold(db, project_id, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
