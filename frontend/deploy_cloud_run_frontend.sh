#!/bin/bash

# Exit on any error
set -e

echo "=== Frontend Cloud Run Deployment Script ==="

# Project Configuration
export PROJECT_ID=ai-workforce-orchestrator
export REGION=europe-west1

# Backend API URL
export BACKEND_URL=https://backend-adk-239683568115.europe-west1.run.app

gcloud config set project $PROJECT_ID
gcloud config set run/region $REGION

echo ""
echo "=== Configuration Summary ==="
echo "PROJECT_ID: $PROJECT_ID"
echo "REGION: $REGION"
echo "BACKEND_URL: $BACKEND_URL"
echo ""

# Verify required variables are set
if [ -z "$PROJECT_ID" ] || [ -z "$REGION" ] || [ -z "$BACKEND_URL" ]; then
    echo "Error: Missing required environment variables."
    exit 1
fi

echo "=== Building Docker Image ==="
cd "$(dirname "$0")"

# Build the Docker image with backend URL as build arg
docker build \
  --build-arg VITE_API_URL=$BACKEND_URL \
  -t ${REGION}-docker.pkg.dev/${PROJECT_ID}/orchestrator-repo/frontend:latest \
  .

echo ""
echo "=== Pushing Docker Image ==="
docker push ${REGION}-docker.pkg.dev/${PROJECT_ID}/orchestrator-repo/frontend:latest

echo ""
echo "=== Deploying to Cloud Run ==="
gcloud run deploy frontend \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/orchestrator-repo/frontend:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --cpu 1 \
  --memory 512Mi \
  --timeout 60 \
  --concurrency 80 \
  --min-instances 0 \
  --max-instances 5

echo ""
echo "=== Deployment Complete ==="
echo "Get your frontend URL with:"
echo "gcloud run services describe frontend --region $REGION --format='value(status.url)'"
echo ""
echo "=== Testing Frontend ==="
export FRONTEND_URL=$(gcloud run services describe frontend --region $REGION --format='value(status.url)')
echo "Frontend URL: $FRONTEND_URL"
echo "Test with: curl -I $FRONTEND_URL"

echo ""
echo "=== Deployment Complete ==="
echo "Get your service URL with:"
echo "gcloud run services describe backend-adk --region $REGION --format='value(status.url)'"