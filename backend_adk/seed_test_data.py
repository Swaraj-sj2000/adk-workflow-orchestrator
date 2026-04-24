#!/usr/bin/env python3
"""
Production seed for AI Workforce Orchestrator — backend_adk (Cloud Run + Cloud SQL + Vertex AI).

TARGET  : Google Cloud SQL PostgreSQL (europe-west1, project havoc-ai-prod)
AI STACK: Gemini 2.5 Flash via Vertex AI + Google ADK
SAFETY  : Non-destructive by default. Skips rows that already exist.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW TO CONNECT TO CLOUD SQL FROM YOUR LAPTOP
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Option A — Cloud SQL Auth Proxy (recommended):

    # Terminal 1: start proxy
    cloud-sql-proxy havoc-ai-prod:europe-west1:orchestrator-sql --port 5432

    # Terminal 2: run seed via localhost
    export DATABASE_URL="postgresql+psycopg2://orchestrator_user:PASSWORD@localhost:5432/orchestrator"
    export GOOGLE_CLOUD_PROJECT="havoc-ai-prod"
    export GOOGLE_CLOUD_LOCATION="europe-west1"
    export GOOGLE_GENAI_USE_VERTEXAI="true"
    export GEMINI_MODEL="gemini-2.5-flash"
    python seed_test_data.py

Option B — Cloud Run Job (no local proxy needed):

    gcloud run jobs create seed-job \
      --image REGION-docker.pkg.dev/havoc-ai-prod/orchestrator-repo/backend-adk:latest \
      --region europe-west1 \
      --service-account ai-workflow-orchestrator@havoc-ai-prod.iam.gserviceaccount.com \
      --add-cloudsql-instances havoc-ai-prod:europe-west1:orchestrator-sql \
      --set-env-vars DATABASE_URL="postgresql+psycopg2://orchestrator_user:PASS@/orchestrator?host=/cloudsql/havoc-ai-prod:europe-west1:orchestrator-sql" \
      --set-env-vars GOOGLE_CLOUD_PROJECT=havoc-ai-prod \
      --set-env-vars GOOGLE_CLOUD_LOCATION=europe-west1 \
      --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true \
      --set-env-vars GEMINI_MODEL=gemini-2.5-flash \
      --command python,seed_test_data.py
    gcloud run jobs execute seed-job --region europe-west1

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FLAGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  --check   Pre-flight only: verify DB + Vertex AI connectivity, no writes
  --reset   DESTRUCTIVE wipe + rebuild (fresh Cloud SQL deployment only)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

# ── Required env vars ─────────────────────────────────────────────────────────
_REQUIRED = {
    "DATABASE_URL":             "Cloud SQL PostgreSQL connection string (see header for format)",
    "GOOGLE_CLOUD_PROJECT":     "GCP project ID (e.g. havoc-ai-prod)",
    "GOOGLE_CLOUD_LOCATION":    "GCP region (e.g. europe-west1)",
    "GOOGLE_GENAI_USE_VERTEXAI":"Must be 'true' for production",
}
_DEFAULTS = {
    "GEMINI_MODEL": "gemini-2.5-flash",
}

_missing = [k for k in _REQUIRED if not os.getenv(k)]
if _missing:
    print("\nERROR: Missing required environment variables:\n")
    for k in _missing:
        print(f"  {k}  —  {_REQUIRED[k]}")
    print("\nSee the file header for connection instructions.")
    print("For local SQLite testing use backend/seed_test_data.py instead.\n")
    sys.exit(1)

DATABASE_URL = os.environ["DATABASE_URL"]
GCP_PROJECT  = os.environ["GOOGLE_CLOUD_PROJECT"]
GCP_REGION   = os.environ["GOOGLE_CLOUD_LOCATION"]

if DATABASE_URL.startswith("sqlite"):
    print("ERROR: DATABASE_URL points to SQLite. This script targets Cloud SQL PostgreSQL.")
    print("For local testing use backend/seed_test_data.py instead.")
    sys.exit(1)

for k, v in _DEFAULTS.items():
    os.environ.setdefault(k, v)

GEMINI_MODEL = os.environ["GEMINI_MODEL"]

# ── Args ──────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="Seed Cloud SQL database for backend_adk")
parser.add_argument("--check", action="store_true",
                    help="Pre-flight checks only — no database writes")
parser.add_argument("--reset", action="store_true",
                    help="DROP and recreate all tables first. DESTRUCTIVE.")
args = parser.parse_args()

# ── sys.path ──────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Pre-flight checks ─────────────────────────────────────────────────────────
def _preflight():
    ok = True
    host_display = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL

    print("\n── Pre-flight checks ─────────────────────────────────────────")

    # 1. Database connectivity
    print(f"\n[1] Cloud SQL PostgreSQL  ({host_display})")
    try:
        import psycopg2
        # Build a raw psycopg2 DSN from SQLAlchemy URL
        raw = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(raw, connect_timeout=10)
        conn.close()
        print("    ✓ Connected successfully")
    except Exception as e:
        print(f"    ✗ FAILED: {e}")
        print("      → Is Cloud SQL Auth Proxy running? (see file header)")
        ok = False

    # 2. google-genai / Vertex AI import
    print(f"\n[2] Vertex AI SDK  (google-genai)")
    try:
        from google import genai
        print("    ✓ google-genai importable")
    except ImportError as e:
        print(f"    ✗ FAILED: {e}")
        print("      → pip install google-genai>=0.2.0")
        ok = False

    # 3. Vertex AI client init + model ping
    print(f"\n[3] Gemini via Vertex AI  (project={GCP_PROJECT}, region={GCP_REGION})")
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(vertexai=True, project=GCP_PROJECT, location=GCP_REGION)
        # Minimal call — list first model to verify credentials + quota
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents="Say 'ok' in one word.",
            config=types.GenerateContentConfig(max_output_tokens=5),
        )
        reply = (getattr(response, "text", "") or "").strip()
        print(f"    ✓ {GEMINI_MODEL} responded: '{reply}'")
    except Exception as e:
        print(f"    ✗ FAILED: {e}")
        print("      → Check IAM: service account needs roles/aiplatform.user")
        print("      → Run: gcloud auth application-default login")
        ok = False

    # 4. ADK availability
    print(f"\n[4] Google ADK")
    try:
        import google.adk  # noqa
        print("    ✓ google-adk importable")
    except ImportError:
        print("    ⚠  google-adk not importable in this env (OK if running seed outside container)")

    print("\n── Pre-flight result ─────────────────────────────────────────")
    if ok:
        print("    ALL CHECKS PASSED ✓\n")
    else:
        print("    ONE OR MORE CHECKS FAILED ✗")
        print("    Fix the errors above before seeding.\n")
    return ok


if args.check:
    passed = _preflight()
    sys.exit(0 if passed else 1)

# Run pre-flight before any imports that touch the DB
passed = _preflight()
if not passed:
    print("Aborting seed — pre-flight failed. Use --check for details.\n")
    sys.exit(1)

# ── Heavy imports (after pre-flight) ─────────────────────────────────────────
import pyotp

from app.core._security import generate_refresh_token, hash_password
from app.db._database import Base, SessionLocal, engine
from app.db._schema import ensure_runtime_schema
from app.models import (
    _agent, _agent_run, _audit_log, _availability, _blocker, _checkpoint,
    _client_profile, _communication, _decision_log, _email_delivery_log,
    _employee_metrics, _employee_profile, _event_queue, _meeting,
    _performance_point, _platform_audit_log, _project, _refresh_token,
    _scheduled_agent_job, _support_ticket, _task, _task_assignment,
    _task_dependency, _task_progress, _team, _team_invite, _tenant,
    _tenant_settings, _user, _user_preferences, _workflow_run,
)
from app.models._agent import Agent
from app.models._agent_run import AgentRun
from app.models._client_profile import ClientProfile
from app.models._decision_log import DecisionLog
from app.models._email_delivery_log import EmailDeliveryLog
from app.models._employee_metrics import EmployeeMetrics
from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
from app.models._refresh_token import RefreshToken
from app.models._scheduled_agent_job import ScheduledAgentJob
from app.models._support_ticket import SupportTicket
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._tenant import Tenant
from app.models._tenant_settings import TenantSettings
from app.models._user import User
from app.models._user_preferences import UserPreferences
from app.models._workflow_run import WorkflowRun

# ── Credentials ───────────────────────────────────────────────────────────────

PLATFORM_OWNER = {
    "email": "swaraj@orchestrator.ai",
    "password": "OwnerSecure#99",
    "full_name": "Swaraj Menon",
    "role": "platform_owner",
}

TENANT_A_NAME = "OrchestrateCo"
TENANT_A_SLUG = "orchestrateco"

CEO = {
    "email": "priya.sharma@orchestrateco.ai",
    "password": "CEO_Secure#88",
    "full_name": "Priya Sharma",
    "role": "ceo",
}
CEO_TOTP_SECRET = pyotp.random_base32()

ADMIN = {
    "email": "rohan.mehta@orchestrateco.ai",
    "password": "Admin_Secure#77",
    "full_name": "Rohan Mehta",
    "role": "admin",
}

EMPLOYEES_A = [
    {"email": "amira.khan@orchestrateco.ai", "password": "team123456",
     "full_name": "Amira Khan", "department": "Solutioning",
     "skills": {"architecture": 0.95, "delivery": 0.82, "backend": 0.72}},
    {"email": "arjun.rao@orchestrateco.ai", "password": "team123456",
     "full_name": "Arjun Rao", "department": "AI Delivery",
     "skills": {"llm": 0.95, "python": 0.88, "prompting": 0.82}},
    {"email": "neha.gupta@orchestrateco.ai", "password": "team123456",
     "full_name": "Neha Gupta", "department": "Engineering",
     "skills": {"backend": 0.93, "python": 0.90, "api": 0.86}},
    {"email": "yash.patel@orchestrateco.ai", "password": "team123456",
     "full_name": "Yash Patel", "department": "Engineering",
     "skills": {"frontend": 0.91, "react": 0.89, "design-systems": 0.74}},
    {"email": "sofia.dsouza@orchestrateco.ai", "password": "team123456",
     "full_name": "Sofia D'Souza", "department": "Quality",
     "skills": {"qa": 0.94, "testing": 0.91, "automation": 0.87}},
]

CLIENT_A = {
    "email": "contact@globalcorp.com", "password": "client123456",
    "full_name": "Marcus Chen", "role": "client", "company_name": "GlobalCorp",
}

TENANT_B_NAME = "GlobalTech Solutions"
TENANT_B_SLUG = "globaltech"

ADMIN_B = {
    "email": "alex.turner@globaltech.io", "password": "Admin_Secure#66",
    "full_name": "Alex Turner", "role": "admin",
}

EMPLOYEES_B = [
    {"email": "maya.r@globaltech.io", "password": "team123456",
     "full_name": "Maya Ramesh", "department": "Data",
     "skills": {"data": 0.93, "python": 0.88, "analytics": 0.84}},
    {"email": "tom.brooks@globaltech.io", "password": "team123456",
     "full_name": "Tom Brooks", "department": "Platform",
     "skills": {"devops": 0.91, "cloud": 0.87, "security": 0.79}},
]

CLIENT_B = {
    "email": "partner@techventures.com", "password": "client123456",
    "full_name": "Lisa Park", "role": "client", "company_name": "TechVentures",
}

# 12 agents that form the two agentic workflows
# model_name matches what the deploy script sets as GEMINI_MODEL
AGENT_DEFINITIONS = [
    # Intake workflow (7 agents)
    {"name": "IntakeAgent",                "role": "intake",        "capability": f"Parse project intake via {GEMINI_MODEL}"},
    {"name": "PlanningAgent",              "role": "planning",      "capability": f"Generate execution plan via {GEMINI_MODEL}"},
    {"name": "StaffingAgent",              "role": "staffing",      "capability": f"Score + assign team members via {GEMINI_MODEL}"},
    {"name": "RiskAgent",                  "role": "risk",          "capability": f"Evaluate timeline/budget risk via {GEMINI_MODEL}"},
    {"name": "ExecutionCoordinatorAgent",  "role": "coordination",  "capability": f"Finalise execution plan via {GEMINI_MODEL}"},
    {"name": "CommunicationAgent",         "role": "communication", "capability": f"Draft client/admin emails via {GEMINI_MODEL}"},
    {"name": "EscalationAgent",            "role": "escalation",    "capability": f"Escalate to humans when confidence < 0.6"},
    # Live execution loop (5 agents)
    {"name": "ProjectObserverAgent",       "role": "observation",   "capability": f"Monitor project health via {GEMINI_MODEL}"},
    {"name": "DeliveryReviewAgent",        "role": "review",        "capability": f"Review deliverables via {GEMINI_MODEL}"},
    {"name": "RebalanceAgent",             "role": "rebalance",     "capability": f"Rebalance assignments via {GEMINI_MODEL}"},
    {"name": "LoopCommunicationAgent",     "role": "loop_comms",    "capability": f"Update stakeholder comms via {GEMINI_MODEL}"},
    {"name": "LoopEscalationAgent",        "role": "loop_escalation","capability": "Escalate loop blockers to admin"},
]

# ── Stats counters ────────────────────────────────────────────────────────────
_created = 0
_skipped = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upsert_user(db, email, password, full_name, role, tenant_id,
                 totp_secret=None, totp_enabled=False):
    global _created, _skipped
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        _skipped += 1
        return existing, False
    u = User(
        email=email, password=hash_password(password),
        full_name=full_name, role=role, tenant_id=tenant_id,
        email_verified=True, email_verify_token=None,
        totp_secret=totp_secret, totp_enabled=totp_enabled,
    )
    db.add(u)
    db.flush()
    _created += 1
    return u, True


def _upsert_tenant(db, name, slug):
    global _created, _skipped
    existing = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing:
        _skipped += 1
        return existing, False
    t = Tenant(name=name, slug=slug)
    db.add(t)
    db.flush()
    _created += 1
    return t, True


def _ensure_prefs(db, user_id, **kwargs):
    if db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first():
        return
    db.add(UserPreferences(user_id=user_id, **kwargs))
    db.flush()


def _ensure_employee(db, user, skills, department):
    existing = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user.id).first()
    if existing:
        return existing
    p = EmployeeProfile(
        tenant_id=user.tenant_id, user_id=user.id,
        skills=skills, max_capacity=8.0, current_load=0.0,
        department=department, availability_status="available",
    )
    db.add(p)
    db.flush()
    db.add(EmployeeMetrics(
        employee_id=p.id, efficiency_score=0.87, reliability_score=0.92,
        avg_completion_time=0.0, total_tasks_completed=12,
        total_tasks_failed=0, total_tasks_delayed=1,
    ))
    return p


def _ensure_client_profile(db, user, company_name):
    existing = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    if existing:
        return existing
    cp = ClientProfile(
        tenant_id=user.tenant_id, user_id=user.id,
        company_name=company_name, contact_person=user.full_name,
    )
    db.add(cp)
    db.flush()
    return cp


def _ensure_tenant_settings(db, tenant_id, **kwargs):
    if db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant_id).first():
        return
    db.add(TenantSettings(tenant_id=tenant_id, **kwargs))
    db.flush()


def _make_task(db, tenant_id, project_id, description, status, required_skills,
               estimated_time=4.0, urgency="medium", difficulty="medium"):
    t = Task(
        tenant_id=tenant_id, project_id=project_id,
        description=description, status=status,
        required_skills=required_skills, estimated_time=estimated_time,
        urgency=urgency, difficulty=difficulty,
        deadline=datetime.utcnow() + timedelta(days=14),
    )
    db.add(t)
    db.flush()
    return t


# ── Seed sections ─────────────────────────────────────────────────────────────

def seed_agents(db):
    """Seed the 12 agent definitions (Gemini 2.5 Flash via Vertex AI)."""
    for defn in AGENT_DEFINITIONS:
        existing = db.query(Agent).filter(Agent.name == defn["name"]).first()
        if not existing:
            db.add(Agent(name=defn["name"], role=defn["role"], capability=defn["capability"]))
    db.flush()


def seed_platform_owner(db):
    platform_tenant, _ = _upsert_tenant(db, "Platform", "platform")
    owner, created = _upsert_user(db, **PLATFORM_OWNER, tenant_id=platform_tenant.id)
    if created:
        _ensure_prefs(db, owner.id, timezone="Asia/Kolkata", theme="dark")
    return owner, platform_tenant


def seed_tenant_a(db):
    tenant, _ = _upsert_tenant(db, TENANT_A_NAME, TENANT_A_SLUG)

    _ensure_tenant_settings(db, tenant.id,
        plan_tier="pro", suspended=False,
        stripe_customer_id="cus_seed_orchestrateco",
        stripe_subscription_id="sub_seed_orchestrateco",
        stripe_plan_id="price_pro_monthly",
        next_billing_date=datetime.utcnow() + timedelta(days=22),
        max_users=50, max_projects=20, max_ai_calls_per_month=500,
    )

    ceo, ceo_created = _upsert_user(
        db, **CEO, tenant_id=tenant.id,
        totp_secret=CEO_TOTP_SECRET, totp_enabled=True,
    )
    if ceo_created:
        _ensure_prefs(db, ceo.id,
            timezone="Asia/Kolkata", theme="dark", ceo_mode=True,
            default_landing_page="ceo-dashboard",
            google_calendar_connected=True,
            google_calendar_email="priya.sharma@gmail.com",
            google_calendar_token={
                "token": "ya29.mock_access_token",
                "refresh_token": "1//mock_refresh_token",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "mock_client_id.apps.googleusercontent.com",
                "client_secret": "mock_secret",
                "scopes": ["https://www.googleapis.com/auth/calendar.events"],
            },
        )

    admin, admin_created = _upsert_user(db, **ADMIN, tenant_id=tenant.id)
    admin_rt = None
    if admin_created:
        _ensure_prefs(db, admin.id, timezone="Asia/Kolkata", theme="light")
        raw_token = generate_refresh_token()
        db.add(RefreshToken(
            user_id=admin.id, token=raw_token,
            expires_at=datetime.utcnow() + timedelta(days=30), revoked=False,
        ))
        admin_rt = raw_token

    emp_profiles = []
    for m in EMPLOYEES_A:
        u, created = _upsert_user(
            db, email=m["email"], password=m["password"],
            full_name=m["full_name"], role="employee", tenant_id=tenant.id,
        )
        if created:
            _ensure_prefs(db, u.id, timezone="Asia/Kolkata")
        emp_profiles.append(_ensure_employee(db, u, m["skills"], m["department"]))

    client_u, _ = _upsert_user(
        db, email=CLIENT_A["email"], password=CLIENT_A["password"],
        full_name=CLIENT_A["full_name"], role=CLIENT_A["role"], tenant_id=tenant.id,
    )
    _ensure_prefs(db, client_u.id, timezone="America/New_York")
    client_cp = _ensure_client_profile(db, client_u, CLIENT_A["company_name"])

    return tenant, ceo, admin, admin_rt, emp_profiles, client_cp


def seed_tenant_b(db):
    tenant, _ = _upsert_tenant(db, TENANT_B_NAME, TENANT_B_SLUG)
    _ensure_tenant_settings(db, tenant.id,
        plan_tier="starter", suspended=False,
        stripe_customer_id="cus_seed_globaltech",
        stripe_subscription_id="sub_seed_globaltech",
        grace_period_ends_at=datetime.utcnow() + timedelta(days=3),
        max_users=10, max_projects=5,
    )
    admin, admin_created = _upsert_user(db, **ADMIN_B, tenant_id=tenant.id)
    if admin_created:
        _ensure_prefs(db, admin.id, timezone="Europe/London")
    for m in EMPLOYEES_B:
        u, created = _upsert_user(
            db, email=m["email"], password=m["password"],
            full_name=m["full_name"], role="employee", tenant_id=tenant.id,
        )
        if created:
            _ensure_prefs(db, u.id, timezone="Europe/London")
        _ensure_employee(db, u, m["skills"], m["department"])
    client_u, _ = _upsert_user(
        db, email=CLIENT_B["email"], password=CLIENT_B["password"],
        full_name=CLIENT_B["full_name"], role=CLIENT_B["role"], tenant_id=tenant.id,
    )
    _ensure_client_profile(db, client_u, CLIENT_B["company_name"])
    return tenant, admin


def seed_projects_and_tasks(db, tenant, admin, emp_profiles, client_cp):
    now = datetime.utcnow()

    existing = db.query(Project).filter(
        Project.tenant_id == tenant.id,
        Project.name == "AI-Powered Analytics Platform",
    ).first()
    if existing:
        print(f"  [skip] Projects already seeded for {tenant.name}")
        return existing, None

    p1 = Project(
        tenant_id=tenant.id, name="AI-Powered Analytics Platform",
        description="End-to-end AI analytics platform with real-time dashboards on GCP.",
        admin_id=admin.id, client_id=client_cp.id,
        status="in-progress", progress=58, budget=120000.0, spent=42000.0,
        payment_status="partial", priority="high",
        start_date=now - timedelta(days=30), deadline=now + timedelta(days=60),
        custom_fields={
            "health_score": 72,
            "risk_flags": ["timeline risk"],
            "ai_stack": f"Gemini {GEMINI_MODEL} via Vertex AI ({GCP_PROJECT}/{GCP_REGION})",
        },
    )
    db.add(p1)
    db.flush()

    tasks_p1 = [
        _make_task(db, tenant.id, p1.id, "Design data ingestion pipeline",
                   "completed", {"architecture": 0.7, "backend": 0.6}, 8.0, "high"),
        _make_task(db, tenant.id, p1.id, "Implement LLM summarisation service (Gemini 2.5)",
                   "in_progress", {"llm": 0.8, "python": 0.7}, 12.0, "high"),
        _make_task(db, tenant.id, p1.id, "Build REST API for dashboard queries",
                   "in_progress", {"backend": 0.8, "api": 0.7}, 8.0, "medium"),
        _make_task(db, tenant.id, p1.id, "Develop React dashboard frontend",
                   "pending", {"frontend": 0.8, "react": 0.7}, 16.0, "medium"),
        _make_task(db, tenant.id, p1.id, "Write E2E test suite",
                   "pending", {"qa": 0.8, "testing": 0.7}, 10.0, "medium"),
    ]

    # Soft-deleted task — tests filter correctness
    dt = _make_task(db, tenant.id, p1.id, "Old requirement — superseded by Gemini approach",
                    "cancelled", {"llm": 0.5}, 4.0)
    dt.deleted_at = now - timedelta(days=5)
    db.add(dt)

    for task, emp_idx in zip(tasks_p1, range(len(emp_profiles))):
        db.add(TaskAssignment(
            task_id=task.id, employee_id=emp_profiles[emp_idx].id,
            status="assigned", assignment_confidence=0.88,
        ))
        emp_profiles[emp_idx].current_load = min(
            emp_profiles[emp_idx].current_load + task.estimated_time, 8.0
        )
        db.add(emp_profiles[emp_idx])

    p2 = Project(
        tenant_id=tenant.id, name="E-Commerce Redesign",
        description="Modernise e-commerce with AI-powered product recommendations via Vertex AI.",
        admin_id=admin.id, client_id=client_cp.id,
        status="planning", progress=0, budget=75000.0, spent=0.0,
        priority="medium", deadline=now + timedelta(days=90),
    )
    db.add(p2)
    db.flush()
    _make_task(db, tenant.id, p2.id, "Stakeholder requirements workshop",
               "pending", {"communication": 0.7, "architecture": 0.5}, 4.0)
    _make_task(db, tenant.id, p2.id, "Define Gemini recommendation model spec",
               "pending", {"llm": 0.7, "architecture": 0.6}, 6.0)

    soft_p = Project(
        tenant_id=tenant.id, name="Legacy CRM Integration (Cancelled)",
        description="Cancelled — client moved budget to AI-first initiative.",
        admin_id=admin.id, status="cancelled", progress=10,
        budget=30000.0, spent=3000.0, deleted_at=now - timedelta(days=10),
    )
    db.add(soft_p)
    db.flush()

    return p1, p2


def seed_workflow_and_agents(db, admin, project):
    if db.query(WorkflowRun).filter(
        WorkflowRun.project_id == project.id,
        WorkflowRun.workflow_type == "intake",
    ).first():
        return

    now = datetime.utcnow()
    run = WorkflowRun(
        workflow_type="intake", status="completed",
        requested_by=admin.id, project_id=project.id,
        input_payload={"project_name": project.name, "budget": project.budget,
                       "model": GEMINI_MODEL, "gcp_project": GCP_PROJECT},
        shared_context={"tenant_id": project.tenant_id, "vertex_ai": True},
        final_output={"plan_approved": True, "risk_level": "medium",
                      "model_used": GEMINI_MODEL},
        created_at=now - timedelta(days=28),
        completed_at=now - timedelta(days=28) + timedelta(minutes=4),
    )
    db.add(run)
    db.flush()

    for name, stage, confidence, reasoning in [
        ("IntakeAgent",               "intake",        0.94, f"Parsed intake via {GEMINI_MODEL} — all fields extracted"),
        ("PlanningAgent",             "planning",      0.89, f"Generated 6-milestone plan via {GEMINI_MODEL}"),
        ("StaffingAgent",             "staffing",      0.91, f"Scored 5 candidates via assignment engine"),
        ("RiskAgent",                 "risk_assessment",0.82, f"Identified timeline risk via {GEMINI_MODEL}"),
        ("ExecutionCoordinatorAgent", "coordination",  0.88, "Finalised execution plan — no conflicts"),
        ("CommunicationAgent",        "communication", 0.95, "Drafted admin + client briefs"),
        ("EscalationAgent",           "escalation",    0.99, "No escalation required — confidence above threshold"),
    ]:
        db.add(AgentRun(
            workflow_run_id=run.id, agent_name=name, role=stage, stage=stage,
            status="completed", confidence=confidence,
            reasoning=reasoning, input_payload={},
            output_payload={"status": "ok", "model": GEMINI_MODEL},
            started_at=run.created_at,
            completed_at=run.created_at + timedelta(seconds=35),
        ))

    db.add(DecisionLog(
        decision_type="assignment", entity_type="task", entity_id=project.id,
        input_data={"agent": "StaffingAgent", "model": GEMINI_MODEL,
                    "scoring_formula": "0.35×skill + 0.25×(1-load) + 0.20×efficiency + 0.20×reliability − 0.15×tz_penalty"},
        decision_taken="Assigned Arjun Rao to LLM service task (score: 0.91)",
        confidence=0.91,
        reasoning="skill_match=0.95 (llm), workload=0.88, efficiency=0.87, reliability=0.92, tz_penalty=0.0",
    ))
    db.flush()


def seed_scheduler_jobs(db, tenant):
    if db.query(ScheduledAgentJob).filter(
        ScheduledAgentJob.tenant_id == tenant.id
    ).first():
        return
    now = datetime.utcnow()
    for job_type, cron, tz, last_delta, next_delta in [
        ("nightly_observer", "0 2 * * *",  "UTC",          timedelta(hours=22), timedelta(hours=2)),
        ("weekly_digest",    "0 9 * * 1",  "Asia/Kolkata", timedelta(days=7),   timedelta(days=1)),
        ("payment_check",    "0 10 * * *", "UTC",          timedelta(hours=14), timedelta(hours=10)),
        ("archive_old_runs", "0 3 * * 0",  "UTC",          timedelta(days=7),   timedelta(days=1)),
    ]:
        db.add(ScheduledAgentJob(
            tenant_id=tenant.id, job_type=job_type, cron_expr=cron,
            timezone=tz, enabled=True,
            last_run_at=now - last_delta,
            next_run_at=now + next_delta,
            last_status="success",
        ))
    db.flush()


def seed_email_logs(db, tenant):
    if db.query(EmailDeliveryLog).filter(EmailDeliveryLog.tenant_id == tenant.id).first():
        return
    now = datetime.utcnow()
    for to_email, subject, template, status in [
        (CEO["email"],   "Welcome to AI Workforce Orchestrator", "welcome",            "success"),
        (ADMIN["email"], "Verify your email address",            "email_verification", "success"),
        (CLIENT_A["email"], "Your project brief is ready",       "project_brief",      "success"),
        (CEO["email"],   "Weekly digest — week of Apr 14",       "weekly_digest",      "success"),
        (ADMIN["email"], "Task assignment: Build REST API",       "task_assignment",    "success"),
        (ADMIN["email"], "Escalation alert: Blocked task",        "escalation_alert",  "failed"),
    ]:
        db.add(EmailDeliveryLog(
            tenant_id=tenant.id, to_email=to_email,
            subject=subject, template_name=template, status=status,
            sendgrid_message_id=f"SG.mock_{template}" if status == "success" else None,
            error_message="SendGrid API timeout" if status == "failed" else None,
            sent_at=now - timedelta(hours=2) if status == "success" else None,
        ))
    db.flush()


def seed_support_ticket(db, tenant, admin):
    if db.query(SupportTicket).filter(SupportTicket.tenant_id == tenant.id).first():
        return
    db.add(SupportTicket(
        tenant_id=tenant.id, user_id=admin.id,
        subject="Request to increase project limit",
        body="Hi Swaraj,\n\nWe need our project cap raised from 20 to 30 for new clients.\n\nThanks,\nRohan",
        status="open", priority="medium",
    ))
    db.flush()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _created, _skipped

    if args.reset:
        db_host = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        confirm = input(
            f"\n⚠  --reset will DELETE ALL DATA in {db_host}\n"
            "Type 'yes-delete-everything' to confirm: "
        )
        if confirm.strip() != "yes-delete-everything":
            print("Aborted.")
            sys.exit(0)
        print("Dropping all tables...")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema(engine)
        print("Tables recreated.\n")
    else:
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema(engine)

    db = SessionLocal()
    try:
        print("Seeding agents (12 × Gemini 2.5 Flash via Vertex AI)...")
        seed_agents(db)

        print("Seeding platform owner...")
        owner, _ = seed_platform_owner(db)

        print("Seeding Tenant A: OrchestrateCo (Pro plan)...")
        tenant_a, ceo, admin, admin_rt, emp_profiles, client_cp = seed_tenant_a(db)

        print("Seeding Tenant B: GlobalTech (grace-period test)...")
        tenant_b, admin_b = seed_tenant_b(db)

        print("Seeding projects + tasks + assignments...")
        p1, p2 = seed_projects_and_tasks(db, tenant_a, admin, emp_profiles, client_cp)

        if p1:
            print(f"Seeding WorkflowRun + 7 AgentRun records ({GEMINI_MODEL})...")
            seed_workflow_and_agents(db, admin, p1)

        print("Seeding scheduler jobs (4 types)...")
        seed_scheduler_jobs(db, tenant_a)

        print("Seeding email delivery logs...")
        seed_email_logs(db, tenant_a)

        print("Seeding support ticket...")
        seed_support_ticket(db, tenant_a, admin)

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    totp = pyotp.TOTP(CEO_TOTP_SECRET)
    db_host = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL

    print("\n" + "=" * 68)
    print("  Production Seed Complete — AI Workforce Orchestrator")
    print("=" * 68)
    print(f"\n  GCP Project  : {GCP_PROJECT}")
    print(f"  Region       : {GCP_REGION}")
    print(f"  AI Model     : {GEMINI_MODEL} via Vertex AI")
    print(f"  Database     : {db_host}")
    print(f"  Records      : {_created} created   {_skipped} skipped (already existed)")

    print("\n[ Platform Owner ]")
    print(f"  {PLATFORM_OWNER['email']}  /  {PLATFORM_OWNER['password']}")

    print("\n[ Tenant A: OrchestrateCo — Pro plan ]")
    print(f"  CEO (2FA)  : {CEO['email']}  /  {CEO['password']}")
    print(f"  TOTP secret: {CEO_TOTP_SECRET}")
    print(f"  Live code  : {totp.now()}  (valid ~30 s — re-run for a fresh code)")
    print(f"  2FA login  : Step 1 → POST /auth/login")
    print(f"               Step 2 → POST /auth/2fa/verify-login {{mfa_session_token, totp_code}}")
    print(f"  Admin      : {ADMIN['email']}  /  {ADMIN['password']}")
    if admin_rt:
        print(f"  Admin RT   : {admin_rt[:24]}...  (30-day refresh token)")
    for m in EMPLOYEES_A:
        print(f"  Employee   : {m['email']}  /  team123456")
    print(f"  Client     : {CLIENT_A['email']}  /  client123456")

    print("\n[ Tenant B: GlobalTech — Starter / grace period (3 days) ]")
    print(f"  Admin      : {ADMIN_B['email']}  /  {ADMIN_B['password']}")
    for m in EMPLOYEES_B:
        print(f"  Employee   : {m['email']}  /  team123456")
    print(f"  Client     : {CLIENT_B['email']}  /  client123456")

    print("\n[ Agents seeded (12 × Vertex AI / Gemini 2.5 Flash) ]")
    for a in AGENT_DEFINITIONS:
        print(f"  {a['name']:35s}  role={a['role']}")

    print("\n[ Live endpoints ]")
    print("  https://backend-adk-974381609416.europe-west1.run.app/docs")
    print("  https://frontend-974381609416.europe-west1.run.app")
    print("  https://backend-adk-974381609416.europe-west1.run.app/healthz")
    print()


if __name__ == "__main__":
    main()
