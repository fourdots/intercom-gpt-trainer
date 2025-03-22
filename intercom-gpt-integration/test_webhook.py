#!/usr/bin/env python3
"""
Test script to simulate an Intercom webhook request.
This can be used to verify your webhook handler without needing to set up a public endpoint.
"""

import os
import json
import requests
import logging
import hmac
import hashlib
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv()
    
    # Get the webhook URL from environment
    webhook_base_url = os.getenv("WEBHOOK_BASE_URL")
    port = int(os.getenv("PORT", "8000"))
    
    if webhook_base_url:
        webhook_url = f"{webhook_base_url}/webhook/intercom"
        logger.info(f"Using ngrok URL: {webhook_url}")
    else:
        webhook_url = f"http://localhost:{port}/webhook/intercom"
        logger.info(f"Using local URL: {webhook_url}")
        
    client_secret = os.getenv("INTERCOM_CLIENT_SECRET")
    
    if not client_secret:
        logger.warning("No client secret found in .env file - signature verification will be skipped")
        client_secret = "dummy_secret_for_testing"
    
    # Create a test webhook payload - this time just a ping notification
    # which doesn't require a real conversation
    payload = {
        "type": "notification_event",
        "app_id": "test_app_id",
        "data": {
            "type": "notification_event_data",
            "item": {
                "type": "ping"
            }
        },
        "links": {},
        "id": "test_notification_id",
        "topic": "ping",
        "delivery_status": "pending",
        "delivery_attempts": 1,
        "delivered_at": 0,
        "first_sent_at": 1622547633,
        "created_at": 1622547633,
        "self": None
    }
    
    # Convert payload to JSON string
    payload_str = json.dumps(payload)
    
    # Create signature
    mac = hmac.new(
        client_secret.encode('utf-8'),
        msg=payload_str.encode('utf-8'),
        digestmod=hashlib.sha1
    )
    signature = mac.hexdigest()
    
    # Set headers
    headers = {
        "Content-Type": "application/json",
        "X-Hub-Signature": f"sha1={signature}"
    }
    
    # First, test the HEAD request that Intercom uses for validation
    logger.info("Testing webhook validation with HEAD request...")
    try:
        head_response = requests.head(webhook_url)
        logger.info(f"HEAD response status: {head_response.status_code}")
        
        if head_response.status_code != 200:
            logger.error("Webhook validation failed! Server should return 200 for HEAD requests.")
            return 1
        
        logger.info("Webhook validation successful!")
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to webhook server at {webhook_url}")
        logger.error("Make sure your webhook server is running (python webhook_server.py)")
        return 1
    
    # Now test the actual webhook with a ping event
    logger.info("Sending test webhook ping request...")
    try:
        response = requests.post(webhook_url, headers=headers, data=payload_str)
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Webhook request failed with status {response.status_code}: {response.text}")
            return 1
        
        logger.info(f"Webhook response: {response.text}")
        logger.info("Ping test completed successfully!")
        
        # If the ping test worked, try a simple conversation event
        # but one that wouldn't try to fetch a real conversation
        logger.info("Now sending a test conversation event (this might return an error due to test data)...")
        conversation_payload = {
            "type": "notification_event",
            "app_id": "test_app_id",
            "data": {
                "type": "notification_event_data",
                "item": {
                    "type": "conversation",
                    "id": "test_conversation_id",
                    "created_at": 1622547633,
                    "updated_at": 1622547633,
                    "user": {
                        "type": "user",
                        "id": "test_user_id",
                        "name": "Test User"
                    },
                    "conversation_parts": {
                        "conversation_parts": [
                            {
                                "id": "test_part_id",
                                "body": "<p>Hello from webhook test</p>",
                                "author": {
                                    "type": "user",
                                    "id": "test_user_id"
                                }
                            }
                        ]
                    }
                }
            },
            "links": {},
            "id": "test_notification_id",
            "topic": "conversation.user.created",
            "delivery_status": "pending",
            "delivery_attempts": 1,
            "delivered_at": 0,
            "first_sent_at": 1622547633,
            "created_at": 1622547633,
            "self": None
        }
        
        # Sign and send
        conv_payload_str = json.dumps(conversation_payload)
        conv_mac = hmac.new(
            client_secret.encode('utf-8'),
            msg=conv_payload_str.encode('utf-8'),
            digestmod=hashlib.sha1
        )
        conv_signature = conv_mac.hexdigest()
        
        conv_headers = {
            "Content-Type": "application/json",
            "X-Hub-Signature": f"sha1={conv_signature}"
        }
        
        conv_response = requests.post(webhook_url, headers=conv_headers, data=conv_payload_str)
        logger.info(f"Conversation event response status: {conv_response.status_code}")
        logger.info(f"Conversation event response (this may show an error, which is normal for test data): {conv_response.text}")
        
        # Return success as long as the ping was handled correctly
        return 0
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
