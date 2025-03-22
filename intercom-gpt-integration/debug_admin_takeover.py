#!/usr/bin/env python3
"""
Admin Takeover Debugging Script

This script helps debug why the admin takeover feature isn't working properly.
It verifies webhook subscriptions, tests admin detection, and provides tools to fix issues.
"""

import os
import sys
import json
import hmac
import hashlib
import requests
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Intercom API credentials
INTERCOM_ACCESS_TOKEN = os.getenv("INTERCOM_ACCESS_TOKEN")
INTERCOM_CLIENT_ID = os.getenv("INTERCOM_CLIENT_ID")
INTERCOM_CLIENT_SECRET = os.getenv("INTERCOM_CLIENT_SECRET")
INTERCOM_ADMIN_ID = os.getenv("INTERCOM_ADMIN_ID")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")

# API URLs
INTERCOM_API_BASE = "https://api.intercom.io"
WEBHOOKS_API_URL = f"{INTERCOM_API_BASE}/subscriptions"
CONVERSATIONS_API_URL = f"{INTERCOM_API_BASE}/conversations"

# Required webhook topics
REQUIRED_TOPICS = [
    "conversation.user.created",
    "conversation.user.replied",
    "conversation.admin.assigned",
    "conversation.admin.replied",
    "conversation.admin.single.created",
    "conversation.admin.closed"
]

def get_intercom_headers():
    """Get headers for Intercom API requests"""
    return {
        "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

def check_webhook_subscriptions():
    """Check current webhook subscriptions in Intercom"""
    logging.info("Checking current webhook subscriptions...")
    
    try:
        response = requests.get(WEBHOOKS_API_URL, headers=get_intercom_headers())
        response.raise_for_status()
        
        webhooks = response.json().get('data', [])
        logging.info(f"Found {len(webhooks)} webhook subscriptions")
        
        our_webhook_url = f"{WEBHOOK_BASE_URL}/webhook/intercom"
        our_webhook = None
        
        for webhook in webhooks:
            logging.info(f"\nWebhook ID: {webhook.get('id')}")
            logging.info(f"URL: {webhook.get('url')}")
            logging.info(f"Topics: {webhook.get('topics')}")
            logging.info(f"Active: {webhook.get('active')}")
            
            if webhook.get('url') == our_webhook_url:
                our_webhook = webhook
        
        # Check if our webhook exists and has all required topics
        if our_webhook:
            logging.info(f"\nFound our webhook: {our_webhook.get('id')}")
            missing_topics = set(REQUIRED_TOPICS) - set(our_webhook.get('topics', []))
            
            if missing_topics:
                logging.warning(f"Missing required topics: {missing_topics}")
                return our_webhook, missing_topics
            else:
                logging.info("All required topics are subscribed!")
                return our_webhook, set()
        else:
            logging.warning(f"Our webhook URL {our_webhook_url} not found!")
            return None, set(REQUIRED_TOPICS)
            
    except Exception as e:
        logging.error(f"Error checking webhooks: {e}")
        return None, set()

def update_webhook_subscription(webhook_id=None, topics=None):
    """Create or update webhook subscription with required topics"""
    our_webhook_url = f"{WEBHOOK_BASE_URL}/webhook/intercom"
    
    # If topics not provided, use all required topics
    if topics is None:
        topics = REQUIRED_TOPICS
    
    webhook_data = {
        "url": our_webhook_url,
        "topics": topics
    }
    
    try:
        if webhook_id:
            # Update existing webhook
            logging.info(f"Updating webhook {webhook_id} with topics: {topics}")
            url = f"{WEBHOOKS_API_URL}/{webhook_id}"
            response = requests.put(url, headers=get_intercom_headers(), json=webhook_data)
        else:
            # Create new webhook
            logging.info(f"Creating new webhook with topics: {topics}")
            response = requests.post(WEBHOOKS_API_URL, headers=get_intercom_headers(), json=webhook_data)
        
        response.raise_for_status()
        webhook = response.json()
        
        logging.info(f"Webhook {'updated' if webhook_id else 'created'} successfully!")
        logging.info(f"Webhook ID: {webhook.get('id')}")
        logging.info(f"URL: {webhook.get('url')}")
        logging.info(f"Topics: {webhook.get('topics')}")
        
        return webhook
        
    except Exception as e:
        logging.error(f"Error {'updating' if webhook_id else 'creating'} webhook: {e}")
        return None

def list_admins():
    """List all admins in Intercom workspace"""
    logging.info("Listing Intercom admins...")
    
    try:
        response = requests.get(f"{INTERCOM_API_BASE}/admins", headers=get_intercom_headers())
        response.raise_for_status()
        
        admins = response.json().get('admins', [])
        logging.info(f"Found {len(admins)} admins:")
        
        for admin in admins:
            logging.info(f"Admin ID: {admin.get('id')}, Name: {admin.get('name')}, Email: {admin.get('email')}")
            
            # Highlight the automated admin
            if str(admin.get('id')) == INTERCOM_ADMIN_ID:
                logging.info(f"  *** THIS IS THE AUTOMATED ADMIN (INTERCOM_ADMIN_ID={INTERCOM_ADMIN_ID}) ***")
        
        return admins
        
    except Exception as e:
        logging.error(f"Error listing admins: {e}")
        return []

def test_admin_takeover_logic():
    """Test the admin takeover logic directly"""
    logging.info("Testing admin takeover logic...")
    
    # Create a test webhook payload with admin reply
    admin_id = "253345"  # Using a different admin ID than the automated one
    conversation_id = f"test_conversation_{int(time.time())}"
    
    test_admin_webhook = {
        "type": "notification_event",
        "topic": "conversation.admin.replied",
        "data": {
            "type": "notification_event_data",
            "item": {
                "type": "conversation",
                "id": conversation_id,
                "admin_assignee_id": INTERCOM_ADMIN_ID,  # Currently assigned to the bot
                "teammates": {
                    "type": "admin.list",
                    "admins": [
                        {"type": "admin", "id": INTERCOM_ADMIN_ID},
                        {"type": "admin", "id": admin_id}
                    ]
                },
                "conversation_parts": {
                    "type": "conversation_part.list",
                    "conversation_parts": [
                        {
                            "type": "conversation_part",
                            "part_type": "comment",
                            "body": "<p>This is a human admin reply</p>",
                            "author": {
                                "type": "admin",
                                "id": admin_id
                            }
                        }
                    ]
                }
            }
        }
    }
    
    # Sign the webhook
    payload = json.dumps(test_admin_webhook)
    signature = sign_webhook(payload, INTERCOM_CLIENT_SECRET)
    
    # Send the test webhook to the server
    webhook_url = f"{WEBHOOK_BASE_URL}/webhook/intercom"
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature": signature
    }
    
    logging.info(f"Sending test admin webhook to {webhook_url}")
    logging.info(f"Admin ID in test: {admin_id}, Automated Admin ID: {INTERCOM_ADMIN_ID}")
    
    try:
        response = requests.post(webhook_url, headers=headers, data=payload)
        logging.info(f"Response status: {response.status_code}")
        logging.info(f"Response body: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        logging.error(f"Error sending test webhook: {e}")
        return False

def sign_webhook(payload, secret):
    """Generate a signature for webhook payload"""
    mac = hmac.new(
        secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha1
    )
    return f"sha1={mac.hexdigest()}"

def create_session_store_with_admin_takeover():
    """Create a session store file with an admin takeover state for testing"""
    from datetime import timedelta
    
    # Create a test conversation ID
    conversation_id = f"test_conversation_{int(time.time())}"
    admin_id = "253345"  # A non-automated admin ID
    
    # Create a session store entry with admin takeover state
    session_data = {
        conversation_id: {
            "session_id": None,
            "state": "admin_takeover",
            "expiry": (datetime.now() + timedelta(hours=24)).isoformat(),
            "admin_id": admin_id
        }
    }
    
    # Save to a test file
    test_file = "test_admin_sessions.json"
    with open(test_file, 'w') as f:
        json.dump(session_data, f, indent=2)
    
    logging.info(f"Created test session store with admin takeover state: {test_file}")
    logging.info(f"Test conversation ID: {conversation_id}")
    logging.info(f"Admin ID: {admin_id}")
    
    return test_file, conversation_id

def verify_webhook_registration():
    """Verify webhook registration and update if needed"""
    webhook, missing_topics = check_webhook_subscriptions()
    
    if missing_topics:
        if webhook:
            # Update existing webhook with all topics
            all_topics = list(set(webhook.get('topics', [])) | missing_topics)
            update_webhook_subscription(webhook.get('id'), all_topics)
        else:
            # Create new webhook with all required topics
            update_webhook_subscription(topics=REQUIRED_TOPICS)
    else:
        logging.info("Webhook registration is correct, no changes needed.")

def manual_takeover_test():
    """Test forcing admin takeover for an existing conversation"""
    # Get a list of open conversations
    try:
        response = requests.get(
            f"{CONVERSATIONS_API_URL}?state=open&sort=updated_at&order=desc&per_page=1", 
            headers=get_intercom_headers()
        )
        response.raise_for_status()
        
        conversations = response.json().get('conversations', [])
        if not conversations:
            logging.error("No open conversations found for testing.")
            return False
            
        conversation = conversations[0]
        conversation_id = conversation.get('id')
        
        logging.info(f"Testing admin takeover on conversation: {conversation_id}")
        
        # Create test data to manually update session store
        from utils.session_store import SessionStore, ADMIN_TAKEOVER
        from utils.persistence import PersistenceManager
        
        # Load existing sessions
        sessions = PersistenceManager.load_json_data("sessions.json", default={})
        
        # Add admin takeover for this conversation
        admin_id = "253345"  # A non-automated admin ID
        
        if conversation_id in sessions:
            sessions[conversation_id]['state'] = ADMIN_TAKEOVER
            sessions[conversation_id]['admin_id'] = admin_id
        else:
            sessions[conversation_id] = {
                'session_id': None,
                'state': ADMIN_TAKEOVER,
                'expiry': (datetime.now() + timedelta(hours=24)).isoformat(),
                'admin_id': admin_id
            }
        
        # Save back to sessions.json
        PersistenceManager.save_json_data("sessions.json", sessions)
        
        logging.info(f"Manually set conversation {conversation_id} to ADMIN_TAKEOVER state")
        logging.info(f"Admin ID: {admin_id}")
        
        return True
        
    except Exception as e:
        logging.error(f"Error in manual takeover test: {e}")
        return False

def debug_admin_detection():
    """Debug admin detection in conversation parts"""
    # Get a list of open conversations
    try:
        response = requests.get(
            f"{CONVERSATIONS_API_URL}?state=open&sort=updated_at&order=desc&per_page=5", 
            headers=get_intercom_headers()
        )
        response.raise_for_status()
        
        conversations = response.json().get('conversations', [])
        if not conversations:
            logging.error("No open conversations found for debugging.")
            return
            
        for conversation in conversations:
            conversation_id = conversation.get('id')
            
            # Get full conversation details
            resp = requests.get(
                f"{CONVERSATIONS_API_URL}/{conversation_id}", 
                headers=get_intercom_headers()
            )
            resp.raise_for_status()
            
            conv_details = resp.json()
            
            # Check for admin replies
            logging.info(f"\nAnalyzing conversation {conversation_id}:")
            
            # Check teammates field
            teammates = conv_details.get('teammates', {}).get('admins', [])
            logging.info(f"Teammates: {teammates}")
            
            admin_ids = [admin.get('id') for admin in teammates if admin.get('type') == 'admin']
            logging.info(f"Admin IDs in conversation: {admin_ids}")
            
            # Check conversation parts for admin authors
            parts = conv_details.get('conversation_parts', {}).get('conversation_parts', [])
            
            for part in parts:
                author = part.get('author', {})
                author_type = author.get('type')
                author_id = author.get('id')
                
                if author_type == 'admin':
                    is_bot = str(author_id) == INTERCOM_ADMIN_ID
                    logging.info(f"Found admin message - ID: {author_id}, Bot?: {is_bot}")
                    logging.info(f"Message: {part.get('body')[:100]}...")
            
    except Exception as e:
        logging.error(f"Error debugging admin detection: {e}")

def run_tests():
    """Run all tests to debug admin takeover issues"""
    print("\n=== ADMIN TAKEOVER DEBUGGING TOOL ===\n")
    print("What would you like to do?")
    print("1. Check webhook subscriptions")
    print("2. Update webhook subscriptions with all required topics")
    print("3. List all Intercom admins")
    print("4. Test admin takeover logic")
    print("5. Debug admin detection in conversations")
    print("6. Manual takeover test")
    print("7. Run all tests")
    print("q. Quit")
    
    choice = input("\nEnter your choice (1-7, q): ")
    
    if choice == '1':
        check_webhook_subscriptions()
    elif choice == '2':
        verify_webhook_registration()
    elif choice == '3':
        list_admins()
    elif choice == '4':
        test_admin_takeover_logic()
    elif choice == '5':
        debug_admin_detection()
    elif choice == '6':
        manual_takeover_test()
    elif choice == '7':
        check_webhook_subscriptions()
        list_admins()
        verify_webhook_registration()
        debug_admin_detection()
        test_admin_takeover_logic()
        manual_takeover_test()
    elif choice.lower() == 'q':
        print("Exiting...")
        sys.exit(0)
    else:
        print("Invalid choice!")
        
if __name__ == "__main__":
    run_tests() 
