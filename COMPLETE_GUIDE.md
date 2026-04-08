# AI Workforce Orchestrator Complete Guide

This is the canonical architecture, product, and operations document for the repository. It is intended to be detailed enough for engineering handoff, judging, onboarding, and deployment planning without sending readers through a pile of stale markdown files.

## 1. Product Overview

AI Workforce Orchestrator is a multi-role project execution platform built around a simple idea:

take a rough business request, convert it into a structured execution plan, staff it intelligently, track work at checkpoint level, keep clients informed in business language, and preserve safety through tenant-aware backend enforcement.

The platform supports three human roles:

- `admin`
  Creates projects, manages teams, approves staffing, updates payment state, monitors delivery, and reviews final reports.
- `employee`
  Accepts or rejects team invites, executes assigned work, updates checkpoints, manages skills and duty hours, raises blockers, and earns experience points.
- `client`
  Views project plan and delivery summaries, reviews business-facing status, sees final reports, and participates in payment-state updates.

The repository also supports two backend modes:

- `backend/`
  The primary product backend.
- `backend_adk/`
  A mirrored backend variant that preserves product behavior while keeping its Google ADK / Vertex AI integration path intact.

## 2. USP And Value Proposition

The strongest product differentiators are:

- it connects business intake directly to delivery execution
- it does not stop at planning; it also tracks ownership, progress, risk, invites, and reporting
- it keeps the client view business-safe and lightweight
- it keeps the employee view operational and actionable
- it treats backend validation as the source of truth
- it gives a realistic path from classic SaaS project management toward agent-assisted orchestration

In practical terms, the system gives teams:

- structured project planning
- role-aware staffing
- tenant-safe data isolation
- invite-driven team formation
- checkpoint-level execution tracking
- automated progress and performance scoring
- payment-state traceability
- generated project reporting and history retention

## 3. Current Repository Layout

```text
.
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   ├── api/routes/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── requirements.txt
│   └── seed_test_data.py
├── backend_adk/
│   ├── app/
│   └── seed_test_data.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.jsx
│   │   └── App.css
│   └── package.json
├── README.md
└── COMPLETE_GUIDE.md
```

## 4. Backend Architecture

### 4.1 Main FastAPI Layers

Important runtime modules in `backend/app`:

- `main.py`
  Creates the app, middleware stack, routers, database bootstrap, and request logging.
- `core/_deps.py`
  Resolves the current user from JWT and enforces tenant consistency.
- `core/_security.py`
  Password hashing, token generation, and token validation.
- `core/_tenant_middleware.py`
  Attaches tenant context to the request.
- `core/_rate_limit.py`
  Basic in-memory throttling for repeated requests.
- `db/_schema.py`
  Runtime additive schema handling for careful roll-forward of new columns.
- `services/_project_service.py`
  The main lifecycle engine for projects, invites, progress, reporting, and history.
- `services/_invite_service.py`
  Team invite creation, linking, and acceptance.
- `services/_auth_service.py`
  Registration, login, tenant assignment, and profile bootstrapping.
- `services/_multi_agent_orchestrator.py`
  Explicit multi-agent orchestration layer for project-intake and execution-loop workflows.

### 4.2 Core Data Entities

Main entities:

- `tenants`
- `users`
- `employee_profiles`
- `employee_metrics`
- `client_profiles`
- `projects`
- `tasks`
- `task_assignments`
- `task_progress`
- `checkpoints`
- `blockers`
- `teams`
- `team_members`
- `team_invites`
- `performance_points`
- `communications`
- `decision_logs`
- `event_queue`
- `meetings`
- `workflow_runs`
- `agent_runs`

### 4.3 Multi-Tenant Model

The system uses a one-tenant-per-user model.

Rules:

- every user belongs to one tenant
- admins operate only inside their own tenant
- employees and clients only see projects tied to their tenant
- invites are tenant-scoped
- user access is enforced on backend queries, not just in the UI

Tenant information is carried in the JWT and enforced during request resolution.

## 5. Frontend Architecture

The frontend is a React + Vite application with a single authenticated shell and role-based dashboards.

Main modules:

- `App.jsx`
  login flow, authenticated shell, and theme state
- `Navbar.jsx`
  navigation and theme toggle
- `Dashboard.jsx`
  admin, employee, and client dashboard entry views
- `Projects.jsx`
  project center with status details
- `EmployeeView.jsx`
  detailed employee execution workspace

