
# Google Cloud Infrastructure Setup Guide for Intercom-GPT Trainer Integration

## 1. Google Cloud Project Setup

### Initial Project Configuration

```bash
# Create a new Google Cloud project (or use an existing one)
gcloud projects create intercom-gpt-integration --name="Intercom GPT Integration"

# Set the active project
gcloud config set project intercom-gpt-integration

# Enable required APIs
gcloud services enable \
  secretmanager.googleapis.com \
  containerregistry.googleapis.com \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  logging.googleapis.com \
  monitoring.googleapis.com
```

### IAM & Permissions

Set up appropriate service accounts and permissions:

```bash
# Create a service account for the application
gcloud iam service-accounts create intercom-gpt-sa \
  --description="Service account for Intercom-GPT Trainer integration" \
  --display-name="Intercom GPT Integration SA"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding intercom-gpt-integration \
  --member="serviceAccount:intercom-gpt-sa@intercom-gpt-integration.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Generate and download a key for local development (optional, but useful for testing)
gcloud iam service-accounts keys create ~/intercom-gpt-sa-key.json \
  --iam-account=intercom-gpt-sa@intercom-gpt-integration.iam.gserviceaccount.com
```

## 2. Secret Manager Setup

### Creating and Managing Secrets

```bash
# Create required secrets for the application
gcloud secrets create intercom-access-token --replication-policy="automatic"
gcloud secrets create intercom-admin-id --replication-policy="automatic"
gcloud secrets create gpt-trainer-api-key --replication-policy="automatic"
gcloud secrets create chatbot-uuid --replication-policy="automatic"

# Add secret values
echo "your-intercom-access-token" | gcloud secrets versions add intercom-access-token --data-file=-
echo "your-intercom-admin-id" | gcloud secrets versions add intercom-admin-id --data-file=-
echo "your-gpt-trainer-api-key" | gcloud secrets versions add gpt-trainer-api-key --data-file=-
echo "your-chatbot-uuid" | gcloud secrets versions add chatbot-uuid --data-file=-
```

### Accessing Secrets in Application Code

```python
# secrets_manager.py
from google.cloud import secretmanager

class SecretsManager:
    """Manage Google Cloud Secret Manager access"""
    
    def __init__(self, project_id="intercom-gpt-integration"):
        self.client = secretmanager.SecretManagerServiceClient()
        self.project_id = project_id
        self.project_path = f"projects/{project_id}"
    
    def get_secret(self, secret_id, version_id="latest"):
        """Get a secret value from Secret Manager"""
        name = f"{self.project_path}/secrets/{secret_id}/versions/{version_id}"
        response = self.client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    
    def load_application_secrets(self):
        """Load all application secrets"""
        return {
            "INTERCOM_ACCESS_TOKEN": self.get_secret("intercom-access-token"),
            "INTERCOM_ADMIN_ID": self.get_secret("intercom-admin-id"),
            "GPT_TRAINER_API_KEY": self.get_secret("gpt-trainer-api-key"),
            "CHATBOT_UUID": self.get_secret("chatbot-uuid")
        }
```

## 3. Google Cloud SDK Installation and Configuration

### Installation

#### macOS
```bash
# Using Homebrew
brew install --cask google-cloud-sdk

# Verify installation
gcloud --version
```

#### Windows
1. Download the installer from: https://cloud.google.com/sdk/docs/install
2. Run the installer and follow the prompts
3. Open a new command prompt and verify with `gcloud --version`

#### Linux
```bash
# Download the SDK
curl -O https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-cli-XXX.0.0-linux-x86_64.tar.gz

# Extract the archive
tar -xf google-cloud-cli-XXX.0.0-linux-x86_64.tar.gz

# Run the installer
./google-cloud-sdk/install.sh

# Initialize the SDK
./google-cloud-sdk/bin/gcloud init
```

### Configuration

```bash
# Log in to your Google account
gcloud auth login

# Configure Docker to use Google Cloud credentials
gcloud auth configure-docker

# Set default project, region, and zone
gcloud config set project intercom-gpt-integration
gcloud config set run/region us-central1
gcloud config set compute/zone us-central1-a
```

