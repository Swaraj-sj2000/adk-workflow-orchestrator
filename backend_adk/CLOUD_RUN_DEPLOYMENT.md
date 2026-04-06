# Cloud Run Deployment Guide for backend_adk

## 1) Pre-deployment code readiness checklist

These are the key changes needed for this codebase to run reliably on Cloud Run:

- Use container entrypoint with `PORT` env var (`uvicorn ... --port ${PORT}`)
- Stream app logs to stdout/stderr (Cloud Logging ingestion)
- Avoid SQLite for production (ephemeral filesystem in Cloud Run)
- Use environment variables (not local `.env`) for secrets and config
- Use IAM service account for Vertex AI (no local key file in container)
- Keep `/healthz` or `/` endpoint for startup/liveness checks
- Run long-lived worker separately (Cloud Run Job / Cloud Tasks), not inside API container

This repository now includes:
- `Dockerfile`
- `.dockerignore`
- Cloud-Run-safe logging setup in `app/core/_logging.py`
- Cloud-Run-safe DB setup in `app/db/_database.py`

## 2) Required GCP setup

Set your project and region:

```bash
gcloud config set project YOUR_PROJECT_ID
gcloud config set run/region YOUR_REGION
```

Enable APIs:

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com aiplatform.googleapis.com
```

Create Artifact Registry repo (one-time):

```bash
gcloud artifacts repositories create orchestrator-repo \
  --repository-format=docker \
  --location=YOUR_REGION \
  --description="Docker images for backend_adk"
```

## 3) Choose production database

### Recommended: Cloud SQL Postgres

Create Cloud SQL instance/database/user (example names):
- Instance: `orchestrator-sql`
- DB: `orchestrator`
- User: `orchestrator_user`

Then set SQLAlchemy URL like:

```bash
DATABASE_URL=postgresql+psycopg2://orchestrator_user:PASSWORD@/orchestrator?host=/cloudsql/PROJECT:REGION:INSTANCE
```

If you use Postgres, add driver to `requirements.txt`:

```txt
psycopg2-binary>=2.9.9
```

## 4) Build and push container

From `backend_adk` directory:

```bash
gcloud builds submit --tag YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/orchestrator-repo/backend-adk:latest
```

## 5) Deploy Cloud Run service

Create/choose service account (recommended):
- Grant `Vertex AI User` role
- If using Secret Manager: `Secret Manager Secret Accessor`
- If using Cloud SQL: `Cloud SQL Client`

Deploy:

```bash
gcloud run deploy backend-adk \
  --image YOUR_REGION-docker.pkg.dev/YOUR_PROJECT_ID/orchestrator-repo/backend-adk:latest \
  --platform managed \
  --region YOUR_REGION \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 1Gi \
  --timeout 300 \
  --concurrency 40 \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GEMINI_MODEL=gemini-2.5-flash,GOOGLE_CLOUD_PROJECT=YOUR_PROJECT_ID,GOOGLE_CLOUD_LOCATION=YOUR_REGION,LOG_LEVEL=INFO,LOG_TO_STDOUT=true,LOG_FILE_ENABLED=false \
  --set-env-vars DATABASE_URL="YOUR_DATABASE_URL"
```

If using Cloud SQL Unix socket, also add:

```bash
--add-cloudsql-instances PROJECT:REGION:INSTANCE
```

## 6) Verify deployment

Get URL:

```bash
gcloud run services describe backend-adk --region YOUR_REGION --format='value(status.url)'
```

Health checks:

```bash
curl https://SERVICE_URL/
```

Check logs:

```bash
gcloud run services logs read backend-adk --region YOUR_REGION --limit 100
```

## 7) Event worker strategy (important)

`run_event_worker.py` is a long-running worker and should **not** run in the same Cloud Run API service.

Options:
- Cloud Run Job triggered by Cloud Scheduler
- Cloud Tasks + API endpoint to process batches
- Separate worker service with explicit control

## 8) Recommended follow-up hardening

- Restrict CORS in production (`allow_origins` not `*`)
- Move `SECRET_KEY` and DB password to Secret Manager
- Add explicit `/healthz` endpoint if you want distinct health probing
- Add DB migrations with Alembic in CI/CD
- Set min instances for cold-start sensitive workloads

## 9) Minimal environment variables reference

Required:
- `GOOGLE_CLOUD_PROJECT`
- `GOOGLE_CLOUD_LOCATION`
- `GOOGLE_GENAI_USE_VERTEXAI=true`
- `GEMINI_MODEL=gemini-2.5-flash`
- `DATABASE_URL`
- `SECRET_KEY`

Recommended:
- `LOG_LEVEL=INFO`
- `LOG_TO_STDOUT=true`
- `LOG_FILE_ENABLED=false`

## 10) Known current code caveat

Ensure `app/services/_llm_service.py` uses Vertex/Gemini runtime dependencies that exist in `requirements.txt`. If this file is reverted to LangChain imports, deployment will fail unless LangChain dependencies are reintroduced.
