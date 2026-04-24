"""Google Calendar OAuth service.

Flow:
  1. GET  /integrations/google/auth-url  → redirect user to Google consent screen
  2. GET  /integrations/google/callback?code=&state=  → exchange code for token, persist to UserPreferences
  3. GET  /integrations/google/status   → connected / email / scopes
  4. DELETE /integrations/google/disconnect  → wipe token

Set env vars:
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET,
  GOOGLE_REDIRECT_URI (must match Google Cloud Console redirect URI)
"""
from __future__ import annotations

import secrets
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core._config import settings
from app.core._logging import get_logger
from app.models._user import User
from app.models._user_preferences import UserPreferences

logger = get_logger(__name__)

# In-process CSRF nonce store: nonce -> (user_id, expires_at)
# Entries expire after 10 minutes. Good enough for single-instance; Redis can replace this.
_oauth_nonces: dict[str, tuple[int, float]] = {}

_SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def _flow():
    """Build an OAuth2 flow. Raises RuntimeError if Google creds are not configured."""
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise RuntimeError("Google OAuth credentials are not configured")
    from google_auth_oauthlib.flow import Flow

    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=_SCOPES,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


def _get_or_create_prefs(db: Session, user_id: int) -> UserPreferences:
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)
        db.flush()
    return prefs


def _purge_expired_nonces() -> None:
    now = time.monotonic()
    expired = [k for k, (_, exp) in _oauth_nonces.items() if exp < now]
    for k in expired:
        del _oauth_nonces[k]


def get_auth_url(user_id: int) -> str:
    _purge_expired_nonces()
    nonce = secrets.token_urlsafe(32)
    _oauth_nonces[nonce] = (user_id, time.monotonic() + 600)  # 10-min TTL
    flow = _flow()
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=nonce,
    )
    return auth_url


def handle_callback(db: Session, code: str, state: str) -> dict:
    """Exchange the OAuth code for tokens, persist them, return status dict."""
    _purge_expired_nonces()
    entry = _oauth_nonces.pop(state, None)
    if not entry:
        raise ValueError("Invalid or expired OAuth state — possible CSRF attempt")
    user_id, expires_at = entry
    if time.monotonic() > expires_at:
        raise ValueError("OAuth state expired")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("User not found")

    flow = _flow()
    flow.fetch_token(code=code)
    credentials = flow.credentials

    # Fetch user email from Google
    google_email: str | None = None
    try:
        import google.auth.transport.requests as _requests
        import requests as _req

        info_resp = _req.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=10,
        )
        if info_resp.ok:
            google_email = info_resp.json().get("email")
    except Exception:
        pass

    token_blob: dict[str, Any] = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": list(credentials.scopes or []),
    }

    prefs = _get_or_create_prefs(db, user_id)
    prefs.google_calendar_connected = True
    prefs.google_calendar_token = token_blob
    prefs.google_calendar_email = google_email
    db.add(prefs)
    db.commit()

    return {"connected": True, "google_email": google_email}


def get_status(db: Session, user_id: int) -> dict:
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs or not prefs.google_calendar_connected:
        return {"connected": False}
    return {
        "connected": True,
        "google_email": prefs.google_calendar_email,
        "scopes": (prefs.google_calendar_token or {}).get("scopes", []),
    }


def disconnect(db: Session, user_id: int) -> None:
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if prefs:
        prefs.google_calendar_connected = False
        prefs.google_calendar_token = None
        prefs.google_calendar_email = None
        db.add(prefs)
        db.commit()


def create_calendar_event(db: Session, user_id: int, event: dict) -> dict:
    """Create a Google Calendar event using stored credentials.

    event dict shape (ISO-8601 strings):
      summary, description, start_datetime, end_datetime, attendee_emails (list)
    """
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs or not prefs.google_calendar_connected or not prefs.google_calendar_token:
        raise ValueError("Google Calendar not connected for this user")

    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    blob = prefs.google_calendar_token
    creds = Credentials(
        token=blob.get("token"),
        refresh_token=blob.get("refresh_token"),
        token_uri=blob.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=blob.get("client_id"),
        client_secret=blob.get("client_secret"),
        scopes=blob.get("scopes"),
    )

    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    body = {
        "summary": event.get("summary", "Meeting"),
        "description": event.get("description", ""),
        "start": {"dateTime": event["start_datetime"], "timeZone": "UTC"},
        "end": {"dateTime": event["end_datetime"], "timeZone": "UTC"},
        "attendees": [{"email": e} for e in (event.get("attendee_emails") or [])],
        "conferenceData": {
            "createRequest": {"requestId": event.get("summary", "meet"), "conferenceSolutionKey": {"type": "hangoutsMeet"}}
        },
    }
    result = service.events().insert(calendarId="primary", body=body, conferenceDataVersion=1, sendUpdates="all").execute()

    # Persist refreshed token
    if creds.token != blob.get("token"):
        blob["token"] = creds.token
        prefs.google_calendar_token = blob
        db.add(prefs)
        db.commit()

    return {"event_id": result.get("id"), "html_link": result.get("htmlLink")}
