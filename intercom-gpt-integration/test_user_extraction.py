#!/usr/bin/env python3
"""
Test script to verify the user extraction from Intercom conversations.
"""

import os
import logging
import json
import time
from dotenv import load_dotenv
import requests
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_user_info(conversation, current_intercom_api=None):
    """
    Extract user information from an Intercom conversation
    
    Args:
        conversation: The Intercom conversation object
        current_intercom_api: Optional API client to help determine platform
        
    Returns:
        dict: User information including name, email, and platform
    """
    user_info = {
        "name": "Unknown User",
        "email": "",
        "platform": "unknown"
    }
    
    try:
        # Log the conversation structure for debugging
        logger.info(f"DEBUG - Extracting user info from conversation: {conversation.get('id')}")
        logger.info(f"DEBUG - Conversation keys: {list(conversation.keys() if conversation else [])}")
        
        # Determine platform (Reportz or Base)
        platform = "unknown"
        
        # Check for platform indicators in the conversation
        conversation_tags = conversation.get("tags", {}).get("tags", [])
        if any(tag.get("name", "").lower() == "base.me" for tag in conversation_tags):
            platform = "Base"
            logger.info(f"DEBUG - Detected Base platform from tags")
        else:
            # Check conversation title
            title = conversation.get("title", "").lower() or ""
            logger.info(f"DEBUG - Conversation title: {title}")
            if "base.me" in title or "base" in title:
                platform = "Base"
                logger.info(f"DEBUG - Detected Base platform from title")
            else:
                # Try to determine from conversation_id format
                conversation_id = conversation.get("id", "")
                if conversation_id and isinstance(conversation_id, (int, str)) and len(str(conversation_id)) <= 6:
                    platform = "Base"
                    logger.info(f"DEBUG - Detected Base platform from conversation ID format: {conversation_id}")
                else:
                    # Manual check: Base conversations typically have IDs that are 5-6 digits
                    # Reportz conversations have longer IDs like: 63371900205536
                    # Check the source field for workspace information
                    workspace_id = conversation.get("workspace_id", "")
                    if workspace_id:
                        if "base" in workspace_id.lower():
                            platform = "Base"
                            logger.info(f"DEBUG - Detected Base platform from workspace ID: {workspace_id}")
                        else:
                            platform = "Reportz"
                            logger.info(f"DEBUG - Detected Reportz platform from workspace ID: {workspace_id}")
                    else:
                        # Default to Reportz if no Base indicators
                        platform = "Reportz"
                        logger.info(f"DEBUG - Defaulting to Reportz platform")
        
        user_info["platform"] = platform
        logger.info(f"DEBUG - Set platform to: {platform}")
        
        # Extract user's contact information from source (which is more consistently populated)
        source = conversation.get("source", {})
        source_author = source.get("author", {})
        
        if source_author and source_author.get("type") == "user":
            logger.info(f"DEBUG - Found source author: {json.dumps(source_author)}")
            
            # Get name
            name = source_author.get("name", "")
            if name:
                user_info["name"] = name
                logger.info(f"DEBUG - Found user name from source: {name}")
            
            # Get email
            email = source_author.get("email", "")
            if email:
                user_info["email"] = email
                logger.info(f"DEBUG - Found user email from source: {email}")
        
        # If name still not found, try contacts
        if user_info["name"] == "Unknown User":
            contacts = conversation.get("contacts", {}).get("contacts", [])
            logger.info(f"DEBUG - Found {len(contacts) if contacts else 0} contacts")
            
            if contacts and len(contacts) > 0:
                contact = contacts[0]  # Get the first contact
                contact_id = contact.get("id")
                logger.info(f"DEBUG - Contact ID: {contact_id}")
                
                # If needed, we could make another API call to get full contact details
                # But let's try other methods first
                
                # Extract name if available directly
                name = contact.get("name", "")
                if name:
                    user_info["name"] = name
                    logger.info(f"DEBUG - Found user name from contact: {name}")
        
        # Additional fallback methods to get user info
        if not user_info["name"] or user_info["name"] == "Unknown User":
            # Check for user name in the initial message author
            initial_author = conversation.get("conversation_message", {}).get("author", {})
            logger.info(f"DEBUG - Initial author: {json.dumps(initial_author)}")
            
            if initial_author.get("type") == "user" and initial_author.get("name"):
                user_info["name"] = initial_author.get("name")
                logger.info(f"DEBUG - Found user name from initial author: {initial_author.get('name')}")
                
                # Also check for email in initial author
                if initial_author.get("email") and not user_info["email"]:
                    user_info["email"] = initial_author.get("email")
                    logger.info(f"DEBUG - Found user email from initial author: {initial_author.get('email')}")
        
        # Check for contact info in user field (yet another place it could be)
        user = conversation.get("user", {})
        if user:
            logger.info(f"DEBUG - User field exists with keys: {list(user.keys())}")
            if user.get("name") and user_info["name"] == "Unknown User":
                user_info["name"] = user.get("name")
                logger.info(f"DEBUG - Found user name from user field: {user.get('name')}")
            if user.get("email") and not user_info["email"]:
                user_info["email"] = user.get("email")
                logger.info(f"DEBUG - Found user email from user field: {user.get('email')}")
        
        # Log final extracted user info
        logger.info(f"DEBUG - Final extracted user info: {json.dumps(user_info)}")
        
        return user_info
    except Exception as e:
        logger.error(f"Error extracting user info: {e}", exc_info=True)
        return user_info

