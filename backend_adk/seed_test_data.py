#!/usr/bin/env python3
"""
Production seed for AI Workforce Orchestrator (backend_adk — Cloud Run / PostgreSQL).

TARGET: Online PostgreSQL database via DATABASE_URL environment variable.
SAFETY: Non-destructive by default — skips records that already exist.

Usage:
    # Default: safe upsert, skips existing rows
    DATABASE_URL='postgresql://user:pass@host/db' python seed_test_data.py

    # Fresh deployment only: wipe and rebuild (DESTRUCTIVE — prompts for confirmation)
    DATABASE_URL='postgresql://...' python seed_test_data.py --reset

Do NOT run with --reset on a live database with real user data.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

# ── Validate DATABASE_URL before importing anything from app ──────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is not set.")
    print()
    print("Set it to your Cloud SQL PostgreSQL connection string, e.g.:")
    print("  export DATABASE_URL='postgresql://user:pass@/dbname?host=/cloudsql/project:region:instance'")
    print()
    print("For local testing, use backend/seed_test_data.py instead.")
    sys.exit(1)

if DATABASE_URL.startswith("sqlite"):
    print("ERROR: DATABASE_URL points to SQLite. This script targets the production PostgreSQL DB.")
    print("For local SQLite testing, use backend/seed_test_data.py instead.")
    sys.exit(1)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Parse args before heavy imports ──────────────────────────────────────────
parser = argparse.ArgumentParser(description="Seed the production database")
parser.add_argument(
    "--reset",
    action="store_true",
    help="DROP and recreate all tables before seeding. DESTRUCTIVE — prompts for confirmation.",
)
args = parser.parse_args()

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

# ── Seed credentials ──────────────────────────────────────────────────────────

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
     "full_name": "Amira Khan", "title": "Solution Architect",
     "department": "Solutioning", "skills": {"architecture": 0.95, "delivery": 0.82, "backend": 0.72}},
    {"email": "arjun.rao@orchestrateco.ai", "password": "team123456",
     "full_name": "Arjun Rao", "title": "AI Engineer",
     "department": "AI Delivery", "skills": {"llm": 0.95, "python": 0.88, "prompting": 0.82}},
    {"email": "neha.gupta@orchestrateco.ai", "password": "team123456",
     "full_name": "Neha Gupta", "title": "Backend Engineer",
     "department": "Engineering", "skills": {"backend": 0.93, "python": 0.90, "api": 0.86}},
    {"email": "yash.patel@orchestrateco.ai", "password": "team123456",
     "full_name": "Yash Patel", "title": "Frontend Engineer",
     "department": "Engineering", "skills": {"frontend": 0.91, "react": 0.89, "design-systems": 0.74}},
    {"email": "sofia.dsouza@orchestrateco.ai", "password": "team123456",
     "full_name": "Sofia D'Souza", "title": "QA Automation Engineer",
     "department": "Quality", "skills": {"qa": 0.94, "testing": 0.91, "automation": 0.87}},
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
     "full_name": "Maya Ramesh", "title": "Data Scientist",
     "department": "Data", "skills": {"data": 0.93, "python": 0.88, "analytics": 0.84}},
    {"email": "tom.brooks@globaltech.io", "password": "team123456",
     "full_name": "Tom Brooks", "title": "DevOps Engineer",
     "department": "Platform", "skills": {"devops": 0.91, "cloud": 0.87, "security": 0.79}},
]

CLIENT_B = {
    "email": "partner@techventures.com", "password": "client123456",
    "full_name": "Lisa Park", "role": "client", "company_name": "TechVentures",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

_created = 0
_skipped = 0


def _upsert_user(db, email, password, full_name, role, tenant_id,
                 totp_secret=None, totp_enabled=False):
    """Insert user if email doesn't exist, else return existing. Never overwrites passwords."""
    global _created, _skipped
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        _skipped += 1
        return existing, False
    u = User(
        email=email,
        password=hash_password(password),
        full_name=full_name,
        role=role,
        tenant_id=tenant_id,
        email_verified=True,
        email_verify_token=None,
        totp_secret=totp_secret,
        totp_enabled=totp_enabled,
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
    existing = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if existing:
        return existing
    p = UserPreferences(user_id=user_id, **kwargs)
    db.add(p)
    db.flush()
    return p


def _ensure_employee(db, user, skills, department):
    existing = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user.id).first()
    if existing:
        return existing
    profile = EmployeeProfile(
        tenant_id=user.tenant_id,
        user_id=user.id,
        skills=skills,
        max_capacity=8.0,
        current_load=0.0,
        department=department,
        availability_status="available",
    )
    db.add(profile)
    db.flush()
    db.add(EmployeeMetrics(
        employee_id=profile.id,
        efficiency_score=0.87,
        reliability_score=0.92,
        avg_completion_time=0.0,
        total_tasks_completed=12,
        total_tasks_failed=0,
        total_tasks_delayed=1,
    ))
    return profile


