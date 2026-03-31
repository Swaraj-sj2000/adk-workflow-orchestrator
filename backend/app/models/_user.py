# backend/app/models/_user.py

from sqlalchemy import Column, Integer, String
from app.db._database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)
    role = Column(String)  # admin / employee / client