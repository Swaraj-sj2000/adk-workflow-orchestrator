# backend/app/core/_config.py

import os

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./agentic_orchestrator.db")
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    
    # Base URL for generating invite links
    BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")

settings = Settings()