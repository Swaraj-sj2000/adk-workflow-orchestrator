# backend/app/services/_invite_service.py

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import uuid
from typing import List, Dict, Tuple, Optional

from app.models._employee_invite import EmployeeInvite
from app.models._organization import Organization
from app.core._config import settings
from fastapi import HTTPException


class InviteService:
    """Service for managing employee invites"""
    
    @staticmethod
    def generate_invite(
        db: Session,
        organization_id: str,
        email: str,
        role: str,
        created_by: str,
        expires_in_days: int = 7
    ) -> EmployeeInvite:
        """
        Generate new employee invite.
        
        Args:
            db: Database session
            organization_id: Organization to create invite for
            email: Email to send invite to
            role: Role (employee, manager)
            created_by: Admin user ID who created it
            expires_in_days: How many days until expiry
        
        Returns:
            Created EmployeeInvite
        
        Raises:
            HTTPException: If email already has pending invite
        """
        # Check if email already has pending invite
        existing = db.query(EmployeeInvite).filter_by(
            email=email.lower(),
            organization_id=organization_id,
            status="pending"
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Email {email} already has a pending invite for this organization"
            )
        
        # Create invite
        invite = EmployeeInvite.create_invite(
            organization_id=organization_id,
            email=email.lower(),
            created_by=created_by,
            role=role,
            expires_in_days=expires_in_days
        )
        
        db.add(invite)
        db.commit()
        db.refresh(invite)
        
        return invite
    
    @staticmethod
    def get_invite_link(org_slug: str, invite_code: str) -> str:
        """
        Generate shareable invite link.
        
        Args:
            org_slug: Organization slug
            invite_code: Invite code
        
        Returns:
            Full shareable link
        """
        base_url = settings.BASE_URL or "http://localhost:3000"
        return f"{base_url}/accept-invite/{invite_code}"
    
    @staticmethod
    def list_invites(
        db: Session,
        organization_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[EmployeeInvite], int]:
        """
        List invites for organization.
        
        Args:
            db: Database session
            organization_id: Filter by org
            status: Filter by status (pending, accepted, expired, cancelled)
            skip: Pagination offset
            limit: Results per page
        
        Returns:
            (invites_list, total_count)
        """
        query = db.query(EmployeeInvite).filter_by(organization_id=organization_id)
        
        if status:
            query = query.filter_by(status=status)
        
        total = query.count()
        
        invites = query.order_by(EmployeeInvite.created_at.desc()).offset(skip).limit(limit).all()
        
        return invites, total
    
    @staticmethod
    def get_invite_stats(db: Session, organization_id: str) -> Dict[str, int]:
        """
        Get invite statistics for organization.
        
        Returns:
            Dict with counts by status
        """
        total = db.query(EmployeeInvite).filter_by(organization_id=organization_id).count()
        
        pending = db.query(EmployeeInvite).filter_by(
            organization_id=organization_id,
            status="pending"
        ).count()
        
        accepted = db.query(EmployeeInvite).filter_by(
            organization_id=organization_id,
            status="accepted"
        ).count()
        
        expired = db.query(EmployeeInvite).filter_by(
            organization_id=organization_id,
            status="expired"
        ).count()
        
        cancelled = db.query(EmployeeInvite).filter_by(
            organization_id=organization_id,
            status="cancelled"
        ).count()
        
        return {
            "total": total,
            "pending": pending,
            "accepted": accepted,
            "expired": expired,
            "cancelled": cancelled
        }
    
    @staticmethod
    def revoke_invite(
        db: Session,
        invite_id: str,
        organization_id: str
    ) -> EmployeeInvite:
        """
        Revoke/cancel an invite.
        
        Args:
            db: Database session
            invite_id: Invite ID to revoke
            organization_id: Organization (for safety check)
        
        Returns:
            Updated EmployeeInvite
        
        Raises:
            HTTPException: If invite not found or cannot be revoked
        """
        invite = db.query(EmployeeInvite).filter_by(
            id=invite_id,
            organization_id=organization_id
        ).first()
        
        if not invite:
            raise HTTPException(
                status_code=404,
                detail="Invite not found"
            )
        
        if invite.status != "pending":
            raise HTTPException(
                status_code=400,
                detail=f"Cannot revoke invite with status '{invite.status}'"
            )
        
        invite.status = "cancelled"
        db.commit()
        db.refresh(invite)
        
        return invite
    
    @staticmethod
    def bulk_generate_invites(
        db: Session,
        organization_id: str,
        emails: List[str],
        role: str,
        created_by: str,
        expires_in_days: int = 7
    ) -> Tuple[List[EmployeeInvite], List[Dict]]:
        """
        Generate multiple invites at once.
        
        Args:
            db: Database session
            organization_id: Organization
            emails: List of emails to invite
            role: Role for all invites
            created_by: Admin creating invites
            expires_in_days: Expiry time
        
        Returns:
            (successful_invites, failed_emails)
            
        Failed emails: [{"email": "x@y.com", "reason": "..."}]
        """
        successful = []
        failed = []
        
        for email in emails:
            try:
                invite = InviteService.generate_invite(
                    db=db,
                    organization_id=organization_id,
                    email=email.lower().strip(),
                    role=role,
                    created_by=created_by,
                    expires_in_days=expires_in_days
                )
                successful.append(invite)
            except HTTPException as e:
                failed.append({
                    "email": email,
                    "reason": e.detail
                })
            except Exception as e:
                failed.append({
                    "email": email,
                    "reason": str(e)
                })
        
        return successful, failed
    
    @staticmethod
    def resend_invite(
        db: Session,
        invite_id: str,
        organization_id: str,
        expire_days: int = 7
    ) -> EmployeeInvite:
        """
        Resend an expired or old invite (extends expiry).
        
        Args:
            db: Database session
            invite_id: Invite ID
            organization_id: Organization (safety check)
            expire_days: New expiry time
        
        Returns:
            Updated invite with new expiry
        """
        invite = db.query(EmployeeInvite).filter_by(
            id=invite_id,
            organization_id=organization_id
        ).first()
        
        if not invite:
            raise HTTPException(
                status_code=404,
                detail="Invite not found"
            )
        
        if invite.status not in ["pending", "expired"]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot resend invite with status '{invite.status}'"
            )
        
        # Reset to pending and extend expiry
        invite.status = "pending"
        invite.expires_at = datetime.utcnow() + timedelta(days=expire_days)
        
        db.commit()
        db.refresh(invite)
        
        return invite
    
    @staticmethod
    def cleanup_expired_invites(db: Session, organization_id: str) -> int:
        """
        Mark expired invites as expired (housekeeping).
        
        Returns:
            Number of invites marked as expired
        """
        now = datetime.utcnow()
        
        expired = db.query(EmployeeInvite).filter(
            EmployeeInvite.organization_id == organization_id,
            EmployeeInvite.status == "pending",
            EmployeeInvite.expires_at < now
        ).update({"status": "expired"})
        
        db.commit()
        
        return expired
