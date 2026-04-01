# 📊 Admin Dashboards Explained

**AI Workforce Orchestrator** - Understanding the 3 Admin Control Surfaces

---

## Quick Summary

| Dashboard | Purpose | When to Use | Main Action |
|-----------|---------|------------|-------------|
| **Agent Dashboard** | Monitor agent decisions & health | Daily monitoring | Approve/reject low-confidence decisions |
| **AutoPM Console** | ⚠️ Legacy - redirects to Multi-Agent | (Deprecated) | N/A - will be removed |
| **Multi-Agent Workbench** | Run end-to-end workflows manually | Test & debug workflows | Execute full project planning cycle |

---

## 🔍 Detailed Breakdown

### 1️⃣ **Agent Dashboard** (Recommended - Daily Use)

**Purpose**: Monitor agent health, decision confidence, and system metrics

**Location**: Click **"Decisions"** in navbar (or Agentic Dashboard)

**What It Shows**:
- ✅ **Total Decisions**: How many decisions agents have made
- ✅ **Automation Level**: % of decisions made autonomously (vs manually)
- ✅ **Average Confidence**: Overall confidence score of all agent decisions (0-1.0)
- ✅ **Overrides**: How many agent decisions admin rejected
- ✅ **LLM Status**: Whether AI planning model is enabled or in fallback

**Key Sections**:

#### Section 1: Decision Health
```
Total Decisions:      47
Automation Level:     84%
Average Confidence:   0.87
Overrides:           3
LLM Model:           Hugging Face active
```

#### Section 2: Low Confidence Alerts
Shows decisions with **confidence < 0.70** that might need review:
```
Decision #12: "Assign Arjun to Task X"
Confidence: 0.65
Reasoning: "Arjun at 92% capacity, but only backend engineer available"
Status: Escalated
```

#### Section 3: Project Approvals
Shows projects waiting for admin action:
```
Project: "Website Redesign"
Status: Awaiting Admin Approval
Team Proposed: Amira (Lead), Yash (Frontend), Sofia (QA)
Your Action: [Approve] [Reject]
```

#### Section 4: Escalation Meetings
Shows high-priority decisions that need human review

**What You Can Do**:
1. ✅ **Monitor system health** - Check confidence scores
2. ✅ **Approve/Reject** project planning recommendations
3. ✅ **View LLM status** - Is AI planning enabled?
4. ✅ **Review escalations** - See blocked decisions
5. ✅ **Identify bottlenecks** - Find where agents are uncertain

**Real Example Use Case**:
```
Scenario: Agents proposed assigning "Data Pipeline Project" to Kavya
Confidence: 0.62 (LOW!)
Reason: "Kavya only has 4 hours free but task needs 16 hours"

Your Action:
1. Click "Review Decision"
2. Propose alternative: "Assign to Arjun instead (18 hours free)"
3. Save override
4. System learns for future assignments
```

---

### 2️⃣ **AutoPM Console** (Legacy - Deprecated)

**Purpose**: N/A - Deprecated system

**Status**: ⚠️ **This panel is being phased out**

**What It Says**:
> "The original AutoPM flow was built around a single service-driven simulation path and is no longer the recommended control surface. This page now routes you into the new multi-agent workflow."

**Why It Exists**:
- Old system had a different orchestration model
- Now there's ONE unified multi-agent system
- AutoPM redirects to Multi-Agent Workbench
- Will be removed in v2.1

**What To Do**: **Ignore this panel** - Use **Multi-Agent Workbench** instead

---

### 3️⃣ **Multi-Agent Workbench** (Power User - Advanced)

**Purpose**: Execute full agent workflows manually, test the system, debug workflows

**Location**: Click **"Multi-Agent"** in navbar

**What It Does**:
Runs the **complete agent orchestration pipeline** in one execution:

```
Input: Project description
    ↓
[Intake Agent] → Parse & structure
    ↓
[Planning Agent] → Break into tasks
    ↓
[Staffing Agent] → Recommend team
    ↓
[Risk Agent] → Identify blockers
    ↓
Output: Workflow result with all agent decisions
```

**Main Controls**:

#### Section 1: Run New Workflow

**Form Fields**:
```
📝 Request Description (textarea):
   "Build an e-commerce website with payment processing, 
    user accounts, and mobile app. Budget: $50k, Deadline: 2 months"

💰 Budget: $50,000 (numeric)

⚡ Priority: [High / Normal / Low]

☑️  Persist Project: [checked]
   If checked: Creates actual project in system
   If unchecked: Runs simulation only (dry-run)
```

