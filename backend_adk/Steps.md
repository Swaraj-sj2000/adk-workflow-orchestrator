# Following steps for deployment

```bash
gcloud config set project ai-workforce-orchestrator

```



## Enable APIs:

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  compute.googleapis.com

```

# 1. Set the variables in your terminal first
``` bash
PROJECT_ID=$(gcloud config get-value project)
PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
SA_NAME=ai-tool-service
REGION=europe-west1
```

# 2. Create the .env file using those variables
``` bash

cat <<EOF > .env
PROJECT_ID=$PROJECT_ID
PROJECT_NUMBER=$PROJECT_NUMBER
SA_NAME=$SA_NAME
SERVICE_ACCOUNT=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com
MODEL="gemini-2.5-flash"
EOF
```

Setup IAM permission

``` bash

source .env

gcloud iam service-accounts create ${SA_NAME} \
    --display-name="Service Account for AI Workflow "

# Grant the "Vertex AI User" role to your service account
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:239683568115-compute@developer.gserviceaccount.com" \
  --role="roles/storage.admin"

```

Create Artifact Registry repo (one-time):

```bash
gcloud artifacts repositories create orchestrator-repo \
  --repository-format=docker \
  --location=europe-west1 \
  --description="Docker images for backend_adk"
  ```


Recommended: Cloud SQL Postgres
Create Cloud SQL instance/database/user (example names):


``` bash

Instance: orchestrator-sql
DB: orchestrator
User: orchestrator-user
pass: admin123
```

## 4) Build and push container

From `backend_adk` directory:

``` bash

gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/orchestrator-repo/backend-adk:latest

```

## 5) Deploy Cloud Run service

Create/choose service account (recommended):

- Grant `Vertex AI User` role
- If using Secret Manager: `Secret Manager Secret Accessor`
- If using Cloud SQL: `Cloud SQL Client`
``` bash

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/aiplatform.user"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/run.admin"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SERVICE_ACCOUNT" \
  --role="roles/secretmanager.admin"


```

Deploy:

```bash
gcloud run deploy backend-adk \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/orchestrator-repo/backend-adk:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 1Gi \
  --timeout 300 \
  --concurrency 40 \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GEMINI_MODEL=gemini-2.5-flash,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,LOG_LEVEL=INFO,LOG_TO_STDOUT=true,LOG_FILE_ENABLED=false \
  --set-env-vars DATABASE_URL="YOUR_DATABASE_URL"
```
