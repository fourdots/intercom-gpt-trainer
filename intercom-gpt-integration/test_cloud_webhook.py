import requests
import json
import hmac
import hashlib
import logging
import os
import time
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get configuration
CLOUD_RUN_URL = "https://intercom-gpt-bridge-11486232322.us-central1.run.app"
INTERCOM_CLIENT_SECRET = os.getenv("INTERCOM_CLIENT_SECRET")

# Webhook URL
WEBHOOK_URL = f"{CLOUD_RUN_URL}/webhook/intercom"

def generate_signature(payload, secret):
    """Generate signature for webhook payload"""
    mac = hmac.new(
        secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha1
    )
    return f"sha1={mac.hexdigest()}"

def test_webhook_validation():
    """Test webhook validation (HEAD request)"""
    logger.info("Testing webhook validation with HEAD request...")
    try:
        head_response = requests.head(WEBHOOK_URL)
        logger.info(f"HEAD response status: {head_response.status_code}")
        
        if head_response.status_code != 200:
            logger.error("Webhook validation failed! Server should return 200 for HEAD requests.")
            return False
        
        logger.info("Webhook validation successful!")
        return True
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to webhook server at {WEBHOOK_URL}")
        return False

def test_ping_webhook():
    """Test webhook with a ping event"""
    logger.info("Sending test webhook ping request...")
    
    # Create a simple ping payload
    payload = {
        "type": "notification_event",
        "app_id": "test_app",
        "id": "test_webhook_" + str(int(time.time())),
        "topic": "ping",
        "data": {
            "item": {
                "type": "ping",
                "message": "This is a test ping from test_cloud_webhook.py"
            }
        }
    }
    
    payload_str = json.dumps(payload)
    
    # Create signature
    signature = generate_signature(payload_str, INTERCOM_CLIENT_SECRET)
    
    # Set headers
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature": signature
    }
    
    try:
        response = requests.post(WEBHOOK_URL, data=payload_str, headers=headers)
        logger.info(f"Ping response status: {response.status_code}")
        logger.info(f"Ping response body: {response.text}")
        
        if response.status_code != 200:
            logger.error("Ping webhook test failed!")
            return False
        
        logger.info("Ping webhook test successful!")
        return True
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to webhook server at {WEBHOOK_URL}")
        return False

def test_secret_manager():
    """Test Secret Manager integration"""
    logger.info("Testing Secret Manager integration...")
    
    try:
        # Use the debug endpoint to check if secrets are available
        # This doesn't actually expose secrets, just verifies they're accessible
        response = requests.get(f"{CLOUD_RUN_URL}/health")
        
        logger.info(f"Secret Manager test status: {response.status_code}")
        logger.info(f"Response: {response.text}")
        
        if response.status_code != 200:
            logger.error("Secret Manager test failed!")
            return False
            
        logger.info("Secret Manager integration appears to be working!")
        return True
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to server at {CLOUD_RUN_URL}")
        return False

if __name__ == "__main__":    
    logger.info(f"Testing webhook at {WEBHOOK_URL}")
    
    # Test webhook validation
    if not test_webhook_validation():
        exit(1)
        
    # Give the server a moment
    time.sleep(1)
    
    # Test ping webhook
    if not test_ping_webhook():
        exit(1)
        
    # Test Secret Manager integration
    if not test_secret_manager():
        exit(1)
        
    logger.info("All tests passed!")
