from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core._deps import get_db, require_platform_owner
from app.models._user import User
from app.services._owner_service import OwnerService


router = APIRouter(tags=["Owner"])


class TenantSuspendRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class TicketResponseRequest(BaseModel):
    response: str = Field(min_length=3, max_length=5000)


@router.get("/tenants")
def list_tenants(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    return OwnerService.list_tenants(db)


@router.post("/tenants/{tenant_id}/suspend")
def suspend_tenant(
    tenant_id: int,
    payload: TenantSuspendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    return OwnerService.suspend_tenant(db, tenant_id, payload.reason)


@router.post("/tenants/{tenant_id}/activate")
def activate_tenant(
    tenant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    return OwnerService.activate_tenant(db, tenant_id)


@router.get("/metrics")
def get_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    return OwnerService.get_platform_metrics(db)


@router.get("/support-tickets")
def list_support_tickets(
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    return OwnerService.list_support_tickets(db, status=status)


@router.patch("/support-tickets/{ticket_id}")
def respond_to_ticket(
    ticket_id: int,
    payload: TicketResponseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    try:
        return OwnerService.respond_to_ticket(db, ticket_id, payload.response)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
