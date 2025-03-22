import os
import requests
import json
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

# Get Intercom API token
INTERCOM_ACCESS_TOKEN = os.getenv("INTERCOM_ACCESS_TOKEN")
INTERCOM_CLIENT_ID = os.getenv("INTERCOM_CLIENT_ID")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")

# API endpoint for webhooks
WEBHOOKS_API_URL = "https://api.intercom.io/subscriptions"

def get_current_webhooks():
    """Get the current webhook configurations from Intercom"""
    headers = {
        "Authorization": f"Bearer {INTERCOM_ACCESS_TOKEN}",
        "Accept": "application/json"
    }
    
    response = requests.get(WEBHOOKS_API_URL, headers=headers)
    
    if response.status_code != 200:
        logging.error(f"Failed to get webhooks: {response.status_code} - {response.text}")
        return None
    
    return response.json().get('data', [])

if __name__ == "__main__":
    logging.info("Checking Intercom webhook configuration...")
    
    # Get current webhooks
    webhooks = get_current_webhooks()
    
    if webhooks is None:
        logging.error("Could not retrieve webhook information")
        exit(1)
    
    logging.info(f"Found {len(webhooks)} webhook subscriptions")
    
    for webhook in webhooks:
        logging.info(f"\nWebhook ID: {webhook.get('id')}")
        logging.info(f"URL: {webhook.get('url')}")
        logging.info(f"Topics: {webhook.get('topics')}")
        logging.info(f"Active: {webhook.get('active')}")
        
    # Check if our webhook URL is in the list
    expected_url = f"{WEBHOOK_BASE_URL}/webhook/intercom"
    found = False
    
    for webhook in webhooks:
        if webhook.get('url') == expected_url:
            found = True
            logging.info(f"\nOur webhook is configured correctly at {expected_url}")
            logging.info(f"Topics: {webhook.get('topics')}")
            logging.info(f"Active: {webhook.get('active')}")
            break
    
    if not found:
        logging.warning(f"\nOur webhook URL {expected_url} is not in the list of configured webhooks!")
        logging.warning("Please check the Intercom Developer Hub to ensure it's configured correctly.") 
