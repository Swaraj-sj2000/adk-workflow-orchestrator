#!/bin/bash
set -e

echo "=== Cloud Run Full Deployment Script ==="

# -------------------------
# Project Configuration
# -------------------------
export PROJECT_ID=havoc-ai-prod
export REGION=europe-west1
export IMAGE_NAME=backend-adk
export REPO_NAME=orchestrator-repo
export IMAGE_URI=${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}/${IMAGE_NAME}:latest

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

# -------------------------
# Service Account
# -------------------------
export SA_NAME=ai-workflow-orchestrator
export SERVICE_ACCOUNT=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com

# -------------------------
# Database Configuration
# -------------------------
export INSTANCE_NAME=orchestrator-sql
export DB_NAME=orchestrator
export DB_USER=orchestrator_user

# -------------------------
# Secrets: DB_PASSWORD
# -------------------------
if [ -z "$DB_PASSWORD" ]; then
    echo "Fetching DB_PASSWORD from Secret Manager..."
    if gcloud secrets describe db-password --project=$PROJECT_ID &>/dev/null; then
        export DB_PASSWORD=$(gcloud secrets versions access latest --secret="db-password" --project=$PROJECT_ID)
        echo "✓ DB_PASSWORD retrieved from Secret Manager"
    else
        export DB_PASSWORD=$(openssl rand -base64 32)
        echo "Generated DB_PASSWORD: $DB_PASSWORD"
        echo "IMPORTANT: Save this password securely!"
    fi
fi

# -------------------------
# Secrets: SECRET_KEY
# -------------------------
if [ -z "$SECRET_KEY" ]; then
    echo "Fetching SECRET_KEY from Secret Manager..."
    if gcloud secrets describe backend-secret-key --project=$PROJECT_ID &>/dev/null; then
        export SECRET_KEY=$(gcloud secrets versions access latest --secret="backend-secret-key" --project=$PROJECT_ID)
        echo "✓ SECRET_KEY retrieved from Secret Manager"
    else
        export SECRET_KEY=$(openssl rand -base64 32)
        echo "Generated SECRET_KEY: $SECRET_KEY"
        echo "IMPORTANT: Save this for future deployments!"
    fi
fi

# -------------------------
# Construct DATABASE_URL
# -------------------------
export DATABASE_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"

# -------------------------
# Build Docker Image
# -------------------------
echo "=== Building Docker Image ==="
docker build -t $IMAGE_URI .

# -------------------------
# Push Docker Image
# -------------------------
echo "=== Pushing Docker Image to Artifact Registry ==="
docker push $IMAGE_URI

# -------------------------
# Deploy to Cloud Run
# -------------------------
echo "=== Deploying to Cloud Run ==="
gcloud run deploy $IMAGE_NAME \
  --image $IMAGE_URI \
  --platform managed \
  --region $REGION \
  --service-account=$SERVICE_ACCOUNT \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 1Gi \
  --timeout 300 \
  --concurrency 40 \
  --min-instances 0 \
  --max-instances 10 \
  --add-cloudsql-instances ${PROJECT_ID}:${REGION}:${INSTANCE_NAME} \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true,GEMINI_MODEL=gemini-2.5-flash,GOOGLE_CLOUD_PROJECT=$PROJECT_ID,GOOGLE_CLOUD_LOCATION=$REGION,LOG_LEVEL=INFO,LOG_TO_STDOUT=true,LOG_FILE_ENABLED=false \
  --set-env-vars DATABASE_URL="$DATABASE_URL" \
  --set-env-vars SECRET_KEY="$SECRET_KEY"

echo ""
echo "=== Deployment Complete ==="
echo "Service URL:"
gcloud run services describe $IMAGE_NAME --region $REGION --format='value(status.url)'