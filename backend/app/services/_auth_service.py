# backend/app/services/_auth_service.py

from sqlalchemy.orm import Session
from datetime import datetime
import uuid
from typing import Optional, Tuple

from app.models._organization import Organization
from app.models._auth_user import AuthUser
from app.models._employee_invite import EmployeeInvite
from app.models._employee_profile import EmployeeProfile
from app.utils._password import hash_password, verify_password
from app.utils._jwt import create_access_token, get_token_expiry_seconds
from app.schemas._auth import (
    UserLogin, UserCreate, EmployeeInviteAccept,
    TokenResponse, AuthResponse, InviteCodeValidation
)
from fastapi import HTTPException


class AuthService:
    """Authentication service for login, signup, and invite acceptance"""
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str, org_id: Optional[str] = None) -> Optional[AuthUser]:
        """
        Authenticate user by email and password.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
            org_id: Organization ID (optional, if provided will scope to that org)
        
        Returns:
            AuthUser if credentials valid, else None
        """
        query = db.query(AuthUser).filter_by(email=email)
        
        if org_id:
            query = query.filter_by(organization_id=org_id)
        
        user = query.first()
        
        if not user:
            return None
        
        if not verify_password(password, user.password_hash):
            return None
        
        if not user.is_active:
            return None
        
        return user
    
    @staticmethod
    def create_user(
        db: Session,
        email: str,
        password: str,
        organization_id: str,
        full_name: Optional[str] = None,
        role: str = "employee"
    ) -> AuthUser:
        """
        Create new user in organization.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password (will be hashed)
            organization_id: Organization to add user to
            full_name: User's full name
            role: User role (admin, manager, employee)
        
        Returns:
            Created AuthUser
        
        Raises:
            HTTPException: If email already exists
        """
        # Check if user already exists
        existing = db.query(AuthUser).filter_by(email=email, organization_id=organization_id).first()
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"User with email {email} already exists in this organization"
            )
        
        user = AuthUser(
            id=str(uuid.uuid4()),
            organization_id=organization_id,
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            role=role,
            is_active=True,
            is_verified=False
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def validate_invite_code(db: Session, invite_code: str) -> Tuple[bool, str, Optional[EmployeeInvite]]:
        """
        Validate invite code.
        
        Returns:
            (is_valid: bool, message: str, invite: EmployeeInvite or None)
        """
        invite = db.query(EmployeeInvite).filter_by(invite_code=invite_code).first()
        
        if not invite:
            return False, "Invalid invite code", None
        
        if invite.status != "pending":
            return False, f"Invite has already been {invite.status}", None
        
        if not invite.is_valid():
            return False, "Invite has expired", None
        
        return True, "Valid invite", invite
    
    @staticmethod
    def accept_invite(
        db: Session,
        invite_code: str,
        email: str,
        password: str,
        full_name: str,
        skills: list = None,
        experience_years: int = None
    ) -> Tuple[AuthUser, str]:
        """
        Accept employee invite and create user.
        
        Returns:
            (auth_user, access_token)
        
        Raises:
            HTTPException: If invite invalid or email mismatch
        """
        # Validate invite
        is_valid, message, invite = AuthService.validate_invite_code(db, invite_code)
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
        
        # Check email matches
        if email.lower() != invite.email.lower():
            raise HTTPException(
                status_code=400,
                detail="Email must match invite email address"
            )
        
        # Create user
        user = AuthService.create_user(
            db=db,
            email=email,
            password=password,
            organization_id=invite.organization_id,
            full_name=full_name,
            role=invite.role
        )
        
        # Create employee profile
        profile = EmployeeProfile(
            id=str(uuid.uuid4()),
            organization_id=invite.organization_id,
            auth_user_id=user.id,
            full_name=full_name,
            role=invite.role,
            skills={skill: 0.5 for skill in (skills or [])},  # Default proficiency
            experience_years=experience_years
        )
        db.add(profile)
        
        # Mark invite as accepted
        invite.status = "accepted"
        invite.accepted_at = datetime.utcnow()
        invite.accepted_by_user_id = user.id
        
        db.commit()
        db.refresh(user)
        
        # Generate token
        token = create_access_token({
            "sub": user.id,
            "org": user.organization_id,
            "role": user.role,
            "email": user.email
        })
        
        return user, token
    
    @staticmethod
    def generate_auth_response(
        db: Session,
        user: AuthUser,
        token: str
    ) -> AuthResponse:
        """
        Generate complete auth response with organization info.
        
        Args:
            db: Database session
            user: AuthUser object
            token: JWT access token
        
        Returns:
            AuthResponse with all auth details
        """
        org = db.query(Organization).filter_by(id=user.organization_id).first()
        
        if not org:
            raise HTTPException(
                status_code=500,
                detail="Organization not found"
            )
        
        expires_in = get_token_expiry_seconds(token)
        
        return AuthResponse(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            organization_id=org.id,
            organization_slug=org.slug,
            role=user.role,
            access_token=token,
            expires_in=expires_in
        )
    
    @staticmethod
    def update_last_login(db: Session, user_id: str) -> None:
        """Update user's last login timestamp"""
        user = db.query(AuthUser).filter_by(id=user_id).first()
        if user:
            user.last_login = datetime.utcnow()
            db.commit()
