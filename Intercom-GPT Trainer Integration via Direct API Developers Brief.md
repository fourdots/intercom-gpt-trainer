
# Developer Brief: Intercom-GPT Trainer Integration via Direct API

## 1. Executive Summary

This brief outlines the implementation process for integrating Intercom's customer messaging platform with GPT Trainer's AI chatbot service using direct API integration. The solution enables an AI-powered customer support experience by actively fetching customer messages from Intercom's API, processing them with GPT Trainer, and sending AI-generated responses back to customers through Intercom.

## 2. Project Overview

### Objective
Create a robust API-based integration service that:
- Regularly polls Intercom API for new messages
- Processes customer inquiries through GPT Trainer
- Sends AI responses back to customers via Intercom's API
- Maintains conversation context across messages

### Architecture
The solution follows a direct API integration approach with a service that regularly polls for new messages rather than relying on webhooks.

## 3. Technical Requirements

### Dependencies
```
requests==2.26.0
python-dotenv==0.19.1
schedule==1.1.0  # For scheduling API polling
retrying==1.3.3  # For implementing retry logic
redis==4.1.0     # Optional: For caching and session storage
```

### Environment Configuration
Key environment variables:
```
# Intercom Configuration
INTERCOM_ACCESS_TOKEN=your_intercom_access_token
INTERCOM_ADMIN_ID=your_admin_id

# GPT Trainer Configuration
GPT_TRAINER_API_KEY=your_gpt_trainer_api_key
CHATBOT_UUID=your_chatbot_uuid
GPT_TRAINER_API_URL=https://app.gpt-trainer.com/api/v1

# Application Configuration
POLLING_INTERVAL=60  # seconds between API polls
MAX_CONVERSATIONS=25  # max conversations to fetch per poll
```

## 4. API Integration Details

### Intercom API

#### Authentication
Intercom uses Bearer token authentication for direct API access:
```python
headers = {
    "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
    "Accept": "application/json",
    "Content-Type": "application/json"
}
```

#### Key Endpoints

1. **List Conversations**: `https://api.intercom.io/conversations`
   - Method: GET
   - Query Parameters:
     - `per_page`: Number of conversations to retrieve (max 60)
     - `order`: Sort order (default: desc)
     - `state`: Conversation state (e.g., "open", "closed")
     - `sort`: Sort field (e.g., "updated_at")
   - Example:
     ```python
     response = requests.get(
         "https://api.intercom.io/conversations",
         headers=headers,
         params={
             "per_page": 25,
             "state": "open",
             "sort": "updated_at",
             "order": "desc"
         }
     )
     ```

2. **Get Conversation**: `https://api.intercom.io/conversations/{conversation_id}`
   - Method: GET
   - Purpose: Retrieve detailed conversation data including all messages
   - Example:
     ```python
     response = requests.get(
         f"https://api.intercom.io/conversations/{conversation_id}",
         headers=headers
     )
     ```

3. **Reply to Conversation**: `https://api.intercom.io/conversations/{conversation_id}/reply`
   - Method: POST
   - Payload:
     ```json
     {
       "type": "admin",
       "admin_id": "your_admin_id",
       "message_type": "comment",
       "body": "<p>AI-generated response here</p>"
     }
     ```
   - Example:
     ```python
     payload = {
         "type": "admin",
         "admin_id": INTERCOM_ADMIN_ID,
         "message_type": "comment",
         "body": f"<p>{ai_response}</p>"
     }
     response = requests.post(
         f"https://api.intercom.io/conversations/{conversation_id}/reply",
         headers=headers,
         json=payload
     )
     ```

4. **Mark Conversation as Read**: `https://api.intercom.io/conversations/{conversation_id}/read`
   - Method: PUT
   - Purpose: Mark a conversation as read to acknowledge processing
   - Example:
     ```python
     response = requests.put(
         f"https://api.intercom.io/conversations/{conversation_id}/read",
         headers=headers
     )
     ```

#### Conversation Data Structure

Key fields in the conversation object:
- `id`: Unique identifier for the conversation
- `created_at`: Unix timestamp of creation
- `updated_at`: Unix timestamp of last update
- `waiting_since`: Time the conversation has been waiting for reply
- `conversation_message`: Initial message that started the conversation
- `conversation_parts`: Array of subsequent messages in the conversation

