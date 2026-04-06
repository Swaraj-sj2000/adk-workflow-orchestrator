# Quick Reference: ADK Backend vs LangChain Backend

## Side-by-Side Comparison

### Starting the Application

**LangChain Backend:**
```bash
cd backend
source venv/bin/activate
export HUGGINGFACEHUB_API_TOKEN=your_token
uvicorn app.main:app --reload
```

**ADK Backend:**
```bash
cd backend_adk
source venv/bin/activate
export GOOGLE_CLOUD_PROJECT=your_project_id
gcloud auth application-default login
uvicorn app.main:app --reload
```

### Environment Variables

**LangChain Backend (.env):**
```bash
HUGGINGFACEHUB_API_TOKEN=hf_xxxxx
HF_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.3
HF_TEMPERATURE=0.2
HF_MAX_NEW_TOKENS=900
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=supersecretkey
```

**ADK Backend (.env):**
```bash
GOOGLE_CLOUD_PROJECT=my-gcp-project
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_GENAI_USE_VERTEXAI=true
GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.2
GEMINI_MAX_TOKENS=2048
DATABASE_URL=sqlite:///./app.db
SECRET_KEY=supersecretkey
```

### Dependencies

**LangChain Backend:**
```
langchain-core
langchain-huggingface
fastapi
sqlalchemy
```

**ADK Backend:**
```
google-adk>=0.14
google-cloud-aiplatform
google-genai
fastapi
sqlalchemy
```

### LLM Service Code Pattern

**LangChain Backend:**
```python
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

class LLMService:
    def __init__(self):
        self.endpoint = HuggingFaceEndpoint(
            repo_id=self.model_id,
            huggingfacehub_api_token=self.token,
            temperature=self.temperature,
        )
        self.chat_model = ChatHuggingFace(llm=self.endpoint)
    
    def parse_project_intake(self, request_text: str):
        messages = [
            SystemMessage(content="You are..."),
            HumanMessage(content=request_text)
        ]
        response = self.chat_model.invoke(messages)
        return self._parse(response.content)
```

**ADK Backend:**
```python
from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.genai import types

class LLMService:
    def __init__(self):
        self.model = "gemini-2.5-flash"
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT")
    
    def parse_project_intake(self, request_text: str):
        agent = Agent(
            name="project_intake_parser",
            model=self.model,
            description="Analyzes project requests...",
            instruction="You are...",
            generate_content_config=types.GenerateContentConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            ),
        )
        
        runner = InMemoryRunner(agent=agent)
        session = asyncio.run(runner.run_async(user_input=request_text))
        return self._parse(self._extract_response(session))
```

### File Structure (Unchanged Parts)

Both backends share identical structure for:
```
app/
├── api/routes/     # All API endpoints
├── core/           # Config, logging, security
├── db/             # Database setup
├── models/         # SQLAlchemy models
├── schemas/        # Pydantic schemas
├── agents/         # Agent definitions
└── services/       # Business logic (except LLM service)
```

### Testing the LLM Service

**LangChain Backend:**
```python
from app.services._llm_service import LLMService

service = LLMService()
print("Enabled:", service.enabled)
print("Model:", service.model_id)

result = service.parse_project_intake("Build a web scraper")
print("Tasks:", len(result.get('tasks', [])))
```

**ADK Backend:**
```python
from app.services._llm_service import LLMService

service = LLMService()
print("Enabled:", service.enabled)
print("Model:", service.model)
print("Project:", service.project_id)

result = service.parse_project_intake("Build a web scraper")
print("Tasks:", len(result.get('tasks', [])))
```

### Cost Comparison (Approximate)

**LangChain + HuggingFace:**
- Free tier: Limited requests/day
- Pay-per-request: $0.01-0.05 per 1K tokens
- Self-hosted: Infrastructure costs

**ADK + Vertex AI:**
- Gemini 2.5 Flash: $0.00001875 per 1K input chars
- Gemini 2.5 Flash: $0.000075 per 1K output chars
- Example: 1000 requests/day ≈ $5-10/month

### Logs Location

**Both backends:**
```
logs/
├── main.log
├── _llm_service.log         # Different content, same structure
├── _multi_agent_orchestrator.log
├── _event_service.log
├── _assignment_engine.log
└── _project.log
```

### Common Issues & Solutions

**LangChain Backend:**
```
Error: "Invalid HuggingFace token"
Solution: Check HUGGINGFACEHUB_API_TOKEN

Error: "Model timeout"
Solution: Increase HF_TIMEOUT_SECONDS

Error: "Rate limit exceeded"  
Solution: Use different model or upgrade plan
```

**ADK Backend:**
```
Error: "Google Cloud Project not configured"
Solution: Set GOOGLE_CLOUD_PROJECT in .env

Error: "Permission denied (403)"
Solution: Grant Vertex AI User role to service account

Error: "Quota exceeded"
Solution: Request quota increase in GCP console

Error: "API not enabled"
Solution: gcloud services enable aiplatform.googleapis.com
```

### Switching Between Backends

**From LangChain to ADK:**
```bash
# 1. Copy database (optional)
cp backend/app.db backend_adk/app.db

# 2. Update environment
cd backend_adk
cp .env.example .env
# Edit .env with GCP credentials

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
uvicorn app.main:app --port 8001
```

**From ADK to LangChain:**
```bash
# 1. Copy database (optional)
cp backend_adk/app.db backend/app.db

# 2. Use existing environment
cd backend
source venv/bin/activate

# 3. Run
uvicorn app.main:app --port 8000
```

### API Endpoints (Identical)

Both backends expose the same REST API:
- `POST /projects` - Create project
- `GET /projects` - List projects
- `POST /multi-agent/intake` - Run intake workflow
- `GET /tasks` - List tasks
- `POST /tasks/{id}/accept` - Accept task
- And all others...

### Database Compatibility

✅ **100% Compatible**: Database files can be used interchangeably
```bash
# Use same database
DATABASE_URL=sqlite:///./shared_app.db
```

### Performance Characteristics

**LangChain + HuggingFace:**
- Latency: 2-5 seconds per request
- Throughput: Limited by API rate limits
- Cold start: ~1 second

**ADK + Vertex AI:**
- Latency: 1-3 seconds per request
- Throughput: High (GCP infrastructure)
- Cold start: <1 second

### When to Use Which

**Use LangChain Backend when:**
- Cost is primary concern (free tier)
- Already have HuggingFace infrastructure
- Need specific open-source models
- No GCP access

**Use ADK Backend when:**
- Need production reliability
- Want Google's latest models (Gemini 2.5)
- Have GCP credits/infrastructure
- Require low latency
- Want enterprise support

---

**Last Updated**: 2026-04-06