The frontend is intentionally thin. It relies on backend-generated data models for:

- project status
- team state
- payment updates
- client-facing reports
- employee progress
- notifications

## 6. End-To-End Product Flow

### 6.1 Project Creation

Admin submits:

- title
- description
- budget
- priority
- deadline
- client details
- initial payment status

Backend flow:

1. validate payload with schemas
2. normalize strings and IDs
3. enforce admin role
4. check duplicate active project names within tenant
5. resolve or create client
6. parse intake using `LLMService`
7. generate role clusters and recommended staffing
8. seed tasks and subtasks
9. generate manager, employee, and client stage briefs
10. persist project and team metadata

### 6.2 Team Invite Flow

Admin sends invite by email:

- invite is created in `team_invites`
- if the email already belongs to a tenant-matching user, the link is immediate
- if not, it remains email-pending

Employee sees invite:

- employee dashboard lists the invite
- employee can accept or reject

Accept:

- `team_members` row is created
- role-aligned tasks are assigned immediately
- checkpoints and work packages become visible

Reject:

- invite is marked rejected
- replacement suggestions are produced
- admin can restaff

### 6.3 Employee Self-Management

Employees can update:

- skills
- duty start hour
- duty end hour
- leave state

Employees cannot directly override:

- cross-tenant visibility
- unauthorized task state
- arbitrary workload
- admin-only project actions

### 6.4 Progress Tracking

Progress is driven by checkpoints.

When an employee marks a checkpoint complete:

- the checkpoint status updates
- task progress updates
- assignment state updates
- project progress recalculates from checkpoint totals
- notifications are added
- experience points may be awarded when a task completes

### 6.5 Project Completion

When checkpoint-based project completion reaches 100%:

- the project is marked `completed`
- employee capacity from that project is released
- the project leaves the active lists and remains in history
- a final generated report is stored
- payment updates remain visible in history

## 7. Agentic Workflow

The repository contains a real explicit agent pipeline, not just AI-themed naming.

### 7.1 Intake Workflow Agents

The intake workflow is managed by `MultiAgentOrchestrator.run_intake_workflow`.

#### `IntakeAgent`

Purpose:

- parse the raw request into a structured brief

Input:

- `request_text`

Output:

- `parsed_brief`

Decision role:

- if confidence is low, it can trigger human review

#### `PlanningAgent`

Purpose:

- transform the parsed brief into:
  - project title
  - project summary
  - task list
  - dependencies
  - basic due-date recommendations

Decision role:

- establishes the execution blueprint

#### `StaffingAgent`

Purpose:

- rank employees for each task using:
  - required skills
  - current load
  - available capacity

Decision role:

- identifies recommended owners and understaffed work

#### `RiskAgent`

Purpose:

- assess complexity, staffing gaps, and load pressure

Decision role:

- classifies workflow risk as low, medium, or high
- can force review when autonomy would be unsafe

#### `ExecutionCoordinatorAgent`

Purpose:

- decide which tasks are safe to start autonomously
- separate tasks into:
  - `autonomous`
  - `review_required`

Decision role:

- creates the execution queue and the next-action list

#### `CommunicationAgent`

Purpose:

- draft admin, employee, and client-facing messages from workflow state

Decision role:

- prepares communication artifacts without granting final authority

#### `EscalationAgent`

Purpose:

- apply explicit escalation policy to current workflow outputs

Decision role:

- decide whether the system can continue autonomously or must stop for review

### 7.2 Live Execution Loop Agents

The execution loop is managed by `MultiAgentOrchestrator.run_project_execution_loop`.

#### `ProjectObserverAgent`

Purpose:

- read actual persisted project state
- gather tasks, blockers, assignments, and progress rows

Decision role:

- provides the authoritative current-state snapshot

#### `DeliveryReviewAgent`

Purpose:

- run delivery health and risk review using monitoring data

Decision role:

- detects delivery blockers, delay pressure, and intervention needs

#### `RebalanceAgent`

Purpose:

- propose reassignments and detect unassigned active tasks

Decision role:

- helps maintain safe staffing under changing execution conditions

#### `LoopCommunicationAgent`

Purpose:

- draft live follow-up updates for admins and other stakeholders

Decision role:

- turns state changes into operational communication

#### `LoopEscalationAgent`

Purpose:

- decide whether the live execution loop can keep running autonomously

Decision role:

- halts autonomy when project delivery risk becomes too high

### 7.3 What The Agent Layer Persists

