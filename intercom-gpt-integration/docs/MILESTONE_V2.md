# Intercom-GPT Trainer Integration: Project Milestone (v2)

This document serves as a comprehensive overview of the Intercom-GPT Trainer integration project, detailing what has been accomplished, how the system functions, and what resources it utilizes.

## Project Overview

The Intercom-GPT Trainer Integration enables AI-powered customer support by connecting Intercom's messaging platform with GPT Trainer's AI service. The system processes customer messages from Intercom, generates intelligent responses using GPT Trainer, and sends these responses back to customers through Intercom.

## System Architecture

The system has been implemented using two approaches:

1. **Polling-based Integration** (Original Implementation)
   - Regularly polls Intercom API for new messages
   - Processes messages with GPT Trainer
   - Sends AI responses back to Intercom
   - Manages conversation state to prevent multiple AI responses

2. **Webhook-based Integration** (Current Implementation)
   - Receives real-time notifications from Intercom when new messages arrive
   - Processes messages with GPT Trainer
   - Sends AI responses back to Intercom
   - Features improved OAuth support and authentication
   - Supports human agent takeover detection

## Components and Their Functions

### 1. Intercom API Integration
- **File**: `services/intercom_api.py`
- **Purpose**: Handles communication with the Intercom API
- **Key Functions**:
  - `list_conversations()`: Retrieves open conversations
  - `get_conversation()`: Gets details of a specific conversation
  - `reply_to_conversation()`: Sends AI-generated responses to users
  - `mark_conversation_read()`: Marks conversations as read
  - `update_token()`: Updates access token after OAuth flow

### 2. GPT Trainer API Integration
- **File**: `services/gpt_trainer.py`
- **Purpose**: Handles communication with the GPT Trainer API
- **Key Functions**:
  - `create_session()`: Initiates a new GPT Trainer session
  - `send_message()`: Sends user messages to GPT Trainer and gets AI responses
  - `verify_session()`: Ensures sessions are valid and active

### 3. Conversation Management
- **File**: `services/conversation_state_manager.py`
- **Purpose**: Manages conversation states to control AI response flow
- **States**:
  - `AWAITING_USER_REPLY`: The AI has sent a message and is waiting for a user reply
  - `READY_FOR_RESPONSE`: The user has replied and the AI can now respond
  - `ADMIN_TAKEOVER`: A human admin has taken over the conversation
- **Key Functions**:
  - `can_send_ai_response()`: Checks if an AI response is appropriate
  - `mark_ai_response_sent()`: Updates state after sending AI response
  - `mark_user_reply_received()`: Updates state when user replies
  - `mark_admin_takeover()`: Updates state when human admin takes over

### 4. Session Management
- **File**: `utils/session_store.py`
- **Purpose**: Maintains mapping between Intercom conversation IDs and GPT Trainer session IDs
- **Key Functions**:
  - `get_session()`: Retrieves GPT Trainer session ID for a conversation
  - `save_session()`: Associates a GPT Trainer session with a conversation
  - `mark_awaiting_user_reply()`: Updates conversation state
  - `mark_ready_for_response()`: Updates conversation state
  - `mark_admin_takeover()`: Updates conversation state for human intervention

### 5. Webhook Server
- **File**: `webhook_server.py`
- **Purpose**: Provides endpoints for Intercom webhook integration
- **Key Features**:
  - Webhook signature verification for security
  - Duplicate webhook detection to prevent double-processing
  - OAuth flow for Intercom app authentication
  - Admin takeover detection
  - Rate limiting
- **Key Endpoints**:
  - `/webhook/intercom`: Receives webhook notifications from Intercom
  - `/auth/intercom`: Initiates OAuth flow
  - `/auth/callback`: Handles OAuth callback from Intercom
  - `/webhook/debug`: Endpoint for debugging webhook issues
  - `/health`: Simple health check endpoint
  - `/`: Landing page with Connect button

### 6. Message Processing
- **File**: `services/message_processor.py`
- **Purpose**: Cleans and processes messages before sending to GPT Trainer
- **Key Functions**:
  - `clean_message_body()`: Cleans HTML and formats messages

### 7. Rate Limiting
- **File**: `services/rate_limiter.py`
- **Purpose**: Prevents excessive API calls and message sending
- **Key Functions**:
  - `check_rate_limits()`: Checks if a conversation has exceeded rate limits
  - `increment_rate_counter()`: Tracks message counts
- **Default Limits**:
  - 15 responses per conversation
  - 10 responses per minute globally

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
FLASK_SECRET_KEY=random_secret_key  # For Flask session management
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
- flask==2.0.1
- schedule==1.1.0 (for polling approach)

## Webhook Integration Details