```json
{
  "type": "conversation",
  "id": "63371900193178",
  "created_at": 1616682576,
  "updated_at": 1616682672,
  "waiting_since": 1616682576,
  "conversation_message": {
    "type": "conversation_message",
    "id": "635252523178",
    "body": "<p>Hello, I need help with my order</p>",
    "author": {
      "type": "user",
      "id": "5b36504e1dcaa1257ff58414"
    }
  },
  "conversation_parts": {
    "total_count": 2,
    "conversation_parts": [
      {
        "type": "conversation_part",
        "id": "636363636",
        "part_type": "comment",
        "body": "<p>Can you help me track my package?</p>",
        "created_at": 1616682600,
        "author": {
          "type": "user",
          "id": "5b36504e1dcaa1257ff58414"
        }
      }
    ]
  }
}
```

#### Conversation ID
- A unique identifier for each Intercom conversation 
- Format: Alphanumeric (e.g., `63371900193178`)
- Used to retrieve conversation details and send replies
- Critical for mapping to GPT Trainer sessions

#### Rate Limiting
Intercom enforces rate limits on API requests:
- Basic plan: ~83 requests/minute (~5,000/hour)
- Standard plan: ~167 requests/minute (~10,000/hour)

Implementation recommendations:
- Implement exponential backoff retry mechanism
- Track rate limits via response headers
- Spread requests evenly rather than bursting

```python
# Rate limit tracking
def track_rate_limits(response):
    """Track Intercom API rate limits from response headers"""
    rate_limit_headers = {
        'X-RateLimit-Limit': response.headers.get('X-RateLimit-Limit'),
        'X-RateLimit-Remaining': response.headers.get('X-RateLimit-Remaining'),
        'X-RateLimit-Reset': response.headers.get('X-RateLimit-Reset')
    }
    
    # Log current rate limit status
    logger.debug(f"Intercom API rate limits: {rate_limit_headers}")
    
    # If close to limit, delay next request
    remaining = int(rate_limit_headers['X-RateLimit-Remaining'] or 1000)
    if remaining < 10:
        reset_time = int(rate_limit_headers['X-RateLimit-Reset'] or 0)
        current_time = int(time.time())
        sleep_time = max(0, reset_time - current_time)
        logger.warning(f"Rate limit nearly reached. Sleeping for {sleep_time} seconds")
        time.sleep(sleep_time)
```

### GPT Trainer API

#### Authentication
GPT Trainer uses Bearer token authentication:
```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {GPT_TRAINER_API_KEY}"
}
```

#### Key Endpoints
1. **Session Creation**: `https://app.gpt-trainer.com/api/v1/chatbot/{CHATBOT_UUID}/session/create`
   - Method: POST
   - Purpose: Creates a new conversation session
   - Response: Returns a session UUID

2. **Message Processing**: `https://app.gpt-trainer.com/api/v1/session/{session_id}/message/stream`
   - Method: POST
   - Payload:
     ```json
     {
       "query": "Customer message here",
       "stream": false
     }
     ```
   - Response: Returns the AI-generated text response

#### Session UUID
- A unique identifier for a GPT Trainer conversation
- Format: UUID string (e.g., `30894fe9c1c648c9b8a3debced1edad1`)
- Critical for maintaining conversation context
- Must be stored and mapped to Intercom's conversation ID

## 5. Data Flow Architecture

```
┌───────────┐         ┌──────────────┐         ┌───────────────┐
│  Intercom │         │ Integration  │         │  GPT Trainer  │
│  Platform │◄────────┤ Service      │◄────────┤  API Service  │
└───────────┘         └──────────────┘         └───────────────┘
      │                      │                         │
      │                      │                         │
      │  1. Poll for         │                         │
      │  open conversations  │                         │
      │◄─────────────────────│                         │
      │                      │                         │
      │  2. Return           │                         │
      │  conversation data   │                         │
      │─────────────────────▶│                         │
      │                      │                         │
      │                      │  3. Create/Get Session  │
      │                      │────────────────────────▶│
      │                      │                         │
      │                      │  4. Session UUID        │
      │                      │◀────────────────────────│
      │                      │                         │
      │                      │  5. Send Message        │
      │                      │────────────────────────▶│
      │                      │                         │
      │                      │  6. AI Response         │
      │                      │◀────────────────────────│
      │                      │                         │
      │  7. Send Reply       │                         │
      │◀─────────────────────│                         │
      │                      │                         │
      │  8. Mark as Read     │                         │
      │◀─────────────────────│                         │
```

## 6. Key Implementation Components

### 1. Integration Service Structure

```
intercom-gpt-api-integration/
├── main.py               # Main application entry point
├── requirements.txt      # Dependencies
├── .env                  # Environment variables
├── services/
│   ├── intercom_api.py   # Intercom API client
│   ├── gpt_trainer.py    # GPT Trainer API client
│   └── poller.py         # Conversation polling service
├── utils/
│   ├── message_parser.py # Message extraction utilities
│   └── session_store.py  # Session management
└── config.py             # Configuration management
```

### 2. Polling Mechanism Implementation

```python
# poller.py
import schedule
import time
import logging
from services.intercom_api import IntercomAPI
from services.gpt_trainer import GPTTrainerAPI
from utils.session_store import SessionStore

logger = logging.getLogger(__name__)

class ConversationPoller:
    def __init__(self, intercom_api, gpt_trainer_api, session_store, polling_interval=60):
        self.intercom_api = intercom_api
        self.gpt_trainer_api = gpt_trainer_api
        self.session_store = session_store
        self.polling_interval = polling_interval
        self.is_running = False
        self.last_processed_time = int(time.time())
    
    def start(self):
        """Start the polling service"""
        logger.info(f"Starting conversation poller with {self.polling_interval}s interval")
        self.is_running = True
        
        # Schedule the polling task
        schedule.every(self.polling_interval).seconds.do(self.poll_and_process)
        
        # Run continuously
        while self.is_running:
            schedule.run_pending()
            time.sleep(1)
    
    def stop(self):
        """Stop the polling service"""
        logger.info("Stopping conversation poller")
        self.is_running = False
    
    def poll_and_process(self):
        """Poll for new conversations and process them"""
        try:
            logger.info("Polling for new conversations")
            
            # Get open conversations
            conversations = self.intercom_api.list_conversations(
                per_page=25,
                state="open",
                sort="updated_at",
                order="desc"
            )
            
            if not conversations:
                logger.info("No conversations found")
                return
                
            logger.info(f"Found {len(conversations)} conversations to check")
            
            # Process each conversation
            for conversation in conversations:
                self._process_conversation(conversation)
                
            logger.info("Polling cycle completed")
            
        except Exception as e:
            logger.error(f"Error in polling cycle: {str(e)}")
    
    def _process_conversation(self, conversation):
        """Process a single conversation"""
        conversation_id = conversation.get('id')
        updated_at = conversation.get('updated_at', 0)
        
        # Skip if we've already processed this conversation in this cycle
        if updated_at <= self.last_processed_time:
            logger.debug(f"Skipping already processed conversation {conversation_id}")
            return
            
        logger.info(f"Processing conversation {conversation_id}")
        
        # Get full conversation details
        conversation_details = self.intercom_api.get_conversation(conversation_id)
        
        # Extract the latest user message
        latest_message = self._extract_latest_user_message(conversation_details)
        if not latest_message:
            logger.info(f"No new user message found in conversation {conversation_id}")
            return
            
        message_text, message_id, message_time = latest_message
        
        # Skip if message is older than our last check
        if message_time <= self.last_processed_time:
            logger.debug(f"Skipping already processed message {message_id}")
            return
            
        # Get or create GPT Trainer session
        session_id = self.session_store.get_session(conversation_id)
        if not session_id:
            session_id = self.gpt_trainer_api.create_session()
            self.session_store.save_session(conversation_id, session_id)
            
        # Process message with GPT Trainer
        logger.info(f"Sending message '{message_text[:50]}...' to GPT Trainer")
        response = self.gpt_trainer_api.send_message(message_text, session_id)
        
        if response:
            # Send response back to Intercom
            self.intercom_api.reply_to_conversation(
                conversation_id, 
                response,
                admin_id=self.intercom_api.admin_id
            )
            
            # Mark conversation as read
            self.intercom_api.mark_conversation_read(conversation_id)
            
            logger.info(f"Sent response to conversation {conversation_id}")
        else:
            logger.error(f"Failed to get response from GPT Trainer for {conversation_id}")
    
    def _extract_latest_user_message(self, conversation):
        """Extract the latest user message from conversation data"""
        try:
            # Check conversation parts for the latest user message
            parts = conversation.get('conversation_parts', {}).get('conversation_parts', [])
            
            # Start with the most recent message
            for part in reversed(parts):
                if part.get('author', {}).get('type') == 'user':
                    message_text = part.get('body', '')
                    # Clean HTML tags
                    message_text = message_text.replace('<p>', '').replace('</p>', ' ').strip()
                    return message_text, part.get('id'), part.get('created_at', 0)
                    
            # If no user message found in parts, check the initial message
            initial_msg = conversation.get('conversation_message', {})
            if initial_msg.get('author', {}).get('type') == 'user':
                message_text = initial_msg.get('body', '')
                # Clean HTML tags
                message_text = message_text.replace('<p>', '').replace('</p>', ' ').strip()
                return message_text, initial_msg.get('id'), initial_msg.get('created_at', 0)
                
            return None
            
        except Exception as e:
            logger.error(f"Error extracting latest message: {str(e)}")
            return None
```

