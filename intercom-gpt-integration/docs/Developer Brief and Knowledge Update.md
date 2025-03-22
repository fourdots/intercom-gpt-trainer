# Developer Brief and Knowledge Update

## Intercom-GPT Trainer Integration: Developer Brief

## Project Overview

The Intercom-GPT Trainer Integration connects Intercom's customer messaging platform with GPT Trainer's AI chatbot service, enabling AI-powered customer support. The system processes customer messages from Intercom, generates responses using GPT Trainer, and sends these responses back to customers through Intercom.

## System Architecture

The project implements two approaches:

### 1\. Polling-based Integration (Original)

- Regularly polls Intercom API for new messages  
- Processes messages with GPT Trainer  
- Sends AI responses back to Intercom  
- Uses `main.py` as entry point

### 2\. Webhook-based Integration (Current Preferred)

- Receives real-time notifications from Intercom via webhooks  
- Processes messages and sends responses via GPT Trainer  
- Leverages `webhook_server.py` as entry point  
- Requires ngrok or similar for local development

## Key Components

### Core Services (`services/`)

- **intercom\_api.py**: Handles all Intercom API interactions  
- **gpt\_trainer.py**: Manages communication with GPT Trainer API  
- **conversation\_state\_manager.py**: Manages conversation states (AWAITING\_USER\_REPLY/READY\_FOR\_RESPONSE)  
- **message\_processor.py**: Cleans and formats messages before processing  
- **rate\_limiter.py**: Prevents excessive API calls and message frequency  
- **poller.py**: Implements the polling mechanism for the original approach  
- **conversation\_processor.py**: Processes conversations and manages workflow

### Utilities (`utils/`)

- **session\_store.py**: Maps Intercom conversation IDs to GPT Trainer session IDs  
- **persistence.py**: Handles data persistence across application restarts  
- **retry.py**: Implements retry mechanisms for API calls

### Server Implementation

- **webhook\_server.py**: Flask server implementing webhook endpoints for Intercom  
- **main.py**: Entry point for polling-based approach

### Testing & Debugging

- **test\_webhook.py**: Tests webhook functionality  
- **test\_intercom\_connection.py**: Tests Intercom API connectivity  
- **test\_gpt\_trainer\_api.py**: Tests GPT Trainer API connectivity  
- **emergency\_fix.py**: Emergency mechanisms to reset conversation states

## Conversation Flow

1. **Initial Message**:  
     
   - User sends message to Intercom  
   - Message is received via webhook or polling  
   - Conversation state is READY\_FOR\_RESPONSE by default

   

2. **AI Processing**:  
     
   - ConversationStateManager verifies state allows response  
   - GPT Trainer generates response  
   - Response sent back to Intercom  
   - State changes to AWAITING\_USER\_REPLY

   

3. **Follow-up Messages**:  
     
   - User response changes state to READY\_FOR\_RESPONSE  
   - AI responds only when user has replied (prevents multiple AI messages)

## Webhook Integration

### Key Endpoints

- `/webhook/intercom`: Receives notifications from Intercom  
- `/auth/callback`: Placeholder for OAuth implementation  
- `/health`: Health check endpoint

### Security

- Webhook requests signed using HMAC SHA-1  
- Signatures verified with client secret  
- All webhook requests include X-Hub-Signature header

## Configuration

### Environment Variables (.env)

- **Intercom**: ACCESS\_TOKEN, ADMIN\_ID, CLIENT\_ID, CLIENT\_SECRET  
- **GPT Trainer**: API\_KEY, CHATBOT\_UUID, API\_URL  
- **Application**: POLLING\_INTERVAL, MAX\_CONVERSATIONS, PORT  
- **Ngrok**: AUTH\_TOKEN, URL, WEBHOOK\_BASE\_URL

### Dependencies (requirements.txt)

- requests  
- python-dotenv  
- schedule  
- flask  
- (optional) redis for caching

## Running the System

### Webhook Approach (Preferred)

python webhook\_server.py

### Polling Approach (Alternative)

python main.py

### Local Development with Ngrok

\# Terminal 1

python webhook\_server.py

\# Terminal 2

ngrok http 8000

## Current Status

- **Webhook Integration**: Functioning and preferred method  
- **Webhook Server**: Running successfully (PID 50013, 47508\)  
- **Ngrok Tunnel**: Currently inactive, needs to be restarted for external access  
- **Intercom Configuration**: Successfully configured with webhook settings  
- **Testing**: Test scripts available and functional

## File Structure

intercom-gpt-integration/

├── webhook\_server.py         \# Main webhook server

├── main.py                   \# Entry point for polling approach

├── services/                 \# Core services

│   ├── intercom\_api.py       \# Intercom API integration

│   ├── gpt\_trainer.py        \# GPT Trainer API integration

│   ├── conversation\_state\_manager.py  \# State management

│   ├── message\_processor.py  \# Message cleaning/formatting

│   ├── rate\_limiter.py       \# Rate limiting

│   └── poller.py             \# Polling implementation

├── utils/                    \# Utility functions

│   ├── session\_store.py      \# Session management

│   ├── persistence.py        \# Data persistence

│   └── retry.py              \# Retry mechanisms

├── tests/                    \# Test scripts

├── MILESTONE.md              \# Project milestone document

├── CONVERSATION\_FLOW.md      \# Conversation flow documentation

└── README.md                 \# Project overview

## Preventing Multiple AI Messages

The system prevents multiple AI messages without user replies through:

1. **ConversationStateManager**: Tracks conversation states  
2. **SessionStore**: Maintains mapping between conversations and sessions  
3. **State Transitions**: Only allows AI responses when in READY\_FOR\_RESPONSE state  
4. **Rate Limiting**: Prevents excessive messages to same conversation

## Next Steps

1. **OAuth Implementation**: Complete the `/auth/callback` endpoint  
2. **Production Deployment**: Deploy webhook server to production  
3. **Enhanced Error Handling**: Implement robust retry mechanisms  
4. **Performance Optimization**: Message processing improvements and caching

## Troubleshooting

1. **Ngrok Tunnel Down**: Restart with `ngrok http 8000`  
2. **Webhook Not Receiving Events**: Verify URL and Intercom settings  
3. **Invalid Signature Errors**: Check CLIENT\_SECRET in .env  
4. **No AI Responses**: Verify API tokens and conversation state

## Testing the Integration

1. **Webhook Testing**: Use `test_webhook.py` to simulate Intercom webhooks  
2. **API Testing**: Use `test_intercom_connection.py` and `test_gpt_trainer_api.py`  
3. **Manual Testing**: Send test messages in Intercom and verify responses

This document serves as a comprehensive reference for the project's architecture, components, and operation. Use it to quickly refresh your understanding of the system or to onboard new team members.  
