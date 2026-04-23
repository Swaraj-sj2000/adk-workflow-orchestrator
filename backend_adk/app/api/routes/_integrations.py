"""Integration endpoints — Google Calendar OAuth."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core._deps import get_current_user, get_db
from app.models._user import User
from app.services import _calendar_service as calendar

router = APIRouter(prefix="/integrations", tags=["Integrations"])


class CalendarEventRequest(BaseModel):
    summary: str
    description: str = ""
    start_datetime: str  # ISO-8601 with timezone, e.g. "2026-05-01T10:00:00Z"
    end_datetime: str
    attendee_emails: list[str] = []


# ── Google Calendar ──────────────────────────────────────────────────────────

@router.get("/google/auth-url")
def google_auth_url(current_user: User = Depends(get_current_user)):
    try:
        url = calendar.get_auth_url(current_user.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"auth_url": url}


@router.get("/google/callback")
def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    """Redirect target registered in Google Cloud Console.

    Google will call this with ?code=...&state=<user_id>.
    In production the frontend intercepts this redirect; in development
    the raw JSON response is sufficient to confirm the handshake.
    """
    try:
        result = calendar.handle_callback(db, code=code, state=state)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google OAuth failed: {exc}")
    return result


@router.get("/google/status")
def google_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return calendar.get_status(db, current_user.id)


@router.delete("/google/disconnect")
def google_disconnect(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    calendar.disconnect(db, current_user.id)
    return {"disconnected": True}


@router.post("/google/calendar/events")
def create_calendar_event(
    payload: CalendarEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return calendar.create_calendar_event(db, current_user.id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Google Calendar error: {exc}")
