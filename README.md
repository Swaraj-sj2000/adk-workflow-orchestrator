# AI Workforce Orchestrator

AI Workforce Orchestrator is a multi-tenant B2B SaaS platform that turns a plain-English project brief into a fully staffed, risk-assessed, AI-monitored delivery pipeline — with real emails, real escalations, and real business intelligence at every layer.

Companies subscribe to the platform. Each company manages their teams, projects, and clients through an agentic workflow. The AI plans, staffs, monitors, and escalates — and actually acts on those decisions rather than just suggesting them.

---

## What Makes It Different

| Capability | What it does |
|---|---|
| **AI Intake Pipeline** | One text brief → structured plan, staffed team, risk assessment, client brief — automatically |
| **Skill Growth Tracking** | Every completed task updates the employee's demonstrated skill confidence. The assignment engine blends declared skills (70%) + proven track record (30%) |
| **Predictive Delivery Forecast** | Per-project velocity, ETA, budget burn rate, and risk score (0–100) with LLM narrative |
| **Proof of Work** | Employees attach optional evidence (commit SHA, PR link, doc URL) to subtasks. Visible to admin and read by the DeliveryReviewAgent |
| **Natural Language Queries** | Admin/CEO asks "who has capacity?" or "which projects are at risk?" — gets a live DB answer |
| **Client Change Requests** | Clients raise scope or delivery concerns directly. Admins approve/reject. Full audit trail |
| **Scope Change Handling** | Admin submits a new brief mid-project. LLM diffs it against existing tasks and generates a formal change order document |
| **Markdown-rendered AI text** | All LLM output (narratives, briefs, risk analysis) renders as structured bullet points and headings — not raw `**markdown**` |

---

## Core Platform Features

### Authentication & Security
- JWT access tokens (HS256, 60-minute expiry) + 30-day rotating refresh tokens
- Email verification — new accounts are gated until the user clicks the verification link
- 2FA / TOTP via `pyotp` — setup, enable, and disable from `/auth/2fa/*`
- bcrypt password hashing, secure password reset (token + 1-hour expiry)
- Redis-backed sliding-window rate limiting (falls back to in-memory per process)
- HTTP security headers (X-Frame-Options, X-Content-Type-Options, etc.)
- CORS driven by `ALLOWED_ORIGINS` env var — never wildcard in production

### Multi-Tenant Platform
- 5-tier user hierarchy: `platform_owner → ceo → admin → employee → client`
- Every query is tenant-scoped — cross-tenant data access is impossible by design
- Tenant suspension gate: 402 for all API calls when payment lapses
- Soft deletes on User, Project, Task, EmployeeProfile — data recoverable, audit trail preserved

### AI & Agents
- 12-agent orchestration system across two workflows (intake + live execution loop)
- **Intake workflow:** IntakeAgent → PlanningAgent → StaffingAgent + RiskAgent → ExecutionCoordinatorAgent → CommunicationAgent → EscalationAgent
- **Live execution loop:** ProjectObserverAgent → DeliveryReviewAgent → RebalanceAgent → LoopCommunicationAgent → LoopEscalationAgent
- **Assignment scoring:** `score = 0.35 × skill_match + 0.25 × (1−workload) + 0.20 × efficiency + 0.20 × reliability − 0.15 × timezone_penalty`
- Skill match now blends **declared skills (70%) + demonstrated skills from completed tasks (30%)**
- Agents send actual emails, escalate real alerts, run nightly health checks

### Intelligence Features (Platform Intelligence Suite)
- **`GET /projects/{id}/delivery-forecast`** — velocity, ETA, risk score, LLM narrative
- **`POST /assistant/nl-query`** — natural language live DB queries for admins and CEOs
- **`PUT /task-progress/{id}/proof`** — employee submits proof of work (note + URL)
- **`POST /projects/{id}/change-requests`** — client or admin raises a change request
- **`POST /projects/{id}/scope-change`** — LLM-powered scope diff + change order generation

