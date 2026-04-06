# 🚀 AI Workforce Orchestrator - Google ADK Backend

> Production-ready backend powered by Google ADK and Gemini 2.5 Flash via Vertex AI

This is the **Google ADK version** of the AI Workforce Orchestrator backend, using Gemini 2.5 Flash through Vertex AI instead of LangChain + Hugging Face.

---

## 📋 Table of Contents

- [What's Different from LangChain Backend](#whats-different)
- [Requirements](#requirements)
- [Setup](#setup)
- [Configuration](#configuration)
- [Running the Application](#running)
- [Testing](#testing)
- [Migration Guide](#migration-guide)
- [Troubleshooting](#troubleshooting)

---

## 🔄 What's Different from LangChain Backend

### **LLM Integration**
| Feature | LangChain Backend | ADK Backend |
|---------|-------------------|-------------|
| **LLM Framework** | LangChain + HuggingFace | Google ADK |
| **Model** | Mistral-7B-Instruct (HuggingFace) | Gemini 2.5 Flash (Vertex AI) |
| **API** | HuggingFace Inference API | Google Vertex AI |
| **Authentication** | HF API Token | GCP Service Account |
| **Async Support** | Limited | Native async with ADK |
| **Cost** | Pay-per-request or self-hosted | GCP pay-as-you-go |

### **Key Changes**

1. **LLM Service** (`app/services/_llm_service.py`):
   - Replaced `LangChain` imports with `google.adk.agents`
   - Uses `Agent` class instead of `ChatHuggingFace`
   - Uses `InMemoryRunner` for execution
   - Async-first architecture

2. **Configuration**:
   - Removed `HUGGINGFACEHUB_API_TOKEN`
   - Added `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`
   - Added `GEMINI_MODEL`, `GEMINI_TEMPERATURE`, etc.

3. **Dependencies** (`requirements.txt`):
   - Removed `langchain-core`, `langchain-huggingface`
   - Added `google-adk`, `google-cloud-aiplatform`, `google-genai`

4. **All other modules** remain the same (database, models, API routes, services)

---

## 📦 Requirements

### Prerequisites

- **Python**: 3.10 or higher
- **Google Cloud Project**: With Vertex AI API enabled
- **Service Account**: With appropriate permissions
- **GCP Billing**: Enabled for Vertex AI usage

### Python Dependencies

See [`requirements.txt`](requirements.txt) for the complete list. Key packages:

```bash
google-adk>=0.14
google-cloud-aiplatform>=1.42.0
google-genai>=0.2.0
fastapi[all]>=0.109.0
sqlalchemy>=2.0.25
```

---

## 🛠️ Setup

### 1. Clone and Navigate

```bash
cd /path/to/Hackathon/adk-workflow-orchestrator/backend_adk
```

### 2. Create Virtual Environment

```bash
python3.10 -m venv venv
source venv/bin/activate  # On macOS/Linux
# OR
venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Set Up Google Cloud

#### Option A: Using gcloud CLI (Recommended for Development)

```bash
# Install gcloud CLI if not already installed
# https://cloud.google.com/sdk/docs/install

# Authenticate
gcloud auth application-default login

# Set project
gcloud config set project YOUR_PROJECT_ID
```

#### Option B: Using Service Account Key

1. Create a service account in Google Cloud Console
2. Grant roles:
   - `Vertex AI User`
   - `Service Usage Consumer`
3. Create and download JSON key
4. Set environment variable:

```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-key.json"
```

### 5. Enable Required APIs

```bash
gcloud services enable aiplatform.googleapis.com
gcloud services enable generativelanguage.googleapis.com
```

### 6. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```bash
# Required
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true

# Optional (defaults shown)
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_TOKENS=2048

# Application
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=your-secret-key-here
LOG_LEVEL=INFO
```

### 7. Initialize Database

```bash
# Seed with test data (optional)
python seed_test_data.py
```

---

## ⚙️ Configuration

### Environment Variables

#### Google Cloud & Vertex AI

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_CLOUD_PROJECT` | ✅ Yes | - | Your GCP project ID |
| `GOOGLE_CLOUD_LOCATION` | No | `us-central1` | GCP region for Vertex AI |
| `GOOGLE_APPLICATION_CREDENTIALS` | Conditional | - | Path to service account JSON (if not using gcloud auth) |
| `GOOGLE_GENAI_USE_VERTEXAI` | No | `true` | Use Vertex AI endpoint |
| `VERTEXAI_LOCATION` | No | Same as GOOGLE_CLOUD_LOCATION | Vertex AI specific location |

#### Gemini Model Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_MODEL` | No | `gemini-2.5-flash` | Model to use |
| `GEMINI_TEMPERATURE` | No | `0.2` | Creativity (0.0-1.0) |
| `GEMINI_MAX_TOKENS` | No | `2048` | Max output tokens |

**Available Models:**
- `gemini-2.5-flash` - Fast, cost-effective (recommended)
- `gemini-2.5-pro` - More capable, higher cost
- `gemini-2.0-flash-exp` - Experimental features

#### Application Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite:///./app.db` | Database connection string |
| `SECRET_KEY` | No | `supersecretkey` | JWT secret (change in production!) |
| `LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `DEBUG` | No | `false` | Debug mode |

---

## 🚀 Running the Application

### Development Mode

```bash
# Start the API server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
# In a separate terminal: Start the event worker
python run_event_worker.py
```

Access the application:
- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **OpenAPI**: http://localhost:8000/redoc

### Production Mode

```bash
# Use the run script
chmod +x run.sh
./run.sh

# Or use Gunicorn
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000
```

### Docker (Optional)

```bash
# Build image
docker build -t adk-orchestrator-backend .

# Run container
docker run -p 8000:8000 \
  -e GOOGLE_CLOUD_PROJECT=your-project \
  -e GOOGLE_APPLICATION_CREDENTIALS=/app/key.json \
  -v /path/to/key.json:/app/key.json \
  adk-orchestrator-backend
```

---

## 🧪 Testing

### Run Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/test_llm_service.py -v

# Skip slow tests
pytest -m "not slow"
```

### Test LLM Service Manually

```python
from app.services._llm_service import LLMService

service = LLMService()
result = service.parse_project_intake("Build a web scraper for e-commerce sites")
print(result)
```

### Check Vertex AI Connection

```bash
python -c "
from google.cloud import aiplatform
aiplatform.init(project='your-project-id', location='us-central1')
print('✓ Vertex AI connection successful')
"
```

---

## 🔄 Migration Guide

### From LangChain to ADK Backend

If you're migrating from the original LangChain backend:

1. **Data is compatible**: Database schema is identical
2. **Copy your `.env`**: Then update with GCP credentials
3. **Update environment variables**:
   ```bash
   # Remove
   HUGGINGFACEHUB_API_TOKEN
   HF_MODEL_ID
   HF_TIMEOUT_SECONDS
   
   # Add
   GOOGLE_CLOUD_PROJECT
   GOOGLE_CLOUD_LOCATION
   GEMINI_MODEL
   ```

4. **Existing data**: SQLite database can be copied directly
   ```bash
   cp ../backend/app.db ./app.db
   ```

5. **API endpoints**: Unchanged - frontend works without modification

### Switching Back to LangChain

The original `backend/` directory is unchanged. To switch back:

1. Stop ADK backend
2. Start LangChain backend with original config
3. Database is compatible

---

## 🐛 Troubleshooting

### Common Issues

#### "Google Cloud Project not configured"

**Problem**: `GOOGLE_CLOUD_PROJECT` not set

**Solution**:
```bash
export GOOGLE_CLOUD_PROJECT=your-project-id
# OR add to .env file
```

#### "Permission Denied" or "403 Forbidden"

**Problem**: Service account lacks permissions

**Solution**:
```bash
# Grant required roles
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
  --member="serviceAccount:YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

#### "Quota Exceeded"

**Problem**: Vertex AI quota limits reached

**Solution**:
1. Check quotas: https://console.cloud.google.com/iam-admin/quotas
2. Request increase if needed
3. Consider rate limiting in code

#### "Fallback mode always used"

**Problem**: ADK not initializing properly

**Check**:
```bash
# Verify ADK installation
python -c "import google.adk; print('ADK:', google.adk.__version__)"

# Check logs
tail -f logs/_llm_service.log
```

#### LLM Responses Seem Off

**Solution**: Adjust temperature and prompts
```bash
# Lower temperature for more deterministic responses
GEMINI_TEMPERATURE=0.1

# Higher for more creative responses
GEMINI_TEMPERATURE=0.8
```

### Debug Logging

Enable detailed logging:

```bash
# Set in .env
LOG_LEVEL=DEBUG
ADK_ENABLE_TRACING=true

# View logs
tail -f logs/*.log
```

### Performance Issues

1. **Check Vertex AI latency**: Monitor in Google Cloud Console
2. **Optimize batch sizes**: Adjust event worker batch size
3. **Use caching**: Enable `ADK_ENABLE_CACHING=true`
4. **Consider regions**: Choose closest GCP location

---

## 📊 Cost Estimation

### Gemini 2.5 Flash Pricing (as of 2026)

| Input | Output |
|-------|--------|
| $0.00001875/1K characters | $0.000075/1K characters |

**Example**: 1000 project intake requests/day
- Average input: 500 chars
- Average output: 2000 chars
- Monthly cost: ~$5-10

See latest pricing: https://cloud.google.com/vertex-ai/pricing

---

## 📝 Logging

Logs are stored in `logs/` directory:

- **_llm_service.log**: ADK/Gemini operations
- **main.log**: Application lifecycle
- **_multi_agent_orchestrator.log**: Workflow executions
- **_event_service.log**: Event queue processing
- **_assignment_engine.log**: Task assignments

View logs:
```bash
tail -f logs/_llm_service.log
```

See [LOGGING.md](../LOGGING.md) for detailed documentation.

---

## 🔒 Security Best Practices

1. **Never commit** `.env` or service account keys
2. **Use Secret Manager** for production credentials
3. **Rotate keys** regularly
4. **Enable VPC-SC** for data protection
5. **Monitor usage** in Cloud Console

---

## 🤝 Support

- **Google ADK Docs**: https://google.github.io/adk-docs/
- **Vertex AI Docs**: https://cloud.google.com/vertex-ai/docs
- **Issues**: Create issue in repository
- **Community**: Google ADK Discord

---

## 📄 License

Same license as main project (MIT)

---

**Last Updated**: 2026-04-06  
**ADK Version**: 0.14+  
**Gemini Model**: 2.5 Flash
