# Intercom-GPT Trainer Integration: Project Milestone

This document serves as a comprehensive overview of the Intercom-GPT Trainer integration project, detailing what has been accomplished, how the system functions, and what resources it utilizes.

## Project Overview

The Intercom-GPT Trainer Integration is a system that connects Intercom's customer messaging platform with GPT Trainer's AI chatbot service. This integration enables AI-powered customer support by processing customer messages from Intercom, generating intelligent responses using GPT Trainer, and sending these responses back to customers through Intercom.

## System Architecture

The system has been implemented using two different approaches:

1. **Polling-based Integration** (Original Implementation)
   - Regularly polls Intercom API for new messages
   - Processes messages with GPT Trainer
   - Sends AI responses back to Intercom
   - Manages conversation state to prevent multiple AI responses

2. **Webhook-based Integration** (New Implementation)
   - Receives real-time notifications from Intercom when new messages arrive
   - Processes messages with GPT Trainer
   - Sends AI responses back to Intercom
   - Leverages Intercom's webhook functionality for improved efficiency

## Components and Their Functions

### 1. Intercom API Integration
- **File**: `services/intercom_api.py`
- **Purpose**: Handles communication with the Intercom API
- **Key Functions**:
  - `list_conversations()`: Retrieves open conversations
  - `get_conversation()`: Gets details of a specific conversation
  - `reply_to_conversation()`: Sends AI-generated responses to users
  - `mark_conversation_read()`: Marks conversations as read

### 2. GPT Trainer API Integration
- **File**: `services/gpt_trainer.py`
- **Purpose**: Handles communication with the GPT Trainer API
- **Key Functions**:
  - `create_session()`: Initiates a new GPT Trainer session
  - `send_message()`: Sends user messages to GPT Trainer and gets AI responses
  - `verify_session()`: Ensures sessions are valid and active

### 3. Conversation Management
- **File**: `services/conversation_state_manager.py`
- **Purpose**: Manages conversation states to prevent multiple AI responses without user replies
- **States**:
  - `AWAITING_USER_REPLY`: The AI has sent a message and is waiting for a user reply
  - `READY_FOR_RESPONSE`: The user has replied and the AI can now respond
- **Key Functions**:
  - `can_send_ai_response()`: Checks if an AI response is appropriate
  - `mark_ai_response_sent()`: Updates state after sending AI response

### 4. Session Management
- **File**: `utils/session_store.py`
- **Purpose**: Maintains mapping between Intercom conversation IDs and GPT Trainer session IDs
- **Key Functions**:
  - `get_session_id()`: Retrieves GPT Trainer session ID for a conversation
  - `set_session_id()`: Associates a GPT Trainer session with a conversation
  - `delete_session()`: Removes a session from storage

### 5. Polling Service (Original)
- **File**: `services/poller.py`
- **Purpose**: Periodically checks Intercom for new messages
- **Key Functions**:
  - `poll_and_process()`: Main function that polls and processes new messages
  - `start()`: Starts the polling service

### 6. Webhook Server (New)
- **File**: `webhook_server.py`
- **Purpose**: Provides endpoints for Intercom webhook integration
- **Key Endpoints**:
  - `/webhook/intercom`: Receives webhook notifications from Intercom
  - `/auth/callback`: Placeholder for OAuth callback implementation
  - `/health`: Simple health check endpoint

### 7. Message Processing
- **File**: `services/message_processor.py`
- **Purpose**: Cleans and processes messages before sending to GPT Trainer
- **Key Functions**:
  - `process_message()`: Cleans HTML and formats messages

### 8. Rate Limiting
- **File**: `services/rate_limiter.py`
- **Purpose**: Prevents excessive API calls and message sending
- **Key Functions**:
  - `is_rate_limited()`: Checks if a conversation has exceeded rate limits
  - `increment_rate_counter()`: Tracks message counts

## Setup and Configuration

### Environment Variables
The system requires various environment variables set in the `.env` file:

#### Intercom Configuration
```
INTERCOM_ACCESS_TOKEN=your_intercom_access_token
INTERCOM_ADMIN_ID=your_admin_id
INTERCOM_CLIENT_ID=your_intercom_client_id
INTERCOM_CLIENT_SECRET=your_intercom_client_secret
```