### Webhook Setup in Intercom
- **Endpoint URL**: https://your-domain.com/webhook/intercom
- **Subscribed Topics**:
  - `conversation.user.created`: New message from a user or lead
  - `conversation.user.replied`: Reply from a user or lead
  - `conversation.admin.assigned`: Conversation assigned to admin
  - `conversation.admin.replied`: Admin reply to conversation
  - `conversation.admin.single.created`: Admin starts conversation
  - `conversation.admin.closed`: Admin closes conversation

### Security
- Webhook requests are signed by Intercom using HMAC SHA-1
- Signatures are verified using the client secret from the app's configuration
- All webhook requests include an `X-Hub-Signature` header

## OAuth Implementation

The application now supports the full OAuth flow for Intercom:

1. **Authorization**: Users visit the landing page and click "Connect Intercom Account"
2. **Redirection**: Users are redirected to Intercom's authorization page
3. **Permission Grant**: Users grant permissions to the application
4. **Token Exchange**: Application exchanges authorization code for access token
5. **Webhook Registration**: Application automatically registers webhooks with required topics
6. **API Access**: Application can now access Intercom API with proper permissions

## Running the System

### Webhook Approach (Recommended)
```bash
python webhook_server.py
```

### Polling Approach (Alternative)
```bash
python main.py
```

For local development with webhook testing:
```bash
# Run webhook server
python webhook_server.py

# In another terminal, use ngrok for tunneling
ngrok http 8000 --domain your-domain

# Test webhook functionality
python test_webhook.py
```

## Key Improvements

1. **Message Source Detection**:
   - Now properly extracts messages from both conversation_parts and source fields
   - Handles both registered users and anonymous leads

2. **Conversation State Management**:
   - Improved state transitions for more reliable processing
   - Added ADMIN_TAKEOVER state for human intervention
   - Fixed user reply detection and state updates

3. **Rate Limiting Refinements**:
   - Increased per-conversation limit from 3 to 15 messages
   - Increased global rate limit from 5 to 10 messages per minute
   - Better logging of rate limit information

4. **Admin Takeover Detection**:
   - System now detects when a human admin replies to a conversation
   - AI stops responding after human admin intervention
   - Preserves natural conversation flow when support staff joins

5. **Webhook Processing Improvements**:
   - Added duplicate webhook detection to prevent double-processing
   - Improved error handling and recovery
   - Added detailed logging for easier debugging

6. **OAuth Integration**:
   - Complete implementation of Intercom OAuth flow
   - Automatic webhook registration with proper topics
   - Token management and API authentication

## Current Status

1. **Webhook Integration**: Fully functional with:
   - Proper handling of user messages and replies
   - Human admin intervention detection
   - OAuth authentication support
   - Duplicate message prevention

2. **Conversation Processing**:
   - Correctly identifies and processes messages from different sources
   - Maintains proper conversation state
   - Prevents multiple AI responses without user replies
   - Supports human agent takeover

3. **GPT Trainer Integration**:
   - Creates and manages sessions correctly
   - Processes user messages and generates responses
   - Maintains conversation context

4. **Rate Limiting**:
   - Prevents flooding conversations with too many AI responses
   - Reasonable limits for normal conversation flow

## Next Steps

1. **Production Deployment**:
   - Deploy webhook server to a production environment
   - Set up permanent domain and SSL
   - Implement proper token storage (database)

2. **Enhanced Admin Controls**:
   - Dashboard for monitoring conversations
   - Manual override options for AI responses
   - Feedback mechanism for AI responses

3. **Analytics Integration**:
   - Track conversation metrics
   - Measure AI response effectiveness
   - Identify improvement opportunities

4. **Performance Optimization**:
   - Caching for frequently accessed data
   - Database for persistent storage
   - Load balancing for high volume

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

4. **Multiple AI Responses**
   - Check for duplicate webhook processing
   - Verify conversation state transitions

5. **Human Admin Takeover Not Working**
   - Verify webhook topics are correctly subscribed
   - Check admin ID detection logic
   - Review conversation state management

## Credentials and Access

All sensitive credentials are stored in the `.env` file and should not be committed to version control. The required credentials include:

1. **Intercom Access Token**: Used to authenticate with the Intercom API
2. **Intercom Admin ID**: Identifies the admin account for sending replies
3. **Intercom Client ID and Secret**: Used for webhook signature verification and OAuth
4. **GPT Trainer API Key**: Authenticates with the GPT Trainer API
5. **GPT Trainer Chatbot UUID**: Identifies which chatbot to use

## Conclusion

The Intercom-GPT Trainer integration has been significantly enhanced with improved webhook processing, OAuth support, conversation state management, and human admin takeover detection. These improvements provide a more reliable and flexible system for handling customer inquiries with AI assistance while allowing for seamless human intervention when needed.

This milestone document serves as a comprehensive reference for the project's current state and can be used for future development and troubleshooting. 
