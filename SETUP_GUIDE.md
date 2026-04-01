# Setup Guide

## Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python seed_test_data.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend

```bash
cd frontend
npm install
npm run dev
```

## Optional LLM Configuration

The system uses LangChain + Hugging Face for LLM-assisted planning and communication if you provide a Hugging Face token.

```bash
export HUGGINGFACEHUB_API_TOKEN="hf_your_token"
export HF_MODEL_ID="mistralai/Mistral-7B-Instruct-v0.3"
```

Without a token, the product still runs using deterministic fallback logic.

## URLs

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:8000`
- Backend docs: `http://localhost:8000/docs`

## Login

- Admin email: `swaraj@orchestrator.ai`
- Admin password: `admin123`

## Seed Result

Running `python seed_test_data.py` resets the database and seeds:

- 1 admin
- 10 employees
- 0 projects
- 0 tasks
- 0 clients

All seeded employees start free and available so you can create the first project manually as admin.
