# backend/app/services/_auth_service.py

from sqlalchemy.orm import Session
from app.models._user import User
from app.core._security import hash_password, verify_password, create_access_token


def register_user(db: Session, email: str, password: str, role: str):
    user = User(email=email, password=hash_password(password), role=role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password):
        return None
    token = create_access_token({"sub": user.email, "role": user.role})
    return token