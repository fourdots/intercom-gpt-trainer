#!/usr/bin/env python3
"""
Utility script to check and display the current state of all tracked conversations.
This helps with troubleshooting and understanding the current system state.
"""

import os
import logging
import json
from dotenv import load_dotenv
from utils.session_store import SessionStore, AWAITING_USER_REPLY, READY_FOR_RESPONSE
from services.conversation_state_manager import ConversationStateManager
from services.intercom_api import IntercomAPI

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
    
    try:
        # Initialize session store and state manager
        session_store = SessionStore()
        state_manager = ConversationStateManager(session_store)
        
        # Get all sessions
        sessions = session_store.get_all_sessions()
        logger.info(f"Found {len(sessions)} active sessions")
        
        if not sessions:
            logger.info("No active conversations found")
            return 0
        
        # Initialize Intercom API for getting conversation details
        intercom_api = IntercomAPI(intercom_token, intercom_admin_id)
        
        # Print header
        print("\n" + "="*80)
        print(f"{'CONVERSATION ID':<40} {'STATE':<25} {'SESSION ID':<40}")
        print("="*80)
        
        # Check state of each conversation
        for conversation_id, session_id in sessions.items():
            state = state_manager.get_conversation_state(conversation_id)
            state_display = "🟢 READY_FOR_RESPONSE" if state == READY_FOR_RESPONSE else "🔴 AWAITING_USER_REPLY"
            
            # Get more details from Intercom (optional)
            try:
                conversation = intercom_api.get_conversation(conversation_id)
                updated_at = conversation.get('updated_at', 'unknown')
                title = conversation.get('title', 'No title')
                print(f"{conversation_id:<40} {state_display:<25} {session_id:<40}")
                print(f"  • Title: {title}")
                print(f"  • Last updated: {updated_at}")
                print("-"*80)
            except Exception as e:
                logger.warning(f"Error getting details for conversation {conversation_id}: {str(e)}")
                print(f"{conversation_id:<40} {state_display:<25} {session_id:<40}")
                print("-"*80)
        
        return 0
        
    except Exception as e:
        logger.error(f"Error checking conversation states: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