## 4. Docker Setup for Local Development

### Docker Installation

#### macOS
```bash
# Install Docker Desktop for Mac
brew install --cask docker
```

#### Windows
1. Download Docker Desktop from: https://www.docker.com/products/docker-desktop
2. Run the installer and follow the prompts

#### Linux
```bash
# Update package index
sudo apt-get update

# Install Docker dependencies
sudo apt-get install \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io

# Enable non-root user to run Docker
sudo usermod -aG docker $USER
newgrp docker
```

### Application Containerization

#### Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV POLLING_INTERVAL=60
ENV USE_SECRET_MANAGER=true
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/service-account.json

# Create directory for credentials
RUN mkdir -p /app/credentials

# Run the application
CMD ["python", "main.py"]
```

#### docker-compose.yml for Local Development
```yaml
version: '3'

services:
  intercom-gpt-integration:
    build: .
    volumes:
      - .:/app
      - ${HOME}/intercom-gpt-sa-key.json:/app/credentials/service-account.json:ro
    env_file:
      - .env.local
    ports:
      - "8080:8080"
    restart: unless-stopped
```

#### .env.local (for local development)
```
# Local development environment
USE_SECRET_MANAGER=false
POLLING_INTERVAL=30

# API Credentials (for local development without Secret Manager)
INTERCOM_ACCESS_TOKEN=your-intercom-access-token
INTERCOM_ADMIN_ID=your-intercom-admin-id
GPT_TRAINER_API_KEY=your-gpt-trainer-api-key
CHATBOT_UUID=your-chatbot-uuid
```

## 5. Cloud Run Deployment

### Building and Deploying to Cloud Run

```bash
# Build the container image
gcloud builds submit --tag gcr.io/intercom-gpt-integration/intercom-gpt-bridge

# Deploy to Cloud Run
gcloud run deploy intercom-gpt-bridge \
  --image gcr.io/intercom-gpt-integration/intercom-gpt-bridge \
  --service-account=intercom-gpt-sa@intercom-gpt-integration.iam.gserviceaccount.com \
  --platform managed \
  --region us-central1 \
  --memory 512Mi \
  --concurrency 10 \
  --timeout 300 \
  --set-env-vars "POLLING_INTERVAL=60,USE_SECRET_MANAGER=true,PROJECT_ID=intercom-gpt-integration" \
  --min-instances 1 \
  --max-instances 3
```

### Continuous Deployment with Cloud Build

#### cloudbuild.yaml
```yaml
steps:
  # Build the container image
  - name: 'gcr.io/cloud-builders/docker'
    args: ['build', '-t', 'gcr.io/$PROJECT_ID/intercom-gpt-bridge:$COMMIT_SHA', '.']

  # Push the container image to Container Registry
  - name: 'gcr.io/cloud-builders/docker'
    args: ['push', 'gcr.io/$PROJECT_ID/intercom-gpt-bridge:$COMMIT_SHA']

  # Deploy container image to Cloud Run
  - name: 'gcr.io/google.com/cloudsdktool/cloud-sdk'
    entrypoint: gcloud
    args:
      - 'run'
      - 'deploy'
      - 'intercom-gpt-bridge'
      - '--image=gcr.io/$PROJECT_ID/intercom-gpt-bridge:$COMMIT_SHA'
      - '--region=us-central1'
      - '--platform=managed'
      - '--service-account=intercom-gpt-sa@$PROJECT_ID.iam.gserviceaccount.com'
      - '--memory=512Mi'
      - '--set-env-vars=POLLING_INTERVAL=60,USE_SECRET_MANAGER=true,PROJECT_ID=$PROJECT_ID'
      - '--min-instances=1'
      - '--max-instances=3'

images:
  - 'gcr.io/$PROJECT_ID/intercom-gpt-bridge:$COMMIT_SHA'
```

### Setting up Cloud Build Trigger

```bash
# Create a trigger for a GitHub repository
gcloud builds triggers create github \
  --name="intercom-gpt-build-deploy" \
  --repo="your-github-org/intercom-gpt-integration" \
  --branch-pattern="main" \
  --build-config="cloudbuild.yaml"
