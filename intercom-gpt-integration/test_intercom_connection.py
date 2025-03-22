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

def test_connection(platform_name, access_token, admin_id):
    """Test connection to Intercom API for a specific platform"""
    logger.info(f"=== Testing {platform_name} Intercom Connection ===")
    logger.info(f"Using Intercom Admin ID: {admin_id}")
    logger.info(f"Intercom Token (truncated): {access_token[:10]}...")
    
    # Setup headers
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    try:
        # 1. List conversations
        logger.info("Testing Intercom API - Listing conversations...")
        list_url = "https://api.intercom.io/conversations"
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
        detail_url = f"https://api.intercom.io/conversations/{conversation_id}"
        
        detail_response = requests.get(detail_url, headers=headers)
        logger.info(f"Response status: {detail_response.status_code}")
        
        if detail_response.status_code != 200:
            logger.error(f"Failed to get conversation details: {detail_response.text}")
            return False
        
        logger.info(f"{platform_name} connection test successful!")
        return True
        
    except Exception as e:
        logger.error(f"Error during test: {str(e)}", exc_info=True)
        return False

def main():
    # Load environment variables
    load_dotenv()
    
    # Get Reportz Intercom credentials
    reportz_token = os.getenv("INTERCOM_ACCESS_TOKEN")
    reportz_admin_id = os.getenv("INTERCOM_ADMIN_ID")
    
    # Get Base Intercom credentials
    base_token = os.getenv("BASE_INTERCOM_ACCESS_TOKEN")
    base_admin_id = os.getenv("INTERCOM_ADMIN_ID")  # Using same admin ID for now
    
    success = True
    
    # Test Reportz connection
    if reportz_token and reportz_admin_id:
        if not test_connection("Reportz", reportz_token, reportz_admin_id):
            success = False
    else:
        logger.error("Missing required Reportz Intercom credentials in environment variables")
        success = False
    
    # Test Base connection
    if base_token and base_admin_id:
        if not test_connection("Base", base_token, base_admin_id):
            success = False
    else:
        logger.error("Missing required Base Intercom credentials in environment variables")
        success = False
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main()) 
