# AI Workforce Orchestrator (AutoPM Hackathon Build)

Autonomous project operations system designed to reduce or remove day-to-day PM overhead.

This build supports:
- Project intake from natural language
- Task generation and team assignment
- Employee response loop (accept / deny / negotiate)
- Execution simulation with blockers
- Daily digest generation
- Client update drafting
- Project closure with performance points

## Tech Stack

- Backend: FastAPI + SQLAlchemy + SQLite
- Frontend: React + Vite
- LLM: LangChain + HuggingFace (with deterministic fallback if token is missing)

## Project Structure

```text
backend/
  app/
    api/routes/
    models/
    services/
frontend/
  src/components/
SETUP_GUIDE.md
SYSTEM_ARCHITECTURE.md
```

## Quick Start

### 1) Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Optional LLM setup (recommended for demo):

```bash
export HUGGINGFACEHUB_API_TOKEN="hf_xxx_your_token_here"
export HF_MODEL_ID="mistralai/Mistral-7B-Instruct-v0.3"
```

Run backend:

```bash
uvicorn app.main:app --reload --port 8000
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

Open: `http://localhost:3000`

## Login and Demo Flow

1. Register a user with role `admin`
2. Login
3. Open `AutoPM` tab
4. Run this sequence:
   - `Run Intake`
   - `Assign Team`
   - `Submit Response` (accepted/denied/negotiating)
   - `Run Simulation`
   - `Generate Daily Digest`
   - `Client Update`
   - `Close Project` (after all tasks are done)

## Key AutoPM APIs

- `POST /autopm/intake`
- `POST /autopm/projects/{project_id}/assign`
- `POST /autopm/assignments/{assignment_id}/respond`
- `POST /autopm/projects/{project_id}/simulate`
- `GET /autopm/digest/daily`
- `POST /autopm/projects/{project_id}/client-update`
- `POST /autopm/projects/{project_id}/close`

Other useful APIs:
- `GET /projects/`
- `GET /tasks/`
- `GET /task-assignments`
- `GET /decisions/`

## Notes

- If HuggingFace token is not set, system still works with deterministic fallback logic.
- Root docs:
  - `SETUP_GUIDE.md`
  - `SYSTEM_ARCHITECTURE.md`
