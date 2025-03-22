#!/bin/bash
# Setup script for Google Cloud project initialization

# Exit on error
set -e

# Set project name and ID (modify these as needed)
PROJECT_NAME="Intercom GPT Integration"
PROJECT_ID="intercom-gpt-integration"

# Colors for prettier output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Creating Google Cloud project: ${PROJECT_NAME}${NC}"
gcloud projects create $PROJECT_ID --name="$PROJECT_NAME"

echo -e "${BLUE}Setting active project to: ${PROJECT_ID}${NC}"
gcloud config set project $PROJECT_ID

echo -e "${BLUE}Enabling required APIs...${NC}"
gcloud services enable \
  secretmanager.googleapis.com \
  containerregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com

echo -e "${BLUE}Creating service account...${NC}"
gcloud iam service-accounts create intercom-gpt-sa \
  --description="Service account for Intercom-GPT Trainer integration" \
  --display-name="Intercom GPT Integration SA"

echo -e "${BLUE}Granting Secret Manager access...${NC}"
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:intercom-gpt-sa@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

echo -e "${BLUE}Creating secrets...${NC}"
# Read secrets from .env file
if [ -f .env ]; then
  source .env
  
  # Create required secrets for the application
  gcloud secrets create intercom-access-token --replication-policy="automatic"
  gcloud secrets create intercom-admin-id --replication-policy="automatic"
  gcloud secrets create intercom-client-id --replication-policy="automatic"
  gcloud secrets create intercom-client-secret --replication-policy="automatic"
  gcloud secrets create gpt-trainer-api-key --replication-policy="automatic"
  gcloud secrets create chatbot-uuid --replication-policy="automatic"
  
  # Add secret values
  echo -n "$INTERCOM_ACCESS_TOKEN" | gcloud secrets versions add intercom-access-token --data-file=-
  echo -n "$INTERCOM_ADMIN_ID" | gcloud secrets versions add intercom-admin-id --data-file=-
  echo -n "$INTERCOM_CLIENT_ID" | gcloud secrets versions add intercom-client-id --data-file=-
  echo -n "$INTERCOM_CLIENT_SECRET" | gcloud secrets versions add intercom-client-secret --data-file=-
  echo -n "$GPT_TRAINER_API_KEY" | gcloud secrets versions add gpt-trainer-api-key --data-file=-
  echo -n "$CHATBOT_UUID" | gcloud secrets versions add chatbot-uuid --data-file=-
  
  echo -e "${GREEN}Secrets created successfully!${NC}"
else
  echo -e "\033[0;31mWarning: .env file not found. Secrets were created but not populated.${NC}"
  echo -e "\033[0;33mYou'll need to add values manually:${NC}"
  echo "gcloud secrets versions add intercom-access-token --data-file=-"
fi

echo -e "${GREEN}Google Cloud project setup completed!${NC}"
echo -e "${BLUE}Next steps:${NC}"
echo "1. Build and deploy the container: gcloud builds submit --tag gcr.io/${PROJECT_ID}/intercom-gpt-bridge"
echo "2. Deploy to Cloud Run: gcloud run deploy intercom-gpt-bridge --image gcr.io/${PROJECT_ID}/intercom-gpt-bridge"
echo "3. Or use Cloud Build for CI/CD: gcloud builds submit --config=cloudbuild.yaml"
