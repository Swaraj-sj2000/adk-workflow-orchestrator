#!/usr/bin/env python3
"""
Comprehensive seed — AI Workforce Orchestrator backend_adk.

Creates 4 tenant companies, each with:
  • 1 CEO
  • 4 department admins (one per team)
  • 20–30 employees spread across departments (varied skills, load, status)
  • 2 clients
  • 4 org-pool Teams (project_id=NULL) — employees pre-assigned to their admin's team
  • NO initial projects (agentic planning starts fresh)
  • EmployeeMetrics for every employee profile

Flags:
  --local   SQLite dev mode (default DATABASE_URL = sqlite:///./app.db)
  --check   Pre-flight only (production)
  --reset   Destructive wipe (production)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

_LOCAL_MODE = "--local" in sys.argv

if _LOCAL_MODE:
    os.environ.setdefault("DATABASE_URL", "sqlite:///./app.db")
    os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")
    DATABASE_URL = os.environ["DATABASE_URL"]
    GCP_PROJECT  = "local-dev"
    GCP_REGION   = "local"
    GEMINI_MODEL = os.environ["GEMINI_MODEL"]
else:
    _REQUIRED = {
        "DATABASE_URL":             "Cloud SQL PostgreSQL connection string",
        "GOOGLE_CLOUD_PROJECT":     "GCP project ID",
        "GOOGLE_CLOUD_LOCATION":    "GCP region",
        "GOOGLE_GENAI_USE_VERTEXAI":"Must be 'true'",
    }
    _missing = [k for k in _REQUIRED if not os.getenv(k)]
    if _missing:
        print("\nERROR: Missing env vars:\n")
        for k in _missing:
            print(f"  {k}  —  {_REQUIRED[k]}")
        print("\nFor local testing run:  python seed_test_data.py --local\n")
        sys.exit(1)

    DATABASE_URL = os.environ["DATABASE_URL"]
    GCP_PROJECT  = os.environ["GOOGLE_CLOUD_PROJECT"]
    GCP_REGION   = os.environ["GOOGLE_CLOUD_LOCATION"]

    if DATABASE_URL.startswith("sqlite"):
        print("ERROR: SQLite not allowed in production mode.")
        sys.exit(1)

    os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-flash")
    GEMINI_MODEL = os.environ["GEMINI_MODEL"]

parser = argparse.ArgumentParser()
parser.add_argument("--local",  action="store_true")
parser.add_argument("--check",  action="store_true")
parser.add_argument("--reset",  action="store_true")
args = parser.parse_args()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _preflight():
    ok = True
    host_display = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    print(f"\n── Pre-flight ({host_display}) ────────────────────────────────")
    try:
        import psycopg2
        raw = DATABASE_URL.replace("postgresql+psycopg2://", "postgresql://")
        conn = psycopg2.connect(raw, connect_timeout=10)
        conn.close()
        print("    ✓ Cloud SQL connected")
    except Exception as e:
        print(f"    ✗ Cloud SQL FAILED: {e}")
        ok = False
    try:
        from google import genai  # noqa
        print("    ✓ google-genai importable")
    except ImportError as e:
        print(f"    ✗ google-genai FAILED: {e}")
        ok = False
    return ok


if args.check:
    if _LOCAL_MODE:
        print("--check is for production only.")
        sys.exit(0)
    sys.exit(0 if _preflight() else 1)

if not _LOCAL_MODE:
    if not _preflight():
        sys.exit(1)

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
from app.models._client_profile import ClientProfile
from app.models._employee_metrics import EmployeeMetrics
from app.models._employee_profile import EmployeeProfile
from app.models._refresh_token import RefreshToken
from app.models._scheduled_agent_job import ScheduledAgentJob
from app.models._team import Team, TeamMember
from app.models._tenant import Tenant
from app.models._tenant_settings import TenantSettings
from app.models._user import User
from app.models._user_preferences import UserPreferences

# ── Agent definitions ─────────────────────────────────────────────────────────

AGENT_DEFINITIONS = [
    {"name": "IntakeAgent",                "role": "intake",         "capability": f"Parse project intake via {GEMINI_MODEL}"},
    {"name": "PlanningAgent",              "role": "planning",       "capability": f"Generate execution plan via {GEMINI_MODEL}"},
    {"name": "StaffingAgent",              "role": "staffing",       "capability": f"Score + assign team members via {GEMINI_MODEL}"},
    {"name": "RiskAgent",                  "role": "risk",           "capability": f"Evaluate timeline/budget risk via {GEMINI_MODEL}"},
    {"name": "ExecutionCoordinatorAgent",  "role": "coordination",   "capability": f"Finalise execution plan via {GEMINI_MODEL}"},
    {"name": "CommunicationAgent",         "role": "communication",  "capability": f"Draft client/admin emails via {GEMINI_MODEL}"},
    {"name": "EscalationAgent",            "role": "escalation",     "capability": "Escalate to humans when confidence < 0.6"},
    {"name": "ProjectObserverAgent",       "role": "observation",    "capability": f"Monitor project health via {GEMINI_MODEL}"},
    {"name": "DeliveryReviewAgent",        "role": "review",         "capability": f"Review deliverables via {GEMINI_MODEL}"},
    {"name": "RebalanceAgent",             "role": "rebalance",      "capability": f"Rebalance assignments via {GEMINI_MODEL}"},
    {"name": "LoopCommunicationAgent",     "role": "loop_comms",     "capability": f"Update stakeholder comms via {GEMINI_MODEL}"},
    {"name": "LoopEscalationAgent",        "role": "loop_escalation","capability": "Escalate loop blockers to admin"},
]

# ── Platform owner ─────────────────────────────────────────────────────────────

PLATFORM_OWNER = {
    "email": "swaraj@orchestrator.ai",
    "password": "OwnerSecure#99",
    "full_name": "Swaraj Menon",
    "role": "platform_owner",
}

# ─────────────────────────────────────────────────────────────────────────────
# TENANT DATA DEFINITIONS
# Each entry: (slug, name, industry, hq, ceo, admins[], employees[], clients[])
#
# Skills chosen to match ROLE_SKILL_MAP in _project_service.py:
#   Solution Architect → architecture, delivery
#   AI Engineer        → llm, modeling
#   Backend Engineer   → backend, api
#   Frontend Engineer  → frontend, react
#   QA Engineer        → qa, testing, automation
#   Delivery Lead      → project-management
#   Client Success Mgr → client-success, reporting
#   DevOps Engineer    → devops, cloud, security
#   Data Engineer      → data, analytics
#   Prompt Engineer    → prompting, research
# ─────────────────────────────────────────────────────────────────────────────

TENANTS = [

    # ── 1. TechNova Solutions ─────────────────────────────────────────────────
    {
        "slug": "technova",
        "name": "TechNova Solutions",
        "industry": "SaaS / AI",
        "hq": "Bengaluru, India",
        "plan_tier": "pro",
        "totp_for_ceo": True,
        "ceo": {
            "email": "priya.sharma@technova.ai",
            "password": "CEO_Secure#88",
            "full_name": "Priya Sharma",
        },
        "admins": [
            {"email": "rohan.mehta@technova.ai",  "password": "Admin#Rohan77", "full_name": "Rohan Mehta",  "department": "Engineering"},
            {"email": "kavya.nair@technova.ai",   "password": "Admin#Kavya77", "full_name": "Kavya Nair",   "department": "Product & AI"},
            {"email": "aditya.singh@technova.ai", "password": "Admin#Adity77", "full_name": "Aditya Singh", "department": "Operations"},
            {"email": "shruti.bose@technova.ai",  "password": "Admin#Shrut77", "full_name": "Shruti Bose",  "department": "People & HR"},
        ],
        "employees": [
            # Engineering (Rohan)
            {"email": "amira.khan@technova.ai",    "full_name": "Amira Khan",      "department": "Engineering",  "skills": {"architecture": 0.92, "delivery": 0.85, "backend": 0.75},          "load": 3.0, "status": "available"},
            {"email": "arjun.rao@technova.ai",     "full_name": "Arjun Rao",       "department": "Engineering",  "skills": {"llm": 0.95, "modeling": 0.90, "python": 0.88},                    "load": 5.0, "status": "available"},
            {"email": "neha.gupta@technova.ai",    "full_name": "Neha Gupta",      "department": "Engineering",  "skills": {"backend": 0.93, "api": 0.90, "python": 0.88},                     "load": 4.0, "status": "available"},
            {"email": "yash.patel@technova.ai",    "full_name": "Yash Patel",      "department": "Engineering",  "skills": {"frontend": 0.91, "react": 0.89, "design-systems": 0.74},          "load": 2.0, "status": "available"},
            {"email": "dev.sharma@technova.ai",    "full_name": "Dev Sharma",      "department": "Engineering",  "skills": {"devops": 0.88, "cloud": 0.85, "security": 0.72},                  "load": 6.0, "status": "available"},
            {"email": "preet.kaur@technova.ai",    "full_name": "Preet Kaur",      "department": "Engineering",  "skills": {"backend": 0.87, "api": 0.84},                                     "load": 0.0, "status": "available"},
            # Product & AI (Kavya)
            {"email": "sofia.dsouza@technova.ai",  "full_name": "Sofia D'Souza",   "department": "Product & AI", "skills": {"qa": 0.94, "testing": 0.91, "automation": 0.87},                  "load": 3.5, "status": "available"},
            {"email": "rahul.joshi@technova.ai",   "full_name": "Rahul Joshi",     "department": "Product & AI", "skills": {"llm": 0.92, "prompting": 0.88, "modeling": 0.82},                 "load": 7.0, "status": "available"},
            {"email": "meera.pillai@technova.ai",  "full_name": "Meera Pillai",    "department": "Product & AI", "skills": {"prompting": 0.95, "research": 0.90, "llm": 0.75},                 "load": 2.0, "status": "available"},
            {"email": "vishal.nair@technova.ai",   "full_name": "Vishal Nair",     "department": "Product & AI", "skills": {"frontend": 0.89, "react": 0.87, "design-systems": 0.80},          "load": 5.5, "status": "available"},
            {"email": "anita.singh@technova.ai",   "full_name": "Anita Singh",     "department": "Product & AI", "skills": {"architecture": 0.90, "delivery": 0.86},                           "load": 0.0, "status": "available"},
            {"email": "karan.mehta@technova.ai",   "full_name": "Karan Mehta",     "department": "Product & AI", "skills": {"llm": 0.88, "modeling": 0.85, "research": 0.70},                  "load": 4.0, "status": "on-leave"},
            # Operations (Aditya)
            {"email": "pooja.sharma@technova.ai",  "full_name": "Pooja Sharma",    "department": "Operations",   "skills": {"project-management": 0.93},                                       "load": 3.0, "status": "available"},
            {"email": "ravi.kumar@technova.ai",    "full_name": "Ravi Kumar",      "department": "Operations",   "skills": {"data": 0.91, "analytics": 0.88},                                  "load": 4.5, "status": "available"},
            {"email": "sunita.rao@technova.ai",    "full_name": "Sunita Rao",      "department": "Operations",   "skills": {"client-success": 0.94, "reporting": 0.90},                        "load": 2.0, "status": "available"},
            {"email": "nitesh.gupta@technova.ai",  "full_name": "Nitesh Gupta",    "department": "Operations",   "skills": {"devops": 0.85, "cloud": 0.82, "security": 0.78},                  "load": 6.5, "status": "available"},
            {"email": "tanvi.singh@technova.ai",   "full_name": "Tanvi Singh",     "department": "Operations",   "skills": {"project-management": 0.87},                                       "load": 1.0, "status": "available"},
            {"email": "deepak.jain@technova.ai",   "full_name": "Deepak Jain",     "department": "Operations",   "skills": {"data": 0.88, "analytics": 0.85, "reporting": 0.75},               "load": 3.0, "status": "available"},
            # People & HR (Shruti)
            {"email": "ashish.verma@technova.ai",  "full_name": "Ashish Verma",    "department": "People & HR",  "skills": {"client-success": 0.89, "reporting": 0.84},                        "load": 2.5, "status": "available"},
            {"email": "lata.menon@technova.ai",    "full_name": "Lata Menon",      "department": "People & HR",  "skills": {"project-management": 0.91},                                       "load": 0.0, "status": "available"},
            {"email": "mohan.tripathi@technova.ai","full_name": "Mohan Tripathi",  "department": "People & HR",  "skills": {"qa": 0.86, "testing": 0.83},                                      "load": 4.0, "status": "available"},
            {"email": "priya2.patel@technova.ai",  "full_name": "Priya Patel",     "department": "People & HR",  "skills": {"architecture": 0.88, "delivery": 0.84},                           "load": 1.5, "status": "available"},
            {"email": "rajesh.nair@technova.ai",   "full_name": "Rajesh Nair",     "department": "People & HR",  "skills": {"backend": 0.84, "api": 0.80},                                     "load": 3.5, "status": "available"},
            {"email": "swati.joshi@technova.ai",   "full_name": "Swati Joshi",     "department": "People & HR",  "skills": {"frontend": 0.87, "react": 0.85},                                  "load": 5.0, "status": "available"},
        ],
        "clients": [
            {"email": "contact@globalcorp.com",   "full_name": "Marcus Chen",   "company": "GlobalCorp Pte Ltd"},
            {"email": "partner@fintech360.io",    "full_name": "Aisha Patel",   "company": "FinTech360 Inc"},
        ],
        "admin_employee_map": {
            "rohan.mehta@technova.ai":  ["Engineering"],
            "kavya.nair@technova.ai":   ["Product & AI"],
            "aditya.singh@technova.ai": ["Operations"],
            "shruti.bose@technova.ai":  ["People & HR"],
        },
    },

    # ── 2. DataSphere Analytics ───────────────────────────────────────────────
    {
        "slug": "datasphere",
        "name": "DataSphere Analytics",
        "industry": "Data & Analytics",
        "hq": "San Francisco, USA",
        "plan_tier": "enterprise",
        "totp_for_ceo": True,
        "ceo": {
            "email": "alex.turner@datasphere.io",
            "password": "CEO_Secure#DS88",
            "full_name": "Alex Turner",
        },
        "admins": [
            {"email": "marcus.chen@datasphere.io",  "password": "Admin#Marc77", "full_name": "Marcus Chen",  "department": "Data Engineering"},
            {"email": "zara.ahmed@datasphere.io",   "password": "Admin#Zara77", "full_name": "Zara Ahmed",   "department": "Analytics & BI"},
            {"email": "ryan.park@datasphere.io",    "password": "Admin#Ryan77", "full_name": "Ryan Park",    "department": "Infrastructure"},
            {"email": "hannah.lee@datasphere.io",   "password": "Admin#Hann77", "full_name": "Dr. Hannah Lee","department": "Research & AI"},
        ],
        "employees": [
            # Data Engineering (Marcus)
            {"email": "tom.brooks@datasphere.io",    "full_name": "Tom Brooks",      "department": "Data Engineering", "skills": {"devops": 0.91, "cloud": 0.87, "security": 0.79},          "load": 5.0, "status": "available"},
            {"email": "maya.ramesh@datasphere.io",   "full_name": "Maya Ramesh",     "department": "Data Engineering", "skills": {"data": 0.93, "analytics": 0.88, "python": 0.85},         "load": 3.0, "status": "available"},
            {"email": "david.kim@datasphere.io",     "full_name": "David Kim",       "department": "Data Engineering", "skills": {"backend": 0.88, "api": 0.85},                             "load": 6.0, "status": "available"},
            {"email": "lucy.zhang@datasphere.io",    "full_name": "Lucy Zhang",      "department": "Data Engineering", "skills": {"data": 0.90, "analytics": 0.87, "reporting": 0.80},      "load": 2.0, "status": "available"},
            {"email": "carlos.rivera@datasphere.io", "full_name": "Carlos Rivera",   "department": "Data Engineering", "skills": {"backend": 0.86, "api": 0.83},                             "load": 4.0, "status": "available"},
            {"email": "preet.kang@datasphere.io",    "full_name": "Preet Kang",      "department": "Data Engineering", "skills": {"data": 0.89, "analytics": 0.86},                          "load": 0.0, "status": "available"},
            # Analytics & BI (Zara)
            {"email": "emma.wilson@datasphere.io",   "full_name": "Emma Wilson",     "department": "Analytics & BI",   "skills": {"data": 0.91, "analytics": 0.88, "reporting": 0.85},      "load": 3.5, "status": "available"},
            {"email": "jason.lee@datasphere.io",     "full_name": "Jason Lee",       "department": "Analytics & BI",   "skills": {"client-success": 0.90, "reporting": 0.87},                "load": 2.0, "status": "available"},
            {"email": "olivia.chen@datasphere.io",   "full_name": "Olivia Chen",     "department": "Analytics & BI",   "skills": {"data": 0.88, "analytics": 0.86},                          "load": 5.0, "status": "available"},
            {"email": "nathan.brown@datasphere.io",  "full_name": "Nathan Brown",    "department": "Analytics & BI",   "skills": {"architecture": 0.87, "delivery": 0.84},                   "load": 1.0, "status": "available"},
            {"email": "sophia.patel@datasphere.io",  "full_name": "Sophia Patel",    "department": "Analytics & BI",   "skills": {"project-management": 0.92},                               "load": 4.5, "status": "available"},
            # Infrastructure (Ryan)
            {"email": "aiden.smith@datasphere.io",   "full_name": "Aiden Smith",     "department": "Infrastructure",   "skills": {"devops": 0.93, "cloud": 0.90, "security": 0.85},          "load": 6.0, "status": "available"},
            {"email": "isabella.m@datasphere.io",    "full_name": "Isabella Martinez","department": "Infrastructure",   "skills": {"backend": 0.87, "api": 0.84},                             "load": 3.0, "status": "on-leave"},
            {"email": "tyler.johnson@datasphere.io", "full_name": "Tyler Johnson",   "department": "Infrastructure",   "skills": {"devops": 0.88, "cloud": 0.85},                            "load": 5.5, "status": "available"},
            {"email": "grace.kim@datasphere.io",     "full_name": "Grace Kim",       "department": "Infrastructure",   "skills": {"frontend": 0.86, "react": 0.84},                          "load": 2.5, "status": "available"},
            {"email": "logan.davis@datasphere.io",   "full_name": "Logan Davis",     "department": "Infrastructure",   "skills": {"backend": 0.85, "api": 0.82},                             "load": 4.0, "status": "available"},
            # Research & AI (Hannah)
            {"email": "charlotte.w@datasphere.io",   "full_name": "Charlotte White", "department": "Research & AI",    "skills": {"llm": 0.95, "modeling": 0.92},                            "load": 3.0, "status": "available"},
            {"email": "ethan.moore@datasphere.io",   "full_name": "Ethan Moore",     "department": "Research & AI",    "skills": {"prompting": 0.93, "research": 0.90, "llm": 0.80},         "load": 5.0, "status": "available"},
            {"email": "ava.jackson@datasphere.io",   "full_name": "Ava Jackson",     "department": "Research & AI",    "skills": {"llm": 0.91, "modeling": 0.88},                            "load": 2.0, "status": "available"},
            {"email": "liam.harris@datasphere.io",   "full_name": "Liam Harris",     "department": "Research & AI",    "skills": {"architecture": 0.89, "delivery": 0.86},                   "load": 0.0, "status": "available"},
            {"email": "mia.thompson@datasphere.io",  "full_name": "Mia Thompson",    "department": "Research & AI",    "skills": {"qa": 0.90, "testing": 0.88, "automation": 0.82},          "load": 4.0, "status": "available"},
            {"email": "noah.garcia@datasphere.io",   "full_name": "Noah Garcia",     "department": "Research & AI",    "skills": {"data": 0.87, "analytics": 0.84, "research": 0.80},        "load": 3.5, "status": "available"},
        ],
        "clients": [
            {"email": "cto@investedge.com",     "full_name": "Rachel Morgan",  "company": "InvestEdge Capital"},
            {"email": "data@supplypro.co",      "full_name": "Vikram Sethi",   "company": "SupplyPro Logistics"},
        ],
        "admin_employee_map": {
            "marcus.chen@datasphere.io": ["Data Engineering"],
            "zara.ahmed@datasphere.io":  ["Analytics & BI"],
            "ryan.park@datasphere.io":   ["Infrastructure"],
            "hannah.lee@datasphere.io":  ["Research & AI"],
        },
    },

    # ── 3. BuildRight Engineering ─────────────────────────────────────────────
    {
        "slug": "buildright",
        "name": "BuildRight Engineering",
        "industry": "Infrastructure Technology",
        "hq": "London, UK",
        "plan_tier": "pro",
        "totp_for_ceo": True,
        "ceo": {
            "email": "james.obrien@buildright.co",
            "password": "CEO_Secure#BR88",
            "full_name": "James O'Brien",
        },
        "admins": [
            {"email": "lisa.chen@buildright.co",   "password": "Admin#Lisa77", "full_name": "Lisa Chen",   "department": "Project Delivery"},
            {"email": "sanjay.kumar@buildright.co","password": "Admin#Sanj77", "full_name": "Sanjay Kumar","department": "Engineering"},
            {"email": "maya.torres@buildright.co", "password": "Admin#Maya77", "full_name": "Maya Torres", "department": "Quality Assurance"},
            {"email": "derek.walsh@buildright.co", "password": "Admin#Dere77", "full_name": "Derek Walsh",  "department": "Finance & Ops"},
        ],
        "employees": [
            # Project Delivery (Lisa)
            {"email": "william.davies@buildright.co", "full_name": "William Davies",  "department": "Project Delivery",  "skills": {"project-management": 0.93},                               "load": 3.0, "status": "available"},
            {"email": "eleanor.smith@buildright.co",  "full_name": "Eleanor Smith",   "department": "Project Delivery",  "skills": {"client-success": 0.91, "reporting": 0.88},                "load": 2.0, "status": "available"},
            {"email": "oliver.brown@buildright.co",   "full_name": "Oliver Brown",    "department": "Project Delivery",  "skills": {"project-management": 0.88},                               "load": 4.5, "status": "available"},
            {"email": "amelia.johnson@buildright.co", "full_name": "Amelia Johnson",  "department": "Project Delivery",  "skills": {"architecture": 0.90, "delivery": 0.87},                   "load": 1.0, "status": "available"},
            {"email": "harry.williams@buildright.co", "full_name": "Harry Williams",  "department": "Project Delivery",  "skills": {"project-management": 0.85},                               "load": 5.0, "status": "available"},
            # Engineering (Sanjay)
            {"email": "george.wilson@buildright.co",  "full_name": "George Wilson",   "department": "Engineering",       "skills": {"backend": 0.90, "api": 0.87},                             "load": 3.5, "status": "available"},
            {"email": "charlotte.t@buildright.co",    "full_name": "Charlotte Taylor","department": "Engineering",       "skills": {"frontend": 0.88, "react": 0.85},                          "load": 6.0, "status": "available"},
            {"email": "alfie.anderson@buildright.co", "full_name": "Alfie Anderson",  "department": "Engineering",       "skills": {"backend": 0.86, "api": 0.83},                             "load": 2.0, "status": "available"},
            {"email": "isla.thomas@buildright.co",    "full_name": "Isla Thomas",     "department": "Engineering",       "skills": {"devops": 0.89, "cloud": 0.86},                            "load": 4.0, "status": "available"},
            {"email": "jack.martin@buildright.co",    "full_name": "Jack Martin",     "department": "Engineering",       "skills": {"backend": 0.84, "api": 0.81},                             "load": 0.0, "status": "available"},
            # Quality Assurance (Maya)
            {"email": "lily.jackson@buildright.co",   "full_name": "Lily Jackson",    "department": "Quality Assurance", "skills": {"qa": 0.94, "testing": 0.91, "automation": 0.88},          "load": 3.0, "status": "available"},
            {"email": "noah.thompson@buildright.co",  "full_name": "Noah Thompson",   "department": "Quality Assurance", "skills": {"qa": 0.90, "testing": 0.87},                              "load": 5.5, "status": "available"},
            {"email": "emily.garcia@buildright.co",   "full_name": "Emily Garcia",    "department": "Quality Assurance", "skills": {"qa": 0.92, "testing": 0.89, "automation": 0.84},          "load": 2.5, "status": "available"},
            {"email": "ben.robinson@buildright.co",   "full_name": "Benjamin Robinson","department": "Quality Assurance", "skills": {"architecture": 0.87, "delivery": 0.83},                  "load": 1.5, "status": "on-leave"},
            {"email": "chloe.hall@buildright.co",     "full_name": "Chloe Hall",      "department": "Quality Assurance", "skills": {"project-management": 0.85},                               "load": 4.0, "status": "available"},
            # Finance & Ops (Derek)
            {"email": "daniel.lewis@buildright.co",   "full_name": "Daniel Lewis",    "department": "Finance & Ops",     "skills": {"data": 0.88, "analytics": 0.85, "reporting": 0.80},      "load": 3.0, "status": "available"},
            {"email": "evie.lee@buildright.co",       "full_name": "Evie Lee",        "department": "Finance & Ops",     "skills": {"client-success": 0.90, "reporting": 0.87},                "load": 2.0, "status": "available"},
            {"email": "joshua.walker@buildright.co",  "full_name": "Joshua Walker",   "department": "Finance & Ops",     "skills": {"project-management": 0.86},                               "load": 5.0, "status": "available"},
            {"email": "ella.allen@buildright.co",     "full_name": "Ella Allen",      "department": "Finance & Ops",     "skills": {"frontend": 0.84, "react": 0.82},                          "load": 0.0, "status": "available"},
            {"email": "samuel.clark@buildright.co",   "full_name": "Samuel Clark",    "department": "Finance & Ops",     "skills": {"backend": 0.83, "api": 0.80},                             "load": 4.5, "status": "available"},
        ],
        "clients": [
            {"email": "ops@citygrid.co.uk",     "full_name": "Thomas Hughes",  "company": "CityGrid Infrastructure"},
            {"email": "tech@thameswater.io",    "full_name": "Claire Dawson",  "company": "Thames Digital Water"},
        ],
        "admin_employee_map": {
            "lisa.chen@buildright.co":   ["Project Delivery"],
            "sanjay.kumar@buildright.co":["Engineering"],
            "maya.torres@buildright.co": ["Quality Assurance"],
            "derek.walsh@buildright.co": ["Finance & Ops"],
        },
    },

    # ── 4. HealthSync Medical ─────────────────────────────────────────────────
    {
        "slug": "healthsync",
        "name": "HealthSync Medical",
        "industry": "Healthcare Technology",
        "hq": "Singapore",
        "plan_tier": "enterprise",
        "totp_for_ceo": True,
        "ceo": {
            "email": "sarah.kim@healthsync.sg",
            "password": "CEO_Secure#HS88",
            "full_name": "Dr. Sarah Kim",
        },
        "admins": [
            {"email": "tom.reddy@healthsync.sg",   "password": "Admin#TomR77", "full_name": "Tom Reddy",        "department": "Engineering"},
            {"email": "ananya.menon@healthsync.sg","password": "Admin#Anan77", "full_name": "Ananya Menon",      "department": "Clinical Product"},
            {"email": "chris.lawson@healthsync.sg","password": "Admin#Chri77", "full_name": "Chris Lawson",      "department": "Data & AI"},
            {"email": "nina.patel@healthsync.sg",  "password": "Admin#Nina77", "full_name": "Nina Patel",        "department": "Operations"},
        ],
        "employees": [
            # Engineering (Tom)
            {"email": "wei.zhang@healthsync.sg",     "full_name": "Wei Zhang",       "department": "Engineering",     "skills": {"backend": 0.92, "api": 0.89},                             "load": 4.0, "status": "available"},
            {"email": "priyanka.s@healthsync.sg",    "full_name": "Priyanka Singh",  "department": "Engineering",     "skills": {"frontend": 0.90, "react": 0.87},                          "load": 2.0, "status": "available"},
            {"email": "raj.kumar@healthsync.sg",     "full_name": "Raj Kumar",       "department": "Engineering",     "skills": {"backend": 0.88, "api": 0.85},                             "load": 6.0, "status": "available"},
            {"email": "lin.chen@healthsync.sg",      "full_name": "Lin Chen",        "department": "Engineering",     "skills": {"devops": 0.91, "cloud": 0.88, "security": 0.80},          "load": 3.0, "status": "available"},
            {"email": "amir.hassan@healthsync.sg",   "full_name": "Amir Hassan",     "department": "Engineering",     "skills": {"backend": 0.86, "api": 0.83},                             "load": 5.0, "status": "available"},
            {"email": "mei.ling@healthsync.sg",      "full_name": "Mei Ling",        "department": "Engineering",     "skills": {"frontend": 0.87, "react": 0.84},                          "load": 1.0, "status": "available"},
            # Clinical Product (Ananya)
            {"email": "james.park@healthsync.sg",    "full_name": "Dr. James Park",  "department": "Clinical Product","skills": {"architecture": 0.93, "delivery": 0.89},                   "load": 3.5, "status": "available"},
            {"email": "fatima.a@healthsync.sg",      "full_name": "Fatima Al-Rashid","department": "Clinical Product","skills": {"client-success": 0.92, "reporting": 0.88},                "load": 2.0, "status": "available"},
            {"email": "samuel.okafor@healthsync.sg", "full_name": "Samuel Okafor",   "department": "Clinical Product","skills": {"project-management": 0.90},                               "load": 4.0, "status": "available"},
            {"email": "rebecca.tan@healthsync.sg",   "full_name": "Rebecca Tan",     "department": "Clinical Product","skills": {"qa": 0.93, "testing": 0.90, "automation": 0.85},          "load": 0.0, "status": "available"},
            {"email": "ibrahim.n@healthsync.sg",     "full_name": "Ibrahim Ndiaye",  "department": "Clinical Product","skills": {"client-success": 0.88, "reporting": 0.85},                "load": 5.5, "status": "available"},
            {"email": "chen.wei@healthsync.sg",      "full_name": "Chen Wei",        "department": "Clinical Product","skills": {"architecture": 0.89, "delivery": 0.85},                   "load": 3.0, "status": "on-leave"},
            # Data & AI (Chris)
            {"email": "ling.hua@healthsync.sg",      "full_name": "Ling Hua",        "department": "Data & AI",       "skills": {"data": 0.93, "analytics": 0.90},                          "load": 3.0, "status": "available"},
            {"email": "seo.park@healthsync.sg",      "full_name": "Seo-Yeon Park",   "department": "Data & AI",       "skills": {"llm": 0.94, "modeling": 0.91},                            "load": 5.0, "status": "available"},
            {"email": "tariq.h@healthsync.sg",       "full_name": "Tariq Al-Hassan", "department": "Data & AI",       "skills": {"data": 0.90, "analytics": 0.87},                          "load": 2.0, "status": "available"},
            {"email": "yuki.tanaka@healthsync.sg",   "full_name": "Yuki Tanaka",     "department": "Data & AI",       "skills": {"prompting": 0.92, "research": 0.89, "llm": 0.78},         "load": 4.5, "status": "available"},
            {"email": "amara.diallo@healthsync.sg",  "full_name": "Amara Diallo",    "department": "Data & AI",       "skills": {"llm": 0.91, "modeling": 0.88},                            "load": 1.0, "status": "available"},
            {"email": "kwame.asante@healthsync.sg",  "full_name": "Kwame Asante",    "department": "Data & AI",       "skills": {"data": 0.88, "analytics": 0.85},                          "load": 6.0, "status": "available"},
            # Operations (Nina)
            {"email": "malia.fonoti@healthsync.sg",  "full_name": "Malia Fonoti",    "department": "Operations",      "skills": {"project-management": 0.91},                               "load": 2.5, "status": "available"},
            {"email": "deepa.k@healthsync.sg",       "full_name": "Deepa Krishnan",  "department": "Operations",      "skills": {"client-success": 0.90, "reporting": 0.87},                "load": 3.0, "status": "available"},
            {"email": "rafael.santos@healthsync.sg", "full_name": "Rafael Santos",   "department": "Operations",      "skills": {"devops": 0.88, "cloud": 0.85},                            "load": 4.0, "status": "available"},
            {"email": "bao.nguyen@healthsync.sg",    "full_name": "Bao Nguyen",      "department": "Operations",      "skills": {"project-management": 0.87},                               "load": 1.5, "status": "available"},
            {"email": "leila.ahmadi@healthsync.sg",  "full_name": "Leila Ahmadi",    "department": "Operations",      "skills": {"qa": 0.89, "testing": 0.86, "automation": 0.80},          "load": 5.0, "status": "available"},
            {"email": "marco.rossi@healthsync.sg",   "full_name": "Marco Rossi",     "department": "Operations",      "skills": {"architecture": 0.88, "delivery": 0.84},                   "load": 0.0, "status": "available"},
        ],
        "clients": [
            {"email": "digital@nuh.sg",         "full_name": "Dr. Amanda Koh",   "company": "NUH Digital Health"},
            {"email": "tech@farmacare.sg",      "full_name": "Rohit Malhotra",   "company": "FarmaCare Asia"},
        ],
        "admin_employee_map": {
            "tom.reddy@healthsync.sg":   ["Engineering"],
            "ananya.menon@healthsync.sg":["Clinical Product"],
            "chris.lawson@healthsync.sg":["Data & AI"],
            "nina.patel@healthsync.sg":  ["Operations"],
        },
    },
]

# ── Stats ──────────────────────────────────────────────────────────────────────
_created = 0
_skipped = 0


# ── Helpers ───────────────────────────────────────────────────────────────────

def _upsert_tenant(db, name, slug, industry=None, hq=None):
    global _created, _skipped
    existing = db.query(Tenant).filter(Tenant.slug == slug).first()
    if existing:
        _skipped += 1
        return existing, False
    t = Tenant(name=name, slug=slug)
    if industry:
        t.industry = industry
    if hq:
        t.headquarters = hq
    db.add(t)
    db.flush()
    _created += 1
    return t, True


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


def _ensure_prefs(db, user_id, **kwargs):
    existing = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if existing:
        for k, v in kwargs.items():
            setattr(existing, k, v)
        db.flush()
        return
    db.add(UserPreferences(user_id=user_id, **kwargs))
    db.flush()


def _ensure_employee(db, user, skills, department, load=0.0, status="available"):
    existing = db.query(EmployeeProfile).filter(EmployeeProfile.user_id == user.id).first()
    if existing:
        return existing
    p = EmployeeProfile(
        tenant_id=user.tenant_id,
        user_id=user.id,
        skills=skills,
        max_capacity=40.0,
        current_load=load,
        department=department,
        availability_status=status,
        duty_start_hour=0.0,   # 24/7 for demo — never "off-duty"
        duty_end_hour=24.0,
    )
    db.add(p)
    db.flush()
    # Vary metrics slightly per employee
    import random
    random.seed(user.id)
    db.add(EmployeeMetrics(
        employee_id=p.id,
        efficiency_score=round(random.uniform(0.78, 0.97), 2),
        reliability_score=round(random.uniform(0.82, 0.99), 2),
        avg_completion_time=round(random.uniform(3.5, 8.0), 1),
        total_tasks_completed=random.randint(6, 32),
        total_tasks_failed=random.randint(0, 2),
        total_tasks_delayed=random.randint(0, 3),
    ))
    db.flush()
    return p


def _ensure_client(db, tenant_id, email, password, full_name, company):
    u, created = _upsert_user(db, email, password, full_name, "client", tenant_id)
    _ensure_prefs(db, u.id, timezone="UTC", onboarding_complete=True)
    existing = db.query(ClientProfile).filter(ClientProfile.user_id == u.id).first()
    if not existing:
        cp = ClientProfile(
            tenant_id=tenant_id, user_id=u.id,
            company_name=company, contact_person=full_name,
        )
        db.add(cp)
        db.flush()
    return u


def _ensure_tenant_settings(db, tenant_id, plan_tier="pro"):
    if db.query(TenantSettings).filter(TenantSettings.tenant_id == tenant_id).first():
        return
    db.add(TenantSettings(
        tenant_id=tenant_id,
        plan_tier=plan_tier,
        suspended=False,
        stripe_customer_id=f"cus_seed_{tenant_id}",
        stripe_subscription_id=f"sub_seed_{tenant_id}",
        stripe_plan_id=f"price_{plan_tier}",
        subscription_expires_at=datetime.utcnow() + timedelta(days=180),
        next_billing_date=datetime.utcnow() + timedelta(days=30),
        max_teams=-1, max_users=-1, max_projects=-1,
        max_ai_calls_per_month=10000 if plan_tier == "enterprise" else 5000,
    ))
    db.flush()


def _ensure_dept_team(db, tenant_id, department, admin_user_id):
    """Ensure one org-pool team per department (project_id=None)."""
    existing = (
        db.query(Team)
        .filter(Team.tenant_id == tenant_id, Team.name == department, Team.project_id.is_(None))
        .first()
    )
    if existing:
        return existing
    team = Team(
        tenant_id=tenant_id,
        project_id=None,
        name=department,
        created_by_user_id=admin_user_id,
    )
    db.add(team)
    db.flush()
    return team


def _add_team_member(db, team, user, employee_profile):
    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team.id,
        TeamMember.user_id == user.id,
    ).first()
    if existing:
        return
    db.add(TeamMember(
        tenant_id=team.tenant_id,
        team_id=team.id,
        user_id=user.id,
        employee_profile_id=employee_profile.id,
        role_title=employee_profile.department,
        status="active",
    ))
    db.flush()


# ── Seed agents ───────────────────────────────────────────────────────────────

def seed_agents(db):
    for defn in AGENT_DEFINITIONS:
        existing = db.query(Agent).filter(Agent.name == defn["name"]).first()
        if not existing:
            db.add(Agent(name=defn["name"], role=defn["role"], capability=defn["capability"]))
    db.flush()


# ── Seed platform owner ───────────────────────────────────────────────────────

def seed_platform_owner(db):
    platform_tenant, _ = _upsert_tenant(db, "Platform", "platform")
    owner, _ = _upsert_user(db, **PLATFORM_OWNER, tenant_id=platform_tenant.id)
    _ensure_prefs(db, owner.id, timezone="Asia/Kolkata", theme="dark", onboarding_complete=True)
    return owner


# ── Seed one tenant ───────────────────────────────────────────────────────────

def seed_tenant(db, spec):
    slug       = spec["slug"]
    name       = spec["name"]
    industry   = spec.get("industry")
    hq         = spec.get("hq")
    plan_tier  = spec.get("plan_tier", "pro")

    print(f"  Seeding tenant: {name}")

    tenant, _ = _upsert_tenant(db, name, slug, industry=industry, hq=hq)
    _ensure_tenant_settings(db, tenant.id, plan_tier=plan_tier)

    # CEO
    totp_secret = pyotp.random_base32() if spec.get("totp_for_ceo") else None
    ceo_data    = spec["ceo"]
    ceo, _      = _upsert_user(
        db,
        email=ceo_data["email"],
        password=ceo_data["password"],
        full_name=ceo_data["full_name"],
        role="ceo",
        tenant_id=tenant.id,
        totp_secret=totp_secret,
        totp_enabled=bool(totp_secret),
    )
    _ensure_prefs(db, ceo.id, timezone="Asia/Kolkata", theme="dark",
                  ceo_mode=True, default_landing_page="ceo-dashboard", onboarding_complete=True)

    # Admins + their department teams
    admin_objects = {}
    for admin_spec in spec["admins"]:
        admin, admin_created = _upsert_user(
            db,
            email=admin_spec["email"],
            password=admin_spec["password"],
            full_name=admin_spec["full_name"],
            role="admin",
            tenant_id=tenant.id,
        )
        _ensure_prefs(db, admin.id, timezone="UTC", theme="light", onboarding_complete=True)
        if admin_created:
            db.add(RefreshToken(
                user_id=admin.id, token=generate_refresh_token(),
                expires_at=datetime.utcnow() + timedelta(days=30), revoked=False,
            ))

        dept = admin_spec["department"]
        admin_objects[admin.email] = (admin, dept)

        # Create department team (org-pool, project_id=None)
        _ensure_dept_team(db, tenant.id, dept, admin.id)

    # Employees
    emp_profile_map = {}  # email → EmployeeProfile
    for emp_spec in spec["employees"]:
        u, _ = _upsert_user(
            db,
            email=emp_spec["email"],
            password="team123456",
            full_name=emp_spec["full_name"],
            role="employee",
            tenant_id=tenant.id,
        )
        _ensure_prefs(db, u.id, timezone="UTC", onboarding_complete=True)
        ep = _ensure_employee(
            db, u,
            skills=emp_spec["skills"],
            department=emp_spec["department"],
            load=emp_spec.get("load", 0.0),
            status=emp_spec.get("status", "available"),
        )
        emp_profile_map[emp_spec["email"]] = (u, ep)

    # Assign employees to their department team + admin as team member
    dept_team_cache = {}
    for emp_email, (u, ep) in emp_profile_map.items():
        dept = ep.department
        if dept not in dept_team_cache:
            team = (
                db.query(Team)
                .filter(Team.tenant_id == tenant.id, Team.name == dept, Team.project_id.is_(None))
                .first()
            )
            dept_team_cache[dept] = team
        team = dept_team_cache[dept]
        if team:
            _add_team_member(db, team, u, ep)

    # Also add each admin as a member of their own team
    for admin_email, (admin, dept) in admin_objects.items():
        team = dept_team_cache.get(dept)
        if team:
            existing = db.query(TeamMember).filter(
                TeamMember.team_id == team.id,
                TeamMember.user_id == admin.id,
            ).first()
            if not existing:
                db.add(TeamMember(
                    tenant_id=tenant.id,
                    team_id=team.id,
                    user_id=admin.id,
                    employee_profile_id=None,
                    role_title="Team Lead",
                    status="active",
                ))
                db.flush()

    # Clients
    for client_spec in spec.get("clients", []):
        _ensure_client(
            db, tenant.id,
            email=client_spec["email"],
            password="client123456",
            full_name=client_spec["full_name"],
            company=client_spec["company"],
        )

    return tenant, ceo, totp_secret


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    global _created, _skipped

    if _LOCAL_MODE:
        print(f"\nLocal mode — resetting SQLite: {DATABASE_URL}")
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema(engine)
    elif args.reset:
        db_host = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        confirm = input(f"\n⚠  --reset will DELETE ALL DATA in {db_host}\nType 'yes-delete-everything': ")
        if confirm.strip() != "yes-delete-everything":
            print("Aborted.")
            sys.exit(0)
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema(engine)
    else:
        Base.metadata.create_all(bind=engine)
        ensure_runtime_schema(engine)

    db = SessionLocal()
    try:
        print("Seeding 12 agent definitions...")
        seed_agents(db)

        print("Seeding platform owner...")
        seed_platform_owner(db)

        seeded_tenants = []
        for spec in TENANTS:
            tenant, ceo, totp_secret = seed_tenant(db, spec)
            seeded_tenants.append((spec, tenant.name, ceo.email, totp_secret))

        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 72)
    print("  Seed Complete — AI Workforce Orchestrator")
    print("=" * 72)
    print(f"  Records: {_created} created   {_skipped} skipped")
    print(f"  Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}")
    print(f"  AI Model: {GEMINI_MODEL}")
    print()

    print("[ Platform Owner ]")
    print(f"  {PLATFORM_OWNER['email']}  /  {PLATFORM_OWNER['password']}")
    print()

    for spec, tenant_name, ceo_email, totp_secret in seeded_tenants:
        print(f"[ {tenant_name} — {spec.get('plan_tier','pro').upper()} ]")
        ceo_data = spec["ceo"]
        line = f"  CEO  : {ceo_data['email']}  /  {ceo_data['password']}"
        if totp_secret:
            totp = pyotp.TOTP(totp_secret)
            line += f"  (TOTP secret: {totp_secret} | code: {totp.now()})"
        print(line)
        for a in spec["admins"]:
            print(f"  Admin: {a['email']}  /  {a['password']}")
        for e in spec["employees"]:
            print(f"  Emp  : {e['email']}  /  team123456  [{e['department']}]")
        for c in spec.get("clients", []):
            print(f"  Client: {c['email']}  /  client123456  [{c['company']}]")
        print()

    print("[ All Employees Password ]  team123456")
    print("[ All Clients Password   ]  client123456")
    print()
    if _LOCAL_MODE:
        print("[ Local endpoints ]")
        print("  uvicorn app.main:app --reload --port 8001")
        print("  http://localhost:8001/docs")
        print("  http://localhost:5173  (frontend)")
    print()


if __name__ == "__main__":
    main()
