import os
import requests
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()

# Get token
INTERCOM_ACCESS_TOKEN = os.getenv("INTERCOM_ACCESS_TOKEN")

def test_token():
    """Test if the current Intercom access token is valid"""
    headers = {
        "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
        "Accept": "application/json"
    }
    
    logging.info(f"Testing token (truncated): {INTERCOM_ACCESS_TOKEN[:10]}...")
    
    # Try to list conversations
    try:
        response = requests.get(
            "https://api.intercom.io/conversations?per_page=1",
            headers=headers
        )
        response.raise_for_status()
        
        data = response.json()
        logging.info(f"Token is valid! Found {len(data.get('conversations', []))} conversations.")
        return True
    except Exception as e:
        logging.error(f"Token is invalid: {str(e)}")
        return False
    
# Try to list webhooks
def test_webhooks():
    """Test if we can list webhooks with the current token"""
    headers = {
        "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(
            "https://api.intercom.io/webhooks",
            headers=headers
        )
        response.raise_for_status()
        
        data = response.json()
        webhooks = data.get("data", [])
        logging.info(f"Successfully listed {len(webhooks)} webhooks.")
        
        for webhook in webhooks:
            logging.info(f"Webhook: {webhook.get('id')} -> {webhook.get('url')}")
            logging.info(f"Topics: {webhook.get('topics')}")
            
        return True
    except Exception as e:
        logging.error(f"Cannot list webhooks: {str(e)}")
        return False

if __name__ == "__main__":
    token_valid = test_token()
    
    if token_valid:
        test_webhooks() 