The orchestration layer records:

- workflow run metadata
- per-agent outputs
- reasoning summaries
- confidence values
- human-review flags
- communication drafts
- decision logs

This is important for demonstrations because it makes the agentic system inspectable instead of magical.

## 8. Security Model

### 8.1 Authentication

- JWT tokens include user ID, role, tenant ID, and email
- token expiry and signature are enforced
- password hashing is handled server-side

### 8.2 Authorization

Admin-only actions include:

- project creation
- team approval
- project deletion
- invite creation
- team monitoring views

Employee-only or employee-scoped actions include:

- invite acceptance/rejection
- checkpoint updates for assigned work
- self-profile updates for skills, duty hours, and leave status

Client-only or client-scoped actions include:

- viewing linked project reporting
- updating project payment status for their own project

### 8.3 Input Validation

Validation is performed with Pydantic schemas for:

- users
- projects
- invites
- employees
- tasks
- blockers
- task progress
- payment updates

Protections include:

- trimmed and normalized strings
- normalized emails
- bounded field sizes
- duplicate invite prevention
- duplicate project prevention
- explicit allowed status sets

### 8.4 Rate Limiting

The backend includes basic in-memory rate limiting middleware. It is appropriate for hackathon or single-instance protection and should be replaced by a distributed limiter for larger production scale.

### 8.5 Data Integrity

Critical flows use defensive consistency logic:

- invite acceptance validates tenant and email match
- project deletion uses transactional cleanup
- checkpoint updates validate assignment ownership
- payment status updates validate actor ownership
- project completion releases employee capacity before archiving to history

## 9. Logging, Monitoring, And Debugging

### 9.1 What Is Logged

The stack logs:

- incoming HTTP requests
- response status and timing
- project creation attempts
- invite and approval actions
- workflow execution steps
- agent confidence and review flags
- deletion activity
- errors with stack traces

### 9.2 Debugging Paths

Useful debugging surfaces:

- `https://<backend-host>/docs`
- request logs from the backend process
- database tables for `workflow_runs`, `decision_logs`, `communications`, `performance_points`
- project status responses from `/projects/{id}/status`
- team and employee dashboards for progress verification

### 9.3 Type-Safety And Mismatch Prevention

The app currently prevents common input mismatches through:

- strict schema parsing
- normalized email and status values
- limited accepted enumerations on key states
- server-side conversion of numeric fields such as budget and hours
- defensive access checks before state mutation

## 10. Reporting Model

The reporting layer now produces:

- business summary
- project plan brief
- USP statement
- feature highlights
- delivery status
- overall status
- today’s status
- final detailed report text
- payment update history

Admin and client users both see reporting artifacts, but the client-facing framing avoids deep technical implementation details unless the project explicitly exposes them.

## 11. Experience Points And Employee Growth

The system tracks:

- total experience points
- grade label
- current level
- current level progress out of 100
- efficiency score
- reliability score
- completed and delayed task counts

XP behavior:

- task completion awards points automatically
- higher levels reduce the effective gain multiplier
- this means the same class of work becomes slightly less rewarding as the employee levels up
- level progress is shown in the UI with a 100-point progress bar

This gives the demo a visible growth loop and makes performance tracking more legible.

## 12. Client And Payment Workflow

The payment workflow is intentionally collaborative:

- admin can update payment status
- the linked client can also update payment status
- updates are retained as a timeline
- the final report remains visible alongside payment history

Supported states include:

- `pending`
- `partial`
- `client-confirmed`
- `admin-confirmed`
- `completed`
- `disputed`

## 13. Project History Model

Completed projects are not treated like open work.

Instead they:

- leave the active project lists
- stay visible in history for admin, employee, and client users
- retain final reporting
- retain payment history
- preserve auditability while releasing active workload pressure

This gives the system the feel of an operations platform rather than a simple CRUD tracker.

## 14. Backend And Backend_ADK Relationship

### `backend/`

Use this for the main application path.

### `backend_adk/`

This backend mirrors the same product behavior but preserves the Google-oriented service path.

Important rule:

- product behavior should stay aligned with `backend/`
- ADK / Vertex-specific service integration should remain intact
- mirrored product changes should avoid replacing `backend_adk/app/services/_llm_service.py`

That allows both backends to evolve in parallel while targeting different runtime integrations.

## 15. Environment And Runtime Reference

### 15.1 Placeholder Pattern

