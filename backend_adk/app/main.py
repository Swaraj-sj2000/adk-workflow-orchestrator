# backend/app/main.py

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.db._database import Base, engine
from app.core._logging import get_logger
from app.core._config import settings
from app.core._rate_limit import RateLimitMiddleware
from app.core._tenant_middleware import TenantMiddleware
from app.db._database import SessionLocal
from app.db._schema import ensure_runtime_schema
from contextlib import asynccontextmanager
import os
import time

logger = get_logger(__name__)

# Routes
from app.api.routes import _auth
from app.api.routes import _project as _project_routes
from app.api.routes import _agent as _agent_routes
from app.api.routes import _task as _task_routes
from app.api.routes import _system as _system_routes
from app.api.routes import _decision as _decision_routes
from app.api.routes import _blocker as _blocker_routes
from app.api.routes import _meeting as _meeting_routes
from app.api.routes import _employee as _employee_routes
from app.api.routes import _autopm as _autopm_routes
from app.api.routes import _invite as _invite_routes
from app.api.routes import _task_assignment as _task_assignment_routes
from app.api.routes import _task_progress as _task_progress_routes
from app.api.routes import _multi_agent as _multi_agent_routes
from app.api.routes import _ceo as _ceo_routes
from app.api.routes import _owner as _owner_routes
from app.api.routes import _settings as _settings_routes
from app.services._auth_service import bootstrap_tenant_data

# Models — must be imported so Base.metadata knows about all tables
from app.models import (
    _user, _project, _agent, _task,
    _employee_profile, _employee_metrics,
    _task_dependency, _task_assignment,
    _decision_log, _blocker,
    _task_progress, _availability,
    _event_queue, _meeting, _client_profile,
    _checkpoint, _communication,
    _performance_point, _audit_log,
    _workflow_run, _agent_run,
    _tenant, _team, _team_invite,
    _platform_audit_log,
    _user_preferences, _tenant_settings, _support_ticket,
    _scheduled_agent_job, _email_delivery_log
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("=== AI Workforce Orchestrator Starting ===")
    try:
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema(engine)
        db = SessionLocal()
        try:
            bootstrap_tenant_data(db)
            db.commit()
        finally:
            db.close()
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise
    
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("=== AI Workforce Orchestrator Shutting Down ===")


app = FastAPI(
    title="AI Workforce Orchestrator",
    lifespan=lifespan
)

app.add_middleware(TenantMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    requests_per_window=settings.BASIC_RATE_LIMIT_REQUESTS,
    window_seconds=settings.BASIC_RATE_LIMIT_WINDOW_SECONDS,
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing."""
    start_time = time.time()
    
    # Log incoming request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        logger.info(
            f"Response: {request.method} {request.url.path} - "
            f"status={response.status_code} duration={duration:.3f}s"
        )
        
        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(
            f"Request failed: {request.method} {request.url.path} - "
            f"error={str(e)} duration={duration:.3f}s",
            exc_info=True
        )
        raise


# Enable CORS
# In production set ALLOWED_ORIGINS to a comma-separated list of your
# actual frontend domains, e.g. "https://app.example.com".
# allow_credentials=True is incompatible with allow_origins=["*"] —
# when the wildcard is active we disable credentials to avoid Starlette's
# origin-echo behaviour that effectively bypasses the same-origin check.
_raw_origins = os.getenv("ALLOWED_ORIGINS", "")
_allowed_origins: list[str] = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else ["*"]
)
_allow_credentials = _allowed_origins != ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(_auth.router)
app.include_router(_project_routes.router)
app.include_router(_agent_routes.router)
app.include_router(_task_routes.router)
app.include_router(_system_routes.router)
app.include_router(_decision_routes.router)
app.include_router(_blocker_routes.router)
app.include_router(_meeting_routes.router)
app.include_router(_employee_routes.router)
app.include_router(_autopm_routes.router)
app.include_router(_invite_routes.router)
app.include_router(_task_assignment_routes.router)
app.include_router(_task_progress_routes.router)
app.include_router(_multi_agent_routes.router)
app.include_router(_ceo_routes.router, prefix="/ceo")
app.include_router(_owner_routes.router, prefix="/owner")
app.include_router(_settings_routes.router, prefix="/settings")


@app.get("/")
def root():
    logger.debug("Health check endpoint called")
    return {"message": "AI Workforce Orchestrator Running"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
