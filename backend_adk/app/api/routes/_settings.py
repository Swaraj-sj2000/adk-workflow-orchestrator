from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core._deps import get_current_user, get_db
from app.models._user import User
from app.schemas._settings import PasswordChange, ProfileUpdate, SupportTicketCreate, UserPreferencesUpdate
from app.services._settings_service import SettingsService


router = APIRouter(tags=["Settings"])


@router.get("/me")
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    preferences = SettingsService.get_preferences(db, current_user.id)
    return {
        "user": {
            "id": current_user.id,
            "email": current_user.email,
            "full_name": current_user.full_name,
            "role": current_user.role,
            "tenant_id": current_user.tenant_id,
        },
        "preferences": {
            "id": preferences.id,
            "timezone": preferences.timezone,
            "theme": preferences.theme,
            "language": preferences.language,
            "ceo_mode": preferences.ceo_mode,
            "notification_density": preferences.notification_density,
            "default_landing_page": preferences.default_landing_page,
            "email_notifications": preferences.email_notifications,
            "weekly_digest": preferences.weekly_digest,
        },
    }


@router.patch("/preferences")
def update_preferences(
    payload: UserPreferencesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        preferences = SettingsService.update_preferences(db, current_user.id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return preferences


@router.patch("/profile")
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        user = SettingsService.update_profile(db, current_user, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    preferences = SettingsService.get_preferences(db, current_user.id)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "tenant_id": user.tenant_id,
        },
        "preferences": {
            "id": preferences.id,
            "timezone": preferences.timezone,
            "theme": preferences.theme,
            "language": preferences.language,
            "ceo_mode": preferences.ceo_mode,
            "notification_density": preferences.notification_density,
            "default_landing_page": preferences.default_landing_page,
            "email_notifications": preferences.email_notifications,
            "weekly_digest": preferences.weekly_digest,
        },
    }


@router.post("/change-password")
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        SettingsService.change_password(db, current_user, payload.current_password, payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"message": "Password changed"}


@router.post("/support")
def submit_support(
    payload: SupportTicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return SettingsService.submit_support_ticket(
            db,
            current_user,
            payload.subject,
            payload.body,
            priority=payload.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/export")
def export_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return SettingsService.export_user_data(db, current_user)
