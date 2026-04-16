# backend/app/api/routes/_auth.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db._database import get_db
from app.schemas._user import UserCreate, UserLogin
from app.services._auth_service import register_user, login_user
from fastapi.security import OAuth2PasswordBearer

router = APIRouter(prefix="/auth", tags=["Auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


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