### CEO & Owner Dashboards
- CEO business view: KPI cards, financials (P&L per project), team utilization, client payment risk, AI-surfaced risk flags
- CEO technical view toggle via `UserPreferences.ceo_mode`
- Platform Owner panel: all tenants, suspend/activate, support ticket inbox, platform MRR metrics

### Billing (Stripe)
- Platform → company subscriptions + company → client project invoicing
- Webhook-driven auto-suspend: `invoice.payment_failed` → grace period → suspend → `invoice.paid` → reactivate
- Plans: Trial (free/30d), Starter (₹1,000/mo), Pro (₹5,000/6mo), Enterprise (₹15,000/yr)

### Email (SendGrid)
- 11 email templates: verification, invite, password reset, task assignment, blocker alert, escalation, weekly digest, suspension warning, suspension
- Every send attempt logged to `EmailDeliveryLog` — failures never crash request flows

### Background Scheduler
- Asyncio background task, wakes every 60 minutes
- **5 job types:** `nightly_observer`, `weekly_digest`, `payment_check`, `archive_old_runs`
- **Log purge policy (runs every Sunday 3am UTC):**
  - `workflow_runs` + `agent_runs`: 90 days (completed/failed only)
  - `decision_logs` + `audit_log`: 90 days
  - `email_delivery_logs`: 60 days
  - `platform_audit_logs`: 180 days

### Integrations
- Google Calendar OAuth 2.0 — connect, create events with Meet links, disconnect
- Stripe (subscriptions + billing portal + webhooks)
- SendGrid (transactional email)
- Vertex AI / Gemini 2.5 Flash (production LLM)
- HuggingFace Inference API (local dev LLM fallback)

---

## How The Platform Works

### 1. Admin Creates a Project
Provides a text description, budget, priority, deadline, and client. The backend runs the 7-agent intake workflow, seeds tasks/checkpoints/dependencies, returns a draft team and risk summary, and emails the admin and client immediately.

### 2. Team Formation
Admins invite employees by email. Accepted invites assign role-matched tasks automatically.

### 3. Employee Execution
Employees see assigned tasks, update progress, submit proof of work (optional), and flag blockers. Blockers trigger the live execution loop: the system checks health, rebalances, drafts communications, and escalates to humans if health turns red.

### 4. Skill Growth
Every completed task updates the employee's `demonstrated_skills` using exponential moving average. The assignment engine uses this alongside declared skills for future task scoring — employees get better matches as they build a track record.

### 5. Client Portal
Clients view live project progress, payment status, and AI-generated status updates. They can raise change requests directly. Admins approve/reject in the dashboard.

### 6. CEO View
Company-wide health scores, per-project P&L, team utilization, client payment standing, and AI-surfaced risk flags. The delivery forecast endpoint gives velocity-based ETA and risk score per project.

### 7. Billing & Suspension
Failed payment → grace period email → auto-suspend (all API calls return 402) → `invoice.paid` → reactivate.

---

## Agentic Workflows

### Intake Workflow (7 agents)

```
IntakeAgent → PlanningAgent → StaffingAgent ─┐
                                              ├─→ ExecutionCoordinatorAgent
                               RiskAgent ─────┘
                                              ↓
                               CommunicationAgent  (sends real emails)
                                              ↓
                               EscalationAgent  (emails admins if review required)
```

### Live Execution Loop (5 agents)

```
ProjectObserverAgent → DeliveryReviewAgent → RebalanceAgent → LoopCommunicationAgent → LoopEscalationAgent
```

DeliveryReviewAgent now reads **proof of work** evidence from completed subtasks as part of its assessment.

### Persistence
Every workflow persists to: `workflow_runs`, `agent_runs`, `decision_logs`, `communications`, `audit_log`.

---

## Key API Endpoints

