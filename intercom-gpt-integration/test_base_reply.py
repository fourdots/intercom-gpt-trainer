#!/usr/bin/env python3
"""
Test script to verify that we can reply to a Base Intercom conversation.
"""

import os
import logging
import json
import time
from dotenv import load_dotenv
import requests
import sys

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_base_reply(user_message=None):
    """Test sending a reply to a Base Intercom conversation"""
    # Load environment variables
    load_dotenv()
    
    # Get Base Intercom configuration
    base_token = os.environ.get("BASE_INTERCOM_ACCESS_TOKEN")
    base_api_url = os.environ.get("BASE_INTERCOM_API_URL", "https://api.intercom.io")
    admin_id = os.environ.get("INTERCOM_ADMIN_ID")
    
    if not base_token or not admin_id:
        logger.error("Missing required Base Intercom credentials in environment variables")
        return False
    
    logger.info("=== Testing Base Intercom Reply ===")
    logger.info(f"Using Intercom Admin ID: {admin_id}")
    logger.info(f"Intercom Token (truncated): {base_token[:10]}...")
    logger.info(f"Using API base URL: {base_api_url}")
    
    # Setup headers
    headers = {
        "Authorization": f"Bearer {base_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # 1. List conversations
        logger.info("Listing Base conversations...")
        list_url = f"{base_api_url}/conversations"
        params = {
            "per_page": 5,
            "state": "open",
            "sort": "updated_at",
            "order": "desc"
        }
        
        response = requests.get(list_url, headers=headers, params=params)
        response.raise_for_status()
        
        conversations = response.json().get('conversations', [])
        logger.info(f"Found {len(conversations)} conversations")
        
        if not conversations:
            logger.warning("No conversations found. Make sure there are active conversations in Base Intercom.")
            return False
        
        # 2. Get first conversation
        conversation = conversations[0]
        conversation_id = conversation.get('id')
        updated_at = conversation.get('updated_at')
        
        logger.info(f"Selected conversation {conversation_id} (updated at: {time.ctime(updated_at)})")
        
        # 3. Get full conversation details
        logger.info(f"Getting full details for conversation {conversation_id}...")
        detail_url = f"{base_api_url}/conversations/{conversation_id}"
        
        detail_response = requests.get(detail_url, headers=headers)
        detail_response.raise_for_status()
        conversation_details = detail_response.json()
        
        # Get contact info for sending user message
        contacts = conversation_details.get('contacts', {}).get('contacts', [])
        if not contacts:
            logger.error("No contacts found in conversation")
            return False
            
        contact_id = contacts[0].get('id')
        logger.info(f"Found contact ID: {contact_id}")
        
        if user_message:
            # 4. Send a message as the user to trigger GPT trainer
            logger.info(f"Sending test user message: {user_message}")
            user_msg_url = f"{base_api_url}/conversations/{conversation_id}/reply"
            user_msg_payload = {
                "type": "user",
                "intercom_user_id": contact_id,
                "message_type": "comment",
                "body": f"<p>{user_message}</p>"
            }
            
            user_msg_response = requests.post(user_msg_url, headers=headers, json=user_msg_payload)
            user_msg_response.raise_for_status()
            logger.info(f"User message sent successfully (status code: {user_msg_response.status_code})")
            
            # Wait longer for GPT trainer to respond
            wait_time = 90  # seconds to wait (increased from 30 to 90)
            logger.info(f"Waiting up to {wait_time} seconds for GPT trainer to respond...")
            for i in range(wait_time):
                if i % 15 == 0:  # Update logging interval to be less verbose
                    logger.info(f"Still waiting... ({i}/{wait_time} seconds)")
                time.sleep(1)
            
            # Get conversation again to see if there's a response
            try:
                updated_detail_response = requests.get(detail_url, headers=headers)
                updated_detail_response.raise_for_status()
                updated_conversation = updated_detail_response.json()
                
                # Check for new responses
                parts = updated_conversation.get('conversation_parts', {}).get('conversation_parts', [])
                if parts:
                    logger.info(f"Found {len(parts)} conversation parts.")
                    
                    # Print all conversation parts for debugging
                    logger.info("All conversation parts:")
                    for i, part in enumerate(parts):
                        try:
                            p_author = part.get('author', {}) or {}
                            p_type = p_author.get('type', 'unknown')
                            p_id = p_author.get('id', 'unknown')
                            p_name = p_author.get('name', 'unknown')
                            p_body = part.get('body', '')
                            p_created = part.get('created_at', 0)
                            p_created_str = time.ctime(p_created) if p_created else 'unknown'
                            
                            logger.info(f"{i+1}. [{p_created_str}] {p_name} ({p_type}, ID: {p_id}): {p_body[:100]}...")
                            
                            # Check if this part was created after our user message
                            if p_created > time.time() - wait_time - 5:  # Within the timeframe of our test
                                if p_type == 'admin' or p_type == 'bot':
                                    logger.info(f"Found a response: {p_body[:200]}...")
                                    logger.info("Success! GPT trainer response received.")
                        except Exception as e:
                            logger.error(f"Error processing conversation part {i}: {e}")
                else:
                    logger.warning("No conversation parts found after waiting")
            except Exception as e:
                logger.error(f"Error checking for response: {e}")
        else:    
            # 4. Send a test reply as admin
            test_message = "This is a test reply from the Base GPT Trainer test script. Current time: " + time.ctime()
            logger.info(f"Sending test reply: {test_message}")
            
            reply_url = f"{base_api_url}/conversations/{conversation_id}/reply"
            reply_payload = {
                "type": "admin",
                "admin_id": admin_id,
                "message_type": "comment",
                "body": f"<p>{test_message}</p>"
            }
            
            reply_response = requests.post(reply_url, headers=headers, json=reply_payload)
            reply_response.raise_for_status()
            
            logger.info(f"Reply sent successfully (status code: {reply_response.status_code})")
        
        return True
    
    except Exception as e:
        logger.error(f"Error testing Base Intercom reply: {e}")
        return False

if __name__ == "__main__":
    # Check if there's a message argument
    if len(sys.argv) > 1:
        user_message = sys.argv[1]
        test_base_reply(user_message)
    else:
        test_base_reply() 
