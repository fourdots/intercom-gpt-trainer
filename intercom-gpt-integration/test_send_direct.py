#!/usr/bin/env python3
"""
Direct test script to send a message to GPT Trainer using the fixed session ID.
This simpler version uses a minimal payload to ensure compatibility.
"""

import os
import logging
import json
from dotenv import load_dotenv
import requests

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fixed session UUID
FIXED_SESSION_UUID = "1c9b9c7f72b14e07bd2c625ab1d12c90"

def main():
    # Load environment variables
    load_dotenv()
    
    # Get API credentials
    api_key = os.getenv("GPT_TRAINER_API_KEY")
    api_url = os.getenv("GPT_TRAINER_API_URL", "https://app.gpt-trainer.com/api/v1")
    
    if not api_key:
        logger.error("Missing required environment variable GPT_TRAINER_API_KEY")
        return 1
    
    logger.info(f"Using API URL: {api_url}")
    logger.info(f"Using fixed Session UUID: {FIXED_SESSION_UUID}")
    
    # Setup headers - using only the essential ones
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Get user input
    test_message = input("Enter a test message to send: ")
    test_conversation_id = input("Enter a test conversation ID (or press Enter to skip): ") or "test_conversation_123"
    
    try:
        # Send message to GPT Trainer with simplified payload
        logger.info("Sending message to GPT Trainer...")
        message_url = f"{api_url}/session/{FIXED_SESSION_UUID}/message/stream"
        logger.info(f"POST {message_url}")
        
        # Use a simpler payload format
        payload = {
            "query": test_message,
            "stream": False,
            "conversation_id": test_conversation_id  # Only include this simple format
        }
        
        logger.info(f"Using payload: {json.dumps(payload)}")
        
        message_response = requests.post(message_url, headers=headers, json=payload)
        logger.info(f"Response status: {message_response.status_code}")
        logger.info(f"Response headers: {dict(message_response.headers)}")
        
        if message_response.status_code != 200:
            logger.error(f"Failed to send message: {message_response.text}")
            return 1
        
        # Get the raw response
        raw_response = message_response.text
        logger.info(f"Raw response: {raw_response}")
        
        # Try to parse JSON but don't fail if not valid
        try:
            data = message_response.json()
            logger.info(f"Response JSON: {json.dumps(data)}")
        except json.JSONDecodeError:
            logger.info("Response is not valid JSON, using raw text")
        
        logger.info("Test completed successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