def _ensure_client_profile(db, user, company_name):
    existing = db.query(ClientProfile).filter(ClientProfile.user_id == user.id).first()
    if existing:
        return existing
    cp = ClientProfile(
        tenant_id=user.tenant_id,
        user_id=user.id,
        company_name=company_name,
        contact_person=user.full_name,
    )
    db.add(cp)
    db.flush()
    return cp


def _ensure_tenant_settings(db, tenant_id, **kwargs):
    existing = db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant_id).first()
    if existing:
        return existing
    ts = TenantSettings(tenant_id=tenant_id, **kwargs)
    db.add(ts)
    db.flush()
    return ts


def _make_task(db, tenant_id, project_id, description, status, required_skills,
               estimated_time=4.0, priority="medium", difficulty="medium"):
    t = Task(
        tenant_id=tenant_id,
        project_id=project_id,
        description=description,
        status=status,
        required_skills=required_skills,
        estimated_time=estimated_time,
        urgency=priority,
        difficulty=difficulty,
        deadline=datetime.utcnow() + timedelta(days=14),
    )
    db.add(t)
    db.flush()
    return t


# ── Seed sections ─────────────────────────────────────────────────────────────

def seed_platform_owner(db):
    platform_tenant, _ = _upsert_tenant(db, "Platform", "platform")
    owner, created = _upsert_user(
        db, **PLATFORM_OWNER, tenant_id=platform_tenant.id
    )
    if created:
        _ensure_prefs(db, owner.id, timezone="Asia/Kolkata", theme="dark")
    return owner, platform_tenant


def seed_tenant_a(db):
    tenant, t_created = _upsert_tenant(db, TENANT_A_NAME, TENANT_A_SLUG)

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
        p = _ensure_employee(db, u, m["skills"], m["department"])
        emp_profiles.append(p)

    client_u, _ = _upsert_user(
        db, email=CLIENT_A["email"], password=CLIENT_A["password"],
        full_name=CLIENT_A["full_name"], role=CLIENT_A["role"], tenant_id=tenant.id,
    )
    client_cp = _ensure_client_profile(db, client_u, CLIENT_A["company_name"])
    _ensure_prefs(db, client_u.id, timezone="America/New_York")

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

    # Skip if project already exists for this tenant
    existing = db.query(Project).filter(
        Project.tenant_id == tenant.id,
        Project.name == "AI-Powered Analytics Platform",
    ).first()
    if existing:
        print(f"  [skip] Projects already seeded for {tenant.name}")
        return existing, None

    p1 = Project(
        tenant_id=tenant.id, name="AI-Powered Analytics Platform",
        description="Build an end-to-end AI analytics platform with real-time dashboards.",
        admin_id=admin.id, client_id=client_cp.id,
        status="in-progress", progress=58, budget=120000.0, spent=42000.0,
        payment_status="partial", priority="high",
        start_date=now - timedelta(days=30), deadline=now + timedelta(days=60),
        custom_fields={"health_score": 72, "risk_flags": ["timeline risk"]},
    )
    db.add(p1)
    db.flush()

    tasks_p1 = [
        _make_task(db, tenant.id, p1.id, "Design data ingestion pipeline",
                   "completed", {"architecture": 0.7, "backend": 0.6}, 8.0, "high"),
        _make_task(db, tenant.id, p1.id, "Implement LLM summarisation service",
                   "in_progress", {"llm": 0.8, "python": 0.7}, 12.0, "high"),
        _make_task(db, tenant.id, p1.id, "Build REST API for dashboard queries",
                   "in_progress", {"backend": 0.8, "api": 0.7}, 8.0, "medium"),
        _make_task(db, tenant.id, p1.id, "Develop React dashboard frontend",
                   "pending", {"frontend": 0.8, "react": 0.7}, 16.0, "medium"),
        _make_task(db, tenant.id, p1.id, "Write E2E test suite",
                   "pending", {"qa": 0.8, "testing": 0.7}, 10.0, "medium"),
    ]

    deleted_task = _make_task(db, tenant.id, p1.id, "Old requirement — replaced",
                               "cancelled", {"llm": 0.5}, 4.0)
    deleted_task.deleted_at = now - timedelta(days=5)
    db.add(deleted_task)

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
        description="Modernise the client e-commerce platform with AI recommendations.",
        admin_id=admin.id, client_id=client_cp.id,
        status="planning", progress=0, budget=75000.0, spent=0.0,
        priority="medium", deadline=now + timedelta(days=90),
    )
    db.add(p2)
    db.flush()
    _make_task(db, tenant.id, p2.id, "Stakeholder requirements workshop",
               "pending", {"communication": 0.7, "architecture": 0.5}, 4.0)
    _make_task(db, tenant.id, p2.id, "Define AI recommendation model spec",
               "pending", {"llm": 0.7, "architecture": 0.6}, 6.0)

    soft_deleted_project = Project(
        tenant_id=tenant.id, name="Legacy CRM Integration (Cancelled)",
        description="Cancelled by client.", admin_id=admin.id,
        status="cancelled", progress=10, budget=30000.0, spent=3000.0,
        deleted_at=now - timedelta(days=10),
    )
    db.add(soft_deleted_project)
    db.flush()

    return p1, p2