def test_user_extraction():
    """Test extracting user info from Intercom conversations."""
    # Load environment variables
    load_dotenv()
    
    # Get Intercom credentials for both platforms
    reportz_token = os.environ.get("INTERCOM_ACCESS_TOKEN")
    base_token = os.environ.get("BASE_INTERCOM_ACCESS_TOKEN")
    
    if not reportz_token or not base_token:
        logger.error("Missing required Intercom credentials")
        return False
    
    logger.info("=== Testing User Info Extraction ===")
    logger.info(f"Reportz token (truncated): {reportz_token[:10]}...")
    logger.info(f"Base token (truncated): {base_token[:10]}...")
    
    # Setup headers for both platforms
    reportz_headers = {
        "Authorization": f"Bearer {reportz_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    base_headers = {
        "Authorization": f"Bearer {base_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # API URL
    api_url = "https://api.intercom.io"
    
    try:
        # Test with Reportz conversation
        logger.info("\n=== Testing Reportz Conversation ===")
        reportz_list_url = f"{api_url}/conversations"
        reportz_params = {
            "per_page": 5,
            "state": "open",
            "sort": "updated_at",
            "order": "desc"
        }
        
        reportz_response = requests.get(reportz_list_url, headers=reportz_headers, params=reportz_params)
        reportz_response.raise_for_status()
        
        reportz_conversations = reportz_response.json().get('conversations', [])
        logger.info(f"Found {len(reportz_conversations)} Reportz conversations")
        
        if reportz_conversations:
            # Get first conversation
            reportz_conversation = reportz_conversations[0]
            reportz_id = reportz_conversation.get('id')
            
            logger.info(f"Getting details for Reportz conversation {reportz_id}")
            reportz_detail_url = f"{api_url}/conversations/{reportz_id}"
            
            reportz_detail_response = requests.get(reportz_detail_url, headers=reportz_headers)
            reportz_detail_response.raise_for_status()
            
            reportz_conversation_details = reportz_detail_response.json()
            
            # Extract user info
            logger.info("Extracting user info from Reportz conversation")
            reportz_user_info = extract_user_info(reportz_conversation_details)
            
            # Print summary
            logger.info(f"Reportz User Info: {json.dumps(reportz_user_info, indent=2)}")
        else:
            logger.warning("No Reportz conversations found")
        
        # Test with Base conversation
        logger.info("\n=== Testing Base Conversation ===")
        base_list_url = f"{api_url}/conversations"
        base_params = {
            "per_page": 5,
            "state": "open",
            "sort": "updated_at",
            "order": "desc"
        }
        
        base_response = requests.get(base_list_url, headers=base_headers, params=base_params)
        base_response.raise_for_status()
        
        base_conversations = base_response.json().get('conversations', [])
        logger.info(f"Found {len(base_conversations)} Base conversations")
        
        if base_conversations:
            # Get first conversation
            base_conversation = base_conversations[0]
            base_id = base_conversation.get('id')
            
            logger.info(f"Getting details for Base conversation {base_id}")
            base_detail_url = f"{api_url}/conversations/{base_id}"
            
            base_detail_response = requests.get(base_detail_url, headers=base_headers)
            base_detail_response.raise_for_status()
            
            base_conversation_details = base_detail_response.json()
            
            # Create a mock api client for testing platform detection
            class MockIntercomAPI:
                def __init__(self, token):
                    self.access_token = token
            
            # Extract user info
            logger.info("Extracting user info from Base conversation")
            mock_api = MockIntercomAPI(base_token)
            base_user_info = extract_user_info(base_conversation_details, mock_api)
            
            # Print summary
            logger.info(f"Base User Info: {json.dumps(base_user_info, indent=2)}")
        else:
            logger.warning("No Base conversations found")
        
        return True
    
    except Exception as e:
        logger.error(f"Error testing user extraction: {e}")
        return False

if __name__ == "__main__":
    test_user_extraction() 
