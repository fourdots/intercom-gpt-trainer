#!/usr/bin/env python3
"""
Test script to verify Intercom API connectivity and ability to retrieve messages for both Reportz and Base platforms.
"""

import os
import logging
import json
import time
from dotenv import load_dotenv
import requests

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_connection(platform_name, access_token, admin_id, api_url=None):
    """Test connection to Intercom API for a specific platform"""
    logger.info(f"=== Testing {platform_name} Intercom Connection ===")
    logger.info(f"Using Intercom Admin ID: {admin_id}")
    logger.info(f"Intercom Token (truncated): {access_token[:10]}...")
    
    # Use the provided API URL or default to the standard Intercom API
    base_url = api_url or "https://api.intercom.io"
    logger.info(f"Using API base URL: {base_url}")
    
    # Setup headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # 1. List conversations
        logger.info("Testing Intercom API - Listing conversations...")
        list_url = f"{base_url}/conversations"
        params = {
            "per_page": 10,
            "state": "open",
            "sort": "updated_at",
            "order": "desc"
        }
        
        response = requests.get(list_url, headers=headers, params=params)
        logger.info(f"Response status: {response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"Failed to list conversations: {response.text}")
            return False
        
        conversations = response.json().get('conversations', [])
        logger.info(f"Found {len(conversations)} conversations")
        
        if not conversations:
            logger.warning("No conversations found. Make sure there are active conversations in Intercom.")
            return True  # Still return True since API connection works
        
        # 2. Get details of the most recent conversation
        conversation = conversations[0]
        conversation_id = conversation.get('id')
        updated_at = conversation.get('updated_at')
        
        logger.info(f"Examining conversation {conversation_id} (updated at: {time.ctime(updated_at)})")
        
        # 3. Get full conversation details
        logger.info(f"Getting full details for conversation {conversation_id}...")
        detail_url = f"{base_url}/conversations/{conversation_id}"
        
        detail_response = requests.get(detail_url, headers=headers)
        logger.info(f"Response status: {detail_response.status_code}")
        
        if detail_response.status_code != 200:
            logger.error(f"Failed to get conversation details: {detail_response.text}")
            return False
        
        logger.info(f"{platform_name} connection test successful!")
        return True
    
    except Exception as e:
        logger.error(f"Error testing connection to {platform_name}: {e}")
        return False

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Get configuration
    reportz_token = os.environ.get("INTERCOM_ACCESS_TOKEN")
    base_token = os.environ.get("BASE_INTERCOM_ACCESS_TOKEN")
    base_api_url = os.environ.get("BASE_INTERCOM_API_URL")
    admin_id = os.environ.get("INTERCOM_ADMIN_ID")
    
    # Test Reportz Intercom connection
    test_connection("Reportz", reportz_token, admin_id)
    
    # Test Base Intercom connection
    test_connection("Base", base_token, admin_id, base_api_url) 