#### GPT Trainer Configuration
```
GPT_TRAINER_API_KEY=your_gpt_trainer_api_key
CHATBOT_UUID=your_chatbot_uuid
GPT_TRAINER_API_URL=https://app.gpt-trainer.com/api/v1
```

#### Application Configuration
```
POLLING_INTERVAL=60  # seconds between API polls
MAX_CONVERSATIONS=25  # max conversations to fetch per poll
PORT=8000  # Port for the webhook server
```

#### Ngrok Configuration (for local testing)
```
NGROK_AUTH_TOKEN=your_ngrok_auth_token
NGROK_URL=your_ngrok_domain
WEBHOOK_BASE_URL=your_ngrok_domain
```

### Dependencies
The system requires the following Python packages:
- requests==2.26.0
- python-dotenv==0.19.1
- schedule==1.1.0
- redis==4.1.0 (optional, for caching)
- flask==2.0.1 (for webhook server)

## Webhook Integration Details

### Webhook Setup in Intercom
- **Endpoint URL**: https://intercom-bridge.suprmind.ai/webhook/intercom
- **Subscribed Topics**:
  - `conversation.user.created`: New message from a user or lead
  - `conversation.user.replied`: Reply from a user or lead

### Security
- Webhook requests are signed by Intercom using HMAC SHA-1
- Signatures are verified using the client secret from the app's configuration
- All webhook requests include an `X-Hub-Signature` header

## Running the System

### Polling Approach
```bash
python main.py
```

### Webhook Approach
```bash
python webhook_server.py
```

For local development with webhook testing:
```bash
# Run webhook server
python webhook_server.py

# In another terminal, use ngrok for tunneling
ngrok http 8000

# Test webhook functionality
python test_webhook.py
```

## Current Status

1. **Polling Integration**: Fully functional, can be used as a fallback.

2. **Webhook Integration**: Successfully implemented and tested. The webhook server:
   - Correctly handles webhook validation (HEAD requests)
   - Processes ping notifications
   - Can receive conversation webhooks from Intercom
   - Authenticates webhook requests using signature verification
   - Processes messages and sends responses using GPT Trainer

3. **Testing**: Test scripts are available for both approaches:
   - `test_intercom_connection.py`: Tests Intercom API connectivity
   - `test_gpt_trainer_api.py`: Tests GPT Trainer API connectivity
   - `test_webhook.py`: Tests webhook functionality

## Next Steps

1. **Production Deployment**:
   - Deploy webhook server to a production environment
   - Update Intercom webhook URL to point to production endpoint
   - Set up monitoring and logging

2. **OAuth Implementation**:
   - Implement full OAuth flow for public app integration
   - Complete the `/auth/callback` endpoint

3. **Enhanced Error Handling**:
   - Implement more robust retry mechanisms
   - Add better logging and monitoring

4. **Performance Optimization**:
   - Optimize message processing
   - Consider caching frequently used data

## Troubleshooting

### Common Issues and Solutions

1. **Webhook Not Receiving Events**
   - Verify webhook URL is correct and publicly accessible
   - Check Intercom Developer Hub for webhook delivery status
   - Ensure server is correctly processing the webhook payload

2. **Invalid Signature Errors**
   - Verify client secret is correct in the `.env` file
   - Check that webhook endpoint is properly verifying signatures

3. **No AI Responses Being Sent**
   - Check API tokens and connection
   - Verify conversation state management is working correctly
   - Check rate limiting settings

4. **Port Already in Use**
   - Change the port in the `.env` file
   - Kill any processes using the desired port

## Credentials and Access

All sensitive credentials are stored in the `.env` file and should not be committed to version control. The required credentials include:

1. **Intercom Access Token**: Used to authenticate with the Intercom API
2. **Intercom Admin ID**: Identifies the admin account for sending replies
3. **Intercom Client ID and Secret**: Used for webhook signature verification and OAuth (future)
4. **GPT Trainer API Key**: Authenticates with the GPT Trainer API
5. **GPT Trainer Chatbot UUID**: Identifies which chatbot to use

## Conclusion

The Intercom-GPT Trainer integration now supports both polling-based and webhook-based approaches, with the webhook approach being more efficient and responsive. The system is designed to maintain conversation context, prevent duplicate AI responses, and handle rate limiting appropriately.

This milestone document serves as a comprehensive reference for the project's current state and can be used for future development and troubleshooting. 
