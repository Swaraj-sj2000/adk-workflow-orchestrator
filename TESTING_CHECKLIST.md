# 🧪 Complete Testing Checklist - April 2, 2026

Test the complete AI Workforce Orchestrator system following these steps.

---

## ✅ Pre-Test: System Setup (5 min)

### Terminal 1: Backend
```bash
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend
source venv/bin/activate

# Reset and seed database
python seed_test_data.py
# OUTPUT: ✅ 11 users created, 10 employees ready

# Start server (keep running)
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
# OUTPUT: ✅ Uvicorn running on http://0.0.0.0:8000
```

### Terminal 2: Frontend
```bash
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/frontend
npm run dev
# OUTPUT: ✅ Vite running on http://localhost:3000
```

### Terminal 3: Testing
```bash
# Use this terminal for curl commands below
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator
```

---

## 📋 Test Suite 1: Authentication (5 min)

### Step 1.1: Admin Login
```bash
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"swaraj@orchestrator.ai","password":"admin123"}' | jq -r '.access_token')

echo "Token: ${ADMIN_TOKEN:0:30}..."
# ✅ Should see token starting with "eyJh..."
```

### Step 1.2: Verify Token Works
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/system/admin-dashboard | jq '.team_size'
# ✅ Should return: 10
```

### Step 1.3: Employee Login
```bash
EMPLOYEE_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"amira.khan@orchestrator.ai","password":"team123456"}' | jq -r '.access_token')

echo "Employee Token: ${EMPLOYEE_TOKEN:0:30}..."
# ✅ Should see token
```

---

## 🤖 Test Suite 2: Multi-Agent Workflow (10 min)

### Step 2.1: Run Intake Workflow
```bash
WORKFLOW=$(curl -s -X POST http://localhost:8000/multi-agent/workflows/intake \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "build a login page with email verification",
    "budget": 3000,
    "priority": "high",
    "persist_project": true
  }')

echo "$WORKFLOW" | jq '.'
# ✅ Should see:
#   - "status": "completed"
#   - "project_id": (should be a number)
#   - "workflow_type": "project_intake"

WORKFLOW_ID=$(echo "$WORKFLOW" | jq '.id')
PROJECT_ID=$(echo "$WORKFLOW" | jq '.project_id')
echo "Workflow: $WORKFLOW_ID, Project: $PROJECT_ID"
```

### Step 2.2: Verify Project Created
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/projects/$PROJECT_ID | jq '.name, .budget, .status'
# ✅ Should see:
#   "build a login page with email verification"
#   3000
#   "planning"
```

### Step 2.3: Verify Tasks Created
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/projects/$PROJECT_ID/tasks | jq '.tasks | length'
# ✅ Should return: 5+ (multiple tasks created from AI plan)

# View task details
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/projects/$PROJECT_ID/tasks | jq '.tasks[0:2] | .[] | {title: .description, priority: .urgency, hours: .estimated_time}'
# ✅ Should see tasks with priorities and time estimates
```

### Step 2.4: Verify Agent Decisions Recorded
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/workflows/$WORKFLOW_ID | jq '.shared_context.intake.confidence'
# ✅ Should see confidence score (0-1)

curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/decisions | jq '.decisions | length'
# ✅ Should see 15+ agent decisions recorded
```

---

## 👥 Test Suite 3: Team & Staffing (7 min)

### Step 3.1: List Employees
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/employees | jq '.employees | length'
# ✅ Should return: 10

curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/employees | jq '.employees[0] | {name: .full_name, email: .email, skills: .skills}'
# ✅ Should see employee details with skills
```

### Step 3.2: Check Employee Availability
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/employees/2/availability | jq '.'
# ✅ Should see availability records (hours available each day)
```

### Step 3.3: Verify Assignments Created
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/projects/$PROJECT_ID/assignments | jq '.assignments | length'
# ✅ Should see: 5+ (one per task)

curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/projects/$PROJECT_ID/assignments | jq '.assignments[0] | {task: .task_id, employee: .employee_id, confidence: .assignment_confidence}'
# ✅ Should see assignment confidence scores
```

---

## 📊 Test Suite 4: Admin Dashboards (5 min)

### Step 4.1: System Dashboard
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/system/admin-dashboard | jq '{team_size: .team_size, active_projects: .active_projects, recent_decisions: .recent_decisions | length}'
# ✅ Should see dashboard data
```

