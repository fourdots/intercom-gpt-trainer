#!/usr/bin/env python3
"""
EMERGENCY SCRIPT to mark all conversations as read and stop further responses.
This will prevent the system from sending more messages to users.
"""

import os
import logging
import time
from dotenv import load_dotenv
import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    # Load environment variables
    load_dotenv()
    
    # Get Intercom credentials
    intercom_token = os.getenv("INTERCOM_ACCESS_TOKEN")
    intercom_admin_id = os.getenv("INTERCOM_ADMIN_ID")
    
    if not intercom_token or not intercom_admin_id:
        logger.error("Missing required Intercom credentials in environment variables")
        return 1
    
    logger.info(f"Using Intercom Admin ID: {intercom_admin_id}")
    logger.info(f"Intercom Token (truncated): {intercom_token[:10]}...")
    
    # Setup Intercom headers
    headers = {
        "Authorization": f"Bearer {intercom_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # 1. Get open conversations
        logger.info("Getting open conversations from Intercom...")
        list_url = "https://api.intercom.io/conversations"
        params = {
            "per_page": 50,  # Get a larger number to ensure we catch all
            "state": "open",
            "sort": "updated_at",
            "order": "desc"
        }
        
        response = requests.get(list_url, headers=headers, params=params)
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Failed to list conversations: {response.text}")
            return 1
        
        conversations = response.json().get('conversations', [])
        logger.info(f"Found {len(conversations)} open conversations")
        
        if not conversations:
            logger.warning("No open conversations found.")
            return 0
        
        # 2. Mark all conversations as read to prevent further replies
        for conversation in conversations:
            conversation_id = conversation.get('id')
            logger.info(f"Marking conversation {conversation_id} as read...")
            
            read_url = f"https://api.intercom.io/conversations/{conversation_id}/read"
            read_response = requests.put(read_url, headers=headers)
            
            if read_response.status_code == 200:
                logger.info(f"Successfully marked conversation {conversation_id} as read")
            else:
                logger.error(f"Failed to mark conversation {conversation_id} as read: {read_response.text}")
            
            # Add a small delay to avoid rate limiting
            time.sleep(0.5)
        
        logger.info("EMERGENCY FIX COMPLETE: All open conversations have been marked as read")
        logger.info("This will prevent the system from sending more automatic replies")
        logger.info("You should still verify in Intercom that no more messages are being sent")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error during emergency fix: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
