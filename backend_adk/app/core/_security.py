# backend/app/core/_security.py

import secrets
from datetime import datetime, timedelta

from jose import jwt
from passlib.context import CryptContext

from app.core._config import settings

REFRESH_TOKEN_EXPIRE_DAYS = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def generate_totp_secret() -> str:
    import pyotp
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    import pyotp
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def get_totp_provisioning_uri(secret: str, email: str) -> str:
    import pyotp
    return pyotp.TOTP(secret).provisioning_uri(
        name=email, issuer_name="AI Workforce Orchestrator"
    )


def create_mfa_session_token(user_id: int) -> str:
    """Short-lived token (5 min) issued when 2FA is required. Not a full access token."""
    payload = {
        "mfa_pending": True,
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_mfa_session_token(token: str) -> int | None:
    """Returns user_id if the token is a valid mfa_pending token, else None."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if not payload.get("mfa_pending"):
            return None
        return payload.get("user_id")
    except Exception:
        return None
