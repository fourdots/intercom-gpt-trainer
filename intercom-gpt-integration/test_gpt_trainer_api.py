#!/usr/bin/env python3
"""
Test script to verify the GPT Trainer API connection.
This script attempts to:
1. Create a session
2. Send a test message
3. Print the response
"""

import os
import logging
import json
from dotenv import load_dotenv
import requests

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv()
    
    # Get API credentials
    api_key = os.getenv("GPT_TRAINER_API_KEY")
    chatbot_uuid = os.getenv("CHATBOT_UUID")
    api_url = os.getenv("GPT_TRAINER_API_URL", "https://app.gpt-trainer.com/api/v1")
    
    if not api_key or not chatbot_uuid:
        logger.error("Missing required environment variables (GPT_TRAINER_API_KEY or CHATBOT_UUID)")
        return 1
    
    logger.info(f"Using API URL: {api_url}")
    logger.info(f"Using Chatbot UUID: {chatbot_uuid}")
    
    # Setup headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        # Step 1: Create a session
        logger.info("Step 1: Creating a new session...")
        session_url = f"{api_url}/chatbot/{chatbot_uuid}/session/create"
        logger.info(f"POST {session_url}")
        
        session_response = requests.post(session_url, headers=headers)
        logger.info(f"Response status: {session_response.status_code}")
        
        if session_response.status_code != 200:
            logger.error(f"Failed to create session: {session_response.text}")
            return 1
        
        session_data = session_response.json()
        logger.info(f"Session creation response: {json.dumps(session_data)}")
        
        # API uses 'uuid' instead of 'session_id'
        session_id = session_data.get('session_id') or session_data.get('uuid')
        if not session_id:
            logger.error("No session_id or uuid in response")
            return 1
        
        logger.info(f"Created session: {session_id}")
        
        # Step 2: Send a test message
        logger.info("Step 2: Sending a test message...")
        message_url = f"{api_url}/session/{session_id}/message/stream"
        logger.info(f"POST {message_url}")
        
        message_payload = {
            "query": "This is a test message from the API test script",
            "stream": False
        }
        
        message_response = requests.post(message_url, headers=headers, json=message_payload)
        logger.info(f"Response status: {message_response.status_code}")
        logger.info(f"Response headers: {dict(message_response.headers)}")
        
        if message_response.status_code != 200:
            logger.error(f"Failed to send message: {message_response.text}")
            return 1
        
        # Try to parse the response as JSON, but handle non-JSON responses
        raw_response = message_response.text
        logger.info(f"Raw response text: {raw_response[:100]}...")  # Print the first 100 chars
        
        # Try to parse as JSON, but don't fail if it's not valid JSON
        message_data = {}
        try:
            message_data = message_response.json()
            logger.info(f"Response parsed as JSON: {json.dumps(message_data)}")
            
            # Try to extract the response from various possible fields
            ai_response = None
            possible_fields = ['response', 'text', 'message', 'answer', 'content']
            
            for field in possible_fields:
                if field in message_data:
                    ai_response = message_data.get(field)
                    logger.info(f"Found AI response in field '{field}'")
                    break
            
            # If we still couldn't find a response, look for any string fields
            if not ai_response:
                for key, value in message_data.items():
                    if isinstance(value, str) and len(value) > 5:
                        logger.info(f"Possible response field '{key}': {value}")
                        if not ai_response:
                            ai_response = value
            
            if ai_response:
                logger.info(f"AI Response (from JSON): {ai_response}")
            else:
                logger.warning("Could not find an AI response in the JSON data")
        
        except json.JSONDecodeError:
            logger.warning("Response is not valid JSON, using raw text as response")
            ai_response = raw_response
            logger.info(f"AI Response (from raw text): {ai_response}")
            
        return 0
        
    except Exception as e:
        logger.error(f"Error during API test: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
