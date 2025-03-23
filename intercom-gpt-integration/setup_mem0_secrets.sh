#!/bin/bash
# Script to add Mem0 API credentials to Google Secret Manager

# Exit on error
set -e

# Set project ID (should match the one in deploy.sh)
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

# Adding Mem0 API key to Secret Manager
print_step "Adding Mem0 API key to Secret Manager..."
gcloud secrets create mem0-api-key --replication-policy="automatic" --project=$PROJECT_ID || echo "Secret already exists"
echo -n "m0-ZJnnQgtE2p7dXNGYfA48FDFTMwOCjgYDKIHFAPTi" | gcloud secrets versions add mem0-api-key --data-file=- --project=$PROJECT_ID
print_success "Mem0 API key added successfully!"

# Adding Mem0 organization ID to Secret Manager
print_step "Adding Mem0 organization ID to Secret Manager..."
gcloud secrets create mem0-org-id --replication-policy="automatic" --project=$PROJECT_ID || echo "Secret already exists"
echo -n "org_nlYuwo06MwtLed6Uu5FTOs4dGSSuqxbMHBGdO0pK" | gcloud secrets versions add mem0-org-id --data-file=- --project=$PROJECT_ID
print_success "Mem0 organization ID added successfully!"

# Adding Mem0 project ID to Secret Manager
print_step "Adding Mem0 project ID to Secret Manager..."
gcloud secrets create mem0-project-id --replication-policy="automatic" --project=$PROJECT_ID || echo "Secret already exists"
echo -n "proj_0g0rD4DaygA2SAnun54YvMbc7aFrJNmbIpbkSfc9" | gcloud secrets versions add mem0-project-id --data-file=- --project=$PROJECT_ID
print_success "Mem0 project ID added successfully!"

# Updating service account permissions for Mem0 secrets
print_step "Updating service account permissions for Mem0 secrets..."
gcloud secrets add-iam-policy-binding mem0-api-key \
    --member="serviceAccount:intercom-gpt-sa@intercom-gpt-trainer.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

gcloud secrets add-iam-policy-binding mem0-org-id \
    --member="serviceAccount:intercom-gpt-sa@intercom-gpt-trainer.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID

gcloud secrets add-iam-policy-binding mem0-project-id \
    --member="serviceAccount:intercom-gpt-sa@intercom-gpt-trainer.iam.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor" \
    --project=$PROJECT_ID
print_success "Service account permissions updated successfully!"

print_step "Done! Mem0 secrets are now set up in Secret Manager."
echo "You should now rebuild and redeploy your service with:"
echo "./deploy.sh" 