### 3. Intercom API Client

```python
# intercom_api.py
import requests
import time
import logging
from retrying import retry

logger = logging.getLogger(__name__)

class IntercomAPI:
    def __init__(self, access_token, admin_id):
        self.access_token = access_token
        self.admin_id = admin_id
        self.base_url = "https://api.intercom.io"
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def list_conversations(self, per_page=25, state="open", sort="updated_at", order="desc"):
        """List conversations from Intercom"""
        try:
            params = {
                "per_page": per_page,
                "state": state,
                "sort": sort,
                "order": order
            }
            
            url = f"{self.base_url}/conversations"
            response = requests.get(url, headers=self.headers, params=params)
            self._handle_rate_limits(response)
            response.raise_for_status()
            
            data = response.json()
            return data.get('conversations', [])
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error listing conversations: {e}")
            raise
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            raise
    
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def get_conversation(self, conversation_id):
        """Get a specific conversation by ID"""
        try:
            url = f"{self.base_url}/conversations/{conversation_id}"
            response = requests.get(url, headers=self.headers)
            self._handle_rate_limits(response)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error getting conversation {conversation_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting conversation {conversation_id}: {e}")
            raise
    
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def reply_to_conversation(self, conversation_id, message, admin_id=None):
        """Send a reply to a conversation"""
        try:
            url = f"{self.base_url}/conversations/{conversation_id}/reply"
            
            admin_id = admin_id or self.admin_id
            payload = {
                "type": "admin",
                "admin_id": admin_id,
                "message_type": "comment",
                "body": f"<p>{message}</p>"
            }
            
            response = requests.post(url, headers=self.headers, json=payload)
            self._handle_rate_limits(response)
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error replying to conversation {conversation_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error replying to conversation {conversation_id}: {e}")
            raise
    
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def mark_conversation_read(self, conversation_id):
        """Mark a conversation as read"""
        try:
            url = f"{self.base_url}/conversations/{conversation_id}/read"
            response = requests.put(url, headers=self.headers)
            self._handle_rate_limits(response)
            response.raise_for_status()
            
            return True
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error marking conversation {conversation_id} as read: {e}")
            return False
        except Exception as e:
            logger.error(f"Error marking conversation {conversation_id} as read: {e}")
            return False
    
    def _handle_rate_limits(self, response):
        """Handle Intercom API rate limits"""
        try:
            remaining = int(response.headers.get('X-RateLimit-Remaining', 1000))
            if remaining < 10:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                current_time = int(time.time())
                sleep_time = max(0, reset_time - current_time) + 1  # Add 1 second buffer
                
                if sleep_time > 0:
                    logger.warning(f"Rate limit nearly reached ({remaining} remaining). Sleeping for {sleep_time}s")
                    time.sleep(sleep_time)
        except Exception as e:
            logger.warning(f"Error handling rate limits: {e}")
```

### 4. Session Management

