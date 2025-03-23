#!/usr/bin/env python3
"""
Script to view the complete response from the most recent Base Intercom conversation.
"""

import os
import logging
import json
import time
from dotenv import load_dotenv
import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def view_complete_response():
    """View the complete response from the most recent Base Intercom conversation"""
    # Load environment variables
    load_dotenv()
    
    # Get Base Intercom configuration
    base_token = os.environ.get("BASE_INTERCOM_ACCESS_TOKEN")
    base_api_url = os.environ.get("BASE_INTERCOM_API_URL", "https://api.intercom.io")
    
    if not base_token:
        logger.error("Missing required Base Intercom credentials in environment variables")
        return False
    
    logger.info("=== Viewing Complete GPT Trainer Response ===")
    
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
            logger.warning("No conversations found.")
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
        
        # Get conversation parts
        parts = conversation_details.get('conversation_parts', {}).get('conversation_parts', [])
        if parts:
            logger.info(f"Found {len(parts)} conversation parts.")
            
            # Get the latest admin response (GPT trainer response)
            latest_admin_response = None
            
            for part in reversed(parts):  # Start from most recent
                p_author = part.get('author', {}) or {}
                p_type = p_author.get('type', 'unknown')
                
                if p_type == 'admin' or p_type == 'bot':
                    latest_admin_response = part
                    break
            
            if latest_admin_response:
                p_name = latest_admin_response.get('author', {}).get('name', 'unknown')
                p_body = latest_admin_response.get('body', '')
                p_created = latest_admin_response.get('created_at', 0)
                p_created_str = time.ctime(p_created) if p_created else 'unknown'
                
                logger.info(f"Latest response from [{p_created_str}] {p_name}:")
                print("\n" + "="*80)
                print("COMPLETE RESPONSE:")
                print("="*80)
                # Remove HTML tags for cleaner output
                clean_response = p_body.replace('<p>', '').replace('</p>', '\n')
                print(clean_response)
                print("="*80)
            else:
                logger.warning("No admin/bot responses found in the conversation")
        else:
            logger.warning("No conversation parts found")
        
        return True
    
    except Exception as e:
        logger.error(f"Error retrieving response: {e}")
        return False

if __name__ == "__main__":
    view_complete_response() 
