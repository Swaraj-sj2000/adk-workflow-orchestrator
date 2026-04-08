#!/bin/bash

# Update Cloud Run Backend ADK Environment Variables
# This script updates the environment variables for the deployed backend-adk service

set -e

echo "=== Updating Backend ADK Cloud Run Environment Variables ==="

PROJECT_ID="havoc-ai-prod"
REGION="europe-west1"
SERVICE_NAME="backend-adk"

echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Set project
gcloud config set project $PROJECT_ID

# Update environment variables
echo "Updating environment variables..."
gcloud run services update $SERVICE_NAME \
  --region $REGION \
  --set-env-vars GOOGLE_CLOUD_PROJECT=havoc-ai-prod \
  --set-env-vars GOOGLE_CLOUD_LOCATION=us-central1 \
  --set-env-vars GOOGLE_GENAI_USE_VERTEXAI=true \
  --set-env-vars GEMINI_MODEL=gemini-2.0-flash-exp \
  --set-env-vars GEMINI_TEMPERATURE=0.2 \
  --set-env-vars GEMINI_MAX_TOKENS=900 \
  --set-env-vars ADK_TIMEOUT=60 \
  --set-env-vars BASIC_RATE_LIMIT_REQUESTS=100 \
  --set-env-vars BASIC_RATE_LIMIT_WINDOW_SECONDS=60 \
  --set-env-vars DEBUG=false \
  --set-env-vars LOG_LEVEL=INFO

echo ""
echo "=== Environment Variables Updated Successfully ==="
echo ""
echo "Verify with:"
echo "gcloud run services describe $SERVICE_NAME --region $REGION --format='value(spec.template.spec.containers[0].env)'"
echo ""
echo "Test the service:"
echo "curl https://backend-adk-974381609416.europe-west1.run.app/health"
echo ""
