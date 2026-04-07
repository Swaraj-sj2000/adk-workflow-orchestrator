#!/usr/bin/env python3
"""
Reset and seed the AI Workforce Orchestrator with a clean admin-first dataset.

Seed result:
- 1 admin
- 10 employees
- 0 projects
- 0 tasks
- 0 clients
- every employee free and available
"""

from __future__ import annotations

import sys

sys.path.insert(0, "/home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend")

from app.core._security import hash_password
from app.db._database import Base, SessionLocal, engine
from app.services._auth_service import ensure_default_tenant
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
    _employee_metrics,
    _employee_profile,
    _event_queue,
    _meeting,
    _performance_point,
    _project,
    _task,
    _task_assignment,
    _task_dependency,
    _task_progress,
    _team,
    _team_invite,
    _tenant,
    _user,
    _workflow_run,
)
from app.models._employee_metrics import EmployeeMetrics
from app.models._employee_profile import EmployeeProfile
from app.models._user import User


TEAM = [
    {
        "email": "swaraj@orchestrator.ai",
        "password": "admin123",
        "full_name": "Swaraj Menon",
        "role": "admin",
    },
    {
        "email": "amira.khan@orchestrator.ai",
        "password": "team123456",
        "full_name": "Amira Khan",
        "title": "Solution Architect",
        "department": "Solutioning",
        "skills": {"architecture": 0.95, "delivery": 0.82, "backend": 0.72},
    },
    {
        "email": "arjun.rao@orchestrator.ai",
        "password": "team123456",
        "full_name": "Arjun Rao",
        "title": "AI Engineer",
        "department": "AI Delivery",
        "skills": {"llm": 0.95, "python": 0.88, "prompting": 0.82},
    },
    {
        "email": "neha.gupta@orchestrator.ai",
        "password": "team123456",
        "full_name": "Neha Gupta",
        "title": "Backend Engineer",
        "department": "Engineering",
        "skills": {"backend": 0.93, "python": 0.9, "api": 0.86},
    },
    {
        "email": "yash.patel@orchestrator.ai",
        "password": "team123456",
        "full_name": "Yash Patel",
        "title": "Frontend Engineer",
        "department": "Engineering",
        "skills": {"frontend": 0.91, "react": 0.89, "design-systems": 0.74},
    },
    {
        "email": "sofia.dsouza@orchestrator.ai",
        "password": "team123456",
        "full_name": "Sofia D'Souza",
        "title": "QA Automation Engineer",
        "department": "Quality",
        "skills": {"qa": 0.94, "testing": 0.91, "automation": 0.87},
    },
    {
        "email": "ibrahim.shaikh@orchestrator.ai",
        "password": "team123456",
        "full_name": "Ibrahim Shaikh",
        "title": "Project Coordinator",
        "department": "Program Management",
        "skills": {"project-management": 0.93, "communication": 0.91, "delivery": 0.83},
    },
    {
        "email": "meera.nair@orchestrator.ai",
        "password": "team123456",
        "full_name": "Meera Nair",
        "title": "Client Success Manager",
        "department": "Client Success",
        "skills": {"client-success": 0.95, "communication": 0.92, "reporting": 0.87},
    },
    {
        "email": "daniel.lee@orchestrator.ai",
        "password": "team123456",
        "full_name": "Daniel Lee",
        "title": "DevOps Engineer",
        "department": "Platform",
        "skills": {"devops": 0.94, "cloud": 0.9, "security": 0.76},
    },
    {
        "email": "kavya.reddy@orchestrator.ai",
        "password": "team123456",
        "full_name": "Kavya Reddy",
        "title": "Data Engineer",
        "department": "Data",
        "skills": {"data": 0.94, "analytics": 0.89, "python": 0.79},
    },
    {
        "email": "lucas.joseph@orchestrator.ai",
        "password": "team123456",
        "full_name": "Lucas Joseph",
        "title": "Prompt Engineer",
        "department": "AI Delivery",
        "skills": {"prompting": 0.96, "research": 0.89, "communication": 0.82},
    },
]


def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def create_user(db, email: str, password: str, full_name: str, role: str, tenant_id: int):
    user = User(
        email=email,
        password=hash_password(password),
        full_name=full_name,
        role=role,
        tenant_id=tenant_id,
    )
    db.add(user)
    db.flush()
    return user


def seed_team(db):
    tenant = ensure_default_tenant(db)
    admin = create_user(db, tenant_id=tenant.id, **TEAM[0])
    employees = []

    for member in TEAM[1:]:
        user = create_user(
            db,
            email=member["email"],
            password=member["password"],
            full_name=member["full_name"],
            role="employee",
            tenant_id=tenant.id,
        )
        profile = EmployeeProfile(
            tenant_id=tenant.id,
            user_id=user.id,
            skills=member["skills"],
            max_capacity=8.0,
            current_load=0.0,
            department=member["department"],
            availability_status="available",
        )
        db.add(profile)
        db.flush()
        db.add(
            EmployeeMetrics(
                employee_id=profile.id,
                efficiency_score=0.85,
                reliability_score=0.91,
                avg_completion_time=0.0,
                total_tasks_completed=0,
                total_tasks_failed=0,
                total_tasks_delayed=0,
            )
        )
        employees.append((user, profile, member["title"]))

    return admin, employees


def print_summary():
    print("\nClean seed complete\n")
    print("Admin login")
    print("  Email: swaraj@orchestrator.ai")
    print("  Password: admin123\n")
    print("Team logins")
    for member in TEAM[1:]:
        print(f"  {member['title']}: {member['email']} / {member['password']}")
    print("\nSeed state")
    print("  - projects: 0")
    print("  - tasks: 0")
    print("  - clients: 0")
    print("  - all 10 employees are free and available")


def main():
    reset_database()
    db = SessionLocal()
    try:
        seed_team(db)
        db.commit()
        print_summary()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
