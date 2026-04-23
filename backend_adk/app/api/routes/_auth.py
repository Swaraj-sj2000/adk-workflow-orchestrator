# backend/app/api/routes/_auth.py

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core._deps import get_current_user
from app.core._security import (
    generate_totp_secret,
    get_totp_provisioning_uri,
    verify_totp,
)
from app.db._database import get_db
from app.models._user import User
from app.schemas._user import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    UserCreate,
    UserLogin,
)
from app.services._auth_service import (
    change_password,
    login_user,
    refresh_access_token,
    register_user,
    request_password_reset,
    reset_password,
    verify_email_token,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


class RefreshRequest(BaseModel):
    refresh_token: str


class TOTPSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str


class TOTPVerifyRequest(BaseModel):
    totp_code: str


@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    return register_user(
        db,
        user.email,
        user.password,
        user.full_name,
        user.role,
        tenant_name=user.tenant_name,
        tenant_slug=user.tenant_slug,
    )


@router.post("/login")
def login(user: UserLogin, db: Session = Depends(get_db)):
    result = login_user(db, user.email, user.password)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token, refresh_token, user_data = result
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user_data,
    }


@router.post("/refresh")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    result = refresh_access_token(db, payload.refresh_token)
    if not result:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    new_access, new_refresh = result
    return {"access_token": new_access, "refresh_token": new_refresh}


@router.get("/verify-email")
def verify_email(token: str = Query(..., min_length=1), db: Session = Depends(get_db)):
    verify_email_token(db, token)
    return {"message": "Email verified successfully. You can now log in."}


@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    request_password_reset(db, payload.email)
    return {"message": "If that email exists, a reset link has been sent"}


@router.post("/reset-password")
def route_reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset_password(db, payload.token, payload.new_password)
    return {"message": "Password updated successfully"}


@router.post("/change-password")
def route_change_password(
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    change_password(db, current_user, payload.current_password, payload.new_password)
    return {"message": "Password changed"}


# ── 2FA / TOTP ──────────────────────────────────────────────────────────────

@router.post("/2fa/setup", response_model=TOTPSetupResponse)
def totp_setup(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if getattr(current_user, "totp_enabled", False):
        raise HTTPException(status_code=400, detail="2FA is already enabled")
    secret = generate_totp_secret()
    current_user.totp_secret = secret
    db.add(current_user)
    db.commit()
    return TOTPSetupResponse(
        secret=secret,
        provisioning_uri=get_totp_provisioning_uri(secret, current_user.email),
    )


@router.post("/2fa/enable")
def totp_enable(
    payload: TOTPVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    secret = getattr(current_user, "totp_secret", None)
    if not secret:
        raise HTTPException(status_code=400, detail="Call /auth/2fa/setup first")
    if not verify_totp(secret, payload.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    current_user.totp_enabled = True
    db.add(current_user)
    db.commit()
    return {"message": "2FA enabled successfully"}


@router.post("/2fa/disable")
def totp_disable(
    payload: TOTPVerifyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not getattr(current_user, "totp_enabled", False):
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    secret = getattr(current_user, "totp_secret", None)
    if not secret or not verify_totp(secret, payload.totp_code):
        raise HTTPException(status_code=400, detail="Invalid TOTP code")
    current_user.totp_enabled = False
    current_user.totp_secret = None
    db.add(current_user)
    db.commit()
    return {"message": "2FA disabled"}
