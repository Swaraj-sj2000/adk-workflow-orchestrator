# 🧪 Testing & Free Hosting Guide

**AI Workforce Orchestrator** — Test Locally & Deploy for FREE

---

## Table of Contents

1. [Quick Testing (5 mins)](#quick-testing-5-mins)
2. [Full Testing (30 mins)](#full-testing-30-mins)
3. [Free Hosting Options](#free-hosting-options)
4. [Deploy to Render (Recommended - $0/month)](#deploy-to-render-recommended--0month)
5. [Deploy to Railway (Alternative - $5 credit/month)](#deploy-to-railway-alternative--5-creditmonth)
6. [Deploy to Heroku (Legacy - limited free tier)](#deploy-to-heroku-legacy--limited-free-tier)
7. [Deploy to Replit (Quick - $0/month)](#deploy-to-replit-quick--0month)

---

## 🚀 Quick Testing (5 mins)

Start the app **RIGHT NOW** in one command:

### Option A: Docker (Recommended)

```bash
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator

# Start both backend and frontend
docker-compose up --build

# Open browser
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option B: Local Development (Manual)

**Terminal 1 - Backend**:
```bash
cd backend
source venv/bin/activate  # On Windows: venv\Scripts\activate
python seed_test_data.py  # Initialize DB with test data
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend**:
```bash
cd frontend
npm install  # First time only
npm run dev
```

**Now open browser**:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📊 Full Testing (30 mins)

### 1. **Test Seed Data**

Backend loads 11 test users pre-configured:

```bash
# Terminal 1 - Backend running

# In Terminal 2 - Test login endpoint
curl -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "swaraj@orchestrator.ai",
    "password": "admin123"
  }'

# Response: JWT token + user info
```

### 2. **Test API Endpoints**

```bash
# Get all organizations
curl http://localhost:8000/api/v1/organizations/seed/projects \
  -H "X-Organization-ID: seed"

# List employees
curl http://localhost:8000/api/v1/employees \
  -H "X-Organization-ID: seed"

# Get current admin user
curl http://localhost:8000/api/v1/auth/me \
  -H "X-Organization-ID: seed"
```

### 3. **Test Interactive UI**

Open http://localhost:3000 and:

- ✅ View dashboard
- ✅ See team members (11 pre-loaded)
- ✅ Check projects (starts at 0)
- ✅ Create a new project
- ✅ Assign tasks to team
- ✅ Monitor agent decisions

### 4. **Test Agent Workflow**

Create a sample project and trigger agents:

```bash
# Create project via API
curl -X POST http://localhost:8000/api/v1/projects \
  -H "X-Organization-ID: seed" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Project",
    "description": "Test agent workflow",
    "client_id": "1",
    "deadline": "2026-04-15"
  }'

# View decision logs
curl http://localhost:8000/api/v1/decision-logs \
  -H "X-Organization-ID: seed"

# View workflow runs
curl http://localhost:8000/api/v1/workflows \
  -H "X-Organization-ID: seed"
```

### 5. **Test Database**

```bash
# Inspect SQLite database (Terminal 3)
cd backend
sqlite3 agentic_orchestrator.db

# SQLite prompt - Show tables
sqlite> .tables
sqlite> SELECT COUNT(*) FROM users;
sqlite> SELECT COUNT(*) FROM employees;
sqlite> SELECT * FROM organizations;
sqlite> .quit
```

### 6. **Run Performance Tests** (Optional)

```bash
# Install locust (load testing)
pip install locust

# Create loadtest file
cat > locustfile.py << 'EOF'
from locust import HttpUser, task, between

class OrchestratorUser(HttpUser):
    wait_time = between(5, 10)
    
    @task
    def get_projects(self):
        self.client.get("/api/v1/projects", 
                       headers={"X-Organization-ID": "seed"})
    
    @task
    def get_employees(self):
        self.client.get("/api/v1/employees",
                       headers={"X-Organization-ID": "seed"})
EOF

# Run load test
locust -f locustfile.py -u 100 -r 10 --headless -t 60s
```

---

## 🌍 Free Hosting Options

### Comparison Table

| Platform | Cost | Database | Limits | Cold Start | Best For |
|----------|------|----------|--------|-----------|----------|
| **Render** | $0 | Free Postgres | 100 connections | Auto-sleep | Teams, Projects |
| **Railway** | $5/mo credit | Free Postgres | 5GB db, 5 builds/mo | None | Production-ready |
| **Heroku** | $0 (limited) | Paid add-on | 1 dyno, 550 hrs/mo | 30s sleep | Testing |
| **Replit** | $0 | Embedded DB | RAM-limited | None | Quick demos |
| **Fly.io** | $0 | Free tier | 3 shared-cpu-1x | None | Containers |
| **Google Cloud Run** | $0 | Paid | 2M reqs/month free | Cold start | Serverless |

### 🌟 Recommended: **Render** (Free, Best Dev DX)

**Why Render**:
- ✅ Free tier with no credit card
- ✅ Free PostgreSQL database
- ✅ Auto-deploys from GitHub
- ✅ Easy environment variables
- ✅ Built-in logs & monitoring
- ✅ No cold start (always on free tier)

---

## 📦 Deploy to Render (Recommended - $0/month)

### Step 1: Prepare Repository

```bash
cd /home/swaraj/sj_code/genai_apac_2026/agentic_orchestrator

# Make sure git is clean
git add -A
git commit -m "prepare for deployment"
git push origin dev-v2-architecture

# Push to GitHub (if not already)
# git remote add origin https://github.com/YOUR_USERNAME/repo.git
# git push -u origin main
```

### Step 2: Create Render Account

1. Go to https://render.com
2. Click **Sign up with GitHub**
3. Authorize Render
4. Create organization or use personal

### Step 3: Deploy Backend

1. Click **+ New** → **Web Service**
2. Select your GitHub repository
3. Fill in details:
   - **Name**: `agentic-orchestrator-api`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port 10000`
   - **Python Version**: `3.10`
4. Click **Create Web Service**

### Step 4: Configure Environment Variables

In Render dashboard for your service:

```env
DATABASE_URL=postgresql://<user>:<password>@<host>/<dbname>
SECRET_KEY=your-secret-key-here-change-in-prod
ALGORITHM=HS256
MULTI_TENANT_MODE=true
```

### Step 5: Create PostgreSQL Database

1. In Render, click **+ New** → **PostgreSQL**
2. Choose **Free** tier
3. Fill details:
   - **Name**: `agentic-orchestrator-db`
   - **Database**: `orchestrator`
4. Click **Create Database**
5. Copy connection string → paste in **Backend Environment Variables** as `DATABASE_URL`

### Step 6: Deploy Frontend

1. Click **+ New** → **Static Site**
2. Select GitHub repository
3. Fill in:
   - **Name**: `agentic-orchestrator-ui`
   - **Build Command**: `cd frontend && npm install && npm run build`
   - **Publish Directory**: `frontend/dist`
   - Add **Environment Variable**:
     ```
     VITE_API_BASE_URL=https://agentic-orchestrator-api.onrender.com
     ```
4. Click **Create Static Site**

### Step 7: Test Deployment

```bash
# Backend API
curl https://agentic-orchestrator-api.onrender.com/health

# Frontend
# Open https://agentic-orchestrator-ui.onrender.com

# API Docs
# https://agentic-orchestrator-api.onrender.com/docs
```

### Step 8: Initialize Database (First Time)

```bash
# SSH into Render backend service
# Or run init script:

# In Render dashboard → backend service → Shell
python init_multi_tenant.py
python seed_test_data.py
```

### Deploy Script (Automated)

```bash
#!/bin/bash
# deploy_render.sh

set -e

echo "🚀 Deploying to Render..."

# Push to GitHub
git add -A
git commit -m "deploy: $(date)"
git push origin main

echo "✅ Pushed to GitHub"
echo "📍 Render will auto-deploy in 1-2 mins"
echo "🌐 Check: https://render.com/dashboard"
```

---

## 🚂 Deploy to Railway (Alternative - $5 credit/month)

### Step 1: Create Railway Account

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Set environment
railway environment add staging
```

### Step 2: Add Services

```bash
# Link your repo
railway link

# Create backend service
railway add

# Create postgresql service
railway add  # Select PostgreSQL
```

### Step 3: Configure

```bash
# Set environment variables
railway variables ENVIRONMENT=production
railway variables DATABASE_URL=<postgres-url>
railway variables SECRET_KEY=your-secret

# Deploy
railway up
```

### Step 3: Deploy

```bash
# Deploy to Railway
railway up

# View logs
railway logs

# Get URL
railway open
```

---

## 💜 Deploy to Heroku (Legacy - limited free tier)

**⚠️ Note**: Heroku removed free tier in November 2022. Use Render or Railway instead.

```bash
# If you have existing Heroku account:
heroku create agentic-orchestrator
heroku addons:create heroku-postgresql:free
git push heroku main
heroku run python seed_test_data.py
```

---

## 🔄 Deploy to Replit (Quick - $0/month)

### Quick Demo (No Git Required)

1. Go to https://replit.com
2. Click **Create** → **Import from GitHub**
3. Paste: `https://github.com/your-username/agentic_orchestrator`
4. Click **Import**
5. Wait for dependencies to install
6. Click **Run**

### Backend runs on: `https://<your-replit>.replit.dev`
### Frontend runs on: Built-in Replit webview

---

## 📋 Pre-Deployment Checklist

- [ ] Database URL configured
- [ ] Secret keys not in code
- [ ] Environment variables set
- [ ] Git repository clean
- [ ] No `.env` file committed
- [ ] `requirements.txt` updated
- [ ] `package.json` updated
- [ ] Seed data script runs without errors
- [ ] Tests pass locally

---

## 🔧 Post-Deployment Testing

### 1. Health Check

```bash
curl https://<your-backend>.onrender.com/health
# Should return: {"status": "ok"}
```

### 2. Database Connectivity

```bash
# SSH into backend or via Render Shell:
python -c "from app.db._database import engine; print('DB Connected:', engine)"
```

### 3. Seed Data

```bash
# In Render Shell or Railway terminal:
python backend/seed_test_data.py
```

### 4. API Test

```bash
curl https://<your-backend>.onrender.com/docs
# Should show Swagger UI
```

### 5. Frontend Test

```bash
# Open https://<your-frontend>.onrender.com
# Should load without CORS errors
```

---

## 🚨 Troubleshooting Deployments

### Issue: "DATABASE_URL not found"
**Solution**: Add environment variable in platform dashboard

### Issue: Cold start takes 30+ seconds
**Solution**: Upgrade to paid tier or use Railway

### Issue: CORS errors on frontend
**Solution**: Add to `backend/app/main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Issue: Database connection timeout
**Solution**: 
- Check PostgreSQL credentials
- Verify database is running
- Whitelist IP addresses if needed

### Issue: Frontend can't reach backend
**Solution**:
- Verify `VITE_API_BASE_URL` matches backend URL
- Add `/api/v1` to API calls if needed
- Check CORS headers in backend

---

## 📚 Useful Commands

### Local Testing

```bash
# Terminal 1: Backend
cd backend && source venv/bin/activate
python seed_test_data.py
uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend && npm run dev

# Terminal 3: Database
sqlite3 backend/agentic_orchestrator.db ".tables"
```

### Render Deployment

```bash
# View logs
railway logs

# SSH into service
railway shell

# Check environment
printenv | grep DATABASE_URL
```

### Manual Database Init

```bash
# After deployment, run initialization:
# Via Render Shell / Railway terminal:

cd backend
python -c "from app.db._database import Base, engine; Base.metadata.create_all(bind=engine)"
python seed_test_data.py
```

---

## 💰 Estimated Monthly Costs (Production)

### Render (Recommended)
- Backend: $0 (free tier)
- Frontend: $0 (static, free)
- Database: $0 (free PostgreSQL)
- **Total: $0/month** ✅

### Railway
- Backend: $5 credit
- Database: Included
- **Total: $5/month** ✅

### AWS (Production Scale)
- Backend: $20 (ECS Fargate)
- Database: $50 (RDS PostgreSQL)
- Frontend: $5 (CloudFront CDN)
- **Total: $75+/month**

### Self-Hosted (VPS)
- DigitalOcean: $5-20/month
- Linode: $5-30/month
- Hetzner: €3-20/month

---

## 🎯 Next Steps

1. **Test Locally** (5 mins):
   ```bash
   docker-compose up --build
   ```

2. **Deploy to Render** (15 mins):
   - Create account
   - Connect GitHub
   - Deploy backend + frontend
   - Initialize database

3. **Share with Team**:
   - Frontend URL: `https://agentic-orchestrator-ui.onrender.com`
   - API Docs: `https://agentic-orchestrator-api.onrender.com/docs`

4. **Monitor**:
   - Check Render dashboard for logs
   - Monitor database connections
   - Set up alerts for downtime

---

## 📞 Support & Resources

- **Render Docs**: https://render.com/docs
- **Railway Docs**: https://railway.app/docs
- **FastAPI Docs**: https://fastapi.tiangolo.com
- **React Docs**: https://react.dev

---

**Happy Testing & Deploying! 🚀**
