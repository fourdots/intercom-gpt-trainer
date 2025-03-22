#!/usr/bin/env python3
"""
Test script to manually send a reply to a specific Intercom conversation.
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
    
    # Get Intercom credentials
    intercom_token = os.getenv("INTERCOM_ACCESS_TOKEN")
    intercom_admin_id = os.getenv("INTERCOM_ADMIN_ID")
    
    if not intercom_token or not intercom_admin_id:
        logger.error("Missing required Intercom credentials in environment variables")
        return 1
    
    logger.info(f"Using Intercom Admin ID: {intercom_admin_id}")
    logger.info(f"Intercom Token (truncated): {intercom_token[:10]}...")
    
    # Setup headers
    headers = {
        "Authorization": f"Bearer {intercom_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Get conversation ID from user input
    conversation_id = input("Enter the Intercom conversation ID to reply to: ")
    if not conversation_id:
        logger.error("No conversation ID provided")
        return 1
        
    # Get reply message from user input
    reply_message = input("Enter the reply message to send: ")
    if not reply_message:
        logger.error("No reply message provided")
        return 1
    
    try:
        # Send reply to the conversation
        logger.info(f"Sending reply to conversation {conversation_id}...")
        reply_url = f"https://api.intercom.io/conversations/{conversation_id}/reply"
        
        payload = {
            "type": "admin",
            "admin_id": intercom_admin_id,
            "message_type": "comment",
            "body": f"<p>{reply_message}</p>"
        }
        
        logger.info(f"Using payload: {json.dumps(payload)}")
        
        response = requests.post(reply_url, headers=headers, json=payload)
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Failed to send reply: {response.text}")
            return 1
        
        logger.info("Reply sent successfully!")
        
        # Mark conversation as read
        logger.info(f"Marking conversation {conversation_id} as read...")
        read_url = f"https://api.intercom.io/conversations/{conversation_id}/read"
        
        read_response = requests.put(read_url, headers=headers)
        logger.info(f"Mark as read response status: {read_response.status_code}")
        
        if read_response.status_code != 200:
            logger.error(f"Failed to mark conversation as read: {read_response.text}")
            return 1
        
        logger.info("Conversation marked as read successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
