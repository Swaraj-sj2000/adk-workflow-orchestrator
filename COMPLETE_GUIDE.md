# AI Workforce Orchestrator — Complete Project Guide
> Single source of truth for architecture, usage, deployment, and development.
> Last updated: 2026-04-27 | Branch: main | Latest commit: 72cb644 (phase-12)

---

## Table of Contents

1. [Project Vision](#1-project-vision)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Technology Stack](#3-technology-stack)
4. [User Role Hierarchy](#4-user-role-hierarchy)
5. [Repository Structure](#5-repository-structure)
6. [Database Models — Full Reference](#6-database-models--full-reference)
7. [API Endpoints — Complete Map](#7-api-endpoints--complete-map)
8. [Services — Business Logic Layer](#8-services--business-logic-layer)
9. [Multi-Agent System](#9-multi-agent-system)
10. [Frontend Components](#10-frontend-components)
11. [Environment Variables](#11-environment-variables)
12. [Email System (SendGrid)](#12-email-system-sendgrid)
13. [Billing & Payments (Stripe)](#13-billing--payments-stripe)
14. [Background Scheduler](#14-background-scheduler)
15. [Authentication & Security](#15-authentication--security)
16. [Data Flow Chains](#16-data-flow-chains)
17. [Deployment Guide](#17-deployment-guide)
18. [Local Development Setup](#18-local-development-setup)
19. [Demo Credentials & Seeded Data](#19-demo-credentials--seeded-data)
20. [Implementation History](#20-implementation-history)
21. [Troubleshooting](#21-troubleshooting)

---

## 1. Project Vision

The AI Workforce Orchestrator is a **multi-tenant B2B SaaS platform** that helps companies manage their internal teams, projects, tasks, and AI-driven delivery pipelines.

**What it is:**
A platform that other companies subscribe to. Each company (tenant) manages their teams, projects, clients, and deliverables through an AI-assisted workflow. The AI handles staffing decisions, project planning, risk assessment, communication drafting, and escalation — and actually acts on those decisions (sends emails, updates state, triggers alerts) rather than just suggesting them.

**Who uses it:**

| Role | Who they are | What they do |
|------|-------------|--------------|
| Platform Owner | Swaraj (you) | Manages all companies on the platform, controls subscriptions, sees all tenants |
| CEO / Executive | Company leadership | Sees company-wide health, financials, team utilization, risk — business view |
| Admin / Manager | Team or project manager | Creates projects, manages teams, approves plans, handles invites |
| Employee | Team member | Does task work, updates checkpoints, tracks performance |
| Client | External customer | Views project status and payment for their specific project |

**The core value proposition:**
- AI agents automatically plan projects from a text description
- AI assigns tasks to the best available employee using skill/workload/efficiency scoring
- Agents send real emails, escalate real alerts, run nightly health checks
- CEOs see company-wide operational health in one screen
- Platform owner controls every company from one panel with billing enforcement

---

## 2. High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLATFORM OWNER LAYER                         │
│  Owner Panel → All tenants, billing, support, suspend/activate  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    TENANT LAYER (per company)                   │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  CEO Panel   │  │ Admin Panel  │  │  Employee/Client UI  │  │
│  │ Business +   │  │ Projects,    │  │  Tasks, Checkpoints, │  │
│  │ Tech views   │  │ Teams, AI    │  │  Invites, Profile    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         └─────────────────┼──────────────────────┘             │
│                           ▼                                     │
│              FastAPI Backend (backend_adk/)                     │
│                                                                 │
│  Auth → Routes → Services → Agents → DB                        │
│                      │                                          │
│  ┌────────────────────▼──────────────────────┐                  │
│  │           Multi-Agent Orchestrator        │                  │
│  │  Intake → Planning → Staffing → Risk →   │                  │
│  │  Execution → Communication → Escalation  │                  │
│  └────────────────────┬──────────────────────┘                  │
│                       │                                          │
│  ┌────────────────────▼──────────────────────┐                  │
│  │  External Integrations                    │                  │
│  │  SendGrid (email) │ Stripe (payments)     │                  │
│  │  HuggingFace LLM  │ Background Scheduler  │                  │
│  └───────────────────────────────────────────┘                  │
│                                                                 │
│              PostgreSQL (Cloud SQL) / SQLite (dev)             │
└─────────────────────────────────────────────────────────────────┘
```

**Key architectural rules:**
- All business logic lives in `backend_adk/app/` — never `backend/`
- Every DB query on tenant-scoped tables must filter by `tenant_id`
- Email failures never crash request flows — always logged, always silent
- Agents persist their output to `WorkflowRun` / `AgentRun` tables
- Schema changes are additive: new tables via model imports, new columns via `_schema.py`

---

## 3. Technology Stack

### Backend
| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | ≥0.109 | HTTP framework, dependency injection, OpenAPI |
| Uvicorn | ≥0.27 | ASGI server |
| SQLAlchemy | ≥2.0 | ORM, connection pooling |
| Pydantic | ≥2.5 | Request/response validation (v2 API) |
| python-jose | ≥3.3 | JWT signing and verification (HS256) |
| passlib + bcrypt | ≥1.7 / 3.2.2 | Password hashing |
| SendGrid | ≥6.11 | Transactional email delivery |
| Stripe | ≥11.0 | Subscription billing, webhooks, Connect |
| pytz | ≥2024.1 | Timezone-aware scheduling in assignment engine |
| pyotp | ≥2.9 | TOTP/2FA code generation and verification |
| redis | ≥5.0 | Distributed rate limiting (optional; falls back to in-memory) |
| google-auth-oauthlib | ≥1.2 | Google Calendar OAuth 2.0 flow |
| google-api-python-client | ≥2.120 | Google Calendar API event creation |
| LangChain + HuggingFace | latest | LLM integration for project parsing |
| structlog | ≥24.1 | Structured logging |
| psycopg2-binary | ≥2.9 | PostgreSQL driver |
| python-dotenv | ≥1.0 | .env loading |

### Frontend
| Package | Version | Purpose |
|---------|---------|---------|
| React | ^18.2 | UI framework |
| React DOM | ^18.2 | DOM rendering |
| Vite | ^5.0 | Build tool, HMR |
| @vitejs/plugin-react | ^4.2 | Vite React integration |
| Axios | ^1.6 | HTTP client |
| React Router DOM | ^6.20 | Client-side routing |

### Infrastructure
| Component | Technology |
|-----------|-----------|
| Backend hosting | Google Cloud Run (europe-west1) |
| Frontend hosting | Google Cloud Run + Nginx |
| Database | Cloud SQL PostgreSQL (orchestrator-sql instance) |
| Container registry | Artifact Registry (europe-west1-docker.pkg.dev/havoc-ai-prod) |
| GCP Project | havoc-ai-prod |

---

## 4. User Role Hierarchy

```
platform_owner  →  Tier 0: You. Cross-tenant. Sees everything.
ceo             →  Tier 1: Company executive. Business + optional technical view.
admin           →  Tier 2: Team/project manager. Manages one company's work.
employee        →  Tier 3: Team member. Executes tasks.
client          →  Tier 4: External customer. View-only on their project.
```

### Role Capabilities Matrix

| Capability | platform_owner | ceo | admin | employee | client |
|-----------|:-:|:-:|:-:|:-:|:-:|
| See all tenants | ✅ | ❌ | ❌ | ❌ | ❌ |
| Suspend a company | ✅ | ❌ | ❌ | ❌ | ❌ |
| Company-wide KPIs | ❌ | ✅ | ❌ | ❌ | ❌ |
| All projects in company | ❌ | ✅ | ✅ | ❌ | ❌ |
| Create projects | ❌ | ✅ | ✅ | ❌ | ❌ |
| Manage team invites | ❌ | ✅ | ✅ | ❌ | ❌ |
| Override AI decisions | ❌ | ✅ | ✅ | ❌ | ❌ |
| Apply payment holds | ❌ | ✅ | ✅ | ❌ | ❌ |
| Accept task assignments | ❌ | ❌ | ❌ | ✅ | ❌ |
| Update task progress | ❌ | ❌ | ❌ | ✅ | ❌ |
| View own project status | ❌ | ❌ | ❌ | ❌ | ✅ |
| View payment status | ❌ | ✅ | ✅ | ❌ | ✅ |

### CEO Mode Toggle
CEOs have two views controlled by `UserPreferences.ceo_mode`:
- **`false` (default)** — Business View: KPI cards, financials, risk flags, client status
- **`true`** — Technical View: same as Admin interface with full project/task/agent drill-down

---

## 5. Repository Structure

```
agentic_orchestrator/
│
├── backend_adk/                      ← PRODUCTION backend (always edit here)
│   ├── app/
│   │   ├── main.py                   ← FastAPI app factory, middleware, routers, lifespan
│   │   ├── agents/                   ← 12 agent classes
│   │   │   ├── _base.py
│   │   │   ├── _intake_agent.py
│   │   │   ├── _planning_agent.py
│   │   │   ├── _staffing_agent.py
│   │   │   ├── _risk_agent.py
│   │   │   ├── _execution_coordinator_agent.py
│   │   │   ├── _communication_agent.py     ← now sends real emails
│   │   │   ├── _escalation_agent.py         ← now sends real alerts
│   │   │   ├── _project_observer_agent.py
│   │   │   ├── _delivery_review_agent.py
│   │   │   ├── _rebalance_agent.py
│   │   │   ├── _loop_communication_agent.py
│   │   │   └── _loop_escalation_agent.py
│   │   ├── api/routes/               ← HTTP route handlers (thin layer)
│   │   │   ├── _auth.py              ← login, register, refresh, verify-email, 2FA
│   │   │   ├── _project.py
│   │   │   ├── _task.py              ← includes soft-delete DELETE /tasks/{id}
│   │   │   ├── _task_assignment.py
│   │   │   ├── _task_progress.py
│   │   │   ├── _employee.py
│   │   │   ├── _invite.py
│   │   │   ├── _blocker.py
│   │   │   ├── _decision.py
│   │   │   ├── _meeting.py
│   │   │   ├── _multi_agent.py
│   │   │   ├── _autopm.py
│   │   │   ├── _agent.py
│   │   │   ├── _system.py
│   │   │   ├── _ceo.py              ← CEO analytics
│   │   │   ├── _owner.py            ← platform owner controls
│   │   │   ├── _settings.py         ← user preferences & profile
│   │   │   ├── _billing.py          ← Stripe billing
│   │   │   └── _integrations.py     ← Google Calendar OAuth
│   │   ├── core/
│   │   │   ├── _config.py            ← Settings singleton (all env vars)
│   │   │   ├── _security.py          ← JWT + bcrypt + TOTP helpers
│   │   │   ├── _deps.py              ← FastAPI dependencies (auth guards)
│   │   │   ├── _tenant_middleware.py ← Tenant context + suspension gate
│   │   │   ├── _rate_limit.py        ← Redis sliding-window / in-memory fallback
│   │   │   ├── _security_headers.py  ← HTTP security headers
│   │   │   └── _logging.py           ← Centralized logger setup
│   │   ├── db/
│   │   │   ├── _database.py          ← Base, engine, SessionLocal
│   │   │   └── _schema.py            ← Additive column patcher (ensure_runtime_schema)
│   │   ├── models/                   ← 32 SQLAlchemy ORM models (incl. RefreshToken)
│   │   ├── schemas/                  ← Pydantic v2 schemas
│   │   ├── services/                 ← Business logic layer
│   │   └── utils/_constants.py       ← All enum values
│   ├── tests/
│   │   ├── conftest.py               ← In-memory SQLite fixture + TestClient
│   │   ├── test_auth.py              ← register, verify, login, refresh, 2FA
│   │   ├── test_billing.py           ← grace period, Stripe webhook handling
│   │   └── test_assignment.py        ← scoring, tenant isolation, candidate selection
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── deploy_cloud_run.sh
│   ├── cloudbuild.yaml
│   └── seed_test_data.py
│
├── backend/                          ← LOCAL DEV MIRROR — do not deploy from here
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx                   ← Shell, routing, auth state, preferences loader
│   │   ├── main.jsx                  ← ReactDOM entry point
│   │   ├── config.js                 ← API_BASE_URL + formatDateInUserTimezone()
│   │   └── components/
│   │       ├── Navbar.jsx             ← Nav + avatar dropdown
│   │       ├── Dashboard.jsx
│   │       ├── Projects.jsx
│   │       ├── EmployeeView.jsx
│   │       ├── TaskDetail.jsx
│   │       ├── Decisions.jsx
│   │       ├── MultiAgentWorkbench.jsx
│   │       ├── AutoPMConsole.jsx
│   │       ├── CEODashboard.jsx      ← NEW
│   │       ├── OwnerPanel.jsx        ← NEW
│   │       └── Settings.jsx          ← NEW
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   └── vite.config.js
│
├── CONTEXT_GRAPH.md                  ← Machine-readable codebase map (gitignored)
├── COMPLETE_GUIDE.md                 ← This file (gitignored)
├── AGENT_MASTER_PROMPT.md            ← Agent execution prompt (gitignored)
└── .gitignore
```

---

## 6. Database Models — Full Reference

All models in `backend_adk/app/models/`. All inherit from `Base` (SQLAlchemy declarative). All tables with `tenant_id` are multi-tenant scoped — **always filter by `tenant_id` in queries**.

### Core Identity

#### `Tenant` (`_tenant.py`)
```
id          Integer PK
name        String unique
slug        String unique indexed
is_active   Boolean default=True
created_at  DateTime
```

#### `User` (`_user.py`)
```
id                      Integer PK
email                   String unique indexed
password                String (bcrypt hash)
full_name               String nullable
role                    String  → "platform_owner"|"ceo"|"admin"|"employee"|"client"
tenant_id               Integer FK→Tenant nullable indexed
password_reset_token    String nullable
password_reset_expires  DateTime nullable
email_verified          Boolean nullable  ← NULL=legacy(no gate), False=pending, True=verified
email_verify_token      String nullable   ← UUID sent in verification email
totp_secret             String nullable   ← base32 TOTP secret (set at /auth/2fa/setup)
totp_enabled            Boolean default=False
deleted_at              DateTime nullable ← soft delete (NULL = active)
```

#### `RefreshToken` (`_refresh_token.py`)
```
id          Integer PK
user_id     Integer FK→User indexed
token       String unique indexed  ← 48-byte URL-safe random token
expires_at  DateTime               ← now + 30 days
revoked     Boolean default=False  ← set True when rotated or logged out
created_at  DateTime
```

#### `UserPreferences` (`_user_preferences.py`)
```
id                        Integer PK
user_id                   Integer FK→User unique
timezone                  String default="UTC"        (IANA e.g. "Asia/Kolkata")
theme                     String default="light"      ("light"|"dark")
language                  String default="en"
ceo_mode                  Boolean default=False       (CEO technical view toggle)
notification_density      String default="all"        ("all"|"summary"|"critical")
default_landing_page      String default="dashboard"
email_notifications       Boolean default=True
weekly_digest             Boolean default=True
google_calendar_connected Boolean default=False
google_calendar_token     JSON nullable               ← encrypted OAuth token blob
google_calendar_email     String nullable             ← Google account email linked
created_at                DateTime
updated_at                DateTime auto-updated
```

#### `TenantSettings` (`_tenant_settings.py`) — NEW
```
id                      Integer PK
tenant_id               Integer FK→Tenant unique
default_timezone        String default="UTC"
data_region             String default="eu"         ("eu"|"us"|"apac")
plan_tier               String default="trial"      ("trial"|"starter"|"growth"|"enterprise")
suspended               Boolean default=False
suspension_reason       String nullable
suspended_at            DateTime nullable
grace_period_ends_at    DateTime nullable
stripe_customer_id      String nullable unique
stripe_subscription_id  String nullable
stripe_plan_id          String nullable
next_billing_date       DateTime nullable
trial_ends_at           DateTime nullable
max_users               Integer default=10
max_projects            Integer default=5
max_ai_calls_per_month  Integer default=100
created_at              DateTime
updated_at              DateTime auto-updated
```

#### `SupportTicket` (`_support_ticket.py`) — NEW
```
id              Integer PK
tenant_id       Integer FK→Tenant indexed
user_id         Integer FK→User indexed
subject         String
body            Text
status          String default="open"    ("open"|"in_progress"|"resolved"|"closed")
priority        String default="medium"  ("low"|"medium"|"high"|"critical")
admin_response  Text nullable
resolved_at     DateTime nullable
created_at      DateTime
updated_at      DateTime auto-updated
```

#### `ScheduledAgentJob` (`_scheduled_agent_job.py`)
```
id          Integer PK
tenant_id   Integer FK→Tenant indexed
project_id  Integer FK→Project nullable indexed
job_type    String      ("nightly_observer"|"weekly_digest"|"payment_check"|"archive_old_runs")
cron_expr   String      (e.g. "0 2 * * *")
timezone    String default="UTC"
enabled     Boolean default=True
last_run_at DateTime nullable
next_run_at DateTime nullable
last_status String nullable  ("success"|"failed")
last_error  String nullable
created_at  DateTime
```

#### `EmailDeliveryLog` (`_email_delivery_log.py`) — NEW
```
id                    Integer PK
tenant_id             Integer FK→Tenant nullable indexed
to_email              String
subject               String
template_name         String
sendgrid_message_id   String nullable
status                String default="queued" ("queued"|"sent"|"delivered"|"failed"|"bounced")
error_message         String nullable
sent_at               DateTime nullable
delivered_at          DateTime nullable
created_at            DateTime
```

#### `PlatformAuditLog` (`_platform_audit_log.py`) — NEW
```
id          Integer PK
action      String   ("tenant_suspended"|"tenant_activated"|"ticket_resolved"|"plan_changed")
tenant_id   Integer nullable
details     JSON nullable
timestamp   DateTime default=now
```

### Client & Employee Profiles

#### `ClientProfile` (`_client_profile.py`)
```
id              Integer PK
tenant_id       Integer FK→Tenant
user_id         Integer FK→User unique
company_name    String
contact_person  String nullable
phone           String nullable
address         String nullable
```

#### `EmployeeProfile` (`_employee_profile.py`)
```
id                  Integer PK
tenant_id           Integer FK→Tenant
user_id             Integer FK→User unique
skills              JSON    {skill_name: float 0..1}
max_capacity        Float   default=8.0 (hours/day)
current_load        Float   default=0.0 (hours assigned)
department          String nullable
availability_status String  ("available"|"on-leave"|"busy")
duty_start_hour     Float   default=9.0
duty_end_hour       Float   default=18.0
deleted_at          DateTime nullable   ← soft delete
```

#### `EmployeeMetrics` (`_employee_metrics.py`)
```
id                      Integer PK
employee_id             Integer FK→EmployeeProfile unique
efficiency_score        Float 0..1 default=0.5
reliability_score       Float 0..1 default=0.5
avg_completion_time     Float nullable (hours)
total_tasks_completed   Integer default=0
total_tasks_failed      Integer default=0
total_tasks_delayed     Integer default=0
updated_at              DateTime auto-updated
```

#### `Availability` (`_availability.py`)
```
id                  Integer PK
employee_id         Integer FK→EmployeeProfile
start_time          DateTime
end_time            DateTime
availability_type   String  ("available"|"on-leave"|"sick"|"training")
notes               String nullable
```

### Projects, Teams, Invites

#### `Project` (`_project.py`)
```
id              Integer PK
deleted_at      DateTime nullable   ← soft delete (filtered from all list queries)
tenant_id       Integer FK→Tenant indexed
name            String indexed
description     String
admin_id        Integer FK→User
client_id       Integer FK→ClientProfile nullable
status          String  ("planning"|"in-progress"|"on-hold"|"completed"|"cancelled")
progress        Integer 0..100 default=0
budget          Float   default=0.0
spent           Float   default=0.0
payment_status  String  ("pending"|"partial"|"client-confirmed"|"admin-confirmed"|"completed"|"disputed")
created_at      DateTime
start_date      DateTime nullable
deadline        DateTime nullable
completed_at    DateTime nullable
priority        String  ("low"|"medium"|"high"|"critical")
custom_fields   JSON nullable          ← invoice records stored here if no Stripe Connect
```

#### `Team` (`_team.py`)
```
id                  Integer PK
tenant_id           Integer FK→Tenant
project_id          Integer FK→Project
name                String
created_by_user_id  Integer FK→User
created_at          DateTime
```

#### `TeamMember` (`_team.py`)
```
id                  Integer PK
tenant_id           Integer FK→Tenant
team_id             Integer FK→Team
user_id             Integer FK→User
employee_profile_id Integer FK→EmployeeProfile nullable
role_title          String nullable
status              String default="active"
joined_at           DateTime
```

#### `TeamInvite` (`_team_invite.py`)
```
id                    Integer PK
tenant_id             Integer FK→Tenant
team_id               Integer FK→Team
email                 String indexed
status                String default="pending" ("pending"|"accepted"|"rejected")
token                 String unique indexed    (UUID, used in accept link)
role_title            String nullable
invited_by_user_id    Integer FK→User
invited_user_id       Integer FK→User nullable (linked if user already exists)
responded_by_user_id  Integer FK→User nullable
note                  Text nullable
created_at            DateTime
responded_at          DateTime nullable
```

### Tasks

#### `Task` (`_task.py`)
```
id              Integer PK
tenant_id       Integer FK→Tenant
project_id      Integer FK→Project
agent_id        Integer FK→Agent nullable
parent_task_id  Integer FK→Task nullable    (subtask tree)
description     String
status          String default="pending"    ("pending"|"running"|"done"|"blocked"|"delayed")
difficulty      String default="medium"     ("easy"|"medium"|"hard")
urgency         String default="medium"     ("low"|"medium"|"high"|"critical")
estimated_time  Float nullable (hours)
required_skills JSON default={}            {skill: proficiency}
created_at      DateTime
deadline        DateTime nullable
deleted_at      DateTime nullable           ← soft delete
```

#### `TaskAssignment` (`_task_assignment.py`)
```
id                    Integer PK
task_id               Integer FK→Task
employee_id           Integer FK→EmployeeProfile
assigned_at           DateTime
started_at            DateTime nullable
completed_at          DateTime nullable
status                String default="assigned" ("assigned"|"in-progress"|"completed"|"failed")
estimated_hours       Float nullable
actual_hours          Float nullable
assignment_confidence Float nullable (0..1 from AssignmentEngine)
notes                 Text nullable
```

#### `TaskDependency` (`_task_dependency.py`)
```
id                  Integer PK
task_id             Integer FK→Task
depends_on_task_id  Integer FK→Task
dependency_type     String default="blocking" ("blocking"|"weak"|"conditional")
```

#### `TaskProgress` (`_task_progress.py`)
```
id                        Integer PK
task_id                   Integer FK→Task unique
completion_percentage     Float default=0.0 (0..100)
last_updated_at           DateTime auto-updated
actual_hours_spent        Float default=0.0
estimated_hours_remaining Float nullable
status_notes              Text nullable
is_on_track               Integer default=1  (1=yes, 0=no)
```

#### `Checkpoint` (`_checkpoint.py`)
```
id           Integer PK
task_id      Integer FK→Task indexed
title        String
due_date     DateTime nullable
status       String default="pending" ("pending"|"completed"|"delayed")
completed_at DateTime nullable
notes        Text nullable
created_at   DateTime
```

#### `Blocker` (`_blocker.py`)
```
id                      Integer PK
task_id                 Integer FK→Task
blocker_type            String  ("dependency"|"resource"|"external"|"ambiguity")
severity                String default="medium" ("low"|"medium"|"high"|"critical")
description             Text
status                  String default="open"  ("open"|"in-progress"|"resolved"|"escalated")
raised_by_user_id       Integer FK→User nullable
ai_response             Text nullable
next_action             Text nullable
escalation_recommended  Integer default=0
created_at              DateTime
resolved_at             DateTime nullable
resolution_notes        Text nullable
```

### Audit & Decision

#### `DecisionLog` (`_decision_log.py`)
```
id                Integer PK
decision_type     String  ("assignment"|"reassignment"|"deadline_change"|"rebalance"|"escalation")
entity_type       String  ("task"|"project"|"employee")
entity_id         Integer
input_data        JSON
decision_taken    Text
confidence        Float 0..1
reasoning         Text nullable
override_by_admin Integer FK→User nullable
created_at        DateTime
```

#### `AuditLog` (`_audit_log.py`)
```
id              Integer PK
action          String
entity_type     String
entity_id       Integer
decision_reason Text nullable
performed_by    String default="agent" ("agent"|"human")
context_data    JSON nullable
timestamp       DateTime
```

### Agents & Workflows

#### `Agent` (`_agent.py`)
```
id          Integer PK
name        String
role        String
capability  String nullable
```

#### `WorkflowRun` (`_workflow_run.py`)
```
id                    Integer PK
workflow_type         String indexed ("project_intake"|"project_execution_loop")
status                String default="running" ("running"|"completed")
requested_by          Integer FK→User
project_id            Integer FK→Project nullable
requires_human_review Boolean default=False
input_payload         JSON default={}
shared_context        JSON nullable
final_output          JSON nullable
created_at            DateTime
completed_at          DateTime nullable
```

#### `AgentRun` (`_agent_run.py`)
```
id                    Integer PK
workflow_run_id       Integer FK→WorkflowRun indexed
agent_name            String indexed
role                  String
stage                 String
status                String default="completed"
confidence            Float nullable
requires_human_review Boolean default=False
reasoning             Text nullable
input_payload         JSON default={}
output_payload        JSON nullable
started_at            DateTime
completed_at          DateTime nullable
```

### Supporting Models

#### `Communication` (`_communication.py`)
```
id          Integer PK
type        String default="ticket" ("email"|"ticket"|"meeting"|"call")
from_actor  String  ("agent"|"admin"|"employee"|"client")
to_actor    String
subject     String
body        Text
project_id  Integer FK→Project nullable
task_id     Integer FK→Task nullable
sent_at     DateTime
status      String default="sent" ("sent"|"queued"|"failed"|"acknowledged")
```

#### `Meeting` (`_meeting.py`)
```
id              Integer PK
project_id      Integer FK→Project
created_by      Integer FK→User
title           String
description     Text nullable
meeting_type    String default="status" ("status"|"emergency"|"review"|"planning")
scheduled_at    DateTime nullable
completed_at    DateTime nullable
attendees       JSON   [user_id, ...]
decisions_made  JSON nullable
created_at      DateTime
```

#### `PerformancePoint` (`_performance_point.py`)
```
id          Integer PK
employee_id Integer FK→EmployeeProfile indexed
project_id  Integer FK→Project
task_id     Integer FK→Task
points      Float default=0.0
reason      String
awarded_at  DateTime
```

#### `EventQueue` (`_event_queue.py`)
```
id            Integer PK
event_type    String  ("TASK_CREATED"|"TASK_UPDATED"|"PROJECT_CREATED"|
                       "ASSIGNMENT_COMPLETE"|"BLOCKER_DETECTED"|
                       "REBALANCE_NEEDED"|"PROJECT_EXECUTION_SIGNAL")
entity_type   String
entity_id     Integer
payload       JSON
status        String default="pending" ("pending"|"processing"|"completed"|"failed")
retry_count   Integer default=0
created_at    DateTime
processed_at  DateTime nullable
error_message String nullable
```

---

## 7. API Endpoints — Complete Map

**Base URL (prod):** `https://orchestrator-backend-yo2mex5f2a-ew.a.run.app`
**Base URL (local):** `http://localhost:8001`
**Auth header:** `Authorization: Bearer <JWT>` on all protected routes
**Paginated list responses:** `{"items": [...], "total": int, "skip": int, "limit": int}`

### Auth (`_auth.py`)
```
POST   /auth/register              UserCreate body → {user, email_verified: false}
POST   /auth/login                 {email, password} → {access_token, refresh_token, user}
POST   /auth/refresh               {refresh_token} → {access_token, refresh_token}  ← token rotation
GET    /auth/verify-email?token=   → 200 or 400 (activates account)
POST   /auth/forgot-password       {email} → 200 always (no leak)
POST   /auth/reset-password        {token, new_password} → 200
POST   /auth/change-password       Bearer + {current_password, new_password} → 200
POST   /auth/2fa/setup             Bearer → {secret, provisioning_uri}  (QR-scannable)
POST   /auth/2fa/enable            Bearer + {totp_code} → 200  (confirms and activates 2FA)
POST   /auth/2fa/disable           Bearer + {totp_code} → 200
```

### Projects (`_project.py`)
```
POST   /projects/                                          [admin/ceo]   → project + planning artifacts
GET    /projects/?skip=0&limit=50                          [any auth]    → paginated project list
GET    /projects/clients                                   [admin/ceo]   → client list
GET    /projects/{id}/status                               [any auth]    → full project status
POST   /projects/{id}/team-approval                        [admin/ceo]   → approve draft team, create invites
PATCH  /projects/{id}/draft-team                           [admin/ceo]   → replace draft team member
POST   /projects/{id}/invite-response                      [employee]    → accept/reject invite
POST   /projects/{id}/task-change-requests                 [any]         → submit task change request
PATCH  /projects/{id}/task-change-requests/{change_id}     [admin/ceo]   → review change request
POST   /projects/{id}/task-reassignment                    [admin/ceo]   → reassign task to new employee
POST   /projects/{id}/payment-status                       [admin/client]→ update payment status
DELETE /projects/{id}                                      [admin/ceo]   → atomic cascade delete
```

### Tasks (`_task.py`)
```
POST   /tasks/                              [admin/ceo] → TaskCreate → TaskOut
GET    /tasks/?skip=0&limit=50              [any auth]  → paginated tasks (deleted_at filtered)
GET    /tasks/{id}                          [any auth]  → TaskOut (404 if soft-deleted)
PATCH  /tasks/{id}/status                   [admin/emp] → status update
DELETE /tasks/{id}                          [admin]     → soft-delete (sets deleted_at, does not purge)
POST   /tasks/{id}/assign/{agent_id}        [admin]     → assign AI agent to task
POST   /tasks/{id}/blockers                 [any auth]  → BlockerCreate → sends email alerts
GET    /tasks/{id}/blockers?skip=0&limit=50 [any]       → paginated blockers
```

### Task Assignments (`_task_assignment.py`)
```
POST   /task-assignments/?skip=0&limit=50  [admin/ceo] → create assignment
GET    /task-assignments/{id}              [any auth]
PATCH  /task-assignments/{id}             [emp/admin]  → update status/hours
```

### Task Progress (`_task_progress.py`)
```
GET    /task-progress?task_id={id}  [any auth] → TaskProgressRead
PATCH  /task-progress/{task_id}     [emp/admin] → update → publishes PROJECT_EXECUTION_SIGNAL
```

### Employees (`_employee.py`)
```
POST   /employees/profile                [admin]      → create employee profile
GET    /employees/{id}/profile           [any auth]
PATCH  /employees/{id}/profile           [self/admin]
GET    /employees/my-work                [employee]   → full workspace
GET    /employees/client-workspace       [client]     → client project view
```

### Invites (`_invite.py`)
```
POST   /invite          [admin/ceo] → TeamInviteCreate → sends invite email
GET    /my-invites      [employee]  → pending invites
POST   /accept-invite   {token}     → join team, get task assignments
POST   /reject-invite   {token}     → reject
```

### Blockers (`_blocker.py`)
```
POST   /blockers/?skip=0&limit=50  [any auth] → BlockerCreate
GET    /blockers/{id}              [any auth]
PATCH  /blockers/{id}             [admin/ceo] → update status
```

### Decisions (`_decision.py`)
```
GET    /decisions/?skip=0&limit=50  [admin/ceo] → paginated decisions
GET    /decisions/{id}              [admin/ceo]
POST   /decisions/{id}/override     [admin/ceo] → {reasoning}
```

### Meetings (`_meeting.py`)
```
POST   /meetings/?skip=0&limit=50  [admin/ceo] → MeetingCreate
GET    /meetings/{id}              [any auth]
PATCH  /meetings/{id}             [admin/ceo]
```

### Multi-Agent (`_multi_agent.py`)
```
POST   /multi-agent/run-intake            [admin/ceo] → trigger intake workflow
POST   /multi-agent/run-execution-loop    [admin/ceo] → trigger execution loop
GET    /multi-agent/workflow/{id}         [admin/ceo] → workflow + agent runs
GET    /multi-agent/agent-runs/{wf_id}    [admin/ceo] → agent run list
```

### CEO Panel (`_ceo.py`) — NEW
```
GET    /ceo/overview    [ceo/admin] → company health score, project counts, employee utilization
GET    /ceo/financials  [ceo/admin] → total budget/spent/invoiced/collected, per-project P&L, overdue payments
GET    /ceo/teams       [ceo/admin] → team utilization bars, overloaded members, top performers
GET    /ceo/clients     [ceo/admin] → all clients with payment standing, aging, risk flag
GET    /ceo/risks       [ceo/admin] → AI-surfaced risk flags with severity and deep links
```

### Platform Owner (`_owner.py`) — NEW
```
GET    /owner/tenants                         [platform_owner] → all companies with plan, usage, status
POST   /owner/tenants/{id}/suspend            [platform_owner] → {reason} → suspend + email admins
POST   /owner/tenants/{id}/activate           [platform_owner] → reactivate + email admins
GET    /owner/metrics                         [platform_owner] → MRR, active/suspended/trial counts
GET    /owner/support-tickets?status=open     [platform_owner] → all tickets across tenants
PATCH  /owner/support-tickets/{id}            [platform_owner] → {response} → resolve + email user
```

### Settings (`_settings.py`) — NEW
```
GET    /settings/me              [any auth]   → {user, preferences}
PATCH  /settings/preferences     [any auth]   → update timezone/theme/ceo_mode/etc
PATCH  /settings/profile         [any auth]   → update full_name
POST   /settings/change-password [any auth]   → {current_password, new_password}
POST   /settings/support         [any auth]   → {subject, body, priority} → SupportTicket
GET    /settings/export          [any auth]   → full GDPR data export as JSON
```

### Billing (`_billing.py`) — NEW
```
POST   /billing/subscribe                    [admin/ceo] → {plan_tier} → Stripe subscription
GET    /billing/portal                       [admin/ceo] → Stripe customer portal URL
POST   /billing/webhook                      [public]    → raw Stripe webhook handler
POST   /billing/projects/{id}/invoice        [admin/ceo] → {amount, due_date} → create invoice
POST   /billing/projects/{id}/hold           [admin/ceo] → apply payment hold (402 for client)
POST   /billing/projects/{id}/lift-hold      [admin/ceo] → restore client access
```

### Integrations (`_integrations.py`)
```
GET    /integrations/google/auth-url              [any auth] → {auth_url}  ← redirect user here
GET    /integrations/google/callback?code=&state= [public]   → OAuth exchange, stores token in UserPreferences
GET    /integrations/google/status                [any auth] → {connected, google_email, scopes}
DELETE /integrations/google/disconnect            [any auth] → wipes token, marks disconnected
POST   /integrations/google/calendar/events       [any auth] → {summary, description, start_datetime, end_datetime, attendee_emails[]}
```

### System
```
GET    /              → {"message": "AI Workforce Orchestrator Running"}
GET    /healthz       → {"status": "ok"}
GET    /docs          → Swagger UI
GET    /redoc         → ReDoc
```

---

## 8. Services — Business Logic Layer

Location: `backend_adk/app/services/`

### `_auth_service.py`
```
register_user(db, email, password, full_name, role, tenant_name, tenant_slug)
  → Creates User (email_verified=False) + generates verify token
  → Creates profile + seeds scheduler jobs
  → Sends verification email (NOT welcome email until verified)
  → Returns {user, email_verified: false}

login_user(db, email, password) → (access_token, refresh_token, user_dict)
  → Raises 401 if email_verified is False
  → Creates RefreshToken record (30-day expiry)

refresh_access_token(db, raw_refresh_token) → (new_access_token, new_refresh_token)
  → Revokes old token, issues new pair (rotation)
  → Returns None if token invalid/expired/revoked

verify_email_token(db, token) → None
  → Sets email_verified=True, clears email_verify_token

request_password_reset(db, email) → sends reset email (silent if not found)
reset_password(db, token, new_password) → validates token expiry, updates hash
change_password(db, user, current_password, new_password)

bootstrap_tenant_data(db) → ensures "default" tenant exists at startup
```

### `_project_service.py`
```
create_project(db, project: ProjectCreate, admin: User) → full AI-driven pipeline
  1. Validate no duplicate active project
  2. Resolve/create client
  3. LLMService.parse_project_intake()
  4. MultiAgentOrchestrator.run_intake_workflow()
  5. Persist Project, Tasks, Checkpoints, Dependencies, Communications
  6. Return {project, draft_team, execution_plan, risk, workflow_run_id}

get_projects(db, viewer: User) → role-filtered list (paginated at route level)
build_project_status(db, project_id, viewer) → full status object
delete_project_atomic(db, project_id, admin) → transactional cascade
update_checkpoint_status / handle_project_invite_response / reassign_project_task
update_project_payment_status(db, project_id, new_status, actor, note)
```

### `_assignment_engine.py`
```
AssignmentEngine.assign_task(db, task, reason, override)
  1. _get_available_employees(task) → filters by tenant_id, availability, capacity
  2. _calculate_employee_score(employee, task):
       score = 0.35 * skill_match
             + 0.25 * (1 - workload_ratio)
             + 0.20 * efficiency_score
             + 0.20 * reliability_score
             - timezone_penalty (0.15 if employee in night hours for urgent task)
  3. Pick best if score >= 0.5
  4. Atomic SQL UPDATE on current_load (prevents race conditions)
  5. Create TaskAssignment, DecisionLog
  6. Send task assignment email to employee
```

### `_email_service.py`
```
EmailService.send_email(to_email, subject, html_body, tenant_id, template_name) → bool
  # Logs to EmailDeliveryLog. Never raises. Returns False on failure.

send_verification_email(to_email, full_name, verify_token)  ← sent on registration
send_invite_email(to_email, inviter_name, project_name, role_title, invite_token, tenant_id)
send_welcome_email(to_email, full_name, role)
send_password_reset_email(to_email, reset_token)
send_task_assignment_email(to_email, employee_name, task_description, project_name, deadline, estimated_hours)
send_blocker_alert_email(to_email, recipient_name, task_description, blocker_description, severity, project_name)
send_escalation_alert_email(to_email, recipient_name, project_name, reason, workflow_run_id)
send_weekly_digest_email(to_email, recipient_name, digest_data)
send_payment_overdue_email(to_email, company_name, days_overdue, amount_due, portal_link)
send_suspension_warning_email(to_email, company_name, grace_period_ends)
send_suspension_email(to_email, company_name)
```

### `_ceo_service.py` — NEW
```
CEOService.get_company_overview(db, tenant_id) → {
  total_projects, projects_on_track, projects_at_risk, projects_delayed, projects_completed,
  total_employees, employees_available, employees_overloaded, total_clients,
  active_blockers, health_score (0-100)
}

get_financial_overview(db, tenant_id) → {
  total_budget, total_spent, total_invoiced, total_collected, total_outstanding,
  overdue_payments: [{client_name, project_name, amount, days_overdue}],
  per_project_pl: [{project_id, name, budget, spent, status, payment_status, profit_margin}]
}

get_team_utilization(db, tenant_id) → {
  overall_utilization_pct,
  teams: [{team_id, name, project_name, member_count, avg_utilization_pct, overloaded_members, active_blockers}],
  top_performers: [{employee_name, efficiency, reliability, tasks_completed}]
}

get_client_status(db, tenant_id) → [
  {client_id, company_name, active_projects, total_billed, total_paid, outstanding,
   payment_status, last_communication_at, risk_flag}
]

get_risk_flags(db, tenant_id) → [
  {type, severity, message, entity_type, entity_id, entity_name, action_url}
]
# Risk types: overdue_payment | delayed_project | overloaded_team | unresolved_blocker | critical_deadline
```

### `_owner_service.py` — NEW
```
OwnerService.list_tenants(db) → all companies with user counts, project counts, billing status
suspend_tenant(db, tenant_id, reason) → suspends + logs to PlatformAuditLog + emails tenant admins
activate_tenant(db, tenant_id) → reactivates + logs + emails
get_platform_metrics(db) → {total_tenants, active, suspended, trial, paid, total_users, total_projects, mrr_estimate}
list_support_tickets(db, status) → all tickets across all tenants with tenant + user info
respond_to_ticket(db, ticket_id, response) → sets status=resolved + emails the submitter
```

### `_settings_service.py` — NEW
```
SettingsService.get_preferences(db, user_id) → UserPreferences (creates with defaults if missing)
update_preferences(db, user_id, updates: dict) → validates timezone, saves
update_profile(db, user, updates: dict) → updates full_name on User
change_password(db, user, current_password, new_password) → verifies + re-hashes
submit_support_ticket(db, user, subject, body, priority) → creates SupportTicket + emails PLATFORM_OWNER_EMAIL
export_user_data(db, user) → full GDPR export dict
```

### `_stripe_service.py` — NEW
```
StripeService.create_tenant_subscription(db, tenant_id, plan_tier, admin_email, company_name)
  → Creates Stripe Customer + Subscription → stores IDs in TenantSettings

get_billing_portal_url(db, tenant_id) → Stripe Customer Portal URL

handle_stripe_webhook(payload, sig_header, db)
  invoice.paid           → unsuspend tenant, update next_billing_date
  invoice.payment_failed → set grace_period_ends_at + warn admins via email
  subscription.deleted   → suspend tenant + email admins

check_and_enforce_grace_periods(db) → auto-suspends tenants past grace period

create_project_invoice(db, project_id, amount, due_date, admin) → stores in custom_fields
apply_payment_hold(db, project_id, admin) → Project.payment_status = "disputed"
lift_payment_hold(db, project_id, admin) → restores previous payment status
```

### `_scheduler_service.py`
```
SchedulerService.run_scheduler_loop(SessionLocal) → async background task
  Polls ScheduledAgentJob every 60 minutes
  Runs due jobs:
    nightly_observer  → run_project_execution_loop() → email if health=red
    weekly_digest     → CEO aggregation → send digest to CEO + admins
    payment_check     → StripeService.check_and_enforce_grace_periods()
    archive_old_runs  → deletes completed WorkflowRun/AgentRun older than 90 days

seed_default_jobs_for_existing_tenants(db) → called at startup
seed_default_jobs_for_tenant(db, tenant_id) → called when new admin registers
```

### `_calendar_service.py`
```
get_auth_url(user_id) → str
  → Builds Google OAuth consent URL with calendar.events + userinfo scopes
  → State param encodes user_id for callback correlation

handle_callback(db, code, state) → {connected, google_email}
  → Exchanges OAuth code for credentials
  → Fetches Google account email via /userinfo
  → Stores token blob in UserPreferences.google_calendar_token

get_status(db, user_id) → {connected, google_email, scopes}

disconnect(db, user_id) → clears token blob, sets connected=False

create_calendar_event(db, user_id, event_dict) → {event_id, html_link}
  → Refreshes credentials if token expired
  → Creates event with Google Meet link (conferenceData)
  → Persists refreshed token back to UserPreferences
```

### `_multi_agent_orchestrator.py`
```
run_intake_workflow(db, request_text, project_id, requested_by_user_id)
  → Creates WorkflowRun, runs 7 agents in sequence/parallel
  → Persists AgentRun per agent, Communications, DecisionLogs
  → Agents (CommunicationAgent, EscalationAgent) now send real emails

run_project_execution_loop(db, project_id, requested_by_user_id)
  → Reads live state, runs health check, rebalances, updates, escalates
```

### `_llm_service.py`
```
parse_project_intake(request_text) → structured brief with tasks, skills, complexity
  Falls back to deterministic parsing if LLM unavailable

generate_client_update(context) → business-facing status update text
generate_stage_brief(stage, audience, context) → role-aligned brief
```

### `_invite_service.py`
```
create_team_invite(db, team, tenant_id, email, invited_by_user_id, role_title, note)
  → Creates TeamInvite with UUID token
  → Sends invite email via EmailService
  → Links to existing user if email found

apply_invite_response(db, invite, accepted, actor, note)
  → Creates TeamMember if accepted
  → Creates TaskAssignment for role-matched tasks
  → Updates EmployeeProfile.current_load
```

### Other Services
```
_event_service.py         → publish_event(), process_event_queue_batch_async()
_task_service.py          → Task CRUD, subtask tree, Checkpoint management
_decision_service.py      → DecisionLog creation, admin override, paginated reads
_monitoring_service.py    → Health checks, delay risk, workload pressure
_autopm_service.py        → AutoPM autonomous project creation (tenant-scoped)
```

---

## 9. Multi-Agent System

### Intake Workflow (7 agents)
Triggered by: `POST /projects/` or `POST /multi-agent/run-intake`

```
Request Text
    │
    ▼
[1] IntakeAgent
    Input:  request_text
    Output: parsed_brief {project_title, project_summary, complexity, tasks[]}
    Confidence: 0.85 (LLM) | 0.55 (fallback)
    │
    ▼
[2] PlanningAgent
    Input:  parsed_brief, deadline
    Output: execution_plan {tasks[], dependencies[], estimated_hours, critical_path}
    Confidence: 0.78
    │
    ├──────────────────────────────────────────────┐
    ▼                                              ▼
[3a] StaffingAgent                          [3b] RiskAgent
    Output: top 3 candidates per task           Output: risk_level, risks[], requires_escalation
    Confidence: 0.8 / 0.6 / 0.4                Confidence: 0.76 (low) | 0.62 (high)
    │                                              │
    └──────────────────────────────────────────────┘
                          │
                          ▼
               [4] ExecutionCoordinatorAgent
                   Output: autonomous_tasks[], review_required_tasks[], autonomy_level
                          │
                          ▼
               [5] CommunicationAgent
                   Output: admin_brief, employee_brief, client_brief, communications[]
                   NOW: actually sends emails via EmailService
                          │
                          ▼
               [6] EscalationAgent
                   Output: escalation_decision, requires_human_review
                   NOW: emails all admins + CEO if review required
```

### Execution Loop (5 agents)
Triggered by: task progress update → `PROJECT_EXECUTION_SIGNAL` event → scheduler or manual

```
[1] ProjectObserverAgent    → reads live DB state (confidence: 1.0)
[2] DeliveryReviewAgent     → health: green/yellow/red, intervention_needs
[3] RebalanceAgent          → reassignment recommendations via AssignmentEngine
[4] LoopCommunicationAgent  → stakeholder update messages
[5] LoopEscalationAgent     → can_continue_autonomous, escalation_needed
```

### Assignment Engine Scoring Formula
```
score = 0.35 × skill_match_avg
      + 0.25 × (1 − current_load / max_capacity)
      + 0.20 × efficiency_score
      + 0.20 × reliability_score
      − 0.15  [timezone penalty if employee in 22:00–07:00 local time and task is urgent]

Minimum accepted score: 0.5
Overload threshold: current_load ≥ 0.9 × max_capacity → excluded
```

### Skill Match — Declared vs Demonstrated Blending
```
skill_match per skill = 1 − |blended_level − required_level|

blended_level:
  - If both declared and demonstrated exist: 0.70 × declared + 0.30 × demonstrated
  - If only demonstrated: demonstrated score
  - If only declared: declared score

Demonstrated skill update (on task completion):
  new_score = 0.80 × old_score + 0.20 × (task_required_level + difficulty_boost)
  difficulty_boost: easy=0.0, medium=0.05, hard=0.10
  Stored in employee_profiles.demonstrated_skills (JSON)
```

---

## 10. Frontend Components

### Routing (App.jsx)
```
Login / Register           → unauthenticated state
/dashboard                 → Dashboard.jsx (role-based)
/ceo                       → CEODashboard.jsx  [role=ceo only]
/owner                     → OwnerPanel.jsx    [role=platform_owner only]
/projects                  → Projects.jsx
/employees                 → EmployeeView.jsx
/task/{id}                 → TaskDetail.jsx
/decisions                 → Decisions.jsx
/multi-agent               → MultiAgentWorkbench.jsx [role=admin only]
/settings                  → Settings.jsx
```

**Auto-routing on login:**
- `platform_owner` → always lands on `/owner`
- `ceo` → always lands on `/ceo`
- Others → `UserPreferences.default_landing_page`

**On login, App.jsx fetches `GET /settings/me` to:**
- Load `userTimezone` into state (passed to all components)
- Apply saved theme
- Apply role-based routing

### CEODashboard.jsx — NEW
- Business View (default): KPI cards (health score, projects, utilization, outstanding payments), risk flags panel, client status table, team utilization bars, financial P&L table
- Technical View (ceo_mode=true): renders Admin UI
- Toggle button visible only to CEO role

### OwnerPanel.jsx — NEW
- Tenant table: company name, plan, users, projects, status badge (green/yellow/red), next billing, suspend/activate buttons
- Support ticket inbox: tabbed (Open / In Progress / Resolved), expandable tickets with response form

### Settings.jsx — NEW
Tabbed layout:
- **Profile**: full name, email (read-only), role badge, timezone dropdown, Save → `PATCH /settings/profile`
- **Preferences**: theme toggle, language, default page, CEO mode toggle (ceo only), notification toggles, Save → `PATCH /settings/preferences`
- **Security**: change password form (current + new + confirm)
- **Support**: priority + subject + body → `POST /settings/support`
- **Data & Privacy**: Export button → `GET /settings/export`, Delete account

### Navbar.jsx (updated)
- Avatar dropdown (top-right): Settings link, Support shortcut, Logout

### Projects.jsx (updated)
- Handles paginated API response `{items, total, skip, limit}` from `GET /projects/`
- Payment hold button: `POST /billing/projects/{id}/hold`
- Payment hold lift: `POST /billing/projects/{id}/lift-hold`

### config.js (updated)
```javascript
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'https://orchestrator-backend-yo2mex5f2a-ew.a.run.app';

export function formatDateInUserTimezone(isoString, timezone) {
    if (!isoString) return "—";
    const tz = timezone || Intl.DateTimeFormat().resolvedOptions().timeZone;
    return new Intl.DateTimeFormat("en-GB", {
        timeZone: tz,
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit"
    }).format(new Date(isoString));
}
```

---

## 11. Environment Variables

Set in Cloud Run service configuration. For local dev, put in `backend_adk/.env`.

### Required in Production
| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | JWT signing key — hard-fails at startup if insecure |
| `DATABASE_URL` | PostgreSQL connection string |
| `SENDGRID_API_KEY` | SendGrid API key for all transactional email |
| `EMAIL_FROM` | From address (e.g. `no-reply@yourdomain.com`) |
| `PLATFORM_OWNER_EMAIL` | Your email — receives support tickets |
| `STRIPE_SECRET_KEY` | Stripe secret key for billing |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `FRONTEND_URL` | Full URL of frontend (used in email links) |
| `ALLOWED_ORIGINS` | Comma-separated frontend origins (no wildcard in prod) |
| `ENVIRONMENT` | Set to `production` to enable hard-fail on insecure secrets |

### Optional / Defaulted
| Variable | Default | Description |
|----------|---------|-------------|
| `EMAIL_FROM_NAME` | `AI Workforce Orchestrator` | Sender display name |
| `STRIPE_STARTER_PRICE_ID` | `""` | Stripe Price ID for Starter plan |
| `STRIPE_GROWTH_PRICE_ID` | `""` | Stripe Price ID for Growth plan |
| `STRIPE_ENTERPRISE_PRICE_ID` | `""` | Stripe Price ID for Enterprise plan |
| `STRIPE_CONNECT_CLIENT_ID` | `""` | For Stripe Connect (company→client billing) |
| `GRACE_PERIOD_DAYS` | `7` | Days before suspension after payment failure |
| `REDIS_URL` | `""` | Redis connection URL — enables distributed rate limiting across Cloud Run instances |
| `GOOGLE_CLIENT_ID` | `""` | Google OAuth client ID for Calendar integration |
| `GOOGLE_CLIENT_SECRET` | `""` | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | `http://localhost:5173/integrations/google/callback` | Must match Google Cloud Console redirect URI |
| `BASIC_RATE_LIMIT_REQUESTS` | `120` | Requests per window per IP |
| `BASIC_RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window |
| `HUGGINGFACEHUB_API_TOKEN` | `""` | HF token for LLM (fallback if absent) |
| `HF_MODEL_ID` | `mistralai/Mistral-7B-Instruct-v0.3` | LLM model |
| `HF_TEMPERATURE` | `0.3` | LLM temperature |
| `HF_MAX_NEW_TOKENS` | `1024` | LLM max output |
| `HF_TIMEOUT_SECONDS` | `60` | LLM request timeout |
| `LOG_DIR` | `./logs` | Log file directory |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_MAX_BYTES` | `10485760` | Log file rotation size (10MB) |
| `LOG_BACKUP_COUNT` | `5` | Number of rotated log files |

### Cloud SQL (Production)
```
DATABASE_URL=postgresql://orchestrator_user:<password>@/orchestrator?host=/cloudsql/havoc-ai-prod:europe-west1:orchestrator-sql
```

### Deployed URLs
```
GCP Project:    havoc-ai-prod
Region:         europe-west1
Backend URL:    https://orchestrator-backend-yo2mex5f2a-ew.a.run.app
Frontend URL:   https://orchestrator-frontend-974381609416.europe-west1.run.app
API Docs:       https://orchestrator-backend-yo2mex5f2a-ew.a.run.app/docs
Cloud SQL:      havoc-ai-prod:europe-west1:orchestrator-sql
DB Name:        orchestrator
DB User:        orchestrator_user
```

---

## 12. Email System (SendGrid)

### Overview
All email goes through `EmailService` in `backend_adk/app/services/_email_service.py`. It uses the SendGrid Python SDK. Every send attempt (success or failure) is logged to `EmailDeliveryLog`. Email failures **never crash** the calling code — they return `False` and log silently.

### Templates (HTML, inline in service)

| Template Name | Triggered By | Recipient |
|--------------|-------------|-----------|
| `email_verification` | User registration | New user (must click to activate account) |
| `welcome` | (reserved for post-verify flow) | Verified user |
| `invite` | Team invite created | Invited employee |
| `password_reset` | `POST /auth/forgot-password` | User |
| `task_assignment` | AssignmentEngine assigns task | Employee |
| `blocker_alert` | `POST /tasks/{id}/blockers` | Admin + assigned employees |
| `escalation_alert` | EscalationAgent fires | All admins + CEO |
| `weekly_digest` | Monday 9am scheduler job | CEO + all admins |
| `payment_overdue` | payment_check scheduler job | Tenant admins |
| `suspension_warning` | invoice.payment_failed webhook | Tenant admins |
| `suspension` | Grace period expired | Tenant admins |

### Email Verification Link Format
```
{FRONTEND_URL}/verify-email?token={UUID}
# No expiry — one-time use (token cleared on verification)
```

### Accept Invite Link Format
```
{FRONTEND_URL}/accept-invite?token={UUID}
```

### Password Reset Link Format
```
{FRONTEND_URL}/reset-password?token={UUID}
# Token valid for 1 hour
```

---

## 13. Billing & Payments (Stripe)

### Two-Layer Model

```
Layer 1: YOU ← company subscription via Stripe
  You charge Company A $X/month for platform access
  Stripe manages recurring billing
  Failed payment → grace period → auto-suspend

Layer 2: Company ← client project payment
  Company admin creates an invoice for the client
  Client pays (via Stripe Connect if connected, or tracked manually)
  Admin can apply payment hold if client doesn't pay
  Client gets 402 on project status while on hold
```

### Plan Tiers
| Tier | Max Users | Max Projects | Max AI Calls/mo |
|------|-----------|-------------|----------------|
| trial | 10 | 5 | 100 |
| starter | (set by Stripe product) | — | — |
| growth | (set by Stripe product) | — | — |
| enterprise | (set by Stripe product) | — | — |

### Stripe Webhook Events Handled
```
invoice.paid                  → reactivate tenant, update next_billing_date
invoice.payment_failed        → set grace_period_ends_at, warn admins by email
customer.subscription.deleted → suspend tenant immediately, email admins
```

### Webhook URL (must register in Stripe dashboard)
```
https://backend-adk-974381609416.europe-west1.run.app/billing/webhook
```

### Suspension Flow
```
invoice.payment_failed
  ↓
grace_period_ends_at = now + GRACE_PERIOD_DAYS
EmailService.send_suspension_warning_email() to all tenant admins
  ↓
Daily payment_check job runs
  ↓
If grace_period_ends_at < now AND suspended = False:
  TenantSettings.suspended = True
  EmailService.send_suspension_email() to all tenant admins
  ↓
All API calls for that tenant → 402 Payment Required
(except /auth/* and /owner/*)
```

---

## 14. Background Scheduler

### How it works
`SchedulerService.run_scheduler_loop()` starts as an asyncio background task in the FastAPI lifespan. It wakes up every 60 minutes, queries `ScheduledAgentJob` for due jobs, runs them, updates `last_run_at` and `next_run_at`.

### Default Jobs Created Per Tenant
| Job Type | Cron | What it does |
|----------|------|-------------|
| `nightly_observer` | `0 2 * * *` (2am UTC) | Runs execution loop per project, emails if health=red |
| `weekly_digest` | `0 9 * * 1` (Mon 9am UTC) | Compiles CEO/admin digest, sends via email |
| `payment_check` | `0 0 * * *` (midnight UTC) | Enforces grace period expirations |
| `archive_old_runs` | `0 3 * * 0` (Sun 3am UTC) | Purges all log tables: workflow_runs/agent_runs (90d), decision_logs/audit_log (90d), email_delivery_logs (60d), platform_audit_logs (180d) |

Jobs are seeded at startup (`seed_default_jobs_for_existing_tenants`) and when a new admin registers (`seed_default_jobs_for_tenant`). One `nightly_observer` job is created per project at project creation.

---

## 15. Authentication & Security

### JWT Access Token
```
Payload: {user_id, tenant_id, email, exp, iat}
Algorithm: HS256
Expiry: 60 minutes
Signing key: SECRET_KEY env var (hard-fails if insecure in production)
```

### Refresh Token
```
Format: 48-byte URL-safe random string (not a JWT)
Storage: refresh_tokens table (per-user, indexed)
Expiry: 30 days
Rotation: every use issues a new pair and revokes the old token
```

### Email Verification
```
New users: email_verified=False, email_verify_token=UUID sent to inbox
Login blocked: if email_verified is False → 401 "Please verify your email"
Existing rows: schema migration sets email_verified=1 (backward compat)
Verification: GET /auth/verify-email?token={UUID} → sets verified=True
```

### 2FA / TOTP
```
Setup: POST /auth/2fa/setup → returns base32 secret + provisioning URI (scan with authenticator app)
Enable: POST /auth/2fa/enable {totp_code} → verifies code, sets totp_enabled=True
Verify window: ±30 seconds (valid_window=1)
Disable: POST /auth/2fa/disable {totp_code} → requires valid code to disable
Library: pyotp (RFC 6238 TOTP)
```

### Middleware Stack (order in main.py)
```
1. SecurityHeadersMiddleware   → adds X-Frame-Options, X-Content-Type-Options, etc.
2. TenantMiddleware            → extracts tenant_id from JWT, checks suspension
3. RateLimitMiddleware         → Redis sliding-window (if REDIS_URL set) or in-memory per IP
4. CORSMiddleware              → ALLOWED_ORIGINS env var (never * in prod)
5. Log Requests middleware     → logs all HTTP in/out with timing
```

### Rate Limiting — Redis vs In-Memory
```
If REDIS_URL is set:
  → Uses Redis sorted-set sliding window (ZADD + ZREMRANGEBYSCORE + ZCARD in a pipeline)
  → Count is shared across all Cloud Run instances → true per-IP global limit

If REDIS_URL is empty (default):
  → Falls back to in-memory deque per process
  → Each Cloud Run instance has its own counter (effective limit = N × config)
  → Acceptable for development; use Redis in production

Auth endpoints (/auth/*, /accept-invite): limit capped at min(configured, 30) requests/window
```

### Soft Deletes
```
Models with soft delete: User, Project, Task, EmployeeProfile
Column: deleted_at DateTime nullable (NULL = active, set = deleted)
List queries: all filter deleted_at IS NULL automatically
Single-fetch: 404 if deleted_at is set
Schema migration: existing rows get deleted_at = NULL (no change to live data)
Recovery: set deleted_at = NULL in DB directly (no API endpoint for undelete yet)
```

### Security Headers Added
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: geolocation=(), microphone=(), camera=()
```

### Tenant Suspension Gate (TenantMiddleware)
```
If TenantSettings.suspended == True for this tenant:
  Return 402 Payment Required
  EXCEPT: /auth/* and /owner/* pass through always
  EXCEPT: platform_owner role bypasses suspension check entirely
```

### Auth Dependencies
```python
get_current_user()          → validates JWT, returns User, enforces tenant match
require_admin()             → role must be "admin"
require_ceo_or_admin()      → role must be "ceo" | "admin" | "platform_owner"
require_platform_owner()    → role must be "platform_owner"
```

### Tenant Safety Rule
Every query on a tenant-scoped model must filter:
```python
db.query(Model).filter(Model.tenant_id == current_user.tenant_id, ...)
```
Exception: `platform_owner` routes intentionally cross tenants. These are the only routes where `tenant_id` filter is omitted.

---

## 16. Data Flow Chains

### A. New Company Onboarding
```
Admin registers (role=admin, tenant_slug=new-company)
  → Creates Tenant + User (email_verified=False) + EmployeeProfile
  → Generates email_verify_token (UUID)
  → Seeds ScheduledAgentJob (weekly_digest, payment_check, archive_old_runs)
  → Sends verification email with link: {FRONTEND_URL}/verify-email?token=...
  → Login blocked until admin clicks the link

Admin clicks verification link → GET /auth/verify-email?token=...
  → email_verified=True, email_verify_token cleared
  → Admin can now log in
  → Receives access_token + refresh_token on first login
Admin creates subscription: POST /billing/subscribe {plan_tier: "starter"}
  → Stripe Customer + Subscription created
  → TenantSettings.stripe_customer_id populated
```

### B. Project Creation (Full AI Pipeline)
```
Admin → POST /projects/ {name, description, deadline, client_email}
  → _project_service.create_project()
  → LLMService.parse_project_intake(description) → structured brief
  → MultiAgentOrchestrator.run_intake_workflow()
      IntakeAgent → parsed_brief confirmed
      PlanningAgent → tasks, dependencies, hours
      StaffingAgent → top 3 employees per task (scored by skill/workload/efficiency/reliability/timezone)
      RiskAgent → risk_level, risks[]
      ExecutionCoordinatorAgent → autonomous vs review tasks
      CommunicationAgent → drafts briefs → sends admin_brief to admin, client_brief to client via email
      EscalationAgent → if high risk → emails all admins + CEO
  → Persists: Project, Task[], Checkpoint[], TaskDependency[], WorkflowRun, AgentRun[], Communication[], DecisionLog[]
  → Returns: {project, draft_team, execution_plan, risk, workflow_run_id}
```

### C. Team Invite → Employee Onboarding
```
Admin → POST /invite {email, role_title}
  → InviteService.create_team_invite()
  → EmailService.send_invite_email() → real email with accept link
Employee clicks link → POST /accept-invite {token}
  → InviteService.apply_invite_response(accepted=True)
  → Creates TeamMember, TaskAssignment for role-matching tasks
  → Updates EmployeeProfile.current_load
  → Returns accepted invite
```

### D. Task Progress → Execution Loop
```
Employee → PATCH /task-progress/{task_id} {completion_percentage: 100}
  → Updates TaskProgress
  → If 100%: TaskAssignment.status = completed, current_load decremented, PerformancePoint awarded
  → EventService.publish_event("PROJECT_EXECUTION_SIGNAL", ...)
  → BackgroundTasks: process_event_queue_batch_async()
  → MultiAgentOrchestrator.run_project_execution_loop(project_id)
      ProjectObserverAgent → live snapshot
      DeliveryReviewAgent → health: green/yellow/red
      RebalanceAgent → reassignment proposals
      LoopCommunicationAgent → update messages
      LoopEscalationAgent → if health=red → email alerts
```

### E. Stripe Payment Failure → Auto-Suspend
```
Stripe → POST /billing/webhook (invoice.payment_failed)
  → StripeService.handle_stripe_webhook()
  → TenantSettings.grace_period_ends_at = now + 7 days
  → EmailService.send_suspension_warning_email() to all tenant admins

Daily scheduler job (payment_check) runs:
  → StripeService.check_and_enforce_grace_periods()
  → TenantSettings.suspended = True for expired graces
  → EmailService.send_suspension_email() to all tenant admins

All subsequent API calls for that tenant:
  → TenantMiddleware returns 402 Payment Required
```

### F. CEO Weekly Digest
```
Monday 9am UTC (scheduler job "weekly_digest"):
  → CEOService.get_company_overview(tenant_id)
  → CEOService.get_financial_overview(tenant_id)
  → CEOService.get_risk_flags(tenant_id)
  → Build digest_data dict
  → Find all users with role=ceo or role=admin in tenant
  → EmailService.send_weekly_digest_email() to each
```

---

## 17. Deployment Guide

### Live URLs (production)
```
Frontend:    https://orchestrator-frontend-974381609416.europe-west1.run.app
Backend:     https://orchestrator-backend-yo2mex5f2a-ew.a.run.app
API Docs:    https://orchestrator-backend-yo2mex5f2a-ew.a.run.app/docs
GCP project: havoc-ai-prod
Billing:     01E336-987ED9-6B9D22
```

### Deploy from Cloud Shell (manual)
```bash
# Clone if needed
git clone https://github.com/Swaraj-sj2000/adk-workflow-orchestrator.git agentic_orchestrator
cd agentic_orchestrator && git pull origin main

# Backend (--source handles build + Artifact Registry push automatically)
cd backend_adk
gcloud run deploy orchestrator-backend \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --add-cloudsql-instances havoc-ai-prod:europe-west1:orchestrator-sql \
  --set-env-vars "LOG_TO_STDOUT=true,GOOGLE_CLOUD_LOCATION=europe-west1,GOOGLE_GENAI_USE_VERTEXAI=true,GOOGLE_CLOUD_PROJECT=havoc-ai-prod" \
  --set-secrets "SECRET_KEY=backend-secret-key:latest,DATABASE_URL=database-url:latest"
# NOTE: ignore the "Service URL" printed above — get the real URL:
echo "Backend: $(gcloud run services describe orchestrator-backend --region europe-west1 --format 'value(status.url)')"

# Frontend (production URL baked into Dockerfile ARG — no extra flags needed)
cd ../frontend
gcloud run deploy orchestrator-frontend \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated
# NOTE: ignore the "Service URL" printed above — get the real URL:
echo "Frontend: $(gcloud run services describe orchestrator-frontend --region europe-west1 --format 'value(status.url)')"
```

### Schema migrations
No manual steps. On startup:
- `ensure_runtime_schema(engine)` adds missing columns (additive, dialect-aware)
- `Base.metadata.create_all(engine)` creates any missing tables
Both are safe to run on every deploy against an existing database.

### Cloud Run env vars (backend)
```
SECRET_KEY                   <64-char random key — stored in Secret Manager>
DATABASE_URL                 postgresql://orchestrator_user:<pwd>@/orchestrator?host=/cloudsql/havoc-ai-prod:europe-west1:orchestrator-sql
ENVIRONMENT                  production
SENDGRID_API_KEY             <sendgrid key>
EMAIL_FROM                   no-reply@yourdomain.com
EMAIL_FROM_NAME              AI Workforce Orchestrator
FRONTEND_URL                 https://orchestrator-frontend-974381609416.europe-west1.run.app
PLATFORM_OWNER_EMAIL         <owner email>
STRIPE_SECRET_KEY            <stripe secret>
STRIPE_WEBHOOK_SECRET        <webhook secret>
STRIPE_STARTER_PRICE_ID      <price_id>
STRIPE_GROWTH_PRICE_ID       <price_id>
STRIPE_ENTERPRISE_PRICE_ID   <price_id>
ALLOWED_ORIGINS              https://orchestrator-frontend-974381609416.europe-west1.run.app
GOOGLE_CLOUD_PROJECT         havoc-ai-prod
GOOGLE_CLOUD_LOCATION        us-central1
GOOGLE_GENAI_USE_VERTEXAI    true
GRACE_PERIOD_DAYS            7
GOOGLE_CLIENT_ID             <oauth client id>
GOOGLE_CLIENT_SECRET         <oauth client secret>
GOOGLE_REDIRECT_URI          https://orchestrator-frontend-974381609416.europe-west1.run.app/integrations/google/callback
```

### Docker Images
```
Backend:  python:3.11-slim → pip install requirements.txt → uvicorn on port 8080
Frontend: node:18 → npm run build → nginx:alpine serve on port 8080
```

### Stripe Webhook
```
URL: {backend-url}/billing/webhook
Events: invoice.paid, invoice.payment_failed, customer.subscription.deleted
```

---

## 18. Local Development Setup & Testing

Two seed scripts exist. Use the right one for your target:

| Script | Target | DB | GCP required |
|--------|--------|----|--------------|
| `backend_adk/seed_test_data.py --local` | Local dev of ADK backend | SQLite | No |
| `backend_adk/seed_test_data.py` | Cloud SQL (production) | PostgreSQL | Yes |
| `backend/seed_test_data.py` | Local dev of backend mirror | SQLite | No |

---

### Step 1 — Set up the ADK backend locally

```bash
cd backend_adk
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create `.env`:
```
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=local-dev-secret-key-change-in-prod
SENDGRID_API_KEY=
EMAIL_FROM=no-reply@localhost
FRONTEND_URL=http://localhost:5173
PLATFORM_OWNER_EMAIL=swaraj@orchestrator.ai
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
ENVIRONMENT=development
```

### Step 2 — Seed the local database

```bash
# Drop + recreate SQLite, seed all roles, projects, agents, billing records
python seed_test_data.py --local
```

Output prints every credential, a live TOTP code for the CEO, and the admin's 30-day refresh token.

### Step 3 — Start the API server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
# Docs: http://localhost:8001/docs
# Health: http://localhost:8001/healthz
```

### Step 4 — Start the frontend

```bash
cd frontend
npm install
VITE_API_URL=http://localhost:8001 npm run dev
# UI: http://localhost:5173
```

### Step 5 — Run the automated test suite

```bash
cd backend_adk
pytest tests/ -v
```

Tests use in-memory SQLite with scoped transaction rollback — they never touch `app.db`.

---

### Testing checklist (manual via Swagger at /docs)

#### Auth layer
- [ ] `POST /auth/register` — register new admin with a `tenant_name`
- [ ] `GET /auth/verify-email?token=` — paste token from seed output (or DB)
- [ ] `POST /auth/login` — returns `{access_token, refresh_token, user}`
- [ ] `POST /auth/refresh` — rotate refresh token, get new pair
- [ ] `POST /auth/forgot-password` → `POST /auth/reset-password`

#### 2FA (CEO account)
- [ ] `POST /auth/login` with CEO creds → returns `{requires_2fa: true, mfa_session_token}`
- [ ] `POST /auth/2fa/verify-login` with `{mfa_session_token, totp_code}` → returns full tokens
- [ ] `POST /auth/2fa/setup` (logged-in user) → get secret + provisioning URI
- [ ] `POST /auth/2fa/enable` with live TOTP code
- [ ] `POST /auth/2fa/disable` with TOTP code

#### Security gate — self-registration block
- [ ] `POST /auth/register` with `role=platform_owner` → must return `403`

#### Tenant isolation
- [ ] Login as GlobalTech admin → `GET /projects` → empty list (cannot see OrchestrateCo data)

#### Projects & tasks
- [ ] `GET /projects` — returns only active (non-deleted) projects for the tenant
- [ ] `GET /tasks?project_id=1` — deleted task must NOT appear
- [ ] `DELETE /tasks/{id}` — soft-deletes; task disappears from list but exists in DB

#### CEO dashboard (login as CEO)
- [ ] `GET /ceo/overview` — KPI cards, health score
- [ ] `GET /ceo/financials` — P&L per project
- [ ] `GET /ceo/teams` — utilisation bars
- [ ] `GET /ceo/clients` — payment standing
- [ ] `GET /ceo/risks` — AI risk flags

#### Platform Owner (login as platform_owner)
- [ ] `GET /owner/tenants` — both OrchestrateCo and GlobalTech visible
- [ ] `POST /owner/tenants/{id}/suspend` → all that tenant's API calls return 402
- [ ] `POST /owner/tenants/{id}/activate` → tenant restored

#### Billing
- [ ] `GET /settings/me` — billing status visible
- [ ] GlobalTech tenant is in grace period — observe `grace_period_ends_at` in TenantSettings

#### Integrations
- [ ] `GET /integrations/google/status` (CEO) → `{connected: true, google_email: "priya.sharma@gmail.com"}`

#### Settings
- [ ] `GET /settings/me` — returns preferences, timezone, theme
- [ ] `PATCH /settings/me` — update timezone, theme
- [ ] `POST /settings/support` — submit support ticket

#### Agents & workflows
- [ ] `GET /multi-agent/workflow-runs` — intake workflow visible with 7 agent runs
- [ ] `GET /decisions` — DecisionLog from StaffingAgent visible

---

### Seed scripts — flags reference

```bash
# backend_adk (production + local)
python seed_test_data.py --local     # local SQLite, drop+recreate, no GCP needed
python seed_test_data.py --check     # production pre-flight only (Vertex AI ping)
python seed_test_data.py             # production seed (requires DATABASE_URL + GCP vars)
python seed_test_data.py --reset     # DESTRUCTIVE — wipe Cloud SQL + reseed

# backend (local mirror)
cd backend && python seed_test_data.py   # always drops + recreates SQLite
```

---

### When local tests pass — push to production

```bash
# From the repo root
git checkout main
git merge feature/secure-multitenant-refactor

cd backend_adk
bash deploy_cloud_run.sh
```

Then seed the production Cloud SQL database (via Cloud SQL Auth Proxy or Cloud Run Job — see `seed_test_data.py` header).

---

## 19. Seed Credentials

Run `seed_test_data.py` (production via Cloud SQL Auth Proxy) to populate all 4 tenants.
All employees share password `team123456`. All clients share `client123456`.
2FA is disabled platform-wide for demo. `/auth/2fa/*` endpoints remain for future use.

### Platform Owner
| Role | Email | Password |
|------|-------|----------|
| Platform Owner | `swaraj@orchestrator.ai` | `OwnerSecure#99` |

---

### Tenant 1 — TechNova Solutions (`technova`)
| Role | Email | Password |
|------|-------|----------|
| CEO | `priya.sharma@technova.ai` | `CEO_Secure#88` |
| Admin — Engineering | `rohan.mehta@technova.ai` | `Admin#Rohan77` |
| Admin — Product & AI | `kavya.nair@technova.ai` | `Admin#Kavya77` |
| Admin — Operations | `aditya.singh@technova.ai` | `Admin#Adity77` |
| Admin — People & HR | `shruti.bose@technova.ai` | `Admin#Shrut77` |
| Employees (20+) | `amira.khan@technova.ai`, `arjun.rao@technova.ai`, `neha.gupta@technova.ai`, `yash.patel@technova.ai`, `dev.sharma@technova.ai`, … | `team123456` |
| Client | `contact@globalcorp.com` | `client123456` | GlobalCorp Pte Ltd |
| Client | `partner@fintech360.io` | `client123456` | FinTech360 Inc |

### Tenant 2 — DataSphere Analytics (`datasphere`)
| Role | Email | Password |
|------|-------|----------|
| CEO | `alex.turner@datasphere.io` | `CEO_Secure#DS88` |
| Admin — Data Engineering | `marcus.chen@datasphere.io` | `Admin#Marc77` |
| Admin — Analytics & BI | `zara.ahmed@datasphere.io` | `Admin#Zara77` |
| Admin — Infrastructure | `ryan.park@datasphere.io` | `Admin#Ryan77` |
| Admin — Research & AI | `hannah.lee@datasphere.io` | `Admin#Hann77` |
| Employees (20+) | `david.kim@datasphere.io`, … | `team123456` |
| Client | `cto@investedge.com` | `client123456` | InvestEdge Capital |
| Client | `data@supplypro.co` | `client123456` | SupplyPro Logistics |

### Tenant 3 — BuildRight Engineering (`buildright`)
| Role | Email | Password |
|------|-------|----------|
| CEO | `james.obrien@buildright.co` | `CEO_Secure#BR88` |
| Admin — Project Delivery | `lisa.chen@buildright.co` | `Admin#Lisa77` |
| Admin — Engineering | `sanjay.kumar@buildright.co` | `Admin#Sanj77` |
| Admin — Quality Assurance | `maya.torres@buildright.co` | `Admin#Maya77` |
| Admin — Finance & Ops | `derek.walsh@buildright.co` | `Admin#Dere77` |
| Employees (20+) | `thomas.wright@buildright.co`, … | `team123456` |
| Client | `ops@citygrid.co.uk` | `client123456` | CityGrid Infrastructure |
| Client | `tech@thameswater.io` | `client123456` | Thames Digital Water |

### Tenant 4 — HealthSync Medical (`healthsync`)
| Role | Email | Password |
|------|-------|----------|
| CEO | `sarah.kim@healthsync.sg` | `CEO_Secure#HS88` |
| Admin — Engineering | `tom.reddy@healthsync.sg` | `Admin#TomR77` |
| Admin — Clinical Product | `ananya.menon@healthsync.sg` | `Admin#Anan77` |
| Admin — Data & AI | `chris.lawson@healthsync.sg` | `Admin#Chri77` |
| Admin — Operations | `nina.patel@healthsync.sg` | `Admin#Nina77` |
| Employees (20+) | `priyanka.s@healthsync.sg`, … | `team123456` |
| Client | `digital@nuh.sg` | `client123456` | NUH Digital Health |
| Client | `tech@farmacare.sg` | `client123456` | FarmaCare Asia |

### Seeded data summary

| Entity | Count |
|--------|-------|
| Tenants | 4 |
| Users | ~100 (4 CEOs + 16 admins + ~80 employees + 8 clients + 1 platform owner) |
| Agents | 11 (Intake + Execution loop) |
| Department Teams | 16 (4 per tenant, org-pool) |

---

## 20. Implementation History

### Phase 0 — Foundation (pre-7-day sprint)
- Initial FastAPI backend with SQLAlchemy models
- Basic auth (JWT + bcrypt)
- Project creation, task management, team invites
- Multi-agent orchestration (intake + execution loop)
- LLM integration (HuggingFace Mistral)
- Assignment engine with skill/workload/efficiency/reliability scoring
- React frontend (Dashboard, Projects, EmployeeView, TaskDetail, Decisions, MultiAgentWorkbench)

### Security Hardening (feature/secure-multitenant-refactor)
- Removed hardcoded JWT fallback and debug token-echo route
- CORS driven by env var (`ALLOWED_ORIGINS`), no wildcard in prod
- Removed `X-Tenant-ID` header spoofing vector
- Tenant-scoped all reads: meetings, workflows, task assignments, decision logs
- Atomic `current_load` UPDATE to prevent race conditions
- Employee candidate filtering by `task.tenant_id` (cross-tenant assignment prevention)
- `autopm_service` now passes `tenant_id` when creating autonomous projects

### 7-Day Platform Upgrade (all on feature/secure-multitenant-refactor)

| Day | Commits | What shipped |
|-----|---------|-------------|
| 1 | `3e6b4e0` `712ee51` `43a4479` | 6 new models, SendGrid email service, new roles, password reset |
| 2 | `fc430eb` | CEO analytics backend (5 endpoints, aggregation queries) |
| 3 | `8bc6da0` | Platform owner panel, suspension middleware, PlatformAuditLog |
| 4 | `29146b1` | Settings API (preferences, profile, password change, support, export) |
| 5 | `8b1dd59` | Stripe billing (subscriptions, webhooks, payment hold/lift) |
| 6 | `e1dac30` | Agents send real emails, scheduler with nightly/weekly/payment jobs |
| 7 | `7baffeb` `46b079f` | Timezone scoring, security headers, pagination, CEODashboard, OwnerPanel, Settings frontend |

### Phase 11 — Production Gap Closure (`c2982de`)

| Gap | What was built |
|-----|---------------|
| JWT refresh tokens | `RefreshToken` model, `/auth/refresh` with rotation, login returns both tokens |
| Email verification | `email_verified` column (existing rows default to verified), `/auth/verify-email`, blocks login until verified |
| 2FA / TOTP | `totp_secret`/`totp_enabled` on User, `/auth/2fa/setup\|enable\|disable` via pyotp |
| Redis rate limiting | `RateLimitMiddleware` uses Redis sorted-set sliding window when `REDIS_URL` set, falls back to in-memory |
| Soft deletes | `deleted_at` on User/Project/Task/EmployeeProfile; list queries filter; `delete_project_atomic` soft-deletes; `DELETE /tasks/{id}` added |
| Archival cleanup | `archive_old_runs` scheduler job — Sunday 3am, purges completed workflow/agent runs >90 days |
| Google Calendar OAuth | Full flow: auth URL → callback → token → create events; `/integrations/google/*`; `google_calendar_*` on UserPreferences |
| Email template | `send_verification_email` added; sent on registration instead of welcome |
| Test suite | `conftest.py` with in-memory SQLite; `test_auth`, `test_billing`, `test_assignment` covering 20+ scenarios |
| Schema migrations | All new columns added via `ensure_runtime_schema` (backward compat for existing DBs) |

### Phase 12 — Platform Intelligence Suite (`67f63b4`→`72cb644`)

| Feature | What was built |
|---------|---------------|
| Skill Growth Tracking | `demonstrated_skills` JSON on `EmployeeProfile`; `_skill_service.py` applies EMA on task completion; `AssignmentEngine` blends declared (70%) + demonstrated (30%) skills |
| Natural Language Queries | `POST /assistant/nl-query` — admin/CEO asks live DB questions; gathers team capacity, project status, task counts, blockers; LLM answer with structured fallback |
| Proof of Work | `proof_note` + `proof_url` columns on `task_progress` (additive migration); `PUT /task-progress/{id}/proof` for employees; `DeliveryReviewAgent` reads proof items in assessment |
| Client Change Requests | `ChangeRequest` model + `change_requests` table; `POST/GET/PATCH /projects/{id}/change-requests`; clients raise requests, admins approve/reject/implement |
| Predictive Delivery Forecast | `GET /projects/{id}/delivery-forecast` — velocity (tasks/day), ETA, budget burn %, risk score 0–100 with specific risk reasons + LLM narrative |
| Scope Change Handling | `POST /projects/{id}/scope-change` — LLM diffs new brief vs existing tasks, generates change order document, saved as `ChangeRequest` with `change_order_doc` |
| Markdown rendering | `Markdown.jsx` zero-dependency component; all LLM text in Dashboard, Projects, MultiAgentWorkbench now renders as formatted bullets/headings instead of raw `**markdown**` |
| Extended log purge | `archive_old_runs` now covers all 5 log tables: workflow_runs (90d), decision_logs (90d), audit_log (90d), email_delivery_logs (60d), platform_audit_logs (180d) |
| PostgreSQL schema fix | `ensure_runtime_schema` is fully dialect-aware: TIMESTAMP vs DATETIME, BOOLEAN vs INTEGER, `information_schema` vs PRAGMA for NOT NULL drops |
| Cloud Run deployment | Deployed to `europe-west1` via Cloud Build; billing switched to account `01E336-987ED9-6B9D22`; Artifact Registry repository created |

---

## 21. Troubleshooting

### App won't start in production
```
[FATAL] SECRET_KEY is set to a known insecure default
```
→ Set `SECRET_KEY` to a strong random string in Cloud Run env vars.
Set `ENVIRONMENT=production` to enable hard-fail.

### Emails not sending
- Check `SENDGRID_API_KEY` is set
- Check `email_delivery_logs` table: `status="failed"` rows have `error_message`
- Email failures never crash the app — check logs for `Email send failed`
- Verify `EMAIL_FROM` domain is verified in SendGrid sender authentication

### Stripe webhook returning 400
- Verify `STRIPE_WEBHOOK_SECRET` matches the signing secret in Stripe Dashboard
- Webhook endpoint must receive raw bytes — do not use JSON middleware on it
- Check Cloud Run logs for `StripeService.handle_stripe_webhook` errors

### Tenant showing as suspended unexpectedly
- Check `TenantSettings.suspended` and `suspension_reason` in DB
- Check `platform_audit_logs` for who suspended it
- Check `email_delivery_logs` for suspension warning emails
- Platform owner can reactivate: `POST /owner/tenants/{id}/activate`

### CEO panel returns empty data
- Verify user has `role=ceo` in DB
- Verify `tenant_id` is set on the CEO user
- Check that projects, employees, and clients exist for that `tenant_id`

### Scheduler jobs not running
- Check app startup logs for `SchedulerService` initialization
- Query `scheduled_agent_jobs` table — check `enabled=True` and `next_run_at`
- Scheduler wakes every 60 minutes — jobs won't run immediately after restart
- Check `last_status` and `last_error` columns for failed jobs

### Frontend shows raw array where paginated list expected
- All list endpoints now return `{items: [...], total: int, skip: int, limit: int}`
- If a component shows `undefined` or breaks, update it to use `response.items` instead of `response`
- `Projects.jsx` and `TaskDetail.jsx` have been updated; other components may need the same

### `ensure_runtime_schema` errors on startup
- New columns (`password_reset_token`, `password_reset_expires`) are patched via `_schema.py`
- If DB user lacks `ALTER TABLE` permission, grant it or recreate the DB
- For fresh DB: all columns created by `Base.metadata.create_all()` — no patching needed

### Cross-tenant data leak suspicion
- Every query must have `.filter(Model.tenant_id == current_user.tenant_id)`
- Platform owner routes intentionally omit this — verify route uses `require_platform_owner`
- Check `TenantMiddleware` — it sets `request.state.tenant_id` from JWT, not from headers

---

### User can't log in after registration
- New accounts require email verification — check inbox for "Verify your email address"
- If SendGrid is not configured, verification email is skipped silently — check `email_delivery_logs`
- Fix for dev/testing: set `email_verified=1` directly in the DB, or set `SENDGRID_API_KEY`

### Refresh token rejected (401)
- Tokens rotate on every use — using the same token twice returns 401
- Frontend must store and replace the new `refresh_token` from each `/auth/refresh` response
- Tokens expire after 30 days — full re-login required after expiry

### 2FA code rejected
- TOTP window is ±30 seconds — ensure device clock is synced (NTP)
- Call `/auth/2fa/setup` again to regenerate a new secret if the previous one is lost (requires a valid session)
- `POST /auth/2fa/disable` requires a valid code — if locked out, set `totp_enabled=0, totp_secret=NULL` in DB

### Rate limit hitting unexpectedly in multi-instance Cloud Run
- Each Cloud Run instance has its own in-memory counter — effective limit is N × configured value
- Set `REDIS_URL` to a shared Redis instance to enforce true global limits
- Cloud Memorystore for Redis is the recommended GCP option

### Google Calendar connection failing
- Verify `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` are all set
- `GOOGLE_REDIRECT_URI` must exactly match a URI registered in Google Cloud Console → OAuth credentials
- The callback endpoint `GET /integrations/google/callback` must be accessible from Google's servers
- For local dev, use `ngrok` to expose the local server and register that URI in Google Console

### Soft-deleted projects/tasks still appearing
- All list queries filter `deleted_at IS NULL` — check if the component is using a cached response
- If a row appears after soft-delete, check `_schema.py` ran successfully (check startup logs for `ensure_runtime_schema`)
- Query the DB directly: `SELECT deleted_at FROM projects WHERE id=X` to confirm the column exists

### `ensure_runtime_schema` errors on startup
- New columns are patched via `_schema.py` additive migration on startup
- If `ALTER TABLE` fails, the DB user may lack DDL permissions — grant `ALTER` permission or recreate tables
- For fresh DBs: all columns created by `Base.metadata.create_all()` — no patching needed

---

*Generated: 2026-04-23 | Updated: 2026-04-23 (phase-11) | Project: AI Workforce Orchestrator | Branch: feature/secure-multitenant-refactor*