### Step 4.2: Project Metrics
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/projects | jq '.total, .projects | length'
# ✅ Should return: 1+ projects
```

### Step 4.3: Agent Health
```bash
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  http://localhost:8000/api/v1/agents/health | jq '.agents[] | {name: .agent_name, runs: .total_runs, success_rate: .success_rate}'
# ✅ Should see health metrics for all agents
```

---

## 🖥️ Test Suite 5: UI Verification (10 min)

### Step 5.1: Login Page
- Open browser: http://localhost:3000
- Enter: `swaraj@orchestrator.ai` / `admin123`
- ✅ Should see admin dashboard with team info

### Step 5.2: Dashboard Widget
- Look for "Team Health" widget
- Should show: 10 employees available
- ✅ No 401 errors in network tab

### Step 5.3: Multi-Agent Workbench
- Navigate to "Multi-Agent Workbench"
- Click "New Workflow"
- Enter request: "Create API authentication system"
- Budget: $5000, Priority: High
- Click "Run Multi-Agent Workflow"
- ✅ Should see "Workflow Running..." 
- Wait 3-5 seconds
- ✅ Should see "Workflow Completed" with project details

### Step 5.4: Project List
- Navigate to Projects
- Should see 2+ projects (from manual workflows)
- Click on first project
- ✅ Should see tasks, team assignments, timeline

### Step 5.5: Employee Directory
- Navigate to Team
- Should list 10 employees
- Click on an employee
- ✅ Should see skills, availability, current assignments

---

## 🔄 Test Suite 6: Workflow Edge Cases (5 min)

### Step 6.1: Large Budget Project
```bash
curl -s -X POST http://localhost:8000/multi-agent/workflows/intake \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "build complete mobile app with backend",
    "budget": 150000,
    "priority": "critical",
    "persist_project": true
  }' | jq '.status'
# ✅ Should complete successfully
```

### Step 6.2: Low Budget Project
```bash
curl -s -X POST http://localhost:8000/multi-agent/workflows/intake \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "fix typo in docs",
    "budget": 100,
    "priority": "low",
    "persist_project": true
  }' | jq '.status'
# ✅ Should complete successfully
```

### Step 6.3: Complex Request
```bash
curl -s -X POST http://localhost:8000/multi-agent/workflows/intake \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "Build real-time collaboration platform with WebSockets, end-to-end encryption, and multi-user conflict resolution",
    "budget": 80000,
    "priority": "high",
    "persist_project": true
  }' | jq '.shared_context.execution_plan.tasks | length'
# ✅ Should create 8+ tasks with complex breakdown
```

---

## 📱 Test Suite 7: Employee Dashboard (5 min)

### Step 7.1: Login as Employee
- Open new browser tab: http://localhost:3000
- Login as: `amira.khan@orchestrator.ai` / `team123456`
- ✅ Should see employee dashboard (different from admin)

### Step 7.2: View My Tasks
- Click "My Tasks"
- Should list assigned tasks
- ✅ Can see task details, deadlines, status

### Step 7.3: Update Task Status
- Click on a task
- Try to change status from "pending" to "in-progress"
- ✅ Should update successfully

### Step 7.4: View Availability
- Navigate to "My Availability"
- Should show current availability
- ✅ Can adjust if needed

---

## ✨ Test Suite 8: Data Integrity (3 min)

### Step 8.1: Database Verification
```bash
# Check projects have organization_id
sqlite3 backend/agentic_orchestrator.db "SELECT COUNT(*) FROM projects WHERE organization_id IS NOT NULL;"
# ✅ Should return: 3+ (all projects have org context)

# Check tasks have organization_id
sqlite3 backend/agentic_orchestrator.db "SELECT COUNT(*) FROM tasks WHERE organization_id IS NOT NULL;"
# ✅ Should return: 15+ (all tasks have org context)

# Check workflow runs recorded
sqlite3 backend/agentic_orchestrator.db "SELECT COUNT(*) FROM workflow_runs;"
# ✅ Should return: 5+ (all workflows recorded)

# Verify no constraint violations
sqlite3 backend/agentic_orchestrator.db "PRAGMA integrity_check;"
# ✅ Should return: "ok"
```

---

## 🎯 Final Verification Checklist

- [ ] **Authentication** - Admin and employee can login
- [ ] **Workflow Execution** - Multi-agent workflow completes without errors
- [ ] **Project Creation** - Projects created with organization context
- [ ] **Task Generation** - AI-generated tasks with descriptions and estimates
- [ ] **Team Assignments** - Tasks assigned to qualified employees
- [ ] **Admin Dashboard** - Shows correct metrics (10 employees, recent decisions)
- [ ] **Employee Dashboard** - Shows assigned tasks and availability
- [ ] **UI Responsiveness** - No 401 errors, pages load quickly
- [ ] **Multi-Agent Workbench** - Can submit workflows and see results in real-time
- [ ] **Data Integrity** - All org_id constraints satisfied

---

## 🚀 Results Summary

If all tests pass:
- ✅ **Core System**: Working correctly
- ✅ **Authentication**: JWT tokens valid for both admin and employees  
- ✅ **Multi-Agent Orchestration**: All 5 agents running with proper context
- ✅ **Database**: Multi-tenant constraints satisfied
- ✅ **UI**: Admin and employee dashboards functional
- ✅ **Ready for**: Deployment and production testing

**Total Test Time**: ~50 minutes
**Effort**: Copy-paste commands from this file