```
# Auth
POST /auth/register                   Register (sends verification email)
GET  /auth/verify-email?token=        Activate account
POST /auth/login                      → {access_token, refresh_token, user}
POST /auth/refresh                    Rotate tokens
POST /auth/2fa/setup|enable|disable   2FA management

# Projects
GET  /projects/                       List projects (tenant-scoped)
POST /projects/                       Create project
GET  /projects/{id}/status            Full project status with team, tasks, AI report
GET  /projects/{id}/delivery-forecast Velocity, ETA, risk score, LLM narrative  ← NEW
POST /projects/{id}/scope-change      Submit new brief → LLM change order         ← NEW
POST /projects/{id}/change-requests   Client/admin raises change request           ← NEW
GET  /projects/{id}/change-requests   List change requests                         ← NEW
PATCH /projects/{id}/change-requests/{cr_id}  Resolve a change request            ← NEW

# Tasks & Progress
GET  /task-progress?task_id=          Get task progress
PATCH /task-progress/{id}             Update progress (hours, %, notes)
PUT  /task-progress/{id}/proof        Submit proof of work (note + URL)            ← NEW

# AI Assistant
POST /assistant/chat                  Platform assistant (role-aware Q&A)
POST /assistant/nl-query              Live DB natural language query (admin/CEO)   ← NEW

# CEO
GET  /ceo/overview|financials|teams|clients|risks   CEO analytics

# Platform Owner
GET  /owner/tenants                   All companies
POST /owner/tenants/{id}/suspend      Suspend a company

# Settings & Billing
GET  /settings/me                     User profile + preferences
POST /billing/subscribe               Start Stripe subscription
POST /billing/webhook                 Stripe event handler

# Multi-Agent
POST /multi-agent/intake              Trigger full intake pipeline
GET  /multi-agent/workflows           List workflow runs

# Health
GET  /healthz                         Health check
GET  /docs                            Swagger UI
```

---

## Security Summary

| Layer | Implementation |
|---|---|
| Access tokens | HS256 JWT, 60-minute expiry |
| Refresh tokens | 48-byte random, 30-day expiry, rotated on each use |
| Password hashing | bcrypt (passlib) |
| Email verification | UUID token, blocks login until verified |
| 2FA | TOTP via pyotp, ±30s window |
| Rate limiting | Redis sliding-window or in-memory fallback |
| Tenant isolation | All queries filter `tenant_id`; JWT enforces tenant match |
| Suspension gate | TenantMiddleware returns 402 for suspended tenants |
| Input validation | Pydantic v2 schemas on all endpoints |
| CORS | Env-driven allowlist, no wildcard in production |
| Soft deletes | `deleted_at` on User/Project/Task/EmployeeProfile |
| Schema safety | Additive-only migrations via `ensure_runtime_schema` |

---

## Repository Layout

```
agentic_orchestrator/
├── backend_adk/                      ← PRODUCTION backend (always edit here)
│   ├── app/
│   │   ├── main.py                   ← FastAPI app, middleware, routers, lifespan
│   │   ├── agents/                   ← 12 agent classes
│   │   │   ├── _intake_agent.py
│   │   │   ├── _planning_agent.py
│   │   │   ├── _staffing_agent.py
│   │   │   ├── _risk_agent.py
│   │   │   ├── _execution_coordinator_agent.py
│   │   │   ├── _communication_agent.py
│   │   │   ├── _escalation_agent.py
│   │   │   ├── _delivery_review_agent.py  ← reads proof of work
│   │   │   ├── _rebalance_agent.py
│   │   │   └── ...
│   │   ├── api/routes/               ← HTTP route handlers (thin)
│   │   ├── core/
│   │   │   ├── _security.py          ← JWT + bcrypt + TOTP
│   │   │   └── _rate_limit.py        ← Redis / in-memory rate limiting
│   │   ├── models/                   ← 33 SQLAlchemy ORM models
│   │   │   ├── _change_request.py    ← NEW: scope/delivery change requests
│   │   │   └── ...
│   │   ├── services/
│   │   │   ├── _skill_service.py     ← NEW: demonstrated skill EMA updates
│   │   │   ├── _assignment_engine.py ← blends declared + demonstrated skills
│   │   │   ├── _llm_service.py       ← Vertex AI / HuggingFace
│   │   │   ├── _scheduler_service.py ← purges all 5 log tables on schedule
│   │   │   └── ...
│   │   └── db/_schema.py             ← Additive column patcher (dialect-aware)
│   ├── tests/
│   │   ├── test_auth.py
│   │   ├── test_billing.py
│   │   └── test_assignment.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                         ← React + Vite frontend
│   └── src/components/
│       ├── Markdown.jsx              ← NEW: zero-dep markdown renderer for AI text
│       ├── MultiAgentWorkbench.jsx
│       ├── Dashboard.jsx
│       ├── Projects.jsx
│       └── ...
├── README.md
└── COMPLETE_GUIDE.md                 ← Full architecture + API + deployment reference
```

