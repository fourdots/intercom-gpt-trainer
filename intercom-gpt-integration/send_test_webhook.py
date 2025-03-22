import os
import requests
import json
import hmac
import hashlib
import logging
import argparse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Get configuration
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")

def generate_signature(payload, secret):
    """Generate signature for webhook payload"""
    logging.debug(f"Generating signature with secret starting with: {secret[:5]}...")
    logging.debug(f"Payload to sign: {payload}")
    
    mac = hmac.new(
        secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha1
    )
    signature = mac.hexdigest()
    logging.debug(f"Generated signature: {signature}")
    return f"sha1={signature}"

def send_test_webhook(topic, platform="reportz", conversation_id="test_conversation_id"):
    """Send a test webhook to the server"""
    # Get the client secret for the platform
    if platform.lower() == "base":
        client_secret = os.getenv("BASE_INTERCOM_CLIENT_SECRET")
        logging.info(f"Using Base client secret (truncated): {client_secret[:5]}...")
    else:
        client_secret = os.getenv("INTERCOM_CLIENT_SECRET")
        logging.info(f"Using Reportz client secret (truncated): {client_secret[:5]}...")
    
    # Webhook URL
    WEBHOOK_URL = f"{WEBHOOK_BASE_URL}/webhook/intercom"
    
    # Create a test webhook payload
    payload = {
        "type": "notification_event",
        "topic": topic,
        "app_id": "app_id_for_platform_" + platform.lower(),
        "data": {
            "item": {
                "id": conversation_id,
                "type": "conversation",
                "created_at": 1710734567,
                "updated_at": 1710734567,
                "workspace_id": "workspace_" + platform.lower(),
                "conversation_message": {
                    "type": "conversation_message",
                    "id": "message_id_1",
                    "body": f"<p>Test message from {platform} platform</p>",
                    "author": {
                        "type": "user",
                        "id": "user_id_1"
                    }
                }
            }
        }
    }
    
    # Convert payload to JSON
    payload_json = json.dumps(payload)
    
    # Generate signature
    signature = generate_signature(payload_json, client_secret)
    
    # Set headers
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature": signature
    }
    
    # Send webhook
    logging.info(f"Sending test webhook for {platform} platform with topic: {topic}")
    logging.info(f"URL: {WEBHOOK_URL}")
    logging.info(f"Signature: {signature}")
    
    response = requests.post(WEBHOOK_URL, headers=headers, data=payload_json)
    
    logging.info(f"Response status: {response.status_code}")
    logging.info(f"Response text: {response.text}")
    
    return response

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send test webhooks to Intercom integration")
    parser.add_argument("--platform", choices=["reportz", "base"], default="reportz",
                        help="Which platform to simulate webhooks for (reportz or base)")
    args = parser.parse_args()
    
    platform = args.platform
    logging.info(f"Sending test webhooks to simulate Intercom events for {platform.upper()} platform")
    
    # Test ping event
    logging.info("\n=== Testing ping event ===")
    send_test_webhook("ping", platform)
    
    # Test conversation.user.created event
    logging.info("\n=== Testing conversation.user.created event ===")
    send_test_webhook("conversation.user.created", platform)
    
    # Test conversation.user.replied event
    logging.info("\n=== Testing conversation.user.replied event ===")
    send_test_webhook("conversation.user.replied", platform)
    
    # Test conversation.admin.assigned event
    logging.info("\n=== Testing conversation.admin.assigned event ===") 
    send_test_webhook("conversation.admin.assigned", platform) 