```python
# session_store.py
import json
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SessionStore:
    """Manages GPT Trainer session IDs for Intercom conversations"""
    
    def __init__(self, storage_path=None, expiry_hours=24):
        self.storage_path = storage_path or "sessions.json"
        self.expiry_hours = expiry_hours
        self.sessions = {}
        self._load_sessions()
    
    def get_session(self, conversation_id):
        """Get session ID for a conversation"""
        self._cleanup_expired()
        
        session_data = self.sessions.get(conversation_id)
        if not session_data:
            return None
            
        # Check if session is expired
        expiry = datetime.fromisoformat(session_data['expiry'])
        if expiry < datetime.now():
            logger.info(f"Session for conversation {conversation_id} expired")
            del self.sessions[conversation_id]
            self._save_sessions()
            return None
            
        return session_data['session_id']
    
    def save_session(self, conversation_id, session_id):
        """Save a session ID for a conversation"""
        expiry = datetime.now() + timedelta(hours=self.expiry_hours)
        
        self.sessions[conversation_id] = {
            'session_id': session_id,
            'created': datetime.now().isoformat(),
            'expiry': expiry.isoformat()
        }
        
        logger.info(f"Saved session {session_id} for conversation {conversation_id}")
        self._save_sessions()
        return True
    
    def _cleanup_expired(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired = []
        
        for conv_id, session_data in self.sessions.items():
            expiry = datetime.fromisoformat(session_data['expiry'])
            if expiry < now:
                expired.append(conv_id)
                
        if expired:
            for conv_id in expired:
                del self.sessions[conv_id]
            logger.info(f"Cleaned up {len(expired)} expired sessions")
            self._save_sessions()
    
    def _load_sessions(self):
        """Load sessions from storage"""
        if not os.path.exists(self.storage_path):
            logger.info("No session file found, starting with empty sessions")
            return
            
        try:
            with open(self.storage_path, 'r') as f:
                self.sessions = json.load(f)
            logger.info(f"Loaded {len(self.sessions)} sessions from storage")
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            self.sessions = {}
    
    def _save_sessions(self):
        """Save sessions to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.sessions, f)
            logger.debug(f"Saved {len(self.sessions)} sessions to storage")
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")
```

### 5. Main Application

```python
# main.py
import os
import logging
import time
from dotenv import load_dotenv
from services.intercom_api import IntercomAPI
from services.gpt_trainer import GPTTrainerAPI
from services.poller import ConversationPoller
from utils.session_store import SessionStore

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv()
    
    # Required environment variables
    intercom_token = os.getenv("INTERCOM_ACCESS_TOKEN")
    intercom_admin_id = os.getenv("INTERCOM_ADMIN_ID")
    gpt_trainer_key = os.getenv("GPT_TRAINER_API_KEY")
    chatbot_uuid = os.getenv("CHATBOT_UUID")
    
    # Optional configuration
    polling_interval = int(os.getenv("POLLING_INTERVAL", "60"))
    
    # Validate environment
    if not all([intercom_token, intercom_admin_id, gpt_trainer_key, chatbot_uuid]):
        logger.error("Missing required environment variables. Please check .env file.")
        return 1
    
    try:
        # Initialize components
        logger.info("Initializing services...")
        intercom_api = IntercomAPI(intercom_token, intercom_admin_id)
        gpt_trainer_api = GPTTrainerAPI(gpt_trainer_key, chatbot_uuid)
        session_store = SessionStore()
        
        # Initialize and start poller
        logger.info(f"Starting conversation poller with {polling_interval}s interval")
        poller = ConversationPoller(
            intercom_api,
            gpt_trainer_api,
            session_store,
            polling_interval=polling_interval
        )
        
        # Start the polling process
        poller.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        return 0
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main())
```

## 7. Deployment Process

### Local Development Setup

1. Clone repository and install dependencies:
   ```bash
   git clone https://github.com/your-org/intercom-gpt-api-integration.git
   cd intercom-gpt-api-integration
   pip install -r requirements.txt
   ```

2. Set up environment variables:
   ```bash
   cp .env.template .env
   # Edit .env with your API credentials
   ```

3. Run the application:
   ```bash
   python main.py
   ```

### Containerized Deployment

1. Build Docker image:
   ```Dockerfile
   FROM python:3.9-slim
   
   WORKDIR /app
   
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   COPY . .
   
   CMD ["python", "main.py"]
   ```

2. Run with Docker:
   ```bash
   docker build -t intercom-gpt-integration .
   docker run -d --env-file .env --name intercom-gpt intercom-gpt-integration
   ```

### Production Deployment

1. Deploy to cloud providers with container support:
   - Google Cloud Run
   - AWS ECS/Fargate
   - Azure Container Instances
   - Digital Ocean App Platform

2. Production deployment example (GCP Cloud Run):
   ```bash
   # Build the container
   gcloud builds submit --tag gcr.io/[PROJECT_ID]/intercom-gpt-integration
   
   # Deploy to Cloud Run
   gcloud run deploy intercom-gpt-integration \
     --image gcr.io/[PROJECT_ID]/intercom-gpt-integration \
     --platform managed \
     --memory 512Mi \
     --set-env-vars=POLLING_INTERVAL=60
   ```

## 8. Testing and Validation

### API Connection Testing

