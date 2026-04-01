# app/core/_deps.py

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.db._database import get_db
from app.models._user import User
from app.models._auth_user import AuthUser
from app.core._config import settings  # ✅ same key that _security.py uses to SIGN tokens

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        # Support both old format (user_id) and new multi-tenant format (sub)
        user_id = payload.get("user_id") or payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Token payload missing user_id or sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Try to get AuthUser first (UUID format)
    if isinstance(user_id, str) and len(user_id) > 10:  # UUID is a long string
        user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
        if user:
            return user
    
    # Fall back to legacy User model (integer ID)
    try:
        user_id_int = int(user_id) if isinstance(user_id, str) else user_id
        user = db.query(User).filter(User.id == user_id_int).first()
        if user:
            return user
    except (ValueError, TypeError):
        pass
    
    raise HTTPException(status_code=401, detail="User not found")