def seed_workflow_and_agents(db, admin, project):
    existing = db.query(WorkflowRun).filter(
        WorkflowRun.project_id == project.id,
        WorkflowRun.workflow_type == "intake",
    ).first()
    if existing:
        return

    now = datetime.utcnow()
    run = WorkflowRun(
        workflow_type="intake", status="completed",
        requested_by=admin.id, project_id=project.id,
        input_payload={"project_name": project.name, "budget": project.budget},
        shared_context={"tenant_id": project.tenant_id},
        final_output={"plan_approved": True, "risk_level": "medium"},
        created_at=now - timedelta(days=28),
        completed_at=now - timedelta(days=28) + timedelta(minutes=4),
    )
    db.add(run)
    db.flush()

    for name, stage, reasoning in [
        ("IntakeAgent", "intake", "Parse and validate project intake"),
        ("PlanningAgent", "planning", "Generate execution plan with milestones"),
        ("StaffingAgent", "staffing", "Score and assign team members"),
        ("RiskAgent", "risk_assessment", "Evaluate timeline and budget risk"),
        ("ExecutionCoordinatorAgent", "coordination", "Finalise execution plan"),
        ("CommunicationAgent", "communication", "Draft project brief emails"),
        ("EscalationAgent", "escalation", "No escalation required"),
    ]:
        db.add(AgentRun(
            workflow_run_id=run.id, agent_name=name, role=stage, stage=stage,
            status="completed", confidence=0.87,
            reasoning=reasoning, input_payload={}, output_payload={"status": "ok"},
            started_at=run.created_at,
            completed_at=run.created_at + timedelta(seconds=30),
        ))

    db.add(DecisionLog(
        decision_type="assignment", entity_type="task", entity_id=project.id,
        input_data={"project_id": project.id, "agent": "StaffingAgent"},
        decision_taken="Assigned Arjun Rao to LLM task (score: 0.91)",
        confidence=0.91,
        reasoning="Highest score across skill match, workload, efficiency, timezone",
    ))
    db.flush()


def seed_scheduler_jobs(db, tenant):
    existing = db.query(ScheduledAgentJob).filter(
        ScheduledAgentJob.tenant_id == tenant.id
    ).first()
    if existing:
        return

    now = datetime.utcnow()
    for job_type, cron, tz, last_offset, next_offset in [
        ("nightly_observer", "0 2 * * *", "UTC", timedelta(hours=22), timedelta(hours=2)),
        ("weekly_digest", "0 9 * * 1", "Asia/Kolkata", timedelta(days=7), timedelta(days=1)),
        ("payment_check", "0 10 * * *", "UTC", timedelta(hours=14), timedelta(hours=10)),
        ("archive_old_runs", "0 3 * * 0", "UTC", timedelta(days=7), timedelta(days=1)),
    ]:
        db.add(ScheduledAgentJob(
            tenant_id=tenant.id, job_type=job_type, cron_expr=cron,
            timezone=tz, enabled=True,
            last_run_at=now - last_offset,
            next_run_at=now + next_offset,
            last_status="success",
        ))
    db.flush()