```python
# test_intercom_connection.py
import os
from dotenv import load_dotenv
from services.intercom_api import IntercomAPI

load_dotenv()

access_token = os.getenv("INTERCOM_ACCESS_TOKEN")
admin_id = os.getenv("INTERCOM_ADMIN_ID")

def test_intercom_connection():
    """Test connection to Intercom API"""
    try:
        intercom = IntercomAPI(access_token, admin_id)
        
        # Try listing conversations
        conversations = intercom.list_conversations(per_page=1)
        if conversations:
            print(f"✅ Successfully connected to Intercom API")
            print(f"Found conversation: {conversations[0].get('id')}")
            return True
        else:
            print("⚠️ Connected to Intercom API but found no conversations")
            return True
    except Exception as e:
        print(f"❌ Failed to connect to Intercom API: {str(e)}")
        return False

if __name__ == "__main__":
    test_intercom_connection()
```

### End-to-End Test

```python
# test_e2e.py
import os
from dotenv import load_dotenv
from services.intercom_api import IntercomAPI
from services.gpt_trainer import GPTTrainerAPI
from utils.session_store import SessionStore

load_dotenv()

def test_e2e_flow():
    """Test the end-to-end flow with one conversation"""
    # Initialize components
    intercom = IntercomAPI(
        os.getenv("INTERCOM_ACCESS_TOKEN"),
        os.getenv("INTERCOM_ADMIN_ID")
    )
    
    gpt_trainer = GPTTrainerAPI(
        os.getenv("GPT_TRAINER_API_KEY"),
        os.getenv("CHATBOT_UUID")
    )
    
    session_store = SessionStore()
    
    # Get one conversation to test with
    conversations = intercom.list_conversations(per_page=1)
    if not conversations:
        print("❌ No conversations found for testing")
        return False
    
    conversation_id = conversations[0].get('id')
    print(f"🔍 Testing with conversation: {conversation_id}")
    
    # Get conversation details
    conversation = intercom.get_conversation(conversation_id)
    
    # Extract message for testing
    message = None
    
    # First check initial message
    initial_msg = conversation.get('conversation_message', {})
    if initial_msg.get('author', {}).get('type') == 'user':
        message = initial_msg.get('body', '')
        message = message.replace('<p>', '').replace('</p>', ' ').strip()
    
    # If no initial user message, check conversation parts
    if not message:
        parts = conversation.get('conversation_parts', {}).get('conversation_parts', [])
        for part in reversed(parts):
            if part.get('author', {}).get('type') == 'user':
                message = part.get('body', '')
                message = message.replace('<p>', '').replace('</p>', ' ').strip()
                break
    
    if not message:
        print("❌ No user message found for testing")
        return False
    
    print(f"📝 Using message: '{message[:50]}...'")
    
    # Create GPT Trainer session
    session_id = gpt_trainer.create_session()
    if not session_id:
        print("❌ Failed to create GPT Trainer session")
        return False
        
    print(f"✅ Created GPT Trainer session: {session_id}")
    
    # Send message to GPT Trainer
    response = gpt_trainer.send_message(message, session_id)
    if not response:
        print("❌ Failed to get response from GPT Trainer")
        return False
        
    print(f"✅ Got response from GPT Trainer: '{response[:50]}...'")
    
    # DO NOT send test response to real customer - just print it
    print("\n=== Test Successful ===")
    print(f"Would send to conversation {conversation_id}:")
    print(f"Response: {response}")
    
    return True

if __name__ == "__main__":
    test_e2e_flow()
```

## 9. Performance Optimization Strategies

### 1. Optimized Polling Strategy

To reduce API calls while maintaining responsiveness:

```python
def optimized_polling_strategy(self):
    """Dynamic polling interval based on conversation volume and activity"""
    BASE_INTERVAL = 60  # seconds
    MAX_INTERVAL = 300  # 5 minutes
    MIN_INTERVAL = 15   # 15 seconds
    
    # Track activity level
    self.activity_count = 0
    
    while self.is_running:
        start_time = time.time()
        
        # Poll for conversations
        conversation_count = self.poll_and_process()
        
        # Adjust polling interval based on activity
        if conversation_count > 0:
            # Increase activity count when conversations found
            self.activity_count = min(10, self.activity_count + 1)
            # More frequent polling when activity detected
            new_interval = max(MIN_INTERVAL, BASE_INTERVAL - (self.activity_count * 5))
        else:
            # Decrease activity count when no conversations
            self.activity_count = max(0, self.activity_count - 1)
            # Less frequent polling when inactive
            new_interval = min(MAX_INTERVAL, BASE_INTERVAL + ((10 - self.activity_count) * 5))
        
        # Update polling interval
        if new_interval != self.polling_interval:
            logger.info(f"Adjusting polling interval: {self.polling_interval}s → {new_interval}s")
            self.polling_interval = new_interval
        
        # Calculate sleep time
        elapsed = time.time() - start_time
        sleep_time = max(1, self.polling_interval - elapsed)
        
        # Sleep until next poll
        time.sleep(sleep_time)
```

