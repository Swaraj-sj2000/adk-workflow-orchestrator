# 🤖 AI Workflow Orchestrator

> *"Natural language in. Executed workflow out. Remembered forever."*

A multi-agent AI system built with **Google ADK** and **Gemini 2.5 Flash**,
deployed on **Google Cloud Run**. Converts business instructions into fully
executed, database-backed workflows with three layers of memory.

---

## What It Does

Tell it what you need to get done. It creates the tasks, schedules the
meetings, writes the documents, stores everything in a database, and
remembers you the next time you come back.

```
You: "Onboard a new client for an AI consulting project"

System:
  ✅ 4 tasks created with deadlines and priorities
  ✅ 2 meetings scheduled with participants
  ✅ 2 documents written and stored
  ✅ Everything linked to your user profile
  ✅ Plan cached — next similar request is instant
```

---

## Memory Architecture

```
┌─────────────────────────────────────────────────┐
│              THREE MEMORY LAYERS                │
├─────────────────────────────────────────────────┤
│                                                 │
│  SESSION MEMORY (ADK state dict)                │
│  Scope: one conversation                        │
│  Holds: USER_INPUT, WORKFLOW_ID, USER_NAME,     │
│         execution_plan, PLAN_SOURCE             │
│  How: tool_context.state — shared across        │
│       all agents in the pipeline                │
│                                                 │
│  USER MEMORY (SQLite users + workflows)         │
│  Scope: one person, across all sessions         │
│  Holds: profile, preferences, full history      │
│  How: email → user_id → linked workflows        │
│       Planner reads history as context          │
│                                                 │
│  GLOBAL MEMORY (workflow_templates)             │
│  Scope: all users, org-wide                     │
│  Holds: standard plans for common workflows     │
│  How: trigger_key fuzzy match → skip planner    │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## Plan Resolution — Cache → Template → LLM

Every incoming instruction goes through this decision tree
before the planner agent runs:

```
User instruction arrives
        │
        ▼
  Exact match in workflow_cache?
        │ YES → use cached plan (0 LLM calls for planning)
        │ NO
        ▼
  Keyword match in workflow_templates?
        │ YES → resolve dates + use template (0 LLM calls)
        │ NO
        ▼
  Planner agent generates plan (1 LLM call)
        │
        ▼
  Plan saved to cache for next time
```

For common enterprise workflows (onboarding, launches, team setup)
the planner is skipped entirely after the first run.

---

## Agent Architecture

```
orchestrator (root_agent)
    ├── identify_user tool   → user profile + history into state
    ├── save_user_intent tool → resolve plan, create workflow record
    └── workflow_pipeline (SequentialAgent)
            ├── planner_agent      → JSON plan (or pass-through if cached)
            ├── task_agent         → create_task × N
            ├── scheduler_agent    → schedule_meeting × N
            ├── doc_agent          → generate_document × N
            └── summary_agent      → get_workflow_status → final report
```

---

## Database Schema

```
users              id | name | email | preferences | created_at
sessions           session_id | user_id | created_at
workflows          id | user_id | user_input | status | created_at
tasks              id | workflow_id | user_id | title | deadline | priority | status
meetings           id | workflow_id | user_id | title | datetime | participants
documents          id | workflow_id | user_id | title | content | created_at
workflow_cache     query_hash | user_input | plan_json | hit_count | created_at
workflow_templates id | name | trigger_key | plan_json | use_count | created_at
```

Every table has indexed foreign keys. All records trace back to a user and workflow.

---

## Project Structure

```
ai_workflow_orchestrator/
├── agent.py          ← agents + tool functions
├── memory.py         ← memory logic: session, user, cache, templates
├── database.py       ← SQLite schema + all CRUD helpers
├── __init__.py
└── requirements.txt
```

**Dependency rule:** agents call memory.py. memory.py calls database.py.
Agents never touch the database directly.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | Google ADK 1.14.0 |
| LLM | Gemini 2.5 Flash (Vertex AI) |
| Orchestration | SequentialAgent (5 sub-agents) |
| Memory | 3-layer: session + user + global |
| Caching | SQLite workflow_cache + org templates |
| Persistence | SQLite (4 core + 2 memory + 2 cache tables) |
| Hosting | Google Cloud Run (serverless) |
| Auth | IAM Service Account |

---

## Deployment

### Step 1 — Create directory
```bash
cd && mkdir ai_workflow_orchestrator && cd ai_workflow_orchestrator
cloudshell open-workspace ~/ai_workflow_orchestrator
```

### Step 2 — Create files
```bash
cloudshell edit __init__.py
cloudshell edit agent.py
cloudshell edit memory.py
cloudshell edit database.py
cloudshell edit requirements.txt
```

### Step 3 — Environment setup
```bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID \
  --format="value(projectNumber)")
SA_NAME=workflow-orchestrator-sa

cat <<EOF > .env
PROJECT_ID=$PROJECT_ID
PROJECT_NUMBER=$PROJECT_NUMBER
SA_NAME=$SA_NAME
SERVICE_ACCOUNT=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
MODEL=gemini-2.5-flash
EOF
```

### Step 4 — Enable APIs
```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  compute.googleapis.com
```

### Step 5 — Install + IAM
```bash
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt
source .env

gcloud iam service-accounts create ${SA_NAME} \
  --display-name="Service Account for AI Workflow Orchestrator"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/aiplatform.user"
```

### Step 6 — Deploy
```bash
source .env

uvx --from google-adk==1.14.0 \
adk deploy cloud_run \
  --project=$PROJECT_ID \
  --region=us-central1 \
  --service_name=ai-workflow-orchestrator \
  --with_ui \
  . \
  -- \
  --labels=project=ai-workflow-orchestrator \
  --service-account=$SERVICE_ACCOUNT
```

Answer **Y** then **y** when prompted.

---

## Demo Script

**Turn 1:** `hello`
→ System asks for email

**Turn 2:** `yourname@gmail.com`
→ New user: welcomed by name, asked for instruction
→ Returning user: greeted with history count

**Turn 3:** `Onboard a new client for an AI consulting project`
→ Pipeline executes (template match — planner skipped)
→ Full report with tasks, meetings, documents

**Turn 4 (same session):** `Plan a product launch for next month`
→ Different template match — different workflow, instant plan

**Turn 5 (new session, same email):**
→ System recognises you, shows previous workflow count

---

## Cleanup
```bash
gcloud run services delete ai-workflow-orchestrator \
  --region=us-central1 --quiet
gcloud artifacts repositories delete cloud-run-source-deploy \
  --location=us-central1 --quiet
```
