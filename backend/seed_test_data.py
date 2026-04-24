#!/usr/bin/env python3
"""
Local development seed for AI Workforce Orchestrator (backend — SQLite).

TARGET: Local SQLite database (app.db in the backend/ directory).
ALWAYS does a full drop + recreate — safe for local dev only.

Covers every role and feature available in the backend/ model set:
  Roles    : admin, ceo, employee (x5), client — across 2 tenants
  Tenants  : OrchestrateCo (main), GlobalTech (isolation test)
  Projects : active (in-progress, 58%), planning, cancelled
  Tasks    : completed, in_progress, pending, blocked (6 tasks)
  Agents   : WorkflowRun + AgentRun records for the intake workflow
  Engine   : 5 TaskAssignment records with scored assignments
  Decisions: 1 DecisionLog from StaffingAgent

Run from inside backend/:
    cd backend
    python seed_test_data.py
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

# Force local SQLite — never touch a remote DB from this script
os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR}/app.db")

from app.core._security import hash_password
from app.db._database import Base, SessionLocal, engine
from app.models import (
    _agent, _agent_run, _audit_log, _availability, _blocker, _checkpoint,
    _client_profile, _communication, _decision_log, _employee_metrics,
    _employee_profile, _event_queue, _meeting, _performance_point,
    _project, _task, _task_assignment, _task_dependency, _task_progress,
    _team, _team_invite, _tenant, _user, _workflow_run,
)
from app.models._agent_run import AgentRun
from app.models._client_profile import ClientProfile
from app.models._decision_log import DecisionLog
from app.models._employee_metrics import EmployeeMetrics
from app.models._employee_profile import EmployeeProfile
from app.models._project import Project
from app.models._task import Task
from app.models._task_assignment import TaskAssignment
from app.models._tenant import Tenant
from app.models._user import User
from app.models._workflow_run import WorkflowRun

# ── Credentials ───────────────────────────────────────────────────────────────

TENANT_A_NAME = "OrchestrateCo"
TENANT_A_SLUG = "orchestrateco"

USERS_A = [
    # (email, password, full_name, role)
    ("swaraj@orchestrator.ai",       "admin123",    "Swaraj Menon",  "admin"),
    ("priya.sharma@orchestrateco.ai", "ceo123456",  "Priya Sharma",  "ceo"),
]

EMPLOYEES_A = [
    {
        "email": "amira.khan@orchestrateco.ai", "password": "team123456",
        "full_name": "Amira Khan", "department": "Solutioning",
        "skills": {"architecture": 0.95, "delivery": 0.82, "backend": 0.72},
    },
    {
        "email": "arjun.rao@orchestrateco.ai", "password": "team123456",
        "full_name": "Arjun Rao", "department": "AI Delivery",
        "skills": {"llm": 0.95, "python": 0.88, "prompting": 0.82},
    },
    {
        "email": "neha.gupta@orchestrateco.ai", "password": "team123456",
        "full_name": "Neha Gupta", "department": "Engineering",
        "skills": {"backend": 0.93, "python": 0.90, "api": 0.86},
    },
    {
        "email": "yash.patel@orchestrateco.ai", "password": "team123456",
        "full_name": "Yash Patel", "department": "Engineering",
        "skills": {"frontend": 0.91, "react": 0.89, "design-systems": 0.74},
    },
    {
        "email": "sofia.dsouza@orchestrateco.ai", "password": "team123456",
        "full_name": "Sofia D'Souza", "department": "Quality",
        "skills": {"qa": 0.94, "testing": 0.91, "automation": 0.87},
    },
]

CLIENT_A = ("contact@globalcorp.com", "client123456", "Marcus Chen", "client", "GlobalCorp")

TENANT_B_NAME = "GlobalTech Solutions"
TENANT_B_SLUG = "globaltech"

USERS_B = [
    ("alex.turner@globaltech.io",  "admin66666", "Alex Turner",  "admin"),
    ("maya.r@globaltech.io",       "team123456", "Maya Ramesh",  "employee"),
    ("tom.brooks@globaltech.io",   "team123456", "Tom Brooks",   "employee"),
    ("partner@techventures.com",   "client1234", "Lisa Park",    "client"),
]

EMPLOYEES_B = [
    {
        "email": "maya.r@globaltech.io",
        "skills": {"data": 0.93, "python": 0.88, "analytics": 0.84},
        "department": "Data",
    },
    {
        "email": "tom.brooks@globaltech.io",
        "skills": {"devops": 0.91, "cloud": 0.87, "security": 0.79},
        "department": "Platform",
    },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def _user(db, email, password, full_name, role, tenant_id):
    u = User(
        email=email,
        password=hash_password(password),
        full_name=full_name,
        role=role,
        tenant_id=tenant_id,
    )
    db.add(u)
    db.flush()
    return u


def _employee_profile(db, user, skills, department):
    p = EmployeeProfile(
        tenant_id=user.tenant_id,
        user_id=user.id,
        skills=skills,
        max_capacity=8.0,
        current_load=0.0,
        department=department,
        availability_status="available",
    )
    db.add(p)
    db.flush()
    db.add(EmployeeMetrics(
        employee_id=p.id,
        efficiency_score=0.87,
        reliability_score=0.92,
        avg_completion_time=0.0,
        total_tasks_completed=8,
        total_tasks_failed=0,
        total_tasks_delayed=1,
    ))
    return p


def _task(db, tenant_id, project_id, description, status, required_skills,
          estimated_time=4.0, urgency="medium", difficulty="medium"):
    t = Task(
        tenant_id=tenant_id,
        project_id=project_id,
        description=description,
        status=status,
        required_skills=required_skills,
        estimated_time=estimated_time,
        urgency=urgency,
        difficulty=difficulty,
        deadline=datetime.utcnow() + timedelta(days=14),
    )
    db.add(t)
    db.flush()
    return t


# ── Seed sections ─────────────────────────────────────────────────────────────

def seed_tenant_a(db):
    tenant = Tenant(name=TENANT_A_NAME, slug=TENANT_A_SLUG)
    db.add(tenant)
    db.flush()

    users = {}
    for email, password, full_name, role in USERS_A:
        users[role] = _user(db, email, password, full_name, role, tenant.id)

    admin = users["admin"]

    emp_profiles = []
    emp_users = {}
    for m in EMPLOYEES_A:
        u = _user(db, m["email"], m["password"], m["full_name"], "employee", tenant.id)
        p = _employee_profile(db, u, m["skills"], m["department"])
        emp_profiles.append(p)
        emp_users[m["email"]] = u

    # Client
    client_u = _user(db, CLIENT_A[0], CLIENT_A[1], CLIENT_A[2], CLIENT_A[3], tenant.id)
    client_cp = ClientProfile(
        tenant_id=tenant.id, user_id=client_u.id,
        company_name=CLIENT_A[4], contact_person=client_u.full_name,
    )
    db.add(client_cp)
    db.flush()

    return tenant, admin, emp_profiles, client_cp


def seed_tenant_b(db):
    tenant = Tenant(name=TENANT_B_NAME, slug=TENANT_B_SLUG)
    db.add(tenant)
    db.flush()

    for email, password, full_name, role in USERS_B:
        u = _user(db, email, password, full_name, role, tenant.id)
        # Wire up employee profiles for isolation test
        for m in EMPLOYEES_B:
            if m["email"] == email:
                _employee_profile(db, u, m["skills"], m["department"])

    return tenant


def seed_projects_and_tasks(db, tenant, admin, emp_profiles, client_cp):
    now = datetime.utcnow()

    # ── Project 1: in-progress ────────────────────────────────────────────────
    p1 = Project(
        tenant_id=tenant.id,
        name="AI-Powered Analytics Platform",
        description="End-to-end AI analytics platform with real-time dashboards.",
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

    # Assign tasks to matching employees (index = emp_profiles order)
    for idx, task in enumerate(tasks_p1[:5]):
        db.add(TaskAssignment(
            task_id=task.id,
            employee_id=emp_profiles[idx].id,
            status="assigned",
            assignment_confidence=0.88,
        ))
        emp_profiles[idx].current_load = min(
            emp_profiles[idx].current_load + task.estimated_time, 8.0
        )
        db.add(emp_profiles[idx])

    # ── Project 2: planning ───────────────────────────────────────────────────
    p2 = Project(
        tenant_id=tenant.id,
        name="E-Commerce Redesign",
        description="Modernise the client e-commerce platform with AI recommendations.",
        admin_id=admin.id,
        client_id=client_cp.id,
        status="planning",
        progress=0,
        budget=75000.0,
        spent=0.0,
        priority="medium",
        deadline=now + timedelta(days=90),
    )
    db.add(p2)
    db.flush()

    _task(db, tenant.id, p2.id, "Stakeholder requirements workshop",
          "pending", {"communication": 0.7, "architecture": 0.5}, 4.0)
    _task(db, tenant.id, p2.id, "Define AI recommendation model spec",
          "pending", {"llm": 0.7, "architecture": 0.6}, 6.0)

    # ── Project 3: cancelled ──────────────────────────────────────────────────
    p3 = Project(
        tenant_id=tenant.id,
        name="Legacy CRM Integration",
        description="Cancelled by client due to budget constraints.",
        admin_id=admin.id,
        status="cancelled",
        progress=10,
        budget=30000.0,
        spent=3000.0,
    )
    db.add(p3)
    db.flush()

    return p1, p2, p3


def seed_workflow_run(db, admin, project):
    now = datetime.utcnow()
    run = WorkflowRun(
        workflow_type="intake",
        status="completed",
        requested_by=admin.id,
        project_id=project.id,
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
            workflow_run_id=run.id,
            agent_name=name, role=stage, stage=stage,
            status="completed", confidence=0.87,
            reasoning=reasoning, input_payload={}, output_payload={"status": "ok"},
            started_at=run.created_at,
            completed_at=run.created_at + timedelta(seconds=30),
        ))

    db.add(DecisionLog(
        decision_type="assignment",
        entity_type="task",
        entity_id=project.id,
        input_data={"project_id": project.id, "agent": "StaffingAgent"},
        decision_taken="Assigned Arjun Rao to LLM task (score: 0.91)",
        confidence=0.91,
        reasoning="Highest score: skill_match=0.95, workload=0.8, efficiency=0.87",
    ))
    db.flush()


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    db_path = os.environ["DATABASE_URL"].replace("sqlite:///", "")
    print(f"\nTarget: {db_path}  (local SQLite — safe to wipe)")
    print("Resetting database...")

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        tenant_a, admin, emp_profiles, client_cp = seed_tenant_a(db)
        tenant_b = seed_tenant_b(db)
        p1, p2, p3 = seed_projects_and_tasks(db, tenant_a, admin, emp_profiles, client_cp)
        seed_workflow_run(db, admin, p1)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print("\n" + "=" * 64)
    print("  Local Seed Complete  (SQLite — local dev only)")
    print("=" * 64)

    print("\n[ Tenant A: OrchestrateCo ]")
    print(f"  Admin  : swaraj@orchestrator.ai       / admin123")
    print(f"  CEO    : priya.sharma@orchestrateco.ai / ceo123456")
    print(f"  Client : contact@globalcorp.com        / client123456  (GlobalCorp)")
    print()
    print("  Employees  (password: team123456 for all)")
    for m in EMPLOYEES_A:
        print(f"    {m['email']}")

    print("\n[ Tenant B: GlobalTech — isolation test ]")
    for email, password, full_name, role in USERS_B:
        print(f"  {role:8s}: {email} / {password}")

    print("\n[ Projects — Tenant A ]")
    print("  1. AI-Powered Analytics Platform  in-progress  58%")
    print("     6 tasks: completed / in_progress / pending / blocked")
    print("     5 TaskAssignments  ·  1 WorkflowRun  ·  7 AgentRuns  ·  1 DecisionLog")
    print("  2. E-Commerce Redesign            planning      0%  (2 tasks)")
    print("  3. Legacy CRM Integration         cancelled     10%")

    print("\n[ Local server ]")
    print("  uvicorn app.main:app --reload --port 8000")
    print("  http://localhost:8000/docs\n")


if __name__ == "__main__":
    main()