### 2. Batched Processing

Process conversations in batches for better efficiency:

```python
def batch_process_conversations(conversations, batch_size=5):
    """Process conversations in batches to optimize API calls"""
    total = len(conversations)
    logger.info(f"Processing {total} conversations in batches of {batch_size}")
    
    for i in range(0, total, batch_size):
        batch = conversations[i:i+batch_size]
        logger.info(f"Processing batch {i//batch_size + 1}/{(total+batch_size-1)//batch_size}")
        
        # Process batch
        for conversation in batch:
            process_conversation(conversation)
            
        # Slight delay between batches to avoid rate limiting
        if i + batch_size < total:
            time.sleep(2)
```

### 3. Persistent Queue

Use a persistent queue for reliability:

```python
# Using a persistent Redis queue for reliability
import redis
from rq import Queue

# Initialize Redis connection
redis_conn = redis.Redis(host='localhost', port=6379)
queue = Queue('intercom_gpt', connection=redis_conn)

def enqueue_conversation_processing(conversation_id):
    """Add conversation to processing queue"""
    # Add job to queue with retry configuration
    job = queue.enqueue(
        process_conversation,
        conversation_id,
        retry=Retry(max=3, interval=[10, 30, 60])
    )
    logger.info(f"Enqueued conversation {conversation_id} as job {job.id}")
    return job.id
```

## 10. Error Handling and Resilience

### 1. Circuit Breaker Pattern

Implement circuit breaker to prevent cascading failures:

```python
class CircuitBreaker:
    """Circuit breaker to prevent cascading failures"""
    
    def __init__(self, failure_threshold=5, reset_timeout=60):
        self.failure_count = 0
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.state = "CLOSED"  # CLOSED, OPEN, HALF-OPEN
        self.last_failure_time = 0
    
    def record_success(self):
        """Record successful call"""
        if self.state == "HALF-OPEN":
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker reset to CLOSED state")
    
    def record_failure(self):
        """Record failed call"""
        self.last_failure_time = time.time()
        self.failure_count += 1
        
        if self.state == "CLOSED" and self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")
    
    def allow_request(self):
        """Check if request should be allowed"""
        if self.state == "CLOSED":
            return True
            
        if self.state == "OPEN":
            # Check if timeout has elapsed
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.reset_timeout:
                self.state = "HALF-OPEN"
                logger.info("Circuit breaker switched to HALF-OPEN state")
                return True
            return False
            
        # HALF-OPEN state - allow one test request
        return True

# Usage with API calls
intercom_circuit = CircuitBreaker()
gpt_trainer_circuit = CircuitBreaker()

def get_conversation_with_breaker(conversation_id):
    """Get conversation with circuit breaker protection"""
    if not intercom_circuit.allow_request():
        logger.warning(f"Circuit breaker preventing Intercom API call for {conversation_id}")
        return None
        
    try:
        response = intercom_api.get_conversation(conversation_id)
        intercom_circuit.record_success()
        return response
    except Exception as e:
        intercom_circuit.record_failure()
        logger.error(f"Error getting conversation: {e}")
        return None
```

### 2. Dead Letter Queue

Handle failed processing with a dead letter queue:

```python
class DeadLetterQueue:
    """Store and handle failed messages"""
    
    def __init__(self, storage_path="dead_letter.json"):
        self.storage_path = storage_path
        self.queue = self._load_queue()
    
    def add(self, conversation_id, message, error):
        """Add failed message to queue"""
        item = {
            "conversation_id": conversation_id,
            "message": message,
            "error": str(error),
            "timestamp": time.time(),
            "retries": 0
        }
        
        self.queue.append(item)
        self._save_queue()
        logger.warning(f"Added conversation {conversation_id} to dead letter queue: {str(error)}")
    
    def retry_all(self, max_age_hours=24):
        """Retry all messages in queue"""
        if not self.queue:
            return 0
            
        current_time = time.time()
        retry_count = 0
        remaining = []
        
        for item in self.queue:
            # Skip items older than max age
            age_hours = (current_time - item["timestamp"]) / 3600
            if age_hours > max_age_hours:
                logger.info(f"Skipping item older than {max_age_hours} hours: {item['conversation_id']}")
                continue
                
            # Attempt to retry
            item["retries"] += 1
            success = self._process_item(item)
            
            if success:
                retry_count += 1
            else:
                # Keep in queue for future retry
                remaining.append(item)
        
        self.queue = remaining
        self._save_queue()
        
        return retry_count
    
    def _process_item(self, item):
        """Process a single item from the queue"""
        try:
            conversation_id = item["conversation_id"]
            logger.info(f"Retrying dead letter queue item: {conversation_id} (attempt {item['retries']})")
            
            # Re-process conversation using the same flow as normal
            # ... processing logic here ...
            
            return True
        except Exception as e:
            logger.error(f"Failed to process dead letter queue item: {e}")
            return False
    
    def _load_queue(self):
        """Load queue from storage"""
        if not os.path.exists(self.storage_path):
            return []
            
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading dead letter queue: {e}")
            return []
    
    def _save_queue(self):
        """Save queue to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(self.queue, f)
        except Exception as e:
            logger.error(f"Error saving dead letter queue: {e}")
```

## 11. Monitoring and Analytics

### 1. Monitoring Implementation

```python
class MetricsCollector:
    """Collect and report operational metrics"""
    
    def __init__(self):
        self.metrics = {
            "conversations_processed": 0,
            "messages_processed": 0,
            "gpt_trainer_calls": 0,
            "intercom_api_calls": 0,
            "errors": 0,
            "response_times": [],
            "polling_cycles": 0
        }
        self.start_time = time.time()
    
    def increment(self, metric_name, value=1):
        """Increment a counter metric"""
        if metric_name in self.metrics:
            self.metrics[metric_name] += value
    
    def record_response_time(self, response_time_ms):
        """Record response time"""
        self.metrics["response_times"].append(response_time_ms)
    
    def get_report(self):
        """Generate a metrics report"""
        runtime_seconds = int(time.time() - self.start_time)
        hours = runtime_seconds // 3600
        minutes = (runtime_seconds % 3600) // 60
        seconds = runtime_seconds % 60
        
        # Calculate average response time
        avg_response_time = 0
        if self.metrics["response_times"]:
            avg_response_time = sum(self.metrics["response_times"]) / len(self.metrics["response_times"])
        
        return {
            "uptime": f"{hours:02}:{minutes:02}:{seconds:02}",
            "conversations_processed": self.metrics["conversations_processed"],
            "messages_processed": self.metrics["messages_processed"],
            "gpt_trainer_calls": self.metrics["gpt_trainer_calls"],
            "intercom_api_calls": self.metrics["intercom_api_calls"],
            "errors": self.metrics["errors"],
            "avg_response_time_ms": round(avg_response_time, 2),
            "polling_cycles": self.metrics["polling_cycles"]
        }
    
    def log_report(self):
        """Log the current metrics report"""
        report = self.get_report()
        logger.info(f"Metrics Report: {json.dumps(report)}")
        return report
```

### 2. Admin API for Monitoring

```python
# In main.py or app.py
from flask import Flask, jsonify

app = Flask(__name__)
metrics = MetricsCollector()

@app.route('/metrics', methods=['GET'])
def get_metrics():
    """Return current metrics as JSON"""
    return jsonify(metrics.get_report())

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "uptime": metrics.get_report()["uptime"],
        "errors": metrics.get_report()["errors"]
    })

@app.route('/stats/conversations', methods=['GET'])
def conversation_stats():
    """Get conversation processing statistics"""
    return jsonify({
        "processed": metrics.metrics["conversations_processed"],
        "polling_cycles": metrics.metrics["polling_cycles"],
        "avg_per_cycle": round(metrics.metrics["conversations_processed"] / max(1, metrics.metrics["polling_cycles"]), 2)
    })
```

## 12. Conclusion

This developer brief provides a comprehensive guide to integrating Intercom and GPT Trainer using direct API integration. By implementing a polling mechanism instead of webhooks, this approach offers greater control over message processing and allows for enhanced resilience mechanisms.

Key advantages of this approach:
1. No need to expose a public endpoint for webhooks
2. Full control over polling frequency and error handling
3. Ability to implement sophisticated retry mechanisms
4. Better handling of rate limits through controlled API access

The implementation details, code samples, and architecture description provide everything needed to quickly build a robust integration between Intercom's customer messaging platform and GPT Trainer's AI capabilities.