Use environment-specific placeholders instead of hardcoded localhost references when preparing new environments:

- frontend app: `https://<frontend-host>`
- primary backend: `https://<backend-host>`
- primary backend docs: `https://<backend-host>/docs`
- ADK backend: `https://<backend-adk-host>`
- ADK backend docs: `https://<backend-adk-host>/docs`

Example environment variables:

```bash
VITE_API_URL=https://<backend-host>
DATABASE_URL=<database-connection-string>
SECRET_KEY=<secret-key>
ACCESS_TOKEN_EXPIRE_MINUTES=60
BASIC_RATE_LIMIT_REQUESTS=120
BASIC_RATE_LIMIT_WINDOW_SECONDS=60
```

### 15.2 Current Hackathon Deployment Reference

The current hackathon deployment values are:

- Google Cloud project: `havoc-ai-prod`
- region: `europe-west1`
- frontend URL: `https://frontend-adk-974381609416.europe-west1.run.app/`
- backend ADK URL: `https://backend-adk-974381609416.europe-west1.run.app/`
- backend ADK docs: `https://backend-adk-974381609416.europe-west1.run.app/docs`
- Artifact Registry image path: `europe-west1-docker.pkg.dev/havoc-ai-prod/orchestrator-repo/backend-adk:latest`
- service account: `ai-workflow-orchestrator@havoc-ai-prod.iam.gserviceaccount.com`

Cloud SQL runtime values:

- instance name: `orchestrator-sql`
- instance connection name: `havoc-ai-prod:europe-west1:orchestrator-sql`
- public IP: `130.211.104.30`
- database name: `orchestrator`
- database user: `orchestrator_user`
- PostgreSQL port: `5432`

Local proxy connection string:

```bash
postgresql+psycopg2://orchestrator_user:B%40ta2910@127.0.0.1:5432/orchestrator
```

Operational note:

- do not use the public IP directly for normal development or seeding
- use Cloud SQL Proxy locally
- use the Cloud SQL Unix socket path on Cloud Run
- keep `backend_adk/deploy_cloud_run.sh` aligned with the real database name `orchestrator`

## 16. Local Setup

### Main Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed_test_data.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### ADK Backend

```bash
cd backend_adk
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed_test_data.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
```

## 17. Seeded Demo Accounts

Primary local demo credentials:

- admin
  - email: `swaraj@orchestrator.ai`
  - password: `admin123`

- employees
  - email pattern: `<firstname>.<lastname>@orchestrator.ai`
  - password: `team123456`

## 18. Verification Checklist

Before shipping or demoing:

1. verify login and tenant-scoped routing
2. create a project with both existing-client and new-client modes
3. send an invite to an existing employee email
4. accept the invite and confirm tasks appear immediately
5. update employee skills and duty hours
6. complete checkpoints and verify:
   - task progress changes
   - project progress changes
   - experience points update
7. verify payment updates from admin and client sides
8. complete a project and confirm:
   - it moves to history
   - employee load is released
   - final report is available
9. run the same validation against `backend_adk`

## 19. Cloud Run And Cloud SQL Operations Manual

This section is the practical deployment and recovery guide for the current ADK-backed demo environment.

### 19.1 What Gets Submitted For The Hackathon

The public demo link to share is:

- `https://frontend-adk-974381609416.europe-west1.run.app/`

Supporting links:

- backend ADK API: `https://backend-adk-974381609416.europe-west1.run.app/`
- backend ADK Swagger docs: `https://backend-adk-974381609416.europe-west1.run.app/docs`

System path:

`browser -> frontend Cloud Run -> backend_adk Cloud Run -> Cloud SQL`

### 19.2 Deploy Order

Recommended deploy order for the current cloud environment:

1. build and deploy `backend_adk`
2. verify backend docs and logs
3. ensure `frontend` points to the correct backend ADK URL
4. deploy `frontend`
5. seed Cloud SQL
6. verify login, project creation, invite flow, and reporting

### 19.3 Backend_ADK Cloud Run Settings

The deployed backend depends on these settings remaining consistent:

- `PROJECT_ID=havoc-ai-prod`
- `REGION=europe-west1`
- `INSTANCE_NAME=orchestrator-sql`
- `DB_NAME=orchestrator`
- `DB_USER=orchestrator_user`

Cloud Run must include:

- `--add-cloudsql-instances havoc-ai-prod:europe-west1:orchestrator-sql`
- a valid `DATABASE_URL`
- a stable `SECRET_KEY`
- the service account `ai-workflow-orchestrator@havoc-ai-prod.iam.gserviceaccount.com`

