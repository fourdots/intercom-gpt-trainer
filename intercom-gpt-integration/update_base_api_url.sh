#!/bin/bash
# Script to update the BASE_INTERCOM_API_URL environment variable in the Cloud Run service

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

# Get current environment variables
print_step "Getting current environment variables from Cloud Run service..."
CURRENT_ENV=$(gcloud run services describe intercom-gpt-bridge --platform managed --region us-central1 --format="value(spec.template.spec.containers[0].env)")
echo "Current environment variables:"
echo "$CURRENT_ENV"

# Update the environment variables
print_step "Updating the BASE_INTERCOM_API_URL environment variable..."
gcloud run services update intercom-gpt-bridge \
  --platform managed \
  --region us-central1 \
  --update-env-vars="BASE_INTERCOM_API_URL=https://api.intercom.io"

print_success "Successfully updated the BASE_INTERCOM_API_URL environment variable to https://api.intercom.io"
print_step "Getting updated environment variables from Cloud Run service..."
UPDATED_ENV=$(gcloud run services describe intercom-gpt-bridge --platform managed --region us-central1 --format="value(spec.template.spec.containers[0].env)")
echo "Updated environment variables:"
echo "$UPDATED_ENV" 
