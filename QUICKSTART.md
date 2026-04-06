# AI Workforce Orchestrator - Quick Start

## ✅ Setup Complete

Your environment is now configured and ready to run!

## 🚀 Running the Application

### Terminal 1 - Backend

```bash
cd /Users/rawatp1/Documents/Repository_local/Hackathon/adk-workflow-orchestrator/backend

# Option 1: Use the run script (recommended)
./run.sh

# Option 2: Manual startup
.venv/bin/python seed_test_data.py  # First time only
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Note:** Always use `.venv/bin/python` instead of `python` to avoid shell alias issues.

### Terminal 2 - Frontend

```bash
cd /Users/rawatp1/Documents/Repository_local/Hackathon/adk-workflow-orchestrator/frontend

# Install dependencies (first time only)
npm install

# Start frontend
npm run dev
```

## 🌐 Access Points

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

## 🔑 Login Credentials

**Admin Account:**
- Email: `swaraj@orchestrator.ai`
- Password: `admin123`

**Employee Accounts:**
- Email: `{firstname}.{lastname}@orchestrator.ai`
- Password: `team123456`
- Examples:
  - amira.khan@orchestrator.ai
  - arjun.rao@orchestrator.ai
  - neha.gupta@orchestrator.ai

## 🛠️ Troubleshooting

### VSCode Python Extension Error

If you see `Failed to run python -m pip list`:

1. **The issue:** Your shell has `python` aliased to system Python, not the venv

2. **Solution:** Always use `.venv/bin/python` directly:
   ```bash
   .venv/bin/python seed_test_data.py
   .venv/bin/pip install -r requirements.txt
   ```

3. **Or run the script:**
   ```bash
   ./run.sh
   ```

4. **Select correct interpreter in VS Code:**
   - Press `Cmd+Shift+P` (Mac) or `Ctrl+Shift+P` (Windows/Linux)
   - Type "Python: Select Interpreter"
   - Choose: `.venv/bin/python` in the backend folder

5. **Reload VS Code:**
   - Press `Cmd+Shift+P` → "Developer: Reload Window"

### Port Already in Use

If port 8000 or 3000 is already in use:

```bash
# Kill process on port 8000
.venv/bin/python seed_test_data.py
```

### Missing Dependencies

Re-install backend dependencies:

```bash
cd backend
.venv/bin/pip install --upgrade pip
.venv/bin/cd backend
rm -f app.db
python seed_test_data.py
```

### Missing Dependencies

Re-install backend dependencies:

```bash
cd backend
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Re-install frontend dependencies:

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## 📦 What's Installed

**Backend Python Packages:**
- FastAPI 0.115.0 (Web framework)
- Uvicorn 0.30.0 (ASGI server)
- SQLAlchemy 2.0.36 (ORM)
- Pydantic 2.9.2 (Data validation)
- Alembic 1.13.3 (Database migrations)
- Python-JOSE 3.3.0 (JWT authentication)
- Passlib 1.7.4 (Password hashing)

**Note**: LangChain dependencies are commented out by default. The system runs with deterministic fallback logic without LLM integration.

## 🔧 Optional: Enable LLM Integration

If you want to enable LangChain + HuggingFace integration:

1. **Uncomment in requirements.txt:**
```python
langchain==0.3.14
langchain-core==0.3.29
langchain-huggingface==0.1.2
huggingface-hub==0.27.1
```

2. **Install:**
```bash
pip install -r requirements.txt
```

3. **Set environment variables:**
```bash
export HUGGINGFACEHUB_API_TOKEN="hf_your_token_here"
export HF_MODEL_ID="mistralai/Mistral-7B-Instruct-v0.3"
```

## 📚 Next Steps

1. **Explore the Admin Dashboard**: Create projects, manage teams
2. **Test the Multi-Agent System**: Watch autonomous decision-making
3. **Check Decision Logs**: See AI reasoning and confidence scores
4. **Review the Architecture**: Read `SYSTEM_ARCHITECTURE.md`

## 🆘 Getting Help

- **Documentation**: See `README.md` for full details
- **Architecture Guide**: `SYSTEM_ARCHITECTURE.md`
- **API Reference**: http://localhost:8000/docs (when running)

---

**Status**: ✅ Ready to run!