The service account needs at least:

- `roles/cloudsql.client`
- `roles/aiplatform.user`
- `roles/logging.logWriter`

### 19.4 Safe Seeding Flow For Demo Data

The current seed script is:

- `backend_adk/seed_test_data.py`

Important behavior:

- it drops all tables
- it recreates the schema
- it seeds 1 admin and 10 employees
- it is safe only when you intentionally want a clean demo reset

Current demo credentials after seeding:

- admin: `swaraj@orchestrator.ai` / `admin123`
- employees: emails from `backend_adk/seed_test_data.py` / `team123456`

Use this exact local seeding flow:

1. start Cloud SQL Proxy in one terminal

```bash
cloud-sql-proxy havoc-ai-prod:europe-west1:orchestrator-sql --port 5432
```

2. in a second terminal, activate the ADK backend environment

```bash
cd ~/adk-workflow-orchestrator/backend_adk
source venv/bin/activate
```

3. export the database URL that points at the proxy

```bash
export DATABASE_URL='postgresql+psycopg2://orchestrator_user:B%40ta2910@127.0.0.1:5432/orchestrator'
```

4. execute the seed

```bash
python seed_test_data.py
```

5. verify the live app using the frontend URL

If the app needs richer demo data later, add a second dedicated demo seed script instead of overloading the clean reset script.

### 19.5 Cloud SQL Connection Failure Checklist

These are the most common causes of connection problems in the current setup:

- Cloud SQL Proxy is not running locally
- the proxy is running, but the app is pointing at the wrong port or host
- the real database name is `orchestrator`, but `DATABASE_URL` is using a different name such as `orchestrator_db`
- the Cloud Run service is still using an older revision with stale environment variables
- `backend_adk/deploy_cloud_run.sh` and the real Cloud SQL database name are out of sync
- the database password in the deployed service does not match the database user password
- `DB_PASSWORD` or `SECRET_KEY` were regenerated accidentally during redeploy because they were unset
- the Cloud Run service account is missing `roles/cloudsql.client`
- `--add-cloudsql-instances` was omitted in the deploy command
- the seed succeeded against one database while the live backend points to another
- the operator attempted to connect through the public IP instead of using Cloud SQL Proxy or the Cloud Run socket path

### 19.6 Fast Diagnosis Commands

Useful commands when something looks wrong:

Check the real database list:

```bash
gcloud sql databases list --instance=orchestrator-sql
```

Check the Cloud Run service URL:

```bash
gcloud run services describe backend-adk --region europe-west1 --format='value(status.url)'
```

Check recent backend logs:

```bash
gcloud run services logs read backend-adk --region europe-west1 --limit=100
```

Check frontend URL:

```bash
gcloud run services describe frontend-adk --region europe-west1 --format='value(status.url)'
```

Check Cloud SQL instance state:

```bash
gcloud sql instances describe orchestrator-sql
```

### 19.7 Pre-Demo Sanity Checklist

Before sharing the link publicly:

1. open the frontend URL in a clean browser session
2. log in with the seeded admin account
3. verify employee accounts can also log in
4. create a sample client and project
5. confirm project planning artifacts appear
6. send and accept at least one team invite
7. update one employee checkpoint and confirm progress changes on both employee and admin views
8. verify client-facing status and payment sections render
9. check `/docs` for backend availability
10. check backend logs for database or auth errors

### 19.8 Git Sync Sequence Before A Fresh Push

When you want to sync your branch with `main` safely:

1. commit or stash local changes
2. fetch remote updates
3. rebase your feature branch on top of `origin/main` or `origin/pankaj-dev`, whichever is your true integration branch
4. resolve conflicts locally
5. run quick verification
6. push the updated feature branch

Example:

```bash
git checkout feature/secure-multitenant-refactor
git fetch origin
git rebase origin/main
git push --force-with-lease origin feature/secure-multitenant-refactor
```

If `pankaj-dev` is your real release branch, replace `origin/main` with `origin/pankaj-dev`.

## 20. Summary

This repository now represents a more complete product story:

- structured intake
- agentic planning
- staffing and risk analysis
- secure tenant-aware execution
- client-safe reporting
- employee growth tracking
- project history and final reporting
- mirrored Google-oriented backend support

That combination is the core narrative to present during judging, reviews, or deployment planning.