```

## 6. Application Configuration for Secret Manager

### Code for Loading Secrets

```python
# config.py
import os
from dotenv import load_dotenv

# Try to load from .env file for local development
load_dotenv()

def get_configuration():
    """Get application configuration from environment or Secret Manager"""
    # Check if we should use Secret Manager
    use_secret_manager = os.getenv('USE_SECRET_MANAGER', 'false').lower() == 'true'
    
    if use_secret_manager:
        # Import here to avoid dependency in local dev
        from secrets_manager import SecretsManager
        
        try:
            project_id = os.getenv('PROJECT_ID', 'intercom-gpt-integration')
            secrets = SecretsManager(project_id).load_application_secrets()
            
            # Merge with environment variables
            config = {
                # Secrets from Secret Manager
                'INTERCOM_ACCESS_TOKEN': secrets.get('INTERCOM_ACCESS_TOKEN'),
                'INTERCOM_ADMIN_ID': secrets.get('INTERCOM_ADMIN_ID'),
                'GPT_TRAINER_API_KEY': secrets.get('GPT_TRAINER_API_KEY'),
                'CHATBOT_UUID': secrets.get('CHATBOT_UUID'),
                
                # Environment variables
                'POLLING_INTERVAL': int(os.getenv('POLLING_INTERVAL', '60')),
                'USE_SECRET_MANAGER': True
            }
            
            return config
        except Exception as e:
            print(f"Error loading from Secret Manager: {e}")
            print("Falling back to environment variables")
    
    # Use environment variables
    return {
        'INTERCOM_ACCESS_TOKEN': os.getenv('INTERCOM_ACCESS_TOKEN'),
        'INTERCOM_ADMIN_ID': os.getenv('INTERCOM_ADMIN_ID'),
        'GPT_TRAINER_API_KEY': os.getenv('GPT_TRAINER_API_KEY'),
        'CHATBOT_UUID': os.getenv('CHATBOT_UUID'),
        'POLLING_INTERVAL': int(os.getenv('POLLING_INTERVAL', '60')),
        'USE_SECRET_MANAGER': False
    }
```

## 7. Logging and Monitoring

### Cloud Logging Integration

```python
# logging_setup.py
import logging
import os
import google.cloud.logging
from google.cloud.logging.handlers import CloudLoggingHandler

def setup_logging():
    """Configure application logging"""
    # Determine if running in cloud environment
    in_cloud = os.getenv('K_SERVICE') is not None
    
    # Set up root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    logger.handlers = []
    
    # Cloud environment: use Cloud Logging
    if in_cloud:
        try:
            client = google.cloud.logging.Client()
            handler = CloudLoggingHandler(client, name="intercom_gpt_bridge")
            
            # Create and add formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            
            # Add handler to logger
            logger.addHandler(handler)
            
            # Add standard error handler for critical items
            console = logging.StreamHandler()
            console.setLevel(logging.ERROR)
            console.setFormatter(formatter)
            logger.addHandler(console)
            
            logger.info("Cloud Logging initialized")
        except Exception as e:
            # Fallback to console logging
            print(f"Failed to initialize Cloud Logging: {e}")
            _setup_console_logging(logger)
    else:
        # Local environment: use console logging
        _setup_console_logging(logger)
    
    return logger

def _setup_console_logging(logger):
    """Set up console logging for local development"""
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logger.addHandler(console)
    logger.info("Console logging initialized")
```

### Structured Logging

```python
def log_structured_event(event_type, **kwargs):
    """Log a structured event to Cloud Logging"""
    logger = logging.getLogger()
    
    # Build structured log entry
    payload = {
        'event_type': event_type,
        'timestamp': time.time(),
        **kwargs
    }
    
    # Check if Google Cloud Logging is enabled
    in_cloud = os.getenv('K_SERVICE') is not None
    if in_cloud:
        logger.info(payload)
    else:
        # For local development, format as JSON
        logger.info(f"EVENT: {json.dumps(payload)}")
    
    return payload

