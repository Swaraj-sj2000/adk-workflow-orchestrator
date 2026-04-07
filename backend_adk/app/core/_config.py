# backend/app/core/_config.py

import os

class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    BASIC_RATE_LIMIT_REQUESTS = int(os.getenv("BASIC_RATE_LIMIT_REQUESTS", "120"))
    BASIC_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("BASIC_RATE_LIMIT_WINDOW_SECONDS", "60"))
    
    # Logging Configuration
    LOG_DIR = os.getenv("LOG_DIR", "./logs")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", 10 * 1024 * 1024))  # 10MB default
    LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
    )

settings = Settings()
