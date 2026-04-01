# 🎯 AI Workforce Orchestrator

> An autonomous project operations platform that shifts project management decisions from humans to intelligent agents, enabling a single admin to orchestrate multiple client projects with minimal day-to-day coordination overhead.

**Created by**: [Swaraj](https://github.com) — AI Workforce Orchestrator Architect  
**Status**: Production-ready | **Version**: 2.0 | **License**: MIT

---

## 📋 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Usage Guide](#usage-guide)
- [API Reference](#api-reference)
- [Multi-Agent System](#multi-agent-system)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)

---

## 🎯 Overview

The **AI Workforce Orchestrator** is an autonomous project management system designed to:

- **Reduce admin burden** by automating 80-90% of coordination decisions
- **Scale project delivery** across multiple teams and clients simultaneously
- **Maintain human oversight** through confidence scoring and escalation gates
- **Integrate AI planning** using large language models (LLMs) for intelligent recommendations
- **Fall back gracefully** to deterministic logic when LLM services are unavailable

### Who It's For

- **Organizations** managing multiple concurrent client projects
- **Consulting/Services** teams handling diverse project scopes
- **Distributed teams** requiring minimal real-time coordination
- **Teams experimenting** with autonomous project workflows

### The Problem It Solves

Traditional project management requires constant human decision-making:
- Which team member should own this task?
- Is the project on track?
- Should we escalate this blocker?
- Has the client's requirement changed?

The Orchestrator **automates these decisions** using intelligent agents while maintaining clarity through checkpoints, decisions logs, and escalation workflows.

---

## ✨ Key Features

### Admin Dashboard
- **Project overview** with instant status visibility
- **Team management** with skill-based assignment recommendations
- **Client approval workflows** with configurable decision gates
- **Automated notifications** for approvals, blockers, and escalations
- **Decision audit trail** showing AI reasoning and human overrides

### Employee Workspace
- **Personalized task queue** with clear checkpoints and acceptance criteria
- **Concern escalation** to AI lead before admin involvement
- **Real-time progress tracking** with completion percentages
- **Blocker documentation** with suggested resolutions
- **Project invitations** with role clarity and scope visibility

### Client Portal
- **Project progress** in business language (not technical jargon)
- **Status updates** scheduled and auto-generated
- **Payment tracking** with milestone-based billing support
- **Communication log** of all decisions and updates

### Autonomous Agents

The system includes 13+ specialized agents:

| Agent | Role | Responsibility |
|-------|------|-----------------|
| **Intake** | Entry point | Convert client requests into structured project briefs |
| **Planning** | Work breakdown | Build tasks, dependencies, and execution milestones |
| **Staffing** | Allocation | Recommend team members based on skills & capacity |
| **Risk** | Health monitor | Detect delays, overload, blockers, and dependency issues |
| **Execution Coordinator** | Orchestrator | Choose next actions, trigger reassignments, manage workflow states |
| **Communication** | Messenger | Draft updates for team, clients, and admins |
| **Escalation** | Gatekeeper | Decide when confidence is too low to proceed autonomously |
| **Project Observer** | Analyst | Track project health metrics and trends |
| **Delivery Review** | QA | Validate task completion and handoff readiness |
| **Rebalance** | Optimizer | Suggest workload redistributions when team is overloaded |
| **Loop Communication** | Async update | Generate cycle-based status summaries |
| **Loop Escalation** | Escalation handler | Route unresolved concerns to human decision-makers |

---

## 🏗️ System Architecture

### High-Level Flow

```
Client Request
    ↓
Intake Agent (parse + structure)
    ↓
Planning Agent (break into tasks)
    ↓
Risk + Staffing Agents (feasibility check)
    ↓
Admin Approval Gate
    ↓
Team Acceptance (4-hour window)
    ↓
Execution Coordinator (assign tasks)
    ↓
[Loop: Monitoring → Risk Detection → Action]
    ↓
Delivery Review (validation)
    ↓
Project Complete
```

### Database Models (15+)

- **Projects & Tasks**: Hierarchical task tracking with dependencies
- **Team Management**: Employee profiles, skills, capacity, availability
- **Assignments**: Task-to-employee mappings with confidence scores
- **Decisions**: Audit trail of all AI and human decisions
- **Workflows**: Multi-stage project execution state machine
- **Communications**: Client updates, team notifications, alerts
- **Metrics**: Performance scoring, blockers, risks

### Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React 18 + Vite | Modern, fast admin/team/client UI |
| **Backend** | FastAPI | High-performance async API |
| **Database** | SQLAlchemy + SQLite | ORM with flexible schema |
| **LLM** | LangChain + HuggingFace | Intelligent planning & communication |
| **Worker** | Background tasks | Async event processing |

---

## 💻 Requirements

### System Requirements
- **Python**: 3.10+
- **Node.js**: 16+
- **RAM**: 4GB minimum (8GB recommended)
- **Disk**: 500MB for initial setup + project data

### Optional (for LLM Features)
- **HuggingFace API Token**: For LLM-powered planning
- **Recommended Model**: `mistralai/Mistral-7B-Instruct-v0.3`
- **SMTP Credentials**: For email alerts (configurable)

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/Swaraj-sj2000/adk-workflow-orchestrator.git
cd agentic_orchestrator
```

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Initialize database with test data
python seed_test_data.py
```

### 3. Start Backend Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**API Documentation**: http://localhost:8000/docs  
**ReDoc**: http://localhost:8000/redoc

### 4. Frontend Setup (new terminal)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

**Application**: http://localhost:3000

### 5. Login

**Admin Account**:
- Email: `swaraj@orchestrator.ai`
- Password: `admin123`

**Employee Accounts** (10 team members):
- All emails: `{firstname}.{lastname}@orchestrator.ai`
- All passwords: `team123456`
- Examples:
  - amira.khan@orchestrator.ai
  - arjun.rao@orchestrator.ai
  - neha.gupta@orchestrator.ai

---

## ⚙️ Configuration

### Environment Variables (Backend)

Create a `.env` file in the `backend/` directory:

```bash
# Database
DATABASE_URL=sqlite:///./app.db

# LLM Configuration (Optional)
HUGGINGFACEHUB_API_TOKEN=hf_your_token_here
HF_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.3
HF_TIMEOUT_SECONDS=60
HF_TEMPERATURE=0.2
HF_MAX_NEW_TOKENS=900

# Server
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true

# Security
SECRET_KEY=your-secret-key-here-change-in-production
ALGORITHM=HS256

# Email (Optional)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### Without LLM Token

The system **runs completely without an LLM token**. It has built-in deterministic fallbacks:

- Project parsing: Template-based structure extraction
- Task planning: Linear dependency-based scheduling
- Team recommendations: Skills + capacity-based matching
- Concern responses: Rule-based guidance

**Performance difference**: LLM-enabled systems show better task decomposition and more natural communication.

### Database Management

```bash
# Reset and reseed database
python backend/seed_test_data.py

# Run migrations (if using Alembic)
alembic upgrade head
```

---

## 📖 Usage Guide

### Admin Workflow

1. **Create Project**
   - Click "New Project" on admin dashboard
   - Paste client requirement text
   - System parses into: summary, tasks, role clusters
   - Review AI-recommended team draft

2. **Approve Team**
   - Review recommended employees
   - Accept or modify team composition
   - 5-minute approval window (configurable)

3. **Monitor Execution**
   - Track task progress across team
   - Watch for blockers and risks
   - Approve escalations or make overrides
   - Document decisions in audit trail

### Employee Workflow

1. **Accept Invitation**
   - Receive project invite with role & scope
   - Review planned tasks and checkpoints
   - Accept or reject within 4-hour window
   - If rejected → system finds replacement

2. **Work on Tasks**
   - See assigned tasks with clear checkpoints
   - Mark checkpoints complete as you progress
   - Each checkpoint = small traceable milestone
   - Flag concerns to AI lead (not admin directly)

3. **Checkpoints**
   - Not just broad tasks
   - Specific implementation steps (e.g., "Create email template for alerts")
   - Each includes acceptance criteria
   - Progress automatically rolls up to project level

### Client Workflow

1. **View Projects**
   - See business-friendly status summaries
   - Not technical task lists
   - Read schedules and payment info

2. **Receive Updates**
   - Auto-generated status emails
   - Escalations if critical decisions needed
   - Payment notifications at milestones

---

## 🔌 API Reference

### Base URL
```
http://localhost:8000
```

### Authentication
All endpoints require JWT token in header:
```
Authorization: Bearer <your_jwt_token>
```

### Key Endpoints

#### Projects
```
POST   /projects/                 # Create new project
GET    /projects/                 # List user's projects
GET    /projects/{id}/status      # Get project details
POST   /projects/{id}/team-approval   # Admin approve team
POST   /projects/{id}/invite-response # Employee accept/reject
DELETE /projects/{id}             # Delete project
```

#### Tasks
```
GET    /tasks/?project_id=1       # List tasks
POST   /tasks/                    # Create task
PATCH  /tasks/{id}/progress       # Update progress
POST   /tasks/{id}/blocker        # Report blocker
```

#### Team
```
GET    /employees/                # List all employees
GET    /employees/{id}/profile    # Get employee details
POST   /employees/{id}/metrics    # Update performance metrics
```

#### Decisions
```
GET    /decisions/?entity=project&id=1  # Get decision audit trail
POST   /decisions/                      # Log decision
```

### Example: Create Project

```bash
curl -X POST http://localhost:8000/projects/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CCTV Fire Detection",
    "description": "Build fire detection pipeline with YOLO model and email alerts",
    "budget": 50000,
    "priority": "high",
    "client_email": "client@company.com"
  }'
```

See **`http://localhost:8000/docs`** for interactive Swagger UI with all endpoints.

---

## 🤖 Multi-Agent System

### How Agents Work

Each agent is a **specialized worker** that:
1. Receives a **shared project context** (what's known so far)
2. Produces an **output payload** (what it decided)
3. Records **confidence score** (0-1, how sure it is)
4. Triggers **escalation if needed** (confidence < threshold)

### Agent Decision Flow

```
Input: Project context (current state)
    ↓
Agent processes with LLM or rules
    ↓
Output: Decision payload + confidence + reasoning
    ↓
Decision Log: Audit trail written to DB
    ↓
Check Confidence:
    - High (>0.85): Auto-proceed
    - Medium (0.7-0.85): Proceed with caution
    - Low (<0.7): Escalate to human
    ↓
Next Agent: Use output as part of context
```

### Adding Custom Agents

1. Create file: `backend/app/agents/_custom_agent.py`
2. Extend `BaseAgent`:
   ```python
   from app.agents._base import BaseAgent, AgentResult
   
   class CustomAgent(BaseAgent):
       agent_name = "custom_agent"
       role = "custom_role"
       stage = "custom_stage"
       
       def run(self, shared_context):
           # Your logic here
           return AgentResult(
               agent_name=self.agent_name,
               role=self.role,
               stage=self.stage,
               confidence=0.85,
               reasoning="Why I made this decision",
               output_payload={...},
               requires_human_review=False,
           )
   ```
3. Register in `MultiAgentOrchestrator`

---

## 📁 Project Structure

```
agentic_orchestrator/
├── backend/
│   ├── app/
│   │   ├── agents/               # 13+ specialized agent implementations
│   │   ├── api/routes/           # FastAPI route handlers (projects, tasks, etc.)
│   │   ├── core/                 # Security, config, dependencies
│   │   ├── db/                   # Database initialization
│   │   ├── models/               # SQLAlchemy ORM models (15+ tables)
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── services/             # Business logic layer
│   │   │   ├── _project_service.py       # Project workflow orchestration
│   │   │   ├── _llm_service.py           # LLM integration + fallbacks
│   │   │   ├── _assignment_engine.py     # Task-to-employee matching
│   │   │   ├── _multi_agent_orchestrator.py # Agent workflow engine
│   │   │   └── [8 more services]
│   │   ├── main.py               # FastAPI app initialization
│   │
│   ├── requirements.txt           # Python dependencies
│   ├── seed_test_data.py         # Database seeding script
│   ├── run_event_worker.py       # Background job processor
│   └── app.db                    # SQLite database (auto-created)
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx     # Admin overview
│   │   │   ├── EmployeeView.jsx  # Employee task workspace
│   │   │   ├── Projects.jsx      # Project management
│   │   │   ├── Decisions.jsx     # Decision logs
│   │   │   └── MultiAgentWorkbench.jsx  # Agent monitoring
│   │   ├── App.jsx               # Main router
│   │   └── main.jsx              # React entry point
│   │
│   ├── package.json              # NPM dependencies
│   ├── vite.config.js            # Vite configuration
│   └── index.html                # HTML template
│
├── README.md                     # This file
├── SETUP_GUIDE.md               # Detailed setup instructions
├── SYSTEM_ARCHITECTURE.md       # Technical architecture documentation
└── MULTI_AGENT_RESET_PLAN.md    # Agent system design & roadmap
```

---

## 🔍 Troubleshooting

### Backend Issues

**Issue**: `ModuleNotFoundError` on startup
```bash
# Solution: Ensure venv is activated and deps installed
source backend/venv/bin/activate
pip install -r backend/requirements.txt
```

**Issue**: Database errors
```bash
# Solution: Reset database
python backend/seed_test_data.py
```

**Issue**: Port 8000 already in use
```bash
# Solution: Use different port
uvicorn app.main:app --port 8001 --reload
```

### Frontend Issues

**Issue**: `npm: command not found`
```bash
# Solution: Install Node.js from nodejs.org
```

**Issue**: Port 3000 already in use
```bash
# Solution: Kill existing process or use different port
npm run dev -- --port 3001
```

**Issue**: API 404 errors
```bash
# Solution: Ensure backend is running on http://localhost:8000
# Check VITE_API_URL in frontend/.env if needed
```

### LLM Issues

**Issue**: "LLM integration unavailable"
```bash
# Normal - system falls back to deterministic logic
# To enable LLM:
export HUGGINGFACEHUB_API_TOKEN="hf_..."
export HF_MODEL_ID="mistralai/Mistral-7B-Instruct-v0.3"
# Then restart backend
```

**Issue**: HuggingFace token invalid
```bash
# Solution: 
# 1. Check token at https://huggingface.co/settings/tokens
# 2. Verify model exists and you have access
# 3. Check HF_TIMEOUT_SECONDS if timing out
```

---

## 🛠️ Development

### Project Standards

- **Code Style**: PEP 8 (Python), Prettier (JavaScript)
- **Type Hints**: Required for all Python functions
- **Git Commits**: Conventional Commits format
- **Testing**: Unit tests for services + integration tests for workflows

### Running Tests

```bash
# Backend unit tests
cd backend
pytest tests/

# Frontend tests
cd frontend
npm run test
```

### Debugging

**Backend Logging**:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Message", extra={"context": "value"})
```

**Frontend Console**:
```javascript
console.log("Debug:", data);
// Use React DevTools browser extension
```

### Common Development Tasks

```bash
# Format code
black backend/
prettier --write frontend/src

# Lint
flake8 backend/
eslint frontend/src

# Type check (Python)
mypy backend/app

# Build for production
cd frontend
npm run build
# Output in frontend/dist/
```

---

## 📋 Contributing

### Before You Begin

1. Check existing issues/PRs
2. Create branch: `git checkout -b feature/description`
3. Follow commit convention: `feat(module): description`

### Making Changes

1. **Backend changes**: Update models → Add schemas → Update services → Add routes
2. **Frontend changes**: Update components → Adjust styling → Test responsiveness
3. **Database changes**: Create migration, test reset, update seed script

### Testing Your Changes

```bash
# Backend
python -m pytest tests/ -v

# Frontend
npm run test -- --watch

# Manual testing
# - Run full stack locally
# - Test both happy path and error cases
# - Check database state after operations
```

### Pull Request Process

1. Write clear PR title and description
2. Link related issues
3. Ensure tests pass
4. Request review from maintainers
5. Squash commits before merge

---

## 📄 License

MIT License - See LICENSE file for details

---

## 📞 Support

- **Documentation**: See [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) for technical deep dives
- **Issues**: GitHub Issues tracker
- **Questions**: Create a Discussion or check existing Q&A

---

## 🎯 Roadmap

- [ ] Real-time WebSocket updates for live dashboards
- [ ] Mobile app for employee task acceptance
- [ ] Advanced role-based access control (RBAC)
- [ ] Integration with Jira, Slack, Microsoft Teams
- [ ] Machine learning-based skill recommendations
- [ ] Payment integration with Stripe/PayPal
- [ ] Multi-language support

---

**Made with ❤️ for autonomous project orchestration**