**Response Shows**:
```json
{
  "workflow_id": 45,
  "status": "completed",
  "agents_run": [
    "intake_agent",
    "planning_agent",
    "staffing_agent",
    "risk_agent"
  ],
  "final_output": {
    "autonomy_status": "requires_admin_approval",
    "tasks_planned": 12,
    "team_recommended": 4,
    "blockers_identified": 1,
    "confidence_score": 0.89
  }
}
```

#### Section 2: Workflow Results
Shows last 25 workflows ran:
```
Workflow #45: "E-commerce Website" - Completed (89% confidence)
Workflow #44: "Mobile App Update" - Approved (92% confidence)
Workflow #43: "Bug Fixes" - Rejected (61% confidence - too risky)
```

#### Section 3: Approve/Reject Workflow
After workflow completes, you can:
- ✅ **Approve**: Accept agent recommendations, create assignments
- ❌ **Reject**: Send back for re-planning

```
[Workflow #45 Details]
Status: AWAITING APPROVAL
Proposed Team:
  - Amira Khan (Tech Lead): Confidence 0.95
  - Yash Patel (Frontend): Confidence 0.92
  - Sofia DSouza (QA): Confidence 0.88
  - Daniel Lee (DevOps): Confidence 0.85

[Approve] [Reject]
```

#### Section 4: Project Execution Loop
Run agent loop on **existing project**:

```
🔄 Run Project Loop
Project ID: [1]
Persist Followup Messages: [checked]

Description: Re-evaluate project health and suggest next actions
Button: [Run Loop]
```

**What This Does**:
- Agents re-assess project progress
- Identify new blockers
- Suggest task reassignments
- Generate status updates for team

#### Section 5: Queue Health
Shows background job status:
```
Queue Status:
  ✅ Processing: 0 jobs
  ⏳ Waiting: 2 jobs
  ❌ Failed: 0 jobs

Failed Events (last 10):
  [None currently]
```

**What You Can Do**:
1. ✅ **Test workflows** - Dry-run agent pipeline
2. ✅ **Run full orchestration** - From description to team + tasks
3. ✅ **Approve recommendations** - Accept or reject
4. ✅ **Debug agent decisions** - See full reasoning
5. ✅ **Monitor queue** - Check job processing health
6. ✅ **Re-run loops** - Continuously monitor existing projects

**Real Example Use Case**:
```
Scenario: Client sends new request
"Build AI chat interface with voice input/output support"

Your Action:
1. Open Multi-Agent Workbench
2. Paste request in textarea
3. Set Budget: $75,000
4. Set Priority: High
5. Check "Persist Project" = OFF (dry-run first)
6. Click [Run Workflow]
7. Review agent recommendations:
   - 9 tasks planned
   - 5 people recommended
   - 3 blockers identified
   - Confidence: 0.91
8. If good: Run again with "Persist Project" ON
9. Agents create real project, send team invites
10. Check "Project Loop" frequently to monitor progress
```

---

## 🎯 Workflow: How These Work Together

### Daily Workflow

**Morning (10 mins)**:
1. Open **Agent Dashboard**
2. Check **Automation Level** - Should be >80%
3. Review **Average Confidence** - Should be >0.85
4. Approve any **low-confidence decisions**
5. Check **LLM status** - Confirm it's working

**When New Request Arrives (20 mins)**:
1. Open **Multi-Agent Workbench**
2. Paste client request
3. Run with **Persist Project = OFF** (test first)
4. Review recommendations
5. If good, run with **Persist Project = ON**
6. Approve workflow
7. Back to **Agent Dashboard** to monitor

**Ongoing (5 mins/day)**:
1. Check **Agent Dashboard** for escalations
2. Open **Multi-Agent Workbench** if needed
3. Run **Project Loops** to re-evaluate active projects

---

## 📊 Comparison Matrix

### Agent Dashboard vs Multi-Agent Workbench

| Aspect | Agent Dashboard | Multi-Agent Workbench |
|--------|-----------------|----------------------|
| **Primary Use** | Monitor health | Execute workflows |
| **Frequency** | Daily, continuous | On-demand |
| **Data Type** | Historical decisions | Active workflow runs |
| **Main Action** | Approve/Reject | Execute full pipeline |
| **Learning** | Tracks agent patterns | Tests new configurations |
| **Time Spent** | 5-10 mins/day | 10-30 mins when needed |
| **User Level** | All admins | Power users / QA |

---

## 🚀 Advanced: Understanding Agent Decisions

### What Each Agent Does

#### Intake Agent
- **Input**: Natural language project request
- **Output**: Structured project scope, tasks, dependencies
- **Decision**: "Break this into how many tasks?"
- **Confidence**: How well did we understand the request?

