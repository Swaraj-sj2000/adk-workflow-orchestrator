# AI Workforce Orchestrator

AI Workforce Orchestrator is a multi-tenant B2B SaaS platform that turns messy project intake into a governed AI-driven delivery system. Companies subscribe to the platform, manage their teams and clients through an agentic workflow, and get real business intelligence through CEO and Platform Owner dashboards — all with production-grade security and billing enforcement.

This repository contains two parallel backend tracks:

- `backend_adk/` — **Production backend** (always edit and deploy from here). Google ADK / Vertex AI compatible.
- `backend/` — Local dev mirror only. Do not deploy from here.

---

## Why This Project Stands Out

The platform is not a task tracker. Its core value is:

- AI-assisted intake converts a business description into a structured execution plan with tasks, skills, staffing, and risk — automatically.
- The assignment engine scores employees on skill match + workload + efficiency + reliability + timezone before placing any task.
- Agents send real emails, escalate real alerts, and run nightly health checks — they don't just suggest.
- CEOs see company-wide operational health, financials, and risk in one screen without needing to be technical.
- Platform owner (you) controls every company from one panel with billing enforcement and suspension gates.
- Every agent decision is persisted in `WorkflowRun` / `AgentRun` / `DecisionLog` — fully inspectable, not inferred from UI state.

---

## Core Product Features

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
- Tenant suspension gate: 402 for all API calls when payment lapses (except `/auth/*` and `/owner/*`)
- Soft deletes on User, Project, Task, EmployeeProfile — data is recoverable, audit trail preserved

### AI & Agents
- 12-agent orchestration system across two workflows (intake + live execution loop)
- Multi-agent intake: IntakeAgent → PlanningAgent → StaffingAgent + RiskAgent → ExecutionCoordinatorAgent → CommunicationAgent → EscalationAgent
- Live execution loop: ProjectObserverAgent → DeliveryReviewAgent → RebalanceAgent → LoopCommunicationAgent → LoopEscalationAgent
- Assignment engine: `score = 0.35×skill_match + 0.25×(1-workload) + 0.20×efficiency + 0.20×reliability − 0.15×timezone_penalty`
- Agents send actual emails (task assignments, escalations, weekly digests)

### CEO & Owner Dashboards
- CEO business view: KPI cards, financials (P&L per project), team utilization bars, client payment risk, AI-surfaced risk flags
- CEO technical view toggle (switch to full admin interface via `UserPreferences.ceo_mode`)
- Platform Owner panel: all tenants table, suspend/activate controls, support ticket inbox, platform MRR metrics

### Billing (Stripe)
- Two-layer model: platform → company subscriptions + company → client project invoicing
- Stripe Customer Portal, subscription checkout flow
- Webhook-driven auto-suspend: `invoice.payment_failed` → grace period → auto-suspend → `invoice.paid` → reactivate
- Payment hold / lift on individual projects: client gets 402 on project status until resolved

### Email (SendGrid)
- 11 email templates including: verification, invite, password reset, task assignment, blocker alert, escalation, weekly digest, suspension warning, suspension
- Every send attempt logged to `EmailDeliveryLog` — failures never crash request flows

### Background Scheduler
- Asyncio background task, wakes every 60 minutes
- 4 job types: `nightly_observer`, `weekly_digest`, `payment_check`, `archive_old_runs`
- Archive job cleans up completed `WorkflowRun` / `AgentRun` records older than 90 days

### Integrations
- Google Calendar OAuth 2.0 — connect, create events with Google Meet links, disconnect
- Google userinfo for linked email display
- Stripe (subscriptions + billing portal + webhooks)
- SendGrid (transactional email)

### Settings & Personalisation
- Per-user preferences: timezone, theme, language, default landing page, notification density, CEO mode toggle
- Profile editing, password change, GDPR data export
- Support ticket submission to platform owner

### Testing
- In-memory SQLite test suite with scoped transactions
- `test_auth.py` — register, verify, login, refresh token rotation, 2FA setup/enable/disable
- `test_billing.py` — grace period enforcement, Stripe webhook event handling
- `test_assignment.py` — skill scoring, workload scoring, tenant isolation, best-candidate selection

---

## How The Platform Works

### 1. Admin Registers and Verifies

The admin registers with `role=admin` and a `tenant_slug`. A verification email is sent. Until they click the link, login is blocked. After verification, they receive access and refresh tokens.

### 2. Admin Creates a Project

The admin provides a description, budget, priority, deadline, and client info. The backend:

1. Parses the intake with `LLMService`
2. Runs the 7-agent intake workflow
3. Seeds Tasks, Checkpoints, Dependencies, Communications
4. Returns a draft team, execution plan, and risk summary
5. Emails the admin brief and client brief immediately

### 3. Team Formation

Admins invite employees by email. If the employee exists, the invite appears in their dashboard. If not, the invite stays pending until they register and is linked automatically on registration. Once accepted, the employee is added to the team and assigned role-matched tasks.

### 4. Employee Execution

Employees see assigned tasks, checkpoint checklists, blockers, and AI escalation paths. Checkpoint completion triggers the live execution loop: the system checks project health, rebalances if needed, updates communication artifacts, and escalates to humans if health turns red.

### 5. CEO View

CEOs see company-wide health scores, per-project P&L, team utilization, client payment standing, and AI-surfaced risk flags. Toggling CEO mode gives full technical access identical to admin.

### 6. Billing & Suspension

Companies subscribe via Stripe. Failed payment triggers a grace period email. After the grace period, all API calls for that tenant return 402. The platform owner can also manually suspend/activate companies from the Owner Panel.

### 7. Platform Owner

