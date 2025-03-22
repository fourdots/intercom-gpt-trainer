# Intercom-GPT Trainer Integration: Project Summary

## Overview

We've successfully built an integration service that connects Intercom's customer messaging platform with GPT Trainer's AI chatbot capabilities. This integration enables an automated AI-powered customer support experience by:

1. Regularly polling the Intercom API for new customer messages
2. Processing these messages with GPT Trainer's AI
3. Sending AI-generated responses back to customers via Intercom
4. Maintaining conversation context across messages

## Architecture

The integration follows a direct API approach, with a polling mechanism rather than webhooks. The main components are:

### 1. Intercom API Client (`services/intercom_api.py`)
- Handles authentication and communication with Intercom's API
- Provides methods to fetch conversations, get details, send replies
- Implements rate limit handling to prevent API throttling

### 2. GPT Trainer API Client (`services/gpt_trainer.py`)
- Manages communication with GPT Trainer's API
- Creates and manages AI conversation sessions
- Sends user messages and retrieves AI responses

### 3. Session Management (`utils/session_store.py`)
- Maintains mapping between Intercom conversation IDs and GPT Trainer session IDs
- Persists sessions to disk to maintain context even if the service restarts
- Implements automatic cleanup of expired sessions

### 4. Polling Service (`services/poller.py`)
- Regularly checks for new conversations in Intercom
- Processes new user messages through GPT Trainer
- Sends AI responses back to Intercom
- Tracks processing state to avoid duplicate replies

### 5. Retry Mechanism (`utils/retry.py`)
- Custom implementation for retrying API calls with exponential backoff
- Helps handle temporary network issues or service disruptions

## Data Flow

1. The poller regularly checks Intercom for new/updated conversations
2. For each conversation with new user messages:
   - Create/retrieve a GPT Trainer session for the conversation
   - Extract the latest user message
   - Send the message to GPT Trainer
   - Get the AI-generated response
   - Send the response back to the Intercom conversation
   - Mark the conversation as read

## Running the Application

The application is designed to run continuously, with several options for deployment:

### Local Development
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py
```

### Docker Deployment
```bash
# Build and run with Docker
docker build -t intercom-gpt-integration .
docker run -d --env-file .env intercom-gpt-integration
```

### Cloud Deployment
The application is well-suited for deployment on cloud platforms like Google Cloud Run, which provides:
- Automatic scaling based on demand
- Secure secret management
- Simple deployment and monitoring

## Configuration

The application is configured via environment variables stored in the `.env` file:

- **Intercom credentials**:
  - `INTERCOM_ACCESS_TOKEN`: API token for Intercom
  - `INTERCOM_ADMIN_ID`: Admin ID to use when sending replies

- **GPT Trainer credentials**:
  - `GPT_TRAINER_API_KEY`: API key for GPT Trainer
  - `CHATBOT_UUID`: UUID of the specific chatbot to use
  - `GPT_TRAINER_API_URL`: Base URL for the GPT Trainer API

- **Application settings**:
  - `POLLING_INTERVAL`: Seconds between API polls (default: 60)
  - `MAX_CONVERSATIONS`: Maximum conversations to fetch per poll (default: 25)

## Next Steps

1. **Monitoring & Alerts**: Add CloudWatch/Stackdriver monitoring for service health
2. **Analytics**: Track conversation metrics and AI response quality
3. **Fallback Mechanism**: Implement human handoff for complex queries
4. **Conversation Filtering**: Add rules to determine which conversations should be handled by AI 
