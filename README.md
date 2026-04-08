# AI Workforce Orchestrator

AI Workforce Orchestrator is a multi-tenant project delivery platform built for AI-assisted execution management. It combines FastAPI, React, tenant-aware security, employee invite workflows, checkpoint-driven progress tracking, client-facing delivery reporting, and a layered agentic orchestration model that can run in a standard backend or a Google ADK / Vertex AI-oriented backend.

This repository currently contains two parallel backend tracks:

- `backend/`
  The main application backend for the current product flow.
- `backend_adk/`
  A Google-oriented backend variant that preserves the same product behavior while keeping its ADK / Vertex AI service path intact.

## Why This Project Stands Out

The product is not only a task tracker. Its USP is that it turns messy project intake into a governed delivery system:

- AI-assisted intake converts a business request into a structured execution plan.
- staffing logic maps tasks to employees based on skills, availability, and load.
- invite-driven team formation keeps access and ownership explicit.
- checkpoint-level execution gives traceable progress instead of vague task states.
- client updates stay business-facing instead of exposing raw technical noise.
- tenant-aware filtering and backend-side validation keep organizations isolated.
- completion automatically frees delivery capacity and preserves the project as history with a generated report.

## Core Product Features

- multi-tenant user, project, task, team, and invite isolation
- JWT-based authentication with tenant enforcement
- role-based access for admin, employee, and client users
- email-based team invites with pending invite linking at registration time
- AI-assisted project planning with tasks, subtasks, role clusters, and execution guidance
- employee self-service profile updates for skills, duty hours, and leave state
- automated experience point tracking, levels, and performance metrics
- client-facing delivery reports, plan briefs, USP summaries, and payment visibility
- checkpoint-based project progress tracking
- completion archiving with generated final reporting and released employee capacity
- basic rate limiting, input validation, duplicate protection, and action logging
- light/dark theme support with login-screen isolation

## How The Platform Works

### 1. Admin Creates A Project

The admin provides:

- project title
- business description
- budget, priority, deadline
- existing or new client information
- initial payment state

The backend then:

1. validates the payload using schemas
2. verifies tenant ownership and duplicate-project rules
3. resolves or creates the client profile
4. parses the intake using `LLMService`
5. builds role clusters and recommended team slots
6. seeds tasks, subtasks, and execution metadata
7. stores business-facing and admin-facing guidance

### 2. Team Formation

Admins can invite employees by email into a project team.

- if the employee already exists, the invite appears immediately in that employee dashboard
- if the employee does not exist yet, the invite stays pending by email
- once the employee registers with that email, the invite is linked automatically
- once accepted, the employee is added to the team and receives role-aligned work immediately

### 3. Employee Execution

Employees see:

- who they are in the system
- their employee ID, role, level, and experience points
- duty hours and leave state
- active invites
- assigned tasks
- checkpoint checklists
- blockers and AI lead escalation path
- active project history and completed project history

Checkpoint completion updates:

- task completion percentage
- project completion percentage
- employee experience points
- employee performance metrics
- project notifications and reporting state

### 4. Client Visibility

Clients get a business-facing workspace with:

- company and contact identity
- plan brief
- USP summary
- feature highlights
- delivery status
- today’s status
- payment status and payment update history
- final project report once delivery is complete

### 5. Completion And History

When delivery reaches completion:

- the project is marked `completed`
- employee assignment load is released
- the project moves out of the active set into history
- a generated final report is stored for admin and client views
- payment state remains visible until fully settled

## Agentic Workflow

The repo includes an explicit multi-agent orchestration layer in `backend/app/services/_multi_agent_orchestrator.py`.

### Intake Workflow

The intake workflow runs these agents in sequence:

1. `IntakeAgent`
   Parses the raw request into a structured brief using `LLMService`.
2. `PlanningAgent`
   Converts the brief into ordered tasks, task dependencies, and a project summary.
3. `StaffingAgent`
   Scores employees against tasks using skills, availability, and capacity.
4. `RiskAgent`
   Flags delivery risks from complexity, staffing gaps, and load pressure.
5. `ExecutionCoordinatorAgent`
   Decides which tasks can start autonomously and which need review.
6. `CommunicationAgent`
   Drafts assignment, admin, and client-facing communication artifacts.
7. `EscalationAgent`
   Applies escalation policy to determine whether human review is required.

### Live Execution Loop

The execution loop runs against a real project state:

1. `ProjectObserverAgent`
   Reads project, task, assignment, blocker, and progress state from the database.
2. `DeliveryReviewAgent`
   Uses monitoring signals to assess delays, blockers, and project health.
3. `RebalanceAgent`
   Suggests reassignment and staffing correction actions.
4. `LoopCommunicationAgent`
   Drafts follow-up updates based on live execution conditions.
5. `LoopEscalationAgent`
   Determines whether the system should continue autonomously or stop for review.

### What Gets Persisted

The orchestrator writes and uses:

- `workflow_runs`
- `agent_runs`
- `decision_logs`
- `communications`
- `audit_logs`
- project/task/task-assignment state

That means the agentic flow is inspectable, not just inferred from the UI.

## Security And Stability

The current stack includes:

- JWT expiry and signature validation
- tenant-aware request context extraction
- backend-enforced RBAC
- Pydantic schema validation for common inputs
- email normalization and invite deduplication
- duplicate active project prevention
- rate limiting middleware
- transaction-backed critical flows such as invite acceptance and project deletion
- defensive checks for tenant mismatch, unauthorized task access, and duplicate actions

The code also includes runtime additive schema handling for careful upgrades of existing databases without a full migration framework.

## Logging And Debugging

The application uses structured logging paths across:

- request/response timing in `app/main.py`
- project creation and lifecycle actions
- invite creation and acceptance
- workflow execution and agent stages
- delivery review, risk, and escalation logic

Useful debugging surfaces:

- HTTP logs from middleware
- Swagger/OpenAPI docs at `https://<backend-host>/docs`
- workflow and decision records in the database
- project status panels in the UI
- notifications generated from payment, invite, progress, and XP events

## Repository Layout

```text
.
├── backend/                  # main FastAPI backend
├── backend_adk/              # Google ADK / Vertex AI compatible backend variant
├── frontend/                 # React + Vite frontend
├── README.md
└── COMPLETE_GUIDE.md
```

## Deployment URLs

Use placeholders in docs and environment configuration rather than hardcoding localhost:

- frontend: `https://<frontend-host>`
- backend: `https://<backend-host>`
- backend docs: `https://<backend-host>/docs`
- backend ADK: `https://<backend-adk-host>`

## Where To Read More

Use [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for:

- detailed architecture
- full data flow
- backend vs backend_adk explanation
- security and validation details
- logging and debugging guidance
- deployment notes and operator runbook
- current Cloud Run URLs and Cloud SQL reference
- testing and rollout checklist
