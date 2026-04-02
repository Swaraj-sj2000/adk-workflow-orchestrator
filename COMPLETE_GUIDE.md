# 🎯 AI Workforce Orchestrator - Complete Guide

**All-in-one documentation for setup, usage, testing, and deployment.**

---

## 📑 Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Setup & Installation](#setup--installation)
4. [Quick Start (5 min)](#quick-start-5-min)
5. [Using the System](#using-the-system)
6. [Testing Complete Workflow](#testing-complete-workflow)
7. [Deployment & Hosting](#deployment--hosting)
8. [Troubleshooting](#troubleshooting)
9. [API Reference](#api-reference)

---

## Overview

**AI Workforce Orchestrator** is an autonomous project management platform that:
- Shifts project management decisions from humans to intelligent agents
- Enables one admin to orchestrate multiple concurrent projects
- Uses AI for planning, staffing, risk assessment, and execution
- Falls back to deterministic logic when LLMs unavailable
- Maintains human oversight through confidence scoring and escalation gates

### Who It's For
- Organizations managing multiple concurrent client projects
- Consulting/services teams handling diverse project scopes
- Distributed teams requiring minimal real-time coordination
- Teams experimenting with autonomous workflows

### Key Features
- ✅ **Multi-Agent Orchestration** - 7 specialized AI agents (Intake, Planning, Staffing, Risk, Execution, Communication, Escalation)
- ✅ **Intelligent Staffing** - Recommends team members based on skills, availability, capacity
- ✅ **Risk Management** - Flags blockers, capacity issues, delivery risks
- ✅ **Autonomous Execution** - Tasks auto-assigned to approved members
- ✅ **Human Oversight** - Admin approval gates, confidence scoring, escalation alerts
- ✅ **Multi-Tenant Support** - Isolate data by organization
- ✅ **Employee Dashboards** - Team members see their assignments and workload
- ✅ **Admin Dashboards** - Project metrics, team health, agent decisions
- ✅ **Light/Dark Theme** - Toggle between light and dark mode (saved per user)

---

## System Architecture

### Technology Stack
- **Backend**: FastAPI (Python 3.10+) on port 8000
- **Frontend**: React 18 + Vite on port 3000
- **Database**: SQLite with SQLAlchemy ORM (for dev/test)
- **Auth**: JWT tokens with bcrypt hashing
- **Multi-tenant**: Organization-scoped data isolation

### Core Models
- **Organization** - Tenant workspace
- **AuthUser** - Multi-tenant user (UUID)
- **EmployeeProfile** - Team member with skills/capacity
- **Project** - Scoped to organization
- **Task** - Work item with dependencies
- **TaskAssignment** - Link task to employee
- **WorkflowRun** - Records agent orchestration runs
- **AgentRun** - Individual agent execution
- **DecisionLog** - Tracks agent decisions & confidence

### Multi-Agent Pipeline
```
User Request (text)
    ↓
[Intake Agent] (confidence: 0.55-0.85)
  - Parse request into structured project brief
  - Extract scope, constraints, requirements
    ↓
[Planning Agent] (confidence: 0.70-0.90)
  - Break brief into 5-10 sequential tasks
  - Estimate effort, identify dependencies
    ↓
[Staffing Agent] (confidence: 0.75-0.95)
  - Rank employees for each task
  - Calculate assignment confidence (skills, availability, capacity)
    ↓
[Risk Agent] (confidence: 0.70-0.90)
  - Assess delivery risk
  - Flag capacity issues, blockers, schedule risks
    ↓
[Execution Coordinator] (confidence: 0.75-0.90)
  - Create execution-ready queue
  - Separate autonomous vs. review-required tasks
    ↓
[Communication Agent] (confidence: 0.60-0.80)
  - Draft messages for employees, admins, clients
  - Summarize project update
    ↓
[Escalation Agent] (confidence: 0.80-0.95)
  - Apply escalation policy
  - Determine if autonomous or needs human approval
    ↓
Result: WorkflowRun with all decisions, tasks, assignments
```

---

## Setup & Installation

### Prerequisites
```bash
Python 3.10+
Node.js 18+
SQLite3
```

### Backend Setup
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Seed test data (create org, 11 users, 10 employees with skills)
python seed_test_data.py

# Expected output:
#  ✅ 11 users created
#  ✅ 10 employees seeded (Solution Architect, AI Engineer, etc.)
#  ✅ Organization 'Seed Org' created

# Start backend server
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# Output: ✅ Uvicorn running on http://0.0.0.0:8000
```

### Frontend Setup
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
# Output: ✅ Vite running on http://localhost:3000
```

### Default Credentials
**Admin**:
- Email: `swaraj@orchestrator.ai`
- Password: `admin123`

**Team Members** (all use password `team123456`):
- `amira.khan@orchestrator.ai` - Solution Architect
- `arjun.rao@orchestrator.ai` - AI Engineer
- `neha.gupta@orchestrator.ai` - Backend Engineer
- `yash.patel@orchestrator.ai` - Frontend Engineer
- `sofia.dsouza@orchestrator.ai` - QA Automation Engineer
- `ibrahim.shaikh@orchestrator.ai` - Project Coordinator
- `meera.nair@orchestrator.ai` - Client Success Manager
- `daniel.lee@orchestrator.ai` - DevOps Engineer
- `kavya.reddy@orchestrator.ai` - Data Engineer
- `lucas.joseph@orchestrator.ai` - Prompt Engineer

---

## Quick Start (5 min)

### 1. Start Servers
```bash
# Terminal 1: Backend
cd backend && python seed_test_data.py && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Ready for testing
```

### 2. Login to Admin Dashboard
- Open http://localhost:3000
- Login: `swaraj@orchestrator.ai` / `admin123`
- See dashboard with 10 available team members

### 3. Run Your First Workflow
- Click **"Multi-Agent"** in navbar
- Enter request: `"build a login page"`
- Budget: `2500`, Priority: `medium`
- Check **"Persist project + task graph"`
- Click **"Run Multi-Agent Workflow"**
- ✅ In 3-5 seconds, workflow completes with:
  - 5 tasks created
  - 5 team assignments with high confidence (0.85-0.95)
  - All agent decisions captured

### 4. View Results
- Go to **"Projects"**
- Click **"Open Status"** on the project
- See tasks, team assignments, risk assessment from agents

### 5. Delete Test Projects (optional)
- In Projects, click **"Delete"** on any project to clean up
- (Delete button available to admins only)

---

## Using the System

### Theme Toggle (Light/Dark Mode)
**Accessible to all users** - Look for the 🌙 or ☀️ button in the top navigation bar

**How to use**:
1. Click the theme toggle button (moon/sun icon) in the navbar
2. The theme preference is automatically saved to your browser
3. Light mode: Clean, bright interface
4. Dark mode: Easy on eyes for low-light environments

**Theme persists** across sessions - Your preference won't change when you logout/login.

---

### Admin Dashboard
**Purpose**: Operational overview and control center

**Shows**:
- Active projects (count)
- Completed projects
- Available team members
- Average workload %
- Projects waiting approval

**Actions**:
- Create new manual project
- Refresh metrics

### Projects Panel
**Purpose**: Manage all projects, approve plans, track status

**For each project**:
- Project name and ID
- Current status (planning / executing / completed)
- Team assignments with confidence scores
- Phase progress (%)
- Approval status

**Admin Actions**:
- View project details
- Approve team plan (AI recommended)
- Reject and request revision
- Delete project (with confirmation)

### Team Dashboard
**Purpose**: Monitor employee capacity, skills, and individual task tracking

**Shows per employee**:
- Name, email, role, department
- Primary skills with proficiency scores
- Current workload % and available hours
- Active projects list
- **Active tasks** with:
  - Task title and project
  - Progress % with visual bar
  - Hours logged vs. estimated
  - Status (on-track ✅ or at-risk ⚠️)
  - Blockers count (if any 🔴)

**How to use it**:
1. Click "Team Dashboard" from nav
2. Click any team member from the list
3. Scroll down to "Active Tasks" section
4. See real-time task progress, blockers, and workload per task

**Example view**:
```
Arjun (Backend Developer)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Active Tasks:

📌 Build Authentication API (Project: CCTV Fire Detection)
   Progress: 60% ████░░░░░░  | Hours: 12.5 / 20h  | ✅ On Track

📌 Implement Email Alerts (Project: CCTV Fire Detection)
   Progress: 0% ░░░░░░░░░░  | Hours: 0 / 15h      | 🔴 2 blockers
```

### Agentic Dashboard (Decisions)
**Purpose**: Monitor AI agent health and decisions

**Shows**:
- Total decisions made by agents
- Automation level (% autonomous vs manual)
- Average confidence score
- Low-confidence alerts (< 0.70)
- Agent decision history
- Escalation alerts

### Multi-Agent Workbench

**What It Is**:
A **debugging & visibility tool** for understanding how the autonomous agent system works. It lets you manually trigger the complete agent workflow and **watch each agent's decision in real-time**.

**How It's Different from Creating a Project**:

| Aspect | Normal Project Creation | Multi-Agent Workbench |
|--------|------------------------|----------------------|
| **Trigger** | User creates project on dashboard | User manually executes workflow |
| **What You See** | Final result only | Each agent's work step-by-step |
| **Agent Outputs** | Hidden (happens in background) | Visible with confidence scores |
| **Use Case** | Operational: "Let's build this project" | Learning: "Show me how you think" |
| **Persistence** | Project saved automatically | Optional (checkbox to persist) |
| **Timing** | Background async | Real-time sequential |

**Example Workflow Output** (you see each step):
```
1️⃣ Intake Agent
   - Parsed: "Build fire detection system with email alerts"
   - Identified roles: Backend Dev, ML Engineer, DevOps
   - Confidence: 0.92 ✅

2️⃣ Planning Agent
   - Created 7 tasks with dependencies
   - Task order: [Setup → Data Prep → Model Training → API → Testing → Deploy → Monitoring]
   - Confidence: 0.88 ✅

3️⃣ Staffing Agent
   - Recommended: Arjun (Backend), Ahmed (ML), Neha (DevOps)
   - Match score: 0.85, 0.90, 0.87
   - Confidence: 0.86 ✅

4️⃣ Risk Agent
   - Detected: "Model training may take 5+ days (deadline: 10 days) ⚠️"
   - Mitigation: Start data prep immediately
   - Confidence: 0.79 ⚠️

5️⃣ Escalation Agent
   - Overall system confidence: 0.85 (above threshold)
   - Decision: Proceed autonomously ✅
   - Confidence: 0.91 ✅
```

**Why Use It?**

1. **Understand agent reasoning** — See WHY the system makes task breakdowns, team assignments, risk calls
2. **Debug issues** — If a normal project isn't working right, use the workbench to see what each agent decided
3. **Test new agents** — When you add custom agents, use workbench to verify they're working
4. **Learning** — Understand how confidence scores work and what triggers escalations
5. **Demos** — Show stakeholders/clients how the autonomous system thinks

**Workflow Form**:
- Project description (text)
- Budget (dollars)
- Priority (low / medium / high)
- Deadline (optional)
- **⚠️ Persist project checkbox** — IMPORTANT:
  - ✅ **CHECKED** = Creates a NEW project in the system (saves results)
  - ❌ **UNCHECKED** = Just shows agent outputs, **doesn't create anything** (test run)

**Use Cases**:

1. **Test Run (Unchecked)** 
   - You want to see "How would agents handle this description?"
   - Results shown but **nothing saved**
   - Perfect for: Understanding agent reasoning, debugging, learning

2. **Create Project (Checked)**
   - Results saved as new project in system
   - Team gets invitations
   - Tasks appear on dashboards
   - Perfect for: Actually starting work

**💡 Important Distinction**:
- Workbench is **only for NEW projects** right now
- If you want to see agent reasoning for an **existing project**, use the **Decisions tab** in that project (shows all past agent decisions)
- Workaround: To re-run agents on existing project, copy its description → test in workbench with unchecked persist → see what they'd recommend

**Results after execution**:
- All 7 agent outputs with confidence scores
- Confidence reasoning for each decision
- Generated task breakdown (5-10 tasks typically)
- Team assignments with match scores
- Risk assessment + suggested mitigations
- Communication drafts
- Escalation decision
- Next recommended actions

**Approval**:
- Review proposed assignments
- If satisfied: Click **"Approve And Continue"** → Tasks assigned, project starts
- Or modify and resubmit

---

## Testing Complete Workflow

### Test Suite 1: Authentication
```bash
# Admin login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"swaraj@orchestrator.ai","password":"admin123"}' | jq '.access_token'

# Store token for next requests
TOKEN="<paste_token_here>"

# Verify token works
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/system/admin-dashboard | jq '.team_size'
# Expected: 10
```

### Test Suite 2: Multi-Agent Workflow
```bash
# Run complete workflow
curl -X POST http://localhost:8000/multi-agent/workflows/intake \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "build a mobile app with push notifications",
    "budget": 50000,
    "priority": "high",
    "persist_project": true
  }' | jq '{status: .status, project_id: .project_id, task_count: (.shared_context.execution_plan.tasks | length)}'

# Expected:
# {
#   "status": "completed",
#   "project_id": 1,
#   "task_count": 8
# }
```

### Test Suite 3: Project Operations
```bash
# List all projects
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects | jq '.[] | {id, name, status}'

# Get project details
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects/1/status | jq '.name, .status, .approval_status'

# Delete project (test cleanup)
curl -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects/1 | jq '.success'
# Expected: true
```

### Test Suite 4: Team & Assignments
```bash
# List employees
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/employees | jq '.employees | length'
# Expected: 10

# Get employee details
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/employees/1 | jq '{name: .full_name, skills: .skills}'

# Get project assignments
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects/1/assignments | jq '.assignments[] | {task_id, employee_id, confidence}'
```

### Test Suite 5: Decisions & Escalation
```bash
# List all agent decisions
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/decisions | jq '.decisions | length'

# Get workflow details
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/workflows/1 | jq '{type: .workflow_type, status: .status, agent_count: (.agent_runs | length)}'
```

### Full Test Automation
```bash
#!/bin/bash
set -e

TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"swaraj@orchestrator.ai","password":"admin123"}' | jq -r '.access_token')

echo "✅ Auth: Token obtained"

WORKFLOW=$(curl -s -X POST http://localhost:8000/multi-agent/workflows/intake \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"request_text":"test project","budget":1000,"priority":"medium","persist_project":true}')

PROJECT_ID=$(echo "$WORKFLOW" | jq '.project_id')
echo "✅ Workflow: Project $PROJECT_ID created"

DELETED=$(curl -s -X DELETE -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects/$PROJECT_ID | jq '.success')

[[ "$DELETED" == "true" ]] && echo "✅ Delete: Project deleted successfully" || echo "❌ Delete failed"
```

---

## Deployment & Hosting

### Option 1: Render.com (Free Tier)
1. Push code to GitHub
2. Create new Web Service → Connect GitHub repo
3. **Backend**:
   - Runtime: Python 3.10
   - Build: `pip install -r requirements.txt`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. **Frontend**:
   - Build: `npm run build`
   - Start: `npm run preview`
5. Set environment variables:
   - `DATABASE_URL=postgres://...` (use Render Postgres addon)
   - `SECRET_KEY=<your_jwt_secret>`

### Option 2: Railway.app
1. Connect GitHub repo
2. Add Python service (backend)
3. Add Node service (frontend)
4. Add Postgres database
5. Railway auto-detects and deploys

### Option 3: Replit
1. Import from GitHub
2. Create `.replit` file:
```
run = ["bash", "start.sh"]
```
3. Create `start.sh`:
```bash
cd backend && python seed_test_data.py && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
cd frontend && npm run dev
```
4. Hit Run button

### Database Migration (Dev → Production)
```bash
# Export SQLite
sqlite3 backend/agentic_orchestrator.db ".dump" > backup.sql

# For Postgres (production):
psql postgres://<user>:<pass>@<host>/<db> < backup.sql

# Or use Render's built-in backup/restore
```

---

## Troubleshooting

### Issue: "Module not found" on startup
**Solution**: Ensure all models are imported in [app/main.py](backend/app/main.py#L25-L37)
```python
from app.models import (
    _user, _project, _agent, _task,
    _employee_profile, _employee_metrics,
    _task_dependency, _task_assignment,
    _decision_log, _blocker,
    _task_progress, _availability,
    _event_queue, _meeting, _client_profile,
    _checkpoint, _communication,
    _performance_point, _audit_log,
    _workflow_run, _agent_run,
    _organization, _auth_user, _employee_invite
)
```

### Issue: 401 Unauthorized on admin endpoints
**Solution**: Clear browser storage and re-login
```bash
# Browser console:
localStorage.removeItem('token')
localStorage.removeItem('user')
# Refresh page and login again
```

### Issue: "NOT NULL constraint failed" on project creation
**Solution**: Ensure organization_id is set. Already fixed in [_multi_agent_orchestrator.py#L95](backend/app/services/_multi_agent_orchestrator.py#L95)

### Issue: Delete button returns 500 error
**Solution**: Fixed in latest version - handles cascade deletes automatically. If still failing, check logs:
```bash
docker logs <container-id>  # or check terminal where server runs
```

### Issue: Frontend won't connect to backend
**Solution**: Check CORS settings in [app/main.py](backend/app/main.py#L42-L47)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to ["http://localhost:3000"] in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Workflows not executing any agents
**Solution**: Check if LLM service is available - system falls back to deterministic logic. View logs:
```python
# In agent output, look for "Used deterministic fallback..."
```

---

## API Reference

### Authentication
```
POST /api/v1/auth/login
  Body: {"email": str, "password": str}
  Returns: {"access_token": str, "token_type": "bearer"}
  
Headers: Authorization: Bearer <token>
```

### Projects
```
GET    /api/v1/projects              # List all projects
POST   /api/v1/projects              # Create project
GET    /api/v1/projects/{id}         # Get project
GET    /api/v1/projects/{id}/status  # Get project with status
DELETE /api/v1/projects/{id}         # Delete project (admin only)
POST   /api/v1/projects/{id}/team-approval  # Approve team plan
```

### Tasks
```
GET    /api/v1/projects/{id}/tasks   # List project tasks
POST   /api/v1/projects/{id}/tasks   # Create task
GET    /api/v1/tasks/{id}            # Get task
PUT    /api/v1/tasks/{id}            # Update task
DELETE /api/v1/tasks/{id}            # Delete task
```

### Employees
```
GET    /api/v1/employees             # List all employees
GET    /api/v1/employees/{id}        # Get employee details
GET    /api/v1/employees/{id}/availability  # Get availability
```

### Workflows & Agents
```
POST   /multi-agent/workflows/intake # Run intake workflow
GET    /multi-agent/workflows        # List workflow runs
GET    /multi-agent/workflows/{id}   # Get workflow details
```

### Admin
```
GET    /system/admin-dashboard       # Dashboard metrics
GET    /api/v1/decisions             # List all decisions
GET    /api/v1/agents/health         # Agent health metrics
```

---

## Support & Contributing

- **Issues**: Open GitHub issues or email support
- **Contributing**: See CONTRIBUTING.md for guidelines
- **License**: MIT - See LICENSE file

---

**Last Updated**: April 2, 2026 | **Version**: 2.0-stable