# Usage
log_structured_event(
    'conversation_processed',
    conversation_id='123456',
    processing_time_ms=1500,
    message_count=3,
    response_length=250
)
```

### Cloud Monitoring Setup

```bash
# Create a custom metric for conversation processing time
gcloud monitoring metrics create custom.googleapis.com/intercom_gpt/conversation_processing_time \
  --project=intercom-gpt-integration \
  --description="Time to process an Intercom conversation" \
  --display-name="Conversation Processing Time" \
  --metric-kind=gauge \
  --value-type=double \
  --unit=ms

# Create alert policy for high processing times
gcloud alpha monitoring policies create \
  --notification-channels="projects/intercom-gpt-integration/notificationChannels/YOUR_CHANNEL_ID" \
  --display-name="High Conversation Processing Time" \
  --condition-display-name="Processing time above threshold" \
  --condition-filter="resource.type = \"cloud_run_revision\" AND resource.labels.service_name = \"intercom-gpt-bridge\" AND metric.type = \"custom.googleapis.com/intercom_gpt/conversation_processing_time\" AND metric.labels.metric_label = \"gauge\" AND value > 5000"
```

## 8. Observability Dashboard

Create a Cloud Monitoring dashboard for your application:

```bash
# Using gcloud beta monitoring dashboards create command
gcloud beta monitoring dashboards create \
  --config-from-file=dashboard.json
```

dashboard.json example:
```json
{
  "displayName": "Intercom-GPT Integration Dashboard",
  "gridLayout": {
    "widgets": [
      {
        "title": "Conversation Processing Time",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"custom.googleapis.com/intercom_gpt/conversation_processing_time\" resource.type=\"cloud_run_revision\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_MEAN"
                  }
                }
              },
              "plotType": "LINE"
            }
          ],
          "yAxis": {
            "label": "Processing Time (ms)",
            "scale": "LINEAR"
          }
        }
      },
      {
        "title": "Conversations Processed",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"custom.googleapis.com/intercom_gpt/conversations_processed_count\" resource.type=\"cloud_run_revision\"",
                  "aggregation": {
                    "alignmentPeriod": "300s",
                    "perSeriesAligner": "ALIGN_SUM",
                    "crossSeriesReducer": "REDUCE_SUM"
                  }
                }
              },
              "plotType": "STACKED_BAR"
            }
          ]
        }
      },
      {
        "title": "API Call Errors",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"custom.googleapis.com/intercom_gpt/api_errors\" resource.type=\"cloud_run_revision\"",
                  "aggregation": {
                    "alignmentPeriod": "300s",
                    "perSeriesAligner": "ALIGN_SUM"
                  }
                }
              },
              "plotType": "STACKED_BAR"
            }
          ]
        }
      },
      {
        "title": "Cloud Run Instance Count",
        "xyChart": {
          "dataSets": [
            {
              "timeSeriesQuery": {
                "timeSeriesFilter": {
                  "filter": "metric.type=\"run.googleapis.com/container/instance_count\" resource.type=\"cloud_run_revision\" resource.label.\"service_name\"=\"intercom-gpt-bridge\"",
                  "aggregation": {
                    "alignmentPeriod": "60s",
                    "perSeriesAligner": "ALIGN_MEAN"
                  }
                }
              },
              "plotType": "LINE"
            }
          ]
        }
      }
    ]
  }
}
```

## 9. Production Scaling and Reliability

### Updating Cloud Run Configuration for Production

```bash
# Update Cloud Run service with production settings
gcloud run services update intercom-gpt-bridge \
  --memory=1Gi \
  --cpu=1 \
  --concurrency=20 \
  --min-instances=1 \
  --max-instances=10 \
  --set-env-vars=POLLING_INTERVAL=30 \
  --timeout=300s
```

### Setting Up a Health Check Endpoint

```python
# In main.py or app.py
from flask import Flask, jsonify

