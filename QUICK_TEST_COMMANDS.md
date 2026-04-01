# ⚡ Quick Testing Commands Reference

**Copy-paste ready commands for complete system testing**

---

## 🔧 Pre-Test Setup

```bash
# Terminal 1: Start Backend (if not running)
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend
source venv/bin/activate
python seed_test_data.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Start Frontend (if not running)
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/frontend
npm run dev

# Terminal 3: Ready for testing commands below
```

---

## 1. Verify Seed Data

```bash
# List all employees
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/employees | jq '.employees | length'

# Detailed employee list
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/employees | jq '.employees[] | {name: .full_name, email: .email, skills: .skills}'

# Check organization
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/organizations/seed | jq '.'

# View specific employee
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/employees/2 | jq '.full_name, .skills'
```

---

## 2. Test Project Lifecycle

### Create Project

```bash
# Simple project creation
curl -X POST http://localhost:8000/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "name": "Website Redesign",
    "description": "Complete redesign of company website",
    "client_id": "acme-corp",
    "deadline": "2026-04-16",
    "budget": 50000,
    "status": "planning"
  }' | jq '.id, .name, .status'
```

### Add Team Members

```bash
# Assuming project ID = 1
curl -X POST http://localhost:8000/api/v1/projects/1/team \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "employee_ids": [2, 3, 4, 5],
    "roles": {
      "2": "tech-lead",
      "3": "frontend-lead",
      "4": "qa-lead",
      "5": "coordinator"
    }
  }' | jq '.team | length'
```

### Create Tasks

```bash
# Task 1: Design
curl -X POST http://localhost:8000/api/v1/projects/1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "title": "Wireframe New Design",
    "description": "Create wireframes for new website layout",
    "priority": "high",
    "estimated_hours": 16,
    "required_skills": ["architecture", "design"],
    "checkpoint": "Wireframes approved by client"
  }' | jq '.id'

# Task 2: Frontend
curl -X POST http://localhost:8000/api/v1/projects/1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "title": "Build Frontend Components",
    "description": "Implement React components for new design",
    "priority": "high",
    "estimated_hours": 32,
    "required_skills": ["frontend", "react"],
    "depends_on": 1
  }' | jq '.id'

# Task 3: Testing
curl -X POST http://localhost:8000/api/v1/projects/1/tasks \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "title": "QA Testing & Bug Fixes",
    "description": "Test all pages, browsers, and devices",
    "priority": "high",
    "estimated_hours": 24,
    "required_skills": ["qa", "testing"],
    "depends_on": 2
  }' | jq '.id'

# View all tasks
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/projects/1 | jq '.tasks[] | {id, title, status}'
```

---

## 3. Test Agents

### Trigger Planning Agent

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/plan \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "mode": "auto",
    "use_llm": false
  }' | jq '{plan_id, status, tasks_created, estimated_total_hours}'
```

### Trigger Staffing Agent

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/staffing \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "strategy": "skill-match",
    "balance_workload": true
  }' | jq '.recommendations[] | {task_id, recommended_employee: .recommended_employee.name, confidence: .recommended_employee.confidence}'
```

### Apply Staffing Recommendations

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/staffing/apply \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{"apply_all": true}' | jq '{applied_count, total_allocation}'
```

### Trigger Risk/Health Agent

```bash
curl -X POST http://localhost:8000/api/v1/projects/1/health-check \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{"include_predictions": true}' | jq '{health: .project_health.status, score: .project_health.score, risks: .project_health.risks}'
```

### View Decision Logs

```bash
# All decisions
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/projects/1/decisions | jq '.decisions[] | {agent, decision, confidence, status}'

# Recently updated
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/projects/1/decisions | jq '.decisions[-3:] | reverse[] | {agent, decision, timestamp}'
```

---

## 4. Test Task Management

### Get Task Details

```bash
# Task 1 details
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/tasks/1 | jq '{id, title, status, assigned_to: .assigned_to.name, estimated_hours}'

# All tasks
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/tasks | jq '.tasks[] | {id, title, status, priority}'
```

### Update Task Progress (Simulate Work)

```bash
# Set to in_progress (4 hours done)
curl -X PUT http://localhost:8000/api/v1/tasks/1/progress \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "status": "in_progress",
    "hours_logged": 4,
    "notes": "Started wireframing desktop screens"
  }' | jq '{status, hours_logged, completion_percentage}'

# 50% complete (8 hours)
curl -X PUT http://localhost:8000/api/v1/tasks/1/progress \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "status": "in_progress",
    "hours_logged": 8,
    "completion_percentage": 50,
    "notes": "Desktop done, mobile in progress"
  }' | jq '{status, hours_logged, completion_percentage}'

