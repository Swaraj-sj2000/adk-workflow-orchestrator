# backend/app/api/routes/_auth.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db._database import get_db
from app.models._organization import Organization
from app.schemas._auth import (
    UserLogin, UserCreate, EmployeeInviteAccept,
    AuthResponse, InviteCodeValidation
)
from app.services._auth_service import AuthService
from app.utils._jwt import create_access_token, get_token_expiry_seconds
from app.core._auth_deps import get_current_user
from app.models._auth_user import AuthUser

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post("/signup", response_model=AuthResponse, status_code=201)
async def signup(request: UserCreate, db: Session = Depends(get_db)):
    """
    Create new organization and admin user.
    Only used for creating new organizations.
    
    Request:
    ```json
    {
        "email": "admin@mycompany.com",
        "password": "securepassword123",
        "full_name": "Admin User",
        "organization_slug": "my-company"
    }
    ```
    """
    # For now, allow signup to create new organizations
    # In production, you'd want to restrict this or require invitation
    
    org_slug = request.organization_slug or request.email.split("@")[0].lower()
    
    # Check if org already exists
    existing_org = db.query(Organization).filter_by(slug=org_slug).first()
    if existing_org:
        raise HTTPException(
            status_code=400,
            detail=f"Organization with slug '{org_slug}' already exists"
        )
    
    # Create organization
    org = Organization(
        name=request.organization_slug or f"{request.full_name}'s Workspace",
        slug=org_slug,
        subscription_tier="free",
        max_employees=50,
        max_projects=10
    )
    db.add(org)
    db.flush()  # Get org.id without committing
    
    # Create admin user
    user = AuthService.create_user(
        db=db,
        email=request.email,
        password=request.password,
        organization_id=org.id,
        full_name=request.full_name,
        role="admin"
    )
    
    # Generate token
    token = create_access_token({
        "sub": user.id,
        "org": org.id,
        "role": "admin",
        "email": user.email
    })
    
    # Update last login
    AuthService.update_last_login(db, user.id)
    
    # Return response
    return AuthService.generate_auth_response(db, user, token)


@router.post("/login", response_model=AuthResponse)
async def login(request: UserLogin, db: Session = Depends(get_db)):
    """
    Login user with email and password.
    
    Request:
    ```json
    {
        "email": "user@company.com",
        "password": "securepassword123",
        "organization_slug": "my-company"
    }
    ```
    """
    # Find organization by slug if provided
    org = None
    if request.organization_slug:
        org = db.query(Organization).filter_by(slug=request.organization_slug).first()
        if not org:
            raise HTTPException(
                status_code=404,
                detail=f"Organization '{request.organization_slug}' not found"
            )
    
    # Authenticate user
    user = AuthService.authenticate_user(
        db=db,
        email=request.email,
        password=request.password,
        org_id=org.id if org else None
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Generate token
    token = create_access_token({
        "sub": user.id,
        "org": user.organization_id,
        "role": user.role,
        "email": user.email
    })
    
    # Update last login
    AuthService.update_last_login(db, user.id)
    
    # Return response
    return AuthService.generate_auth_response(db, user, token)


@router.post("/accept-invite", response_model=AuthResponse, status_code=201)
async def accept_invite(request: EmployeeInviteAccept, db: Session = Depends(get_db)):
    """
    Accept employee invite and create account.
    
    Request:
    ```json
    {
        "invite_code": "unique_secure_token_here",
        "full_name": "John Doe",
        "email": "john@company.com",
        "password": "securepassword123",
        "skills": ["Python", "FastAPI", "React"],
        "experience_years": 5
    }
    ```
    """
    # Accept invite
    user, token = AuthService.accept_invite(
        db=db,
        invite_code=request.invite_code,
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        skills=request.skills,
        experience_years=request.experience_years
    )
    
    # Update last login
    AuthService.update_last_login(db, user.id)
    
    # Return response
    return AuthService.generate_auth_response(db, user, token)


@router.post("/validate-invite", response_model=InviteCodeValidation)
async def validate_invite(invite_code: str, db: Session = Depends(get_db)):
    """
    Validate invite code before accepting.
    Returns organization and invite details if valid.
    
    Query:
        ?invite_code=unique_secure_token_here
    """
    is_valid, message, invite = AuthService.validate_invite_code(db, invite_code)
    
    if not is_valid:
        return InviteCodeValidation(valid=False, message=message)
    
    org = db.query(Organization).filter_by(id=invite.organization_id).first()
    
    return InviteCodeValidation(
        valid=True,
        message="Valid invite",
        email=invite.email,
        organization_id=invite.organization_id,
        organization_name=org.name if org else None,
        expires_at=invite.expires_at
    )


@router.get("/me", response_model=dict)
async def get_current_user_info(current_user: AuthUser = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Get current authenticated user information.
    Requires valid JWT token.
    """
    org = db.query(Organization).filter_by(id=current_user.organization_id).first()
    
    return {
        "user_id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "organization": {
            "id": org.id,
            "slug": org.slug,
            "name": org.name
        },
        "created_at": current_user.created_at,
        "last_login": current_user.last_login
    }


@router.post("/logout")
async def logout(current_user: AuthUser = Depends(get_current_user)):
    """
    Logout (client-side token deletion).
    In JWT-based auth, logout is handled by client removing token.
    This endpoint is mainly for audit logging if needed.
    """
    return {"message": "Successfully logged out"}