#!/usr/bin/env python3
"""
Full-featured seed for AI Workforce Orchestrator.

Covers every role and every feature introduced through Phase 11:

  Roles        : platform_owner, ceo (2FA), admin, employee (x5), client
  Tenants      : OrchestrateCo (main), GlobalTech (isolation test)
  Auth         : email verification, refresh tokens, 2FA (pyotp)
  Projects     : active (in-progress), planning, soft-deleted
  Tasks        : pending, in_progress, completed, blocked, soft-deleted
  Billing      : TenantSettings with Stripe ids, grace-period tenant
  Scheduler    : 4 job types seeded
  Agents       : WorkflowRun + AgentRun records
  Email        : EmailDeliveryLog samples
  Settings     : UserPreferences (CEO mode, Google Calendar mock)
  Support      : SupportTicket from admin to platform owner

Run:
    cd backend_adk
    python seed_test_data.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta

sys.path.insert(0, "/home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend_adk")

import pyotp

from app.core._security import generate_refresh_token, hash_password
from app.db._database import Base, SessionLocal, engine
from app.db._schema import ensure_runtime_schema
from app.models import (
    _agent,
    _agent_run,
    _audit_log,
    _availability,
    _blocker,
    _checkpoint,
    _client_profile,
    _communication,
    _decision_log,
    _email_delivery_log,
    _employee_metrics,
    _employee_profile,
    _event_queue,
    _meeting,
    _performance_point,
    _platform_audit_log,
    _project,
    _refresh_token,
    _scheduled_agent_job,
    _support_ticket,
    _task,
    _task_assignment,
    _task_dependency,
    _task_progress,
    _team,
    _team_invite,
    _tenant,
    _tenant_settings,
    _user,
    _user_preferences,
    _workflow_run,
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

# ── Credentials ──────────────────────────────────────────────────────────────

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
# Known TOTP secret — printed at the end so you can scan the QR or read the live code
CEO_TOTP_SECRET = pyotp.random_base32()

ADMIN = {
    "email": "rohan.mehta@orchestrateco.ai",
    "password": "Admin_Secure#77",
    "full_name": "Rohan Mehta",
    "role": "admin",
}

EMPLOYEES_A = [
    {
        "email": "amira.khan@orchestrateco.ai",
        "password": "team123456",
        "full_name": "Amira Khan",
        "title": "Solution Architect",
        "department": "Solutioning",
        "skills": {"architecture": 0.95, "delivery": 0.82, "backend": 0.72},
        "timezone": "Asia/Kolkata",
    },
    {
        "email": "arjun.rao@orchestrateco.ai",
        "password": "team123456",
        "full_name": "Arjun Rao",
        "title": "AI Engineer",
        "department": "AI Delivery",
        "skills": {"llm": 0.95, "python": 0.88, "prompting": 0.82},
        "timezone": "Asia/Kolkata",
    },
    {
        "email": "neha.gupta@orchestrateco.ai",
        "password": "team123456",
        "full_name": "Neha Gupta",
        "title": "Backend Engineer",
        "department": "Engineering",
        "skills": {"backend": 0.93, "python": 0.90, "api": 0.86},
        "timezone": "Asia/Singapore",
    },
    {
        "email": "yash.patel@orchestrateco.ai",
        "password": "team123456",
        "full_name": "Yash Patel",
        "title": "Frontend Engineer",
        "department": "Engineering",
        "skills": {"frontend": 0.91, "react": 0.89, "design-systems": 0.74},
        "timezone": "Asia/Singapore",
    },
    {
        "email": "sofia.dsouza@orchestrateco.ai",
        "password": "team123456",
        "full_name": "Sofia D'Souza",
        "title": "QA Automation Engineer",
        "department": "Quality",
        "skills": {"qa": 0.94, "testing": 0.91, "automation": 0.87},
        "timezone": "Australia/Sydney",
    },
]

CLIENT_A = {
    "email": "contact@globalcorp.com",
    "password": "client123456",
    "full_name": "Marcus Chen",
    "role": "client",
    "company_name": "GlobalCorp",
}

TENANT_B_NAME = "GlobalTech Solutions"
TENANT_B_SLUG = "globaltech"

ADMIN_B = {
    "email": "alex.turner@globaltech.io",
    "password": "Admin_Secure#66",
    "full_name": "Alex Turner",
    "role": "admin",
}

EMPLOYEES_B = [
    {
        "email": "maya.r@globaltech.io",
        "password": "team123456",
        "full_name": "Maya Ramesh",
        "title": "Data Scientist",
        "department": "Data",
        "skills": {"data": 0.93, "python": 0.88, "analytics": 0.84},
        "timezone": "Europe/London",
    },
    {
        "email": "tom.brooks@globaltech.io",
        "password": "team123456",
        "full_name": "Tom Brooks",
        "title": "DevOps Engineer",
        "department": "Platform",
        "skills": {"devops": 0.91, "cloud": 0.87, "security": 0.79},
        "timezone": "Europe/London",
    },
]

CLIENT_B = {
    "email": "partner@techventures.com",
    "password": "client123456",
    "full_name": "Lisa Park",
    "role": "client",
    "company_name": "TechVentures",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _user(db, email, password, full_name, role, tenant_id):
    u = User(
        email=email,
        password=hash_password(password),
        full_name=full_name,
        role=role,
        tenant_id=tenant_id,
        email_verified=True,
        email_verify_token=None,
    )
    db.add(u)
    db.flush()
    return u


def _prefs(db, user_id, **kwargs):
    p = UserPreferences(user_id=user_id, **kwargs)
    db.add(p)
    db.flush()
    return p


def _employee(db, user, skills, department, title, timezone="UTC"):
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
    db.add(
        EmployeeMetrics(
            employee_id=profile.id,
            efficiency_score=0.87,
            reliability_score=0.92,
            avg_completion_time=0.0,
            total_tasks_completed=12,
            total_tasks_failed=0,
            total_tasks_delayed=1,
        )
    )
    return profile


def _client_profile(db, user, company_name):
    cp = ClientProfile(
        tenant_id=user.tenant_id,
        user_id=user.id,
        company_name=company_name,
        contact_person=user.full_name,
    )
    db.add(cp)
    db.flush()
    return cp


def _task(db, tenant_id, project_id, description, status, required_skills,
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


def _assign(db, task_id, employee_profile_id):
    a = TaskAssignment(
        task_id=task_id,
        employee_id=employee_profile_id,
        status="assigned",
        assignment_confidence=0.88,
    )
    db.add(a)
    db.flush()
    return a


# ── Main seed sections ────────────────────────────────────────────────────────

def seed_platform_owner(db):
    # Platform owner belongs to a special "platform" tenant (no real company)
    platform_tenant = Tenant(name="Platform", slug="platform")
    db.add(platform_tenant)
    db.flush()

    owner = _user(db, **PLATFORM_OWNER, tenant_id=platform_tenant.id)
    _prefs(db, owner.id, timezone="Asia/Kolkata", theme="dark", ceo_mode=False)
    return owner


def seed_tenant_a(db):
    """OrchestrateCo — full feature demo tenant."""
    tenant = Tenant(name=TENANT_A_NAME, slug=TENANT_A_SLUG)
    db.add(tenant)
    db.flush()

    # Billing — active Pro plan
    db.add(TenantSettings(
        tenant_id=tenant.id,
        plan_tier="pro",
        suspended=False,
        stripe_customer_id="cus_seed_orchestrateco",
        stripe_subscription_id="sub_seed_orchestrateco",
        stripe_plan_id="price_pro_monthly",
        next_billing_date=datetime.utcnow() + timedelta(days=22),
        max_users=50,
        max_projects=20,
        max_ai_calls_per_month=500,
    ))
    db.flush()

    # CEO — with 2FA enabled
    ceo = _user(db, **CEO, tenant_id=tenant.id)
    ceo.totp_secret = CEO_TOTP_SECRET
    ceo.totp_enabled = True
    db.add(ceo)
    _prefs(
        db, ceo.id,
        timezone="Asia/Kolkata",
        theme="dark",
        ceo_mode=True,
        default_landing_page="ceo-dashboard",
        # Mock Google Calendar connected
        google_calendar_connected=True,
        google_calendar_email="priya.sharma@gmail.com",
        google_calendar_token={
            "token": "ya29.mock_access_token",
            "refresh_token": "1//mock_refresh_token",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "mock_client_id.apps.googleusercontent.com",
            "client_secret": "mock_secret",
            "scopes": [
                "https://www.googleapis.com/auth/calendar.events",
                "https://www.googleapis.com/auth/userinfo.email",
            ],
        },
    )

    # Admin — with a live refresh token (simulates logged-in session)
    admin = _user(db, **ADMIN, tenant_id=tenant.id)
    _prefs(db, admin.id, timezone="Asia/Kolkata", theme="light")
    raw_token = generate_refresh_token()
    db.add(RefreshToken(
        user_id=admin.id,
        token=raw_token,
        expires_at=datetime.utcnow() + timedelta(days=30),
        revoked=False,
    ))

    # Employees
    emp_users = []
    emp_profiles = []
    for m in EMPLOYEES_A:
        u = _user(db, email=m["email"], password=m["password"],
                  full_name=m["full_name"], role="employee", tenant_id=tenant.id)
        _prefs(db, u.id, timezone=m["timezone"])
        p = _employee(db, u, m["skills"], m["department"], m["title"], m["timezone"])
        emp_users.append(u)
        emp_profiles.append(p)

    # Client
    client_u = _user(db, **{k: v for k, v in CLIENT_A.items() if k != "company_name"},
                     tenant_id=tenant.id)
    client_cp = _client_profile(db, client_u, CLIENT_A["company_name"])
    _prefs(db, client_u.id, timezone="America/New_York")

    return tenant, ceo, admin, raw_token, emp_profiles, client_cp


def seed_tenant_b(db):
    """GlobalTech — second tenant for isolation testing."""
    tenant = Tenant(name=TENANT_B_NAME, slug=TENANT_B_SLUG)
    db.add(tenant)
    db.flush()

    # Billing — grace period (payment failed, not yet suspended)
    db.add(TenantSettings(
        tenant_id=tenant.id,
        plan_tier="starter",
        suspended=False,
        stripe_customer_id="cus_seed_globaltech",
        stripe_subscription_id="sub_seed_globaltech",
        grace_period_ends_at=datetime.utcnow() + timedelta(days=3),
        max_users=10,
        max_projects=5,
    ))
    db.flush()

    admin = _user(db, **ADMIN_B, tenant_id=tenant.id)
    _prefs(db, admin.id, timezone="Europe/London")

    for m in EMPLOYEES_B:
        u = _user(db, email=m["email"], password=m["password"],
                  full_name=m["full_name"], role="employee", tenant_id=tenant.id)
        _prefs(db, u.id, timezone=m["timezone"])
        _employee(db, u, m["skills"], m["department"], m["title"], m["timezone"])

    client_u = _user(db, **{k: v for k, v in CLIENT_B.items() if k != "company_name"},
                     tenant_id=tenant.id)
    _client_profile(db, client_u, CLIENT_B["company_name"])

    return tenant, admin


def seed_projects_and_tasks(db, tenant, admin, emp_profiles, client_cp):
    """Seed projects at different stages with tasks and assignments."""

    now = datetime.utcnow()

    # ── Project 1: AI Analytics — in-progress ────────────────────────────────
    p1 = Project(
        tenant_id=tenant.id,
        name="AI-Powered Analytics Platform",
        description="Build an end-to-end AI analytics platform with real-time dashboards.",
        admin_id=admin.id,
        client_id=client_cp.id,
        status="in-progress",
        progress=58,
        budget=120000.0,
        spent=42000.0,
        payment_status="partial",
        priority="high",
        start_date=now - timedelta(days=30),
        deadline=now + timedelta(days=60),
        custom_fields={"health_score": 72, "risk_flags": ["timeline risk"]},
    )
    db.add(p1)
    db.flush()

    # Tasks for P1
    tasks_p1 = [
        _task(db, tenant.id, p1.id, "Design data ingestion pipeline",
              "completed", {"architecture": 0.7, "backend": 0.6}, 8.0, "high"),
        _task(db, tenant.id, p1.id, "Implement LLM summarisation service",
              "in_progress", {"llm": 0.8, "python": 0.7}, 12.0, "high"),
        _task(db, tenant.id, p1.id, "Build REST API for dashboard queries",
              "in_progress", {"backend": 0.8, "api": 0.7}, 8.0, "medium"),
        _task(db, tenant.id, p1.id, "Develop React dashboard frontend",
              "pending", {"frontend": 0.8, "react": 0.7}, 16.0, "medium"),
        _task(db, tenant.id, p1.id, "Write E2E test suite",
              "pending", {"qa": 0.8, "testing": 0.7}, 10.0, "medium"),
        _task(db, tenant.id, p1.id, "Deploy infrastructure on Cloud Run",
              "blocked", {"devops": 0.7, "cloud": 0.6}, 6.0, "high", "hard"),
    ]

    # Soft-deleted task (tests soft-delete filter)
    deleted_task = _task(db, tenant.id, p1.id, "Old requirement — replaced by LLM service",
                         "cancelled", {"llm": 0.5}, 4.0)
    deleted_task.deleted_at = now - timedelta(days=5)
    db.add(deleted_task)

    # Assignments — assign tasks to matching employees
    # emp_profiles: [Amira/arch, Arjun/llm, Neha/backend, Yash/frontend, Sofia/qa]
    assign_map = [
        (tasks_p1[0], 0),   # Design pipeline → Amira (architect)
        (tasks_p1[1], 1),   # LLM service → Arjun
        (tasks_p1[2], 2),   # REST API → Neha
        (tasks_p1[3], 3),   # Dashboard → Yash
        (tasks_p1[4], 4),   # E2E tests → Sofia
    ]
    for task, emp_idx in assign_map:
        _assign(db, task.id, emp_profiles[emp_idx].id)
        # Update employee workload
        emp_profiles[emp_idx].current_load = min(
            emp_profiles[emp_idx].current_load + task.estimated_time, 8.0
        )
        db.add(emp_profiles[emp_idx])

    # ── Project 2: E-Commerce Redesign — planning ─────────────────────────────
    p2 = Project(
        tenant_id=tenant.id,
        name="E-Commerce Redesign",
        description="Modernise the client e-commerce platform with AI-powered recommendations.",
        admin_id=admin.id,
        client_id=client_cp.id,
        status="planning",
        progress=0,
        budget=75000.0,
        spent=0.0,
        payment_status="pending",
        priority="medium",
        deadline=now + timedelta(days=90),
    )
    db.add(p2)
    db.flush()

    _task(db, tenant.id, p2.id, "Stakeholder requirements workshop", "pending",
          {"communication": 0.7, "architecture": 0.5}, 4.0)
    _task(db, tenant.id, p2.id, "Define AI recommendation model spec", "pending",
          {"llm": 0.7, "architecture": 0.6}, 6.0)

    # ── Project 3: DELETED — soft-delete demo ─────────────────────────────────
    p3 = Project(
        tenant_id=tenant.id,
        name="Legacy CRM Integration (Cancelled)",
        description="Integration project cancelled by client.",
        admin_id=admin.id,
        status="cancelled",
        progress=10,
        budget=30000.0,
        spent=3000.0,
        deleted_at=now - timedelta(days=10),
    )
    db.add(p3)
    db.flush()

    return p1, p2


def seed_workflow_runs(db, admin, project):
    """Seed a completed intake workflow run with agent records."""
    now = datetime.utcnow()
    run = WorkflowRun(
        workflow_type="intake",
        status="completed",
        requested_by=admin.id,
        project_id=project.id,
        requires_human_review=False,
        input_payload={"project_name": project.name, "budget": project.budget},
        shared_context={"tenant_id": project.tenant_id},
        final_output={"plan_approved": True, "risk_level": "medium"},
        created_at=now - timedelta(days=28),
        completed_at=now - timedelta(days=28) + timedelta(minutes=4),
    )
    db.add(run)
    db.flush()

    agent_stages = [
        ("IntakeAgent", "intake", "Parse and validate project intake"),
        ("PlanningAgent", "planning", "Generate execution plan with milestones"),
        ("StaffingAgent", "staffing", "Score and assign team members"),
        ("RiskAgent", "risk_assessment", "Evaluate timeline and budget risk"),
        ("ExecutionCoordinatorAgent", "coordination", "Finalise execution plan"),
        ("CommunicationAgent", "communication", "Draft project brief emails"),
        ("EscalationAgent", "escalation", "No escalation required"),
    ]
    for name, stage, reasoning in agent_stages:
        db.add(AgentRun(
            workflow_run_id=run.id,
            agent_name=name,
            role=stage,
            stage=stage,
            status="completed",
            confidence=0.87,
            requires_human_review=False,
            reasoning=reasoning,
            input_payload={},
            output_payload={"status": "ok"},
            started_at=run.created_at,
            completed_at=run.created_at + timedelta(seconds=30),
        ))

    db.add(DecisionLog(
        decision_type="assignment",
        entity_type="task",
        entity_id=project.id,
        input_data={"project_id": project.id, "agent": "StaffingAgent"},
        decision_taken="Assigned Arjun Rao to LLM service task (skill_match=0.95, score=0.91)",
        confidence=0.91,
        reasoning="Highest overall score across skill match, workload, efficiency, timezone fit",
    ))
    db.flush()


def seed_scheduler_jobs(db, tenant):
    now = datetime.utcnow()
    jobs = [
        ScheduledAgentJob(
            tenant_id=tenant.id,
            job_type="nightly_observer",
            cron_expr="0 2 * * *",
            timezone="UTC",
            enabled=True,
            last_run_at=now - timedelta(hours=22),
            next_run_at=now + timedelta(hours=2),
            last_status="success",
        ),
        ScheduledAgentJob(
            tenant_id=tenant.id,
            job_type="weekly_digest",
            cron_expr="0 9 * * 1",
            timezone="Asia/Kolkata",
            enabled=True,
            last_run_at=now - timedelta(days=7),
            next_run_at=now + timedelta(days=1),
            last_status="success",
        ),
        ScheduledAgentJob(
            tenant_id=tenant.id,
            job_type="payment_check",
            cron_expr="0 10 * * *",
            timezone="UTC",
            enabled=True,
            last_run_at=now - timedelta(hours=14),
            next_run_at=now + timedelta(hours=10),
            last_status="success",
        ),
        ScheduledAgentJob(
            tenant_id=tenant.id,
            job_type="archive_old_runs",
            cron_expr="0 3 * * 0",
            timezone="UTC",
            enabled=True,
            last_run_at=now - timedelta(days=7),
            next_run_at=now + timedelta(days=1),
            last_status="success",
        ),
    ]
    for j in jobs:
        db.add(j)
    db.flush()


def seed_email_logs(db, tenant):
    samples = [
        ("priya.sharma@orchestrateco.ai", "Welcome to AI Workforce Orchestrator", "welcome", "success"),
        ("rohan.mehta@orchestrateco.ai", "Verify your email address", "email_verification", "success"),
        ("contact@globalcorp.com", "Your project brief is ready", "project_brief", "success"),
        ("priya.sharma@orchestrateco.ai", "Weekly digest — week of Apr 14", "weekly_digest", "success"),
        ("rohan.mehta@orchestrateco.ai", "Task assignment: Build REST API", "task_assignment", "success"),
        ("rohan.mehta@orchestrateco.ai", "Escalation alert: Blocked task", "escalation_alert", "failed"),
    ]
    now = datetime.utcnow()
    for to_email, subject, template, status in samples:
        db.add(EmailDeliveryLog(
            tenant_id=tenant.id,
            to_email=to_email,
            subject=subject,
            template_name=template,
            status=status,
            sendgrid_message_id=f"SG.mock_{template}" if status == "success" else None,
            error_message="SendGrid API timeout" if status == "failed" else None,
            sent_at=now - timedelta(hours=2) if status == "success" else None,
        ))
    db.flush()


def seed_support_ticket(db, tenant, admin, owner):
    db.add(SupportTicket(
        tenant_id=tenant.id,
        user_id=admin.id,
        subject="Request to increase project limit",
        body=(
            "Hi Swaraj,\n\nWe have 3 new client projects starting next month "
            "and would need our project cap raised from 20 to 30. "
            "Could you update our plan?\n\nThanks,\nRohan"
        ),
        status="open",
        priority="medium",
    ))
    db.flush()


# ── Reset & run ───────────────────────────────────────────────────────────────

def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema(engine)


def print_summary(admin_refresh_token: str):
    totp = pyotp.TOTP(CEO_TOTP_SECRET)
    current_code = totp.now()
    provisioning_uri = totp.provisioning_uri(
        name=CEO["email"], issuer_name="AI Workforce Orchestrator"
    )

    print("\n" + "=" * 64)
    print("  AI Workforce Orchestrator — Seed Complete")
    print("=" * 64)

    print("\n[ Platform Owner ]")
    print(f"  Email    : {PLATFORM_OWNER['email']}")
    print(f"  Password : {PLATFORM_OWNER['password']}")
    print(f"  Role     : platform_owner  (cross-tenant access)")

    print("\n[ Tenant A: OrchestrateCo ]")
    print(f"  Slug     : {TENANT_A_SLUG}")
    print(f"  Plan     : Pro  (Stripe: cus_seed_orchestrateco)")
    print(f"\n  CEO (2FA ENABLED)")
    print(f"    Email    : {CEO['email']}")
    print(f"    Password : {CEO['password']}")
    print(f"    2FA flow : POST /auth/login → gets mfa_session_token")
    print(f"               POST /auth/2fa/verify-login  {{mfa_session_token, totp_code}}")
    print(f"    TOTP key : {CEO_TOTP_SECRET}")
    print(f"    LIVE code: {current_code}  (valid ~30 s)")
    print(f"    QR URI   : {provisioning_uri}")
    print(f"\n  Admin")
    print(f"    Email    : {ADMIN['email']}")
    print(f"    Password : {ADMIN['password']}")
    print(f"    Refresh  : {admin_refresh_token[:20]}...  (30-day session)")
    print(f"\n  Employees")
    for m in EMPLOYEES_A:
        print(f"    {m['title']:30s}  {m['email']} / {m['password']}")
    print(f"\n  Client")
    print(f"    Email    : {CLIENT_A['email']} / {CLIENT_A['password']}")
    print(f"    Company  : {CLIENT_A['company_name']}")

    print("\n[ Tenant B: GlobalTech (isolation + grace-period test) ]")
    print(f"  Slug     : {TENANT_B_SLUG}")
    print(f"  Plan     : Starter  (grace period — 3 days left)")
    print(f"  Admin    : {ADMIN_B['email']} / {ADMIN_B['password']}")
    for m in EMPLOYEES_B:
        print(f"  Employee : {m['email']} / {m['password']}")
    print(f"  Client   : {CLIENT_B['email']} / {CLIENT_B['password']}")

    print("\n[ Projects seeded (Tenant A) ]")
    print("  1. AI-Powered Analytics Platform  — in-progress  (58%)")
    print("     6 tasks: completed/in_progress/pending/blocked + 1 soft-deleted")
    print("     5 task assignments, 1 WorkflowRun (7 AgentRun records)")
    print("  2. E-Commerce Redesign            — planning     (0%)")
    print("     2 tasks: pending")
    print("  3. Legacy CRM Integration         — SOFT DELETED (not visible in API)")

    print("\n[ Features to test ]")
    print("  Auth       : login, refresh, email verify, 2FA setup/enable/verify-login")
    print("  Projects   : CRUD, soft-delete, pagination")
    print("  CEO dash   : /ceo/overview|financials|teams|clients|risks")
    print("  Owner      : /owner/tenants  (see both companies)")
    print("  Billing    : /billing/subscribe  (Tenant A active, Tenant B grace)")
    print("  Calendar   : /integrations/google/status  (CEO is connected)")
    print("  Scheduler  : 4 jobs visible in DB  (nightly/weekly/payment/archive)")
    print("  Email logs : 6 sample records  (1 failed)")
    print("  Support    : 1 open ticket from admin to platform owner")
    print("  Isolation  : Tenant B users cannot see Tenant A data")

    print("\n" + "=" * 64 + "\n")


def main():
    reset_database()
    db = SessionLocal()
    try:
        owner = seed_platform_owner(db)
        tenant_a, ceo, admin, admin_rt, emp_profiles, client_cp = seed_tenant_a(db)
        tenant_b, admin_b = seed_tenant_b(db)
        p1, p2 = seed_projects_and_tasks(db, tenant_a, admin, emp_profiles, client_cp)
        seed_workflow_runs(db, admin, p1)
        seed_scheduler_jobs(db, tenant_a)
        seed_email_logs(db, tenant_a)
        seed_support_ticket(db, tenant_a, admin, owner)
        db.commit()
        print_summary(admin_rt)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