The platform owner (Swaraj) sees all companies, their plan tier, user counts, project counts, billing status, and support tickets — in one panel, cross-tenant.

---

## Agentic Workflow

### Intake Workflow (7 agents in sequence/parallel)

```
IntakeAgent → PlanningAgent → StaffingAgent ┐
                                             ├→ ExecutionCoordinatorAgent
                              RiskAgent ─────┘
                                             ↓
                              CommunicationAgent (sends real emails)
                                             ↓
                              EscalationAgent (emails admins if review required)
```

### Live Execution Loop (5 agents)

```
ProjectObserverAgent → DeliveryReviewAgent → RebalanceAgent → LoopCommunicationAgent → LoopEscalationAgent
```

### Persistence

All agent runs persist to:
- `workflow_runs` — one per workflow invocation
- `agent_runs` — one per agent per workflow
- `decision_logs` — all assignment and escalation decisions
- `communications` — drafted and sent messages
- `audit_logs` — admin/human overrides

---

## Security & Stability

| Layer | Implementation |
|-------|---------------|
| Access tokens | HS256 JWT, 60-minute expiry |
| Refresh tokens | 48-byte random, 30-day expiry, rotated on each use |
| Password hashing | bcrypt (passlib) |
| Email verification | UUID token, blocks login until verified |
| 2FA | TOTP via pyotp, ±30s window |
| Rate limiting | Redis sliding-window (distributed) or in-memory fallback |
| Tenant isolation | All queries filter `tenant_id`; JWT enforces tenant match |
| Suspension gate | TenantMiddleware returns 402 for suspended tenants |
| Input validation | Pydantic v2 schemas on all endpoints |
| CORS | Env-driven allowlist, no wildcard in production |
| HTTP headers | X-Frame-Options, X-Content-Type-Options, Referrer-Policy, etc. |
| Soft deletes | `deleted_at` on User/Project/Task/EmployeeProfile |
| Schema safety | Additive-only migrations via `ensure_runtime_schema` |

---

## Repository Layout

```text
agentic_orchestrator/
├── backend_adk/                 ← PRODUCTION backend (edit and deploy here)
│   ├── app/
│   │   ├── main.py              ← FastAPI app, middleware, routers, lifespan
│   │   ├── agents/              ← 12 agent classes
│   │   ├── api/routes/          ← HTTP route handlers (thin)
│   │   │   ├── _auth.py         ← login, register, refresh, verify-email, 2FA
│   │   │   ├── _integrations.py ← Google Calendar OAuth
│   │   │   └── ...
│   │   ├── core/
│   │   │   ├── _security.py     ← JWT + bcrypt + TOTP helpers
│   │   │   └── _rate_limit.py   ← Redis / in-memory rate limiting
│   │   ├── models/              ← 32 SQLAlchemy ORM models
│   │   ├── services/
│   │   │   ├── _calendar_service.py  ← Google Calendar OAuth flow
│   │   │   └── ...
│   │   └── db/_schema.py        ← Additive column patcher
│   ├── tests/
│   │   ├── conftest.py          ← In-memory SQLite + TestClient fixture
│   │   ├── test_auth.py
│   │   ├── test_billing.py
│   │   └── test_assignment.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── deploy_cloud_run.sh
├── backend/                     ← Local dev mirror — do not deploy
├── frontend/                    ← React + Vite frontend
│   └── src/components/
│       ├── CEODashboard.jsx
│       ├── OwnerPanel.jsx
│       └── Settings.jsx
├── README.md
└── COMPLETE_GUIDE.md            ← Full architecture + API + deployment reference
```

---

## Quick Reference — Key Endpoints

```
POST /auth/register                   Register (sends verification email)
GET  /auth/verify-email?token=        Activate account
POST /auth/login                      → {access_token, refresh_token, user}
POST /auth/refresh                    → rotate tokens
POST /auth/2fa/setup|enable|disable   2FA management

GET  /ceo/overview|financials|teams|clients|risks   CEO analytics
GET  /owner/tenants                   All companies (platform_owner only)
POST /owner/tenants/{id}/suspend      Suspend a company
GET  /settings/me                     User profile + preferences
POST /billing/subscribe               Start Stripe subscription
POST /billing/webhook                 Stripe event handler

GET  /integrations/google/auth-url    Start Google Calendar OAuth
GET  /integrations/google/callback    OAuth callback (registered with Google)
POST /integrations/google/calendar/events  Create calendar event

GET  /healthz                         Health check
GET  /docs                            Swagger UI
```

---

## Deployment URLs

- Frontend: `https://frontend-974381609416.europe-west1.run.app`
- Backend: `https://backend-adk-974381609416.europe-west1.run.app`
- API Docs: `https://backend-adk-974381609416.europe-west1.run.app/docs`
- Stripe Webhook: `https://backend-adk-974381609416.europe-west1.run.app/billing/webhook`

---

## Where To Read More

Use [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for:

- Full database model reference (all 32 models + every field)
- Complete API endpoint map with guards and response shapes
- Service-layer method signatures and business logic descriptions
- Multi-agent workflow diagrams
- All environment variables (required + optional + defaults)
- Email template list and link formats
- Billing flow (Stripe webhook → grace period → suspension)
- Scheduler job types and cron schedules
- Authentication & security deep-dive (JWT, refresh tokens, 2FA, rate limiting, soft deletes)
- Deployment guide (Cloud Run env vars, Dockerfile, Stripe webhook registration)
- Local development setup
- Demo credentials and end-to-end demo flow
- Full implementation history (phases 0 → 11)
- Troubleshooting runbook (30+ known issues with fixes)
