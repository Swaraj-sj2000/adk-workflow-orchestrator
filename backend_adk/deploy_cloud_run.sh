#!/bin/bash

# Exit on any error
set -e

echo "=== Cloud Run Deployment Script ==="

# Project Configuration
export PROJECT_ID=ai-workforce-orchestrator
export REGION=europe-west1

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

export PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")

# Service Account Configuration
export SA_NAME=ai-workflow-orchestrator
export SERVICE_ACCOUNT=${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com

# Database Configuration
export INSTANCE_NAME=orchestrator-sql
export DB_NAME=orchestrator
export DB_USER=orchestrator_user

# Fetch DB_PASSWORD from Secret Manager if not provided
if [ -z "$DB_PASSWORD" ]; then
    echo "Fetching DB_PASSWORD from Secret Manager..."
    if gcloud secrets describe db-password --project=$PROJECT_ID &>/dev/null; then
        export DB_PASSWORD=$(gcloud secrets versions access latest --secret="db-password" --project=$PROJECT_ID)
        echo "✓ DB_PASSWORD retrieved from Secret Manager"
    else
        export DB_PASSWORD=$(openssl rand -base64 32)
        echo "Generated DB Password: $DB_PASSWORD"
        echo "IMPORTANT: Save this password securely!"

        gcloud sql users create $DB_USER \
          --instance=$INSTANCE_NAME \
          --password="$DB_PASSWORD"

        echo " DB_PASSWORD created"
    fi
fi

# Fetch SECRET_KEY from Secret Manager if not provided
if [ -z "$SECRET_KEY" ]; then
    echo "Fetching SECRET_KEY from Secret Manager..."
    if gcloud secrets describe backend-secret-key --project=$PROJECT_ID &>/dev/null; then
        export SECRET_KEY=$(gcloud secrets versions access latest --secret="backend-secret-key" --project=$PROJECT_ID)
        echo "✓ SECRET_KEY retrieved from Secret Manager"
    else
        echo "Generating new SECRET_KEY..."
        export SECRET_KEY=$(openssl rand -base64 32)
        echo "Generated SECRET_KEY: $SECRET_KEY"
        echo "IMPORTANT: Save this for future use!"
        echo ""
        echo "To store in Secret Manager for future deployments:"
        echo "echo -n '$SECRET_KEY' | gcloud secrets create backend-secret-key --data-file=-"
    fi
fi

# Construct DATABASE_URL (now DB_PASSWORD is defined)
export DATABASE_URL="postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@/${DB_NAME}?host=/cloudsql/${PROJECT_ID}:${REGION}:${INSTANCE_NAME}"

echo ""
echo "=== Configuration Summary ==="
echo "PROJECT_ID: $PROJECT_ID"
echo "REGION: $REGION"
echo "SERVICE_ACCOUNT: $SERVICE_ACCOUNT"
echo "INSTANCE_NAME: $INSTANCE_NAME"
echo "DB_NAME: $DB_NAME"
echo "DB_USER: $DB_USER"
echo "SECRET_KEY: ${SECRET_KEY:0:10}... (truncated)"
echo "DATABASE_URL: postgresql+psycopg2://${DB_USER}:****@/${DB_NAME}?host=/cloudsql/..."
echo ""

# Verify all required variables are set
if [ -z "$DB_PASSWORD" ] || [ -z "$PROJECT_ID" ] || [ -z "$REGION" ] || [ -z "$INSTANCE_NAME" ] || [ -z "$SERVICE_ACCOUNT" ] || [ -z "$SECRET_KEY" ]; then
    echo "Error: Missing required environment variables."
    exit 1
fi

echo "=== Deploying to Cloud Run ==="
gcloud run deploy backend-adk \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/orchestrator-repo/backend-adk:latest \
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
echo "Get your service URL with:"
echo "gcloud run services describe backend-adk --region $REGION --format='value(status.url)'"