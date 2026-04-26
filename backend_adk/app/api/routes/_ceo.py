from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core._deps import get_db, require_ceo_or_admin
from app.models._user import User
from app.services._ceo_service import CEOService


router = APIRouter(tags=["CEO"])


@router.get("/overview")
def get_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    return CEOService.get_company_overview(db, current_user.tenant_id)


@router.get("/financials")
def get_financials(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    return CEOService.get_financial_overview(db, current_user.tenant_id)


@router.get("/teams")
def get_teams(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    return CEOService.get_team_utilization(db, current_user.tenant_id)


@router.get("/clients")
def get_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    return CEOService.get_client_status(db, current_user.tenant_id)


@router.get("/risks")
def get_risks(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    return CEOService.get_risk_flags(db, current_user.tenant_id)


@router.get("/analytics")
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_ceo_or_admin),
):
    return CEOService.get_analytics(db, current_user.tenant_id)
