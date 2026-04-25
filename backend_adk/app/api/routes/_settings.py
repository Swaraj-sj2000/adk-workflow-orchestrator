import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
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
            "id":              current_user.id,
            "email":           current_user.email,
            "full_name":       current_user.full_name,
            "first_name":      getattr(current_user, "first_name", None),
            "last_name":       getattr(current_user, "last_name", None),
            "phone":           getattr(current_user, "phone", None),
            "secondary_email": getattr(current_user, "secondary_email", None),
            "position":        getattr(current_user, "position", None),
            "location":        getattr(current_user, "location", None),
            "avatar_url":      getattr(current_user, "avatar_url", None),
            "role":            current_user.role,
            "tenant_id":       current_user.tenant_id,
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
            "id":              user.id,
            "email":           user.email,
            "full_name":       user.full_name,
            "first_name":      getattr(user, "first_name", None),
            "last_name":       getattr(user, "last_name", None),
            "phone":           getattr(user, "phone", None),
            "secondary_email": getattr(user, "secondary_email", None),
            "position":        getattr(user, "position", None),
            "location":        getattr(user, "location", None),
            "avatar_url":      getattr(user, "avatar_url", None),
            "role":            user.role,
            "tenant_id":       user.tenant_id,
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


class PositionValidateRequest(BaseModel):
    position: str


@router.post("/validate-position")
def validate_position(
    payload: PositionValidateRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Validate a free-text job position title.
    Uses LLM when available; falls back to heuristics.
    Returns { valid: bool, suggestion: str | null, reason: str | null }
    """
    text = payload.position.strip()

    # Hard heuristic gates (fast-fail before any LLM call)
    if len(text) < 2:
        return {"valid": False, "suggestion": None, "reason": "Too short."}
    if re.fullmatch(r'[^a-zA-Z]+', text):
        return {"valid": False, "suggestion": None, "reason": "Must contain letters."}
    if re.search(r'(.)\1{4,}', text):          # 5+ repeated chars like "aaaaaa"
        return {"valid": False, "suggestion": None, "reason": "Doesn't look like a real job title."}
    if not re.search(r'[a-zA-Z]{2,}', text):
        return {"valid": False, "suggestion": None, "reason": "Doesn't look like a real job title."}

    # Try LLM validation
    try:
        from app.services._llm_service import LLMService
        llm = LLMService()
        if llm.enabled:
            from langchain_core.messages import HumanMessage, SystemMessage
            messages = [
                SystemMessage(content=(
                    "You validate job position titles. Reply ONLY with valid JSON, no markdown, no explanation. "
                    'Format: {"valid": true/false, "suggestion": "Corrected Title or null", "reason": "short reason or null"}'
                )),
                HumanMessage(content=(
                    f'Is "{text}" a meaningful, professional job title someone would have on LinkedIn? '
                    "If it is valid, return valid=true, suggestion=null, reason=null. "
                    "If it is gibberish or meaningless, return valid=false and optionally suggest a corrected version."
                )),
            ]
            import json as _json
            raw = llm._invoke_text(messages)
            cleaned = re.sub(r"```[a-z]*\n?|```", "", raw).strip()
            result = _json.loads(cleaned)
            return {
                "valid":      bool(result.get("valid", False)),
                "suggestion": result.get("suggestion"),
                "reason":     result.get("reason"),
            }
    except Exception:
        pass

    # Fallback heuristic: accept anything that looks like real words
    word_count = len(re.findall(r'[a-zA-Z]{2,}', text))
    if word_count == 0:
        return {"valid": False, "suggestion": None, "reason": "Doesn't look like a real job title."}
    return {"valid": True, "suggestion": None, "reason": None}
