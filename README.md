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

- **Email**: dubeybishal70@gmail.com
- **LinkedIn**: [swaraj-swaraj-a6339023b](https://www.linkedin.com/in/bishaldubey/)
