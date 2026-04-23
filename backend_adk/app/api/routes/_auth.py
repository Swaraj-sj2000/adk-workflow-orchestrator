# backend/app/api/routes/_auth.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core._deps import get_current_user
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
    register_user,
    request_password_reset,
    reset_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


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
    token, user_data = result
    return {"access_token": token, "user": user_data}


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
