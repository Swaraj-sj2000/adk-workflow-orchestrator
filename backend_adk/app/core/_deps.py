# app/core/_deps.py

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.db._database import get_db
from app.models._user import User
from app.core._config import settings
from app.core._tenant_context import TenantContext

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: int = payload.get("user_id")
        tenant_id: int = payload.get("tenant_id")
        role: str | None = payload.get("role")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token payload missing user_id")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    if role == "platform_owner" or user.role == "platform_owner":
        request.state.tenant_id = None
        TenantContext.clear()
        return user

    if tenant_id is None or user.tenant_id != tenant_id:
        raise HTTPException(status_code=401, detail="Tenant mismatch for authenticated user")

    request.state.tenant_id = user.tenant_id
    TenantContext.set_tenant_id(user.tenant_id)
    return user


def require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_ceo_or_admin(current_user: User = Depends(get_current_user)):
    if current_user.role not in ("ceo", "admin", "platform_owner"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return current_user


def require_platform_owner(current_user: User = Depends(get_current_user)):
    if current_user.role != "platform_owner":
        raise HTTPException(status_code=403, detail="Platform owner access required")
    return current_user
