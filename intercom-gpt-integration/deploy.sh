#!/bin/bash
# Deployment script for Intercom-GPT Trainer integration

# Exit on error
set -e

# Set project ID (should match the one in setup_gcloud.sh)
PROJECT_ID=${PROJECT_ID:-intercom-gpt-trainer}

# Colors for prettier output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
function print_step() {
  echo -e "${BLUE}[STEP] $1${NC}"
}

function print_success() {
  echo -e "${GREEN}[SUCCESS] $1${NC}"
}

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
  echo "Docker is not running. Please start Docker and try again."
  exit 1
fi

# Build the Docker image for linux/amd64 and push directly to registry
print_step "Building Docker image for linux/amd64 platform and pushing to registry..."
docker buildx build --platform linux/amd64 --push -t gcr.io/$PROJECT_ID/intercom-gpt-bridge:latest .
print_success "Docker image built and pushed successfully!"

# Authenticate with Google Cloud
print_step "Authenticating with Google Cloud..."
gcloud auth configure-docker

# Deploy to Cloud Run
print_step "Deploying to Cloud Run..."
gcloud run deploy intercom-gpt-bridge \
  --image gcr.io/$PROJECT_ID/intercom-gpt-bridge:latest \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --concurrency 10 \
  --timeout 300 \
  --set-env-vars="POLLING_INTERVAL=60,USE_SECRET_MANAGER=true,PROJECT_ID=$PROJECT_ID,BASE_INTERCOM_CLIENT_ID=c900675b-8328-4c2d-8ee5-a3d07ce72e9d,BASE_INTERCOM_CLIENT_SECRET=712646ac-659d-49f6-8f49-fc1446c4013e,WEBHOOK_BASE_URL=https://intercom-gpt-bridge-7dcghnke4a-uc.a.run.app" \
  --min-instances=2 \
  --max-instances=3
print_success "Deployment successful!"

# Get the service URL
print_step "Getting service URL..."
SERVICE_URL=$(gcloud run services describe intercom-gpt-bridge --platform managed --region us-central1 --format="value(status.url)")
print_success "Service deployed at: $SERVICE_URL"

echo ""
echo "Next steps:"
echo "1. Update your Intercom webhook URL to: $SERVICE_URL/webhook/intercom"
echo "2. Test the integration by sending a message in Intercom"
echo "3. View logs with: gcloud logging read 'resource.type=cloud_run_revision AND resource.labels.service_name=intercom-gpt-bridge'"