# Complete task (16 hours full)
curl -X PUT http://localhost:8000/api/v1/tasks/1/progress \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "status": "completed",
    "hours_logged": 16,
    "completion_percentage": 100,
    "notes": "All wireframes complete, ready for review"
  }' | jq '{status, completion_percentage}'
```

### Create Blocker

```bash
curl -X POST http://localhost:8000/api/v1/tasks/2/blockers \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "title": "Waiting for design approval",
    "description": "Cannot start frontend until wireframes approved",
    "severity": "high"
  }' | jq '{blocker_id: .id, title, severity, blocking_task_id}'
```

### Escalate Task

```bash
curl -X POST http://localhost:8000/api/v1/tasks/2/escalate \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "reason": "Task depends on delayed design approval",
    "severity": "high",
    "suggested_action": "Contact client for urgent review"
  }' | jq '{escalation_id: .id, status, notified_to}'
```

### Filter Tasks by Status

```bash
# In progress
curl -s -H "X-Organization-ID: seed" "http://localhost:8000/api/v1/tasks?status=in_progress" | jq '.tasks[] | {id, title}'

# Completed
curl -s -H "X-Organization-ID: seed" "http://localhost:8000/api/v1/tasks?status=completed" | jq '.tasks[] | {id, title}'

# Blocked
curl -s -H "X-Organization-ID: seed" "http://localhost:8000/api/v1/tasks?status=blocked" | jq '.tasks[] | {id, title}'
```

---

## 5. Test Multi-Tenant Features

### Create New Organization

```bash
curl -X POST http://localhost:8000/api/v1/organizations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "TechCorp Inc",
    "slug": "techcorp",
    "subscription_tier": "pro",
    "max_employees": 50
  }' | jq '.id, .name, .slug'
```

### Test Tenant Isolation

```bash
# Seed org projects
SEED_PROJECTS=$(curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/projects | jq '.projects | length')
echo "Seed org projects: $SEED_PROJECTS"

# TechCorp org projects (should be 0)
TECH_PROJECTS=$(curl -s -H "X-Organization-ID: techcorp" http://localhost:8000/api/v1/projects | jq '.projects | length')
echo "TechCorp org projects: $TECH_PROJECTS"
```

### Create Invite

```bash
curl -X POST http://localhost:8000/api/v1/organizations/seed/invites \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: seed" \
  -d '{
    "email": "newemployee@company.com",
    "role": "employee"
  }' | jq '{invite_id: .id, email, invite_code, expires_at}'
```

### List Invites

```bash
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/organizations/seed/invites | jq '.invites[] | {id, email, status, expires_at}'
```

---

## 6. Test API Core Functionality

### Health Check

```bash
curl -s http://localhost:8000/health | jq '.'
```

### Login

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "swaraj@orchestrator.ai",
    "password": "admin123"
  }' | jq '{token: .access_token, user: .user.full_name}'
```

### Get Current User

```bash
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/auth/me | jq '{email, full_name, role}'
```

### Search Employees by Skill

```bash
# Backend skills
curl -s -H "X-Organization-ID: seed" "http://localhost:8000/api/v1/employees?skill=backend" | jq '.employees[] | {name: .full_name, skills: .skills}'

# Frontend skills
curl -s -H "X-Organization-ID: seed" "http://localhost:8000/api/v1/employees?skill=frontend" | jq '.employees[] | {name: .full_name, skills: .skills}'

# LLM skills
curl -s -H "X-Organization-ID: seed" "http://localhost:8000/api/v1/employees?skill=llm" | jq '.employees[] | {name: .full_name, skills: .skills}'
```

### Get Metrics

```bash
# Project metrics
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/metrics/projects | jq '.'

# Team metrics
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/metrics/team | jq '.team_metrics[] | {name: .employee_name, efficiency_score, reliability_score}'

# Task metrics
curl -s -H "X-Organization-ID: seed" http://localhost:8000/api/v1/metrics/tasks | jq '.task_metrics[]'
```

---

## 7. Database Inspection

### Open Database

```bash
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend
sqlite3 agentic_orchestrator.db
```

### In SQLite Console

```sql
-- List all tables
.tables

-- Row counts
SELECT 'organizations' as table_name, COUNT(*) as rows FROM organizations
UNION ALL
SELECT 'auth_users', COUNT(*) FROM auth_users
UNION ALL
SELECT 'employee_profiles', COUNT(*) FROM employee_profiles
UNION ALL
SELECT 'projects', COUNT(*) FROM projects
UNION ALL
SELECT 'tasks', COUNT(*) FROM tasks;

-- View organizations
SELECT id, name, slug, subscription_tier FROM organizations;

-- View admin user
SELECT email, full_name, role, is_active FROM auth_users WHERE email = 'swaraj@orchestrator.ai';

-- View projects
SELECT id, name, status FROM projects;

-- View tasks
SELECT id, title, status, estimated_hours FROM tasks;

-- View task progress
SELECT task_id, status, hours_logged, completion_percentage FROM task_progress ORDER BY updated_at DESC;

-- View decisions
SELECT agent, decision, confidence, status FROM decision_logs ORDER BY created_at DESC LIMIT 10;

-- Exit
.quit
```

---

## 8. Full Test Scenario (Copy & Run All)

```bash
#!/bin/bash

set -e
ORG_ID="seed"
API="http://localhost:8000"

echo "🧪 Starting Complete System Test"
echo "================================"

# 1. Verify seed data
echo -e "\n1️⃣ Verifying seed data..."
EMPLOYEE_COUNT=$(curl -s -H "X-Organization-ID: $ORG_ID" $API/api/v1/employees | jq '.employees | length')
echo "✅ Found $EMPLOYEE_COUNT employees"

# 2. Create project
echo -e "\n2️⃣ Creating project..."
PROJECT=$(curl -s -X POST $API/api/v1/projects \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: $ORG_ID" \
  -d '{
    "name": "Website Redesign",
    "description": "Complete redesign",
    "client_id": "acme-corp",
    "deadline": "2026-04-16"
  }')
PROJECT_ID=$(echo $PROJECT | jq '.id')
echo "✅ Created project ID: $PROJECT_ID"

# 3. Add team
echo -e "\n3️⃣ Adding team members..."
curl -s -X POST $API/api/v1/projects/$PROJECT_ID/team \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: $ORG_ID" \
  -d '{
    "employee_ids": [2, 3, 4, 5],
    "roles": {"2": "tech-lead", "3": "frontend-lead", "4": "qa-lead", "5": "coordinator"}
  }' > /dev/null
echo "✅ Added 4 team members"

# 4. Create tasks
echo -e "\n4️⃣ Creating tasks..."
TASK1=$(curl -s -X POST $API/api/v1/projects/$PROJECT_ID/tasks \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: $ORG_ID" \
  -d '{
    "title": "Wireframe New Design",
    "priority": "high",
    "estimated_hours": 16
  }' | jq '.id')
echo "✅ Created 3 tasks"

# 5. Run agents
echo -e "\n5️⃣ Running planning agent..."
curl -s -X POST $API/api/v1/projects/$PROJECT_ID/plan \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: $ORG_ID" \
  -d '{"mode": "auto"}' > /dev/null
echo "✅ Planning complete"

echo -e "\n6️⃣ Running staffing agent..."
curl -s -X POST $API/api/v1/projects/$PROJECT_ID/staffing \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: $ORG_ID" \
  -d '{"strategy": "skill-match"}' > /dev/null
echo "✅ Staffing recommendations generated"

echo -e "\n7️⃣ Applying staffing..."
curl -s -X POST $API/api/v1/projects/$PROJECT_ID/staffing/apply \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: $ORG_ID" \
  -d '{"apply_all": true}' > /dev/null
echo "✅ Staffing applied"

# 6. Test task progress
echo -e "\n8️⃣ Simulating task progress..."
curl -s -X PUT $API/api/v1/tasks/$TASK1/progress \
  -H "Content-Type: application/json" \
  -H "X-Organization-ID: $ORG_ID" \
  -d '{
    "status": "in_progress",
    "hours_logged": 4,
    "notes": "Started work"
  }' > /dev/null
echo "✅ Task progress updated"

# 7. View metrics
echo -e "\n9️⃣ Retrieving metrics..."
METRICS=$(curl -s -H "X-Organization-ID: $ORG_ID" $API/api/v1/metrics/projects)
echo "✅ Metrics: $(echo $METRICS | jq '.total_projects') projects, $(echo $METRICS | jq '.total_tasks') tasks"

# 8. Check decisions
echo -e "\n🔟 Viewing decisions..."
DECISIONS=$(curl -s -H "X-Organization-ID: $ORG_ID" $API/api/v1/projects/$PROJECT_ID/decisions | jq '.total_decisions')
echo "✅ $DECISIONS decisions logged"

echo -e "\n✅ All tests complete!"
```

**Save and run**:
```bash
nano test_all.sh
chmod +x test_all.sh
./test_all.sh
```

---

## 🐛 Debugging Commands

```bash
# View logs in real-time
tail -f /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend/app.log

# Check if backend is running
ps aux | grep uvicorn

# Check if frontend is running
ps aux | grep npm

# View SQLite database file size
ls -lh /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend/agentic_orchestrator.db

# Reset database
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator/backend
rm agentic_orchestrator.db
python seed_test_data.py
```

---

**Ready to test? Run the commands above section by section! 🚀**