app = Flask(__name__)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for Cloud Run"""
    # Check database connections, API access, etc.
    return jsonify({
        "status": "healthy",
        "version": os.getenv('K_REVISION', 'local'),
        "environment": os.getenv('ENVIRONMENT', 'development')
    })

# Run when deployed to Cloud Run
if __name__ == "__main__":
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
```

## 10. Development Workflow Best Practices

### Local Development Flow

1. Clone the repository:
   ```bash
   git clone https://github.com/your-org/intercom-gpt-integration.git
   cd intercom-gpt-integration
   ```

2. Set up the virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Set up local environment variables:
   ```bash
   cp .env.example .env.local
   # Edit .env.local with your credentials
   ```

4. Run locally for development:
   ```bash
   # Option 1: Direct Python execution
   python main.py
   
   # Option 2: Using Flask development server
   FLASK_APP=api.py FLASK_ENV=development flask run
   
   # Option 3: Docker Compose
   docker-compose up
   ```

### Testing Before Deployment

```bash
# Run linting
flake8 .

# Run unit tests
pytest

# Build and test Docker container locally
docker build -t intercom-gpt-local .
docker run -it --env-file .env.local intercom-gpt-local

# Manual deployment test
gcloud builds submit --tag gcr.io/intercom-gpt-integration/intercom-gpt-bridge:test
gcloud run deploy intercom-gpt-test \
  --image gcr.io/intercom-gpt-integration/intercom-gpt-bridge:test \
  --service-account=intercom-gpt-sa@intercom-gpt-integration.iam.gserviceaccount.com \
  --platform managed \
  --region us-central1 \
  --no-traffic \
  --tag=test
```

## 11. Secrets Rotation and Management

### Automated Secret Rotation

```python
# secrets_rotation.py
import logging
import requests
import base64
import google.cloud.secretmanager as secretmanager

logger = logging.getLogger(__name__)

def rotate_intercom_token(project_id, secret_id):
    """Rotate Intercom access token"""
    client = secretmanager.SecretManagerServiceClient()
    
    # Get the current client ID and secret from Secret Manager
    client_id = get_secret(client, project_id, "intercom-client-id")
    client_secret = get_secret(client, project_id, "intercom-client-secret")
    refresh_token = get_secret(client, project_id, "intercom-refresh-token")
    
    # Get a new access token using the refresh token
    token_response = requests.post(
        "https://api.intercom.io/auth/eagle/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token
        }
    )
    
    if token_response.status_code != 200:
        logger.error(f"Failed to refresh Intercom token: {token_response.text}")
        return False
    
    # Extract the new tokens
    token_data = token_response.json()
    new_access_token = token_data.get("access_token")
    new_refresh_token = token_data.get("refresh_token")
    
    if not new_access_token or not new_refresh_token:
        logger.error("Missing tokens in response")
        return False
    
    # Update access token in Secret Manager
    update_secret(client, project_id, secret_id, new_access_token)
    
    # Update refresh token in Secret Manager
    update_secret(client, project_id, "intercom-refresh-token", new_refresh_token)
    
    logger.info("Successfully rotated Intercom tokens")
    return True

def get_secret(client, project_id, secret_id, version="latest"):
    """Get a secret from Secret Manager"""
    name = f"projects/{project_id}/secrets/{secret_id}/versions/{version}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def update_secret(client, project_id, secret_id, value):
    """Update a secret in Secret Manager"""
    parent = f"projects/{project_id}/secrets/{secret_id}"
    
    # Add new version
    client.add_secret_version(
        request={
            "parent": parent,
            "payload": {"data": value.encode("UTF-8")}
        }
    )
```

### Cloud Scheduler for Regular Rotation

```bash
# Create Cloud Scheduler job for token rotation
gcloud scheduler jobs create http rotate-intercom-token \
  --schedule="0 0 */7 * *" \  # Every 7 days
  --uri="https://intercom-gpt-bridge-rotate-szgowzwfna-uc.a.run.app/rotate-tokens" \
  --http-method=POST \
  --oidc-service-account=intercom-gpt-sa@intercom-gpt-integration.iam.gserviceaccount.com \
  --oidc-token-audience="https://intercom-gpt-bridge-rotate-szgowzwfna-uc.a.run.app" \
  --description="Rotate Intercom access tokens"
```

## 12. Data Privacy and Compliance

### Data Minimization

```python
# message_sanitizer.py
import re

def sanitize_message(message, remove_pii=True):
    """Remove sensitive information from messages before processing"""
    if not message:
        return message
        
    # Remove HTML tags
    message = re.sub(r'<[^>]+>', ' ', message)
    
    if remove_pii:
        # Remove email addresses
        message = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', message)
        
        # Remove phone numbers (various formats)
        message = re.sub(r'\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b', '[PHONE]', message)
        
        # Remove credit card numbers
        message = re.sub(r'\b(?:\d{4}[- ]?){3}\d{4}\b', '[CREDIT_CARD]', message)
        
        # Remove social security numbers
        message = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[SSN]', message)
    
    # Trim extra whitespace
    message = re.sub(r'\s+', ' ', message).strip()
    
    return message

def sanitize_response(response):
    """Sanitize AI responses before sending to user"""
    if not response:
        return response
        
    # Remove any accidentally generated email addresses
    response = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[contact our support team]', response)
    
    # Remove any accidentally generated phone numbers
    response = re.sub(r'\b(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b', '[our support number]', response)
    
    return response
```

## 13. Troubleshooting Guide

```markdown
# Troubleshooting Guide for Intercom-GPT Integration

## Common Issues and Solutions

### Authentication Issues

#### Google Cloud Authentication
```bash
# Check if you're authenticated with gcloud
gcloud auth list

# Re-authenticate if needed
gcloud auth login
```

#### Secret Manager Access Issues
```bash
# Verify permissions on the secrets
gcloud secrets get-iam-policy intercom-access-token

# Grant permissions if needed
gcloud secrets add-iam-policy-binding intercom-access-token \
  --member="serviceAccount:intercom-gpt-sa@intercom-gpt-integration.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Deployment Issues

#### Cloud Build Failures
```bash
# View build logs
gcloud builds log $(gcloud builds list --limit=1 --format="value(id)")

# Test the build locally
gcloud builds submit --config=cloudbuild.yaml --substitutions=COMMIT_SHA=$(git rev-parse HEAD) .
```

#### Cloud Run Issues
```bash
# Check service logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=intercom-gpt-bridge" --limit=50

# Check service status
gcloud run services describe intercom-gpt-bridge
```

### Runtime Issues

#### Configuration
1. Check all environment variables are correctly set
2. Verify Secret Manager access from Cloud Run
3. Test API access to Intercom and GPT Trainer

#### Performance
1. Increase memory/CPU allocation if needed
2. Adjust concurrency settings
3. Check for memory leaks or resource usage issues

#### API Rate Limiting
1. Implement exponential backoff retry strategy
2. Reduce polling frequency
3. Use batch processing instead of individual API calls
```

## 14. Cost Optimization

```markdown
## Cost Optimization Strategies

### Google Cloud Run

- Use minimum instances (0) for dev/staging, minimum 1 for production
- Set appropriate memory and CPU allocations
- Use cloud run gen2 for better pricing

### Secret Manager

- Keep number of secret versions low by cleaning up old versions
- Use Secret Manager API carefully (charged per 10,000 accesses)

### Cloud Logging & Monitoring

- Set appropriate retention periods
- Use log-based metrics carefully
- Filter logs to reduce storage volume

### Container Registry

- Clean up unused container images
- Use lifecycle policies to automatically delete old images

### General

- Set up billing alerts
- Regularly review usage and adjust resources
```

## 15. Useful Commands Cheatsheet

```bash
# Deploy application
gcloud builds submit --tag gcr.io/intercom-gpt-integration/intercom-gpt-bridge
gcloud run deploy intercom-gpt-bridge --image gcr.io/intercom-gpt-integration/intercom-gpt-bridge

# View logs
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=intercom-gpt-bridge" --limit=50

# Update secrets
echo "new-secret-value" | gcloud secrets versions add intercom-access-token --data-file=-

# Check service status
gcloud run services describe intercom-gpt-bridge

# Local development with Docker
docker build -t intercom-gpt-local .
docker run -it --env-file .env.local -p 8080:8080 intercom-gpt-local

# Clean up resources
gcloud run services delete intercom-gpt-bridge
gcloud secrets delete intercom-access-token
gcloud projects delete intercom-gpt-integration
```