def seed_email_logs(db, tenant):
    existing = db.query(EmailDeliveryLog).filter(
        EmailDeliveryLog.tenant_id == tenant.id
    ).first()
    if existing:
        return

    now = datetime.utcnow()
    for to_email, subject, template, status in [
        (CEO["email"], "Welcome to AI Workforce Orchestrator", "welcome", "success"),
        (ADMIN["email"], "Verify your email address", "email_verification", "success"),
        (CLIENT_A["email"], "Your project brief is ready", "project_brief", "success"),
        (CEO["email"], "Weekly digest — week of Apr 14", "weekly_digest", "success"),
        (ADMIN["email"], "Task assignment: Build REST API", "task_assignment", "success"),
        (ADMIN["email"], "Escalation alert: Blocked task", "escalation_alert", "failed"),
    ]:
        db.add(EmailDeliveryLog(
            tenant_id=tenant.id, to_email=to_email,
            subject=subject, template_name=template, status=status,
            sendgrid_message_id=f"SG.mock_{template}" if status == "success" else None,
            error_message="SendGrid API timeout" if status == "failed" else None,
            sent_at=now - timedelta(hours=2) if status == "success" else None,
        ))
    db.flush()


def seed_support_ticket(db, tenant, admin, owner):
    existing = db.query(SupportTicket).filter(
        SupportTicket.tenant_id == tenant.id
    ).first()
    if existing:
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
        print(f"\nTarget database: {DATABASE_URL[:DATABASE_URL.index('@') + 1]}***")
        confirm = input(
            "\nWARNING: --reset will DELETE ALL DATA in this database.\n"
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
        owner, _ = seed_platform_owner(db)
        tenant_a, ceo, admin, admin_rt, emp_profiles, client_cp = seed_tenant_a(db)
        tenant_b, admin_b = seed_tenant_b(db)
        p1, p2 = seed_projects_and_tasks(db, tenant_a, admin, emp_profiles, client_cp)
        if p1:
            seed_workflow_and_agents(db, admin, p1)
        seed_scheduler_jobs(db, tenant_a)
        seed_email_logs(db, tenant_a)
        seed_support_ticket(db, tenant_a, admin, owner)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    totp = pyotp.TOTP(CEO_TOTP_SECRET)
    print("\n" + "=" * 64)
    print("  Production Seed Complete")
    print(f"  DB: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    print(f"  Created: {_created} records   Skipped (already exist): {_skipped}")
    print("=" * 64)

    print("\n[ Platform Owner ]")
    print(f"  {PLATFORM_OWNER['email']}  /  {PLATFORM_OWNER['password']}")

    print("\n[ Tenant A: OrchestrateCo — Pro plan ]")
    print(f"  CEO (2FA)  : {CEO['email']}  /  {CEO['password']}")
    print(f"  TOTP secret: {CEO_TOTP_SECRET}")
    print(f"  Live code  : {totp.now()}  (valid ~30 s — regenerate fresh code on next login)")
    print(f"  2FA login  : Step 1 → POST /auth/login")
    print(f"               Step 2 → POST /auth/2fa/verify-login  {{mfa_session_token, totp_code}}")
    print(f"  Admin      : {ADMIN['email']}  /  {ADMIN['password']}")
    if admin_rt:
        print(f"  Admin RT   : {admin_rt[:24]}... (30-day refresh token)")
    for m in EMPLOYEES_A:
        print(f"  Employee   : {m['email']}  /  {m['password']}")
    print(f"  Client     : {CLIENT_A['email']}  /  {CLIENT_A['password']}")

    print("\n[ Tenant B: GlobalTech — Starter / grace period ]")
    print(f"  Admin      : {ADMIN_B['email']}  /  {ADMIN_B['password']}")
    for m in EMPLOYEES_B:
        print(f"  Employee   : {m['email']}  /  {m['password']}")
    print(f"  Client     : {CLIENT_B['email']}  /  {CLIENT_B['password']}")

    print("\n[ Projects — Tenant A ]")
    print("  1. AI-Powered Analytics Platform  in-progress  58%  (5 tasks + 5 assignments)")
    print("  2. E-Commerce Redesign            planning      0%  (2 tasks)")
    print("  3. Legacy CRM Integration         SOFT DELETED      (hidden from API)")

    print("\n[ Online endpoints ]")
    print("  https://backend-adk-974381609416.europe-west1.run.app/docs")
    print("  https://frontend-974381609416.europe-west1.run.app")
    print()


if __name__ == "__main__":
    main()
