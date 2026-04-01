# 🚀 Quick Start Testing (5 Minutes)

**Essential tests to verify everything works**

## Setup
```bash
# Terminal 1: Backend
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend
source venv/bin/activate
python seed_test_data.py
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend  
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/frontend
npm run dev

# Terminal 3: Testing (copy commands below)
```

---

## Test 1: Auth Works ✅
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"swaraj@orchestrator.ai","password":"admin123"}' | jq -r '.access_token')

curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/system/admin-dashboard | jq '.team_size'
```
**Expected**: `10`

---

## Test 2: Workflow Runs ✅
```bash
curl -s -X POST http://localhost:8000/multi-agent/workflows/intake \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "build a login page",
    "budget": 2500,
    "priority": "medium",
    "persist_project": true
  }' | jq '{status: .status, project_id: .project_id, workflow_id: .id}'
```
**Expected**:
```json
{
  "status": "completed",
  "project_id": 1,
  "workflow_id": 1
}
```

---

## Test 3: Project Created ✅
```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/projects/1 | jq '{name: .name, budget: .budget, tasks: .tasks | length}'
```
**Expected**:
```json
{
  "name": "build a login page",
  "budget": 2500,
  "tasks": 5
}
```

---

## Test 4: UI Login ✅
- Open http://localhost:3000
- Login: `swaraj@orchestrator.ai` / `admin123`
- **Expected**: See dashboard with "Team Size: 10"

---

## Test 5: UI Workflow ✅
- In admin dashboard, go to "Multi-Agent Workbench"
- Click "New Workflow"
- Enter: "build a payment system"
- Budget: 5000, Priority: High
- Click "Run"
- **Expected**: See workflow complete in 3-5 seconds

---

## ✅ All Pass?
System is ready! Run `TESTING_CHECKLIST.md` for comprehensive tests.
