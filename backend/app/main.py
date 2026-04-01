# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db._database import Base, engine

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
from app.api.routes import _task_assignment as _task_assignment_routes
from app.api.routes import _task_progress as _task_progress_routes
from app.api.routes import _multi_agent as _multi_agent_routes

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
    _workflow_run, _agent_run
)

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Workforce Orchestrator")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
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
app.include_router(_task_assignment_routes.router)
app.include_router(_task_progress_routes.router)
app.include_router(_multi_agent_routes.router)


@app.get("/")
def root():
    return {"message": "AI Workforce Orchestrator Running"}