#### Planning Agent
- **Input**: Project scope from intake
- **Output**: Task breakdown, milestones, dependencies
- **Decision**: "Which tasks block which?"
- **Confidence**: Is the task structure logical?

#### Staffing Agent
- **Input**: Tasks + team capabilities
- **Output**: Team recommendations with confidence
- **Decision**: "Who should do what?"
- **Confidence**: Do people have right skills?

#### Risk Agent
- **Input**: Tasks + assignments + timeline
- **Output**: Blockers, risks, timeline health
- **Decision**: "Will this timeline work?"
- **Confidence**: Do we have enough buffer?

---

## ✅ Features You Can Test Right Now

### Test 1: Simple Project Creation
```
Request: "Build a landing page"
Budget: $10,000
Priority: Medium
Result: Should be 4-6 tasks, 2 people
Confidence: >0.90
```

### Test 2: Complex Request
```
Request: "Build full SaaS platform with auth, payments, analytics dashboard, 
          mobile app, and admin panel. Support 1000 concurrent users."
Budget: $200,000
Priority: High
Result: Should be 20+ tasks, 5+ people
Confidence: ~0.75-0.85 (more complex = lower confidence)
```

### Test 3: Override an Agent Decision
```
Scenario: Agent assigns Arjun to Backend task but it's not ideal
Action: Open Agent Dashboard → Reject decision → Propose alternative
Result: Agent learns for next assignment
```

---

## 🔧 Common Tasks

### Task 1: Check System Health
```
1. Agent Dashboard
2. Look at:
   - Automation Level (should be >80%)
   - Average Confidence (should be >0.85)
   - Overrides (should be <10%)
   - LLM Status (should be "Enabled")
```

### Task 2: Test New Workflow
```
1. Multi-Agent Workbench
2. Paste project description
3. Set Persist = OFF
4. [Run Workflow]
5. Review all agent outputs
6. If happy, run again with Persist = ON
```

### Task 3: Approve Project
```
1. Multi-Agent Workbench
2. Select workflow from list
3. Review recommendations
4. [Approve] button
5. Check Agent Dashboard - workflow now in approvals
```

### Task 4: Monitor Project
```
1. Multi-Agent Workbench
2. Enter Project ID
3. [Run Project Loop]
4. Check updated status and recommendations
5. Repeat daily
```

---

## 🎓 Learning Path

### Beginner (First Day)
1. ✅ Open Agent Dashboard
2. ✅ Understand the metrics (confidence, automation, overrides)
3. ✅ Approve 1-2 low-confidence decisions
4. ✅ Understand why agents made those decisions

### Intermediate (Week 1)
1. ✅ Open Multi-Agent Workbench
2. ✅ Test a workflow with a simple request
3. ✅ Review all agent decisions
4. ✅ Run with Persist ON
5. ✅ Approve the workflow
6. ✅ Match with Agent Dashboard approval section

### Advanced (Week 2+)
1. ✅ Use Multi-Agent for real client requests
2. ✅ Override agent decisions in Agent Dashboard
3. ✅ Run Project Loops to monitor
4. ✅ Test edge cases to understand agent behavior
5. ✅ Optimize prompts based on decision patterns

---

## 🤔 FAQ

**Q: Which dashboard should I use most?**
A: Agent Dashboard for daily health checks (5-10 mins). Multi-Agent Workbench when handling new requests (10-30 mins per request).

**Q: What's the difference between these dashboards and the main Dashboard?**
A:
- **Main Dashboard**: Project overview, task status, team workload (what's happening)
- **Agent Dashboard**: Agent decision health, confidence scores (how decisions are made)
- **Multi-Agent Workbench**: Execute workflows, test agents (manually run the system)

**Q: Why would workflow confidence be low?**
A:
- Conflicting requirements in the description
- Team capacity constraints
- Unclear timeline or dependencies
- Risky technical approach

**Q: Can I reject an agent decision?**
A: Yes! In Agent Dashboard → Click decision → Propose alternative. System learns and improves.

**Q: What does "Persist Project" mean?**
A: 
- **ON**: Creates actual project, tasks, and sends team invites
- **OFF**: Test run only, nothing persists to database

**Q: How often should I run Project Loops?**
A: 
- Small projects (1 week): Daily
- Medium projects (2-4 weeks): 2-3x per week
- Large projects (1+ month): Weekly

---

## 📚 Documentation Links

- Project Overview: Check **Dashboard** tab
- Agent Reasoning: Check **Decisions** dashboard
- Workflow Testing: Use **Multi-Agent Workbench**
- Decision Logs: Right-click any project → "View Decisions"

---

**Ready to explore? Start with Agent Dashboard → understand metrics → then test Multi-Agent Workbench with a simple request! 🚀**
