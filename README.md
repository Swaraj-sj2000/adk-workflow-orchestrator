# AI Workforce Orchestrator

An admin-first autonomous project operations platform designed to reduce the need for day-to-day human project management.

## What It Does

- Lets one admin manage multiple client projects
- Creates projects from a clean intake flow
- Tracks client state, approvals, tasks, payments, and employee involvement
- Exposes admin, team, and agentic dashboards
- Uses LangChain + Hugging Face for LLM-assisted planning and communication when configured
- Falls back to deterministic logic when no Hugging Face token is present

## Stack

- Backend: FastAPI + SQLAlchemy + SQLite
- Frontend: React + Vite
- LLM layer: LangChain + Hugging Face

## Run It

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Optional but recommended for LLM-powered planning:

```bash
export HUGGINGFACEHUB_API_TOKEN="hf_your_token"
export HF_MODEL_ID="mistralai/Mistral-7B-Instruct-v0.3"
```

Reset and seed the database:

```bash
python seed_test_data.py
```

Start the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API docs:

`http://localhost:8000/docs`

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

`http://localhost:3000`

## Seeded Access

Admin:

- Email: `swaraj@orchestrator.ai`
- Password: `admin123`

Team:

- 10 employees are seeded
- all employees start free with `0%` workload
- there are no seeded projects, tasks, or clients

## Starting State

After running `python seed_test_data.py`, the system is intentionally clean:

- 1 admin
- 10 available employees
- 0 projects
- 0 tasks
- 0 clients

That means you can log in as admin and create the first project yourself from the dashboard.
