# backend/app/core/_config.py

import os
import sys
import logging

_logger = logging.getLogger(__name__)

_KNOWN_INSECURE_DEFAULTS = {"supersecretkey", "secret", "changeme", ""}

_raw_secret = os.getenv("SECRET_KEY", "supersecretkey")

if _raw_secret in _KNOWN_INSECURE_DEFAULTS:
    _env = os.getenv("ENVIRONMENT", "development").lower()
    if _env == "production":
        # Hard-fail: insecure key must never sign production JWTs
        sys.exit(
            "[FATAL] SECRET_KEY is set to a known insecure default. "
            "Set a strong SECRET_KEY env var before starting in production."
        )
    else:
        _logger.critical(
            "SECRET_KEY is using an insecure default value. "
            "Set the SECRET_KEY environment variable before deploying to production."
        )


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    SECRET_KEY = _raw_secret
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60
    BASIC_RATE_LIMIT_REQUESTS = int(os.getenv("BASIC_RATE_LIMIT_REQUESTS", "120"))
    BASIC_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("BASIC_RATE_LIMIT_WINDOW_SECONDS", "60"))
    SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
    EMAIL_FROM = os.getenv("EMAIL_FROM", "no-reply@orchestrator.ai")
    EMAIL_FROM_NAME = os.getenv("EMAIL_FROM_NAME", "AI Workforce Orchestrator")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    PLATFORM_OWNER_EMAIL = os.getenv("PLATFORM_OWNER_EMAIL", "")
    STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_STARTER_PRICE_ID = os.getenv("STRIPE_STARTER_PRICE_ID", "")
    STRIPE_GROWTH_PRICE_ID = os.getenv("STRIPE_GROWTH_PRICE_ID", "")
    STRIPE_ENTERPRISE_PRICE_ID = os.getenv("STRIPE_ENTERPRISE_PRICE_ID", "")
    STRIPE_CONNECT_CLIENT_ID = os.getenv("STRIPE_CONNECT_CLIENT_ID", "")
    GRACE_PERIOD_DAYS = int(os.getenv("GRACE_PERIOD_DAYS", "7"))
    REDIS_URL = os.getenv("REDIS_URL", "")
    # Google OAuth (Calendar / Gmail integrations)
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
    GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:5173/integrations/google/callback")
    
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
