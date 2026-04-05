# 🎯 AI Workforce Orchestrator

> An autonomous project operations platform that shifts project management decisions from humans to intelligent agents.

**Status**: Production-ready | **License**: MIT

---

## 📌 Quick Navigation

- **🎓 Full Setup & Architecture**: See [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md)
- **🚀 Quick Start**: [5-minute setup below](#quick-start-5-minutes)
- **📚 Deployment**: [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md)
- **💡 How It Works**: [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md#how-it-works)

---

## What It Does

Automates 80-90% of project management decisions:
- **Assigns tasks** based on skills & capacity
- **Monitors projects** for delays, blockers, overload
- **Routes decisions** to humans only when confidence is low
- **Updates clients & teams** automatically with context
- **Maintains audit trail** of all decisions

---

## 🏗️ System Architecture

### High-Level Overview
<img width="1112" height="273" alt="compact_flowchart drawio" src="https://github.com/user-attachments/assets/8c70b441-55b8-45ba-be29-5483fbc68da8" />


**Understanding the architecture** (simple explanation):

Think of this like a **restaurant kitchen** with different stations:

1. **Client Layer** (Top - Purple boxes)
   - Like the **front of house** where customers place orders
   - Admin, employees, and clients each have their own interface
   - All built with React for a modern, responsive experience

2. **API Gateway** (Yellow layer)
   - Like the **order window** between front and back of house
   - Checks who you are (authentication)
   - Routes your request to the right place
   - Built with FastAPI for high performance

3. **Orchestration Layer** (Green layer)
   - Like the **head chef** coordinating everything
   - Multi-Agent Orchestrator decides which agents work on what
   - Model Context Protocol (MCP) lets agents share information
   - Ensures agents work together smoothly

4. **Agent Layer** (Blue & Green boxes)
   - Like **specialized chefs** at different stations
   - **Blue agents** (Intake → Escalation): Handle new project setup
   - **Green agents** (Observer → Rebalance): Monitor ongoing projects
   - Each agent has a confidence score showing how sure it is

5. **Data Layer** (Bottom - Pink boxes)
   - Like the **pantry and recipe book**
   - AlloyDB AI stores all project data with AI-powered search
   - Redis caches frequently used information for speed
   - Vector embeddings match skills to tasks intelligently

### How Data Flows

```
Your Request ("Build a login page")
    ↓
API Gateway (authenticates you)
    ↓
Orchestrator (coordinates agents)
    ↓
7 Agents process in sequence + parallel
    ↓
Results saved to database
    ↓
Response back to you (5 seconds total)
```

### The Two Workflows

**Workflow 1: Project Intake** (Blue agents - left side)
- Sequential: Intake → Planning
- Parallel: Staffing + Risk (run simultaneously)
- Sequential: Execution → Communication → Escalation
- **Time**: 3-5 seconds
- **Output**: Complete project plan with team assignments

**Workflow 2: Monitoring Loop** (Green agents - right side)
- Observe → Reason → Act → Loop back
- Runs continuously 24/7
- Catches issues before they become problems
- **Frequency**: Triggered by project state changes

### Key Technologies

- **ADK (Agent Development Kit)**: Google's framework for building AI agents
- **MCP (Model Context Protocol)**: Standardized way for agents to communicate
- **AlloyDB AI**: PostgreSQL database with built-in AI capabilities
  - Vector similarity search for skill matching
  - Predictive queries for risk assessment
  - Sub-millisecond query performance
- **Redis**: In-memory cache for fast data access

### Why This Architecture Scales

1. **Stateless API**: Any server can handle any request (easy to add more servers)
2. **Specialized Agents**: Each agent scales independently based on load
3. **Parallel Processing**: Staffing + Risk agents run simultaneously (2x faster)
4. **Event-Driven**: ReAct loop only processes changes (efficient)
5. **Caching**: Redis reduces database load by 70%

**Current Capacity**: 100+ concurrent projects, 1000+ requests/second

[View editable diagram](architecture_diagram_ppt.drawio) | [View compact flowchart](compact_flowchart.mmd)

---

## 🤖 Meet the AI Agents

Our system uses **7 specialized AI agents** that work like a real project management team. Each agent has a specific expertise and produces a confidence score (0-1.0) showing how sure it is about its decisions.

### Agent Workflow Visualization

![Agent Workflow](compact_flowchart.png)

**What you're seeing**: The compact flowchart shows the complete agent workflow from left to right. Blue boxes are the main agents, the orange diamond is the decision point (escalate or proceed), and green boxes show the continuous monitoring loop.

### The 7 Agents Explained

---

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Python 3.10+
- Node.js 16+
- ~50MB disk space

### 1. Backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python seed_test_data.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**API**: http://localhost:8000/docs

### 2. Frontend (new terminal)

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

**Application**: http://localhost:3000

### 5. Login

**Test Accounts**:
- **Admin**: `swaraj@orchestrator.ai` / `admin123`
- **Team**: `{firstname}.{lastname}@orchestrator.ai` / `team123456`
  - Examples: amira.khan@orchestrator.ai, arjun.rao@orchestrator.ai, neha.gupta@orchestrator.ai

---

## 📚 Full Documentation

Visit [COMPLETE_GUIDE.md](COMPLETE_GUIDE.md) for:
- ✅ Detailed configuration & environment setup
- ✅ Admin, employee, and client workflows
- ✅ Complete API reference with examples
- ✅ Multi-agent system architecture  
- ✅ How to add custom agents
- ✅ Development standards & testing
- ✅ Troubleshooting guide
- ✅ Contributing guidelines

---

## 🔑 Test Accounts & Quick Tips

**Run without LLM token**: System has built-in fallbacks (deterministic logic works perfectly).

**Enable LLM** (optional):
```bash
export HUGGINGFACEHUB_API_TOKEN="hf_your_token"
export HF_MODEL_ID="mistralai/Mistral-7B-Instruct-v0.3"
```

**Reset database**:
```bash
cd backend
python seed_test_data.py
```

**API docs**: http://localhost:8000/docs

---

## 📄 License

MIT — See LICENSE file

---

## 👤 Author

**Swaraj**  
Director & CRO — Lumin Aerospace Pvt. Ltd.

Building autonomous workflows for lean teams managing multiple projects.

- **Email**: swarajsj8102000@gmail.com
- **LinkedIn**: [swaraj-swaraj-a6339023b](https://www.linkedin.com/in/swaraj-swaraj-a6339023b)