---

## Deployment

### Live URLs
- **Frontend:** `https://agentic-orchestrator-frontend-974381609416.europe-west1.run.app`
- **Backend API:** Cloud Run service `agentic-orchestrator-backend` (europe-west1)
- **API Docs:** `{backend-url}/docs`
- **GCP Project:** `havoc-ai-prod`
- **Billing account:** `01E336-987ED9-6B9D22`

### Deploy (manual)
```bash
# In Cloud Shell — clone if needed
git clone https://github.com/Swaraj-sj2000/adk-workflow-orchestrator.git agentic_orchestrator
cd agentic_orchestrator

git pull origin main

# Backend
cd backend_adk
gcloud builds submit \
  --tag europe-west1-docker.pkg.dev/havoc-ai-prod/cloud-run-source-deploy/agentic-orchestrator-backend \
  --project havoc-ai-prod
gcloud run deploy agentic-orchestrator-backend \
  --image europe-west1-docker.pkg.dev/havoc-ai-prod/cloud-run-source-deploy/agentic-orchestrator-backend \
  --region europe-west1 --project havoc-ai-prod

# Frontend
cd ../frontend
gcloud builds submit \
  --tag europe-west1-docker.pkg.dev/havoc-ai-prod/cloud-run-source-deploy/agentic-orchestrator-frontend \
  --project havoc-ai-prod
gcloud run deploy agentic-orchestrator-frontend \
  --image europe-west1-docker.pkg.dev/havoc-ai-prod/cloud-run-source-deploy/agentic-orchestrator-frontend \
  --region europe-west1 --project havoc-ai-prod --allow-unauthenticated
```

### Schema migrations
No manual migrations needed. On startup `ensure_runtime_schema` adds any missing columns additively (dialect-aware: PostgreSQL uses `TIMESTAMP`/`BOOLEAN`, SQLite uses `DATETIME`/`INTEGER`). New tables are created by `Base.metadata.create_all`.

### Required environment variables (backend)
```
SECRET_KEY                Database JWT signing key
DATABASE_URL              postgresql://... or sqlite:///...
SENDGRID_API_KEY          SendGrid transactional email
STRIPE_SECRET_KEY         Stripe payments
STRIPE_WEBHOOK_SECRET     Stripe webhook signature
GOOGLE_CLOUD_PROJECT      GCP project ID (Vertex AI)
GOOGLE_CLOUD_LOCATION     e.g. us-central1
GOOGLE_GENAI_USE_VERTEXAI true
ALLOWED_ORIGINS           Comma-separated frontend URLs
```

---

## Where To Read More

See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for:
- Full database model reference (all 33 models + every field)
- Complete API endpoint map with auth guards and response shapes
- Service-layer method signatures and business logic
- Multi-agent workflow diagrams and data flow chains
- All environment variables (required + optional + defaults)
- Email template list and link formats
- Billing flow (Stripe webhook → grace period → suspension)
- Scheduler job types and cron schedules
- Authentication & security deep-dive
- Local development setup
- Demo credentials and seeded data
- Full implementation history (phases 0 → 12)
- Troubleshooting runbook
