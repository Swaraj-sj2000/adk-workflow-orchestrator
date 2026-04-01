# backend/app/api/routes/invites.py

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.db._database import get_db
from app.models._auth_user import AuthUser
from app.models._organization import Organization
from app.core._auth_deps import get_current_admin, get_current_user, get_organization
from app.services._invite_service import InviteService
from app.schemas._invite import (
    CreateInviteRequest, InviteResponse, InviteListResponse,
    InviteLinkResponse, RevokeInviteRequest, BulkInviteRequest,
    BulkInviteResponse
)
from typing import List

router = APIRouter(prefix="/api/v1/invites", tags=["Employee Invites"])


@router.post("", response_model=InviteLinkResponse, status_code=201)
async def create_invite(
    request: CreateInviteRequest,
    db: Session = Depends(get_db),
    current_admin: AuthUser = Depends(get_current_admin),
    org: Organization = Depends(get_organization)
):
    """
    Create new employee invite.
    Admin only.
    
    Request:
    ```json
    {
        "email": "john@company.com",
        "role": "employee",
        "expires_in_days": 7,
        "message": "Welcome to our team!"
    }
    ```
    
    Returns invite link to share with employee.
    """
    # Generate invite
    invite = InviteService.generate_invite(
        db=db,
        organization_id=org.id,
        email=request.email,
        role=request.role,
        created_by=current_admin.id,
        expires_in_days=request.expires_in_days
    )
    
    # Generate shareable link
    invite_link = InviteService.get_invite_link(org.slug, invite.invite_code)
    
    return InviteLinkResponse(
        invite_id=invite.id,
        email=invite.email,
        role=invite.role,
        status=invite.status,
        expires_at=invite.expires_at,
        invite_link=invite_link,
        created_at=invite.created_at
    )


@router.post("/bulk", response_model=BulkInviteResponse, status_code=201)
async def bulk_create_invites(
    request: BulkInviteRequest,
    db: Session = Depends(get_db),
    current_admin: AuthUser = Depends(get_current_admin),
    org: Organization = Depends(get_organization)
):
    """
    Create multiple invites at once.
    Admin only.
    
    Request:
    ```json
    {
        "emails": ["john@company.com", "jane@company.com"],
        "role": "employee",
        "expires_in_days": 7
    }
    ```
    """
    successful, failed = InviteService.bulk_generate_invites(
        db=db,
        organization_id=org.id,
        emails=request.emails,
        role=request.role,
        created_by=current_admin.id,
        expires_in_days=request.expires_in_days
    )
    
    # Generate links for successful invites
    invite_links = []
    for invite in successful:
        link = InviteService.get_invite_link(org.slug, invite.invite_code)
        invite_links.append(InviteLinkResponse(
            invite_id=invite.id,
            email=invite.email,
            role=invite.role,
            status=invite.status,
            expires_at=invite.expires_at,
            invite_link=link,
            created_at=invite.created_at
        ))
    
    return BulkInviteResponse(
        created=len(successful),
        failed=len(failed),
        invites=invite_links
    )


@router.get("", response_model=InviteListResponse)
async def list_invites(
    status: str = Query(None, description="Filter by status: pending|accepted|expired|cancelled"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: AuthUser = Depends(get_current_admin),
    org: Organization = Depends(get_organization)
):
    """
    List all invites for current organization.
    Admin only.
    
    Query parameters:
    - status: Filter by status
    - skip: Pagination offset (default: 0)
    - limit: Results per page (default: 50, max: 100)
    """
    # Clean up expired invites first
    InviteService.cleanup_expired_invites(db, org.id)
    
    # Get invites
    invites, total = InviteService.list_invites(
        db=db,
        organization_id=org.id,
        status=status,
        skip=skip,
        limit=limit
    )
    
    # Get stats
    stats = InviteService.get_invite_stats(db, org.id)
    
    # Convert to response models
    items = [
        InviteResponse.from_orm(invite)
        for invite in invites
    ]
    
    return InviteListResponse(
        items=items,
        total=total,
        pending_count=stats["pending"],
        accepted_count=stats["accepted"],
        expired_count=stats["expired"],
        cancelled_count=stats["cancelled"]
    )


@router.get("/stats", response_model=dict)
async def get_invite_stats(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
    org: Organization = Depends(get_organization)
):
    """
    Get invite statistics for current organization.
    Any authenticated user can view.
    """
    InviteService.cleanup_expired_invites(db, org.id)
    stats = InviteService.get_invite_stats(db, org.id)
    
    return {
        "organization_id": org.id,
        "organization_name": org.name,
        **stats
    }


@router.delete("/{invite_id}", response_model=dict, status_code=200)
async def revoke_invite(
    invite_id: str,
    request: RevokeInviteRequest = None,
    db: Session = Depends(get_db),
    current_admin: AuthUser = Depends(get_current_admin),
    org: Organization = Depends(get_organization)
):
    """
    Revoke/cancel a pending invite.
    Admin only.
    Cannot revoke accepted or already cancelled invites.
    
    Request:
    ```json
    {
        "reason": "Employee declined"
    }
    ```
    """
    invite = InviteService.revoke_invite(
        db=db,
        invite_id=invite_id,
        organization_id=org.id
    )
    
    return {
        "invite_id": invite.id,
        "email": invite.email,
        "status": invite.status,
        "message": "Invite revoked successfully"
    }


@router.post("/{invite_id}/resend", response_model=InviteLinkResponse)
async def resend_invite(
    invite_id: str,
    db: Session = Depends(get_db),
    current_admin: AuthUser = Depends(get_current_admin),
    org: Organization = Depends(get_organization)
):
    """
    Resend an expired or pending invite (extends expiry).
    Admin only.
    """
    invite = InviteService.resend_invite(
        db=db,
        invite_id=invite_id,
        organization_id=org.id,
        expire_days=7
    )
    
    # Generate shareable link
    invite_link = InviteService.get_invite_link(org.slug, invite.invite_code)
    
    return InviteLinkResponse(
        invite_id=invite.id,
        email=invite.email,
        role=invite.role,
        status=invite.status,
        expires_at=invite.expires_at,
        invite_link=invite_link,
        created_at=invite.created_at
    )


@router.get("/{invite_id}", response_model=InviteResponse)
async def get_invite(
    invite_id: str,
    db: Session = Depends(get_db),
    current_admin: AuthUser = Depends(get_current_admin),
    org: Organization = Depends(get_organization)
):
    """
    Get single invite details.
    Admin only.
    """
    from app.models._employee_invite import EmployeeInvite
    
    invite = db.query(EmployeeInvite).filter_by(
        id=invite_id,
        organization_id=org.id
    ).first()
    
    if not invite:
        raise HTTPException(
            status_code=404,
            detail="Invite not found"
        )
    
    return InviteResponse.from_orm(invite)
