#!/usr/bin/env python3
"""
Debug version of the main script with enhanced logging and
immediate polling of a specific conversation ID for testing.
"""

import os
import logging
import time
import json
from dotenv import load_dotenv
from services.intercom_api import IntercomAPI
from services.gpt_trainer import GPTTrainerAPI
from services.poller import ConversationPoller
from utils.session_store import SessionStore
from services.conversation_state_manager import ConversationStateManager
from services.message_processor import MessageProcessor
from services.rate_limiter import RateLimiter

# Configure logging with maximal detail
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Reduce logging noise from external libraries
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def process_specific_conversation(intercom_api, gpt_trainer_api, conversation_id, session_store=None):
    """
    Process a specific conversation directly without going through the poller.
    This allows for more focused debugging.
    """
    logger.info(f"Directly processing conversation {conversation_id}...")
    
    # Initialize session store and state manager if not provided
    if session_store is None:
        session_store = SessionStore()
    
    # Initialize components
    state_manager = ConversationStateManager(session_store)
    message_processor = MessageProcessor()
    rate_limiter = RateLimiter()
    
    try:
        # Get the conversation details
        conversation_details = intercom_api.get_conversation(conversation_id)
        
        # Log the full response structure
        logger.debug(f"Full conversation data: {json.dumps(conversation_details, indent=2)}")
        
        # Print key information about the conversation
        logger.info(f"Conversation ID: {conversation_id}")
        logger.info(f"Updated at: {conversation_details.get('updated_at')}")
        
        # Extract messages using the MessageProcessor
        messages = message_processor.extract_messages(conversation_details)
        logger.info(f"Extracted {len(messages)} messages for processing")
        
        for i, message in enumerate(messages):
            logger.info(f"Message {i+1}: from {message['author_type']}: {message['text'][:50]}...")
        
        # Mark that we have user messages
        if messages:
            state_manager.mark_user_reply_received(conversation_id)
        
        # Check if we can send a response based on conversation state
        if not state_manager.can_send_ai_response(conversation_id):
            logger.warning(f"Conversation {conversation_id} is awaiting user reply. Will not send AI response.")
            return
        
        # Check rate limits
        if not rate_limiter.check_rate_limits(conversation_id):
            logger.warning(f"Rate limit reached for conversation {conversation_id}. Skipping.")
            return
        
        # Also try the direct forcing approach by creating a test message
        logger.info("Testing direct message forwarding with a static test message...")
        
        # Create a test message
        test_message = "Hi, this is a test message to verify integration is working."
        
        # Add context to the message
        prefixed_message = f"[Intercom Conversation {conversation_id}] {test_message}"
        
        # Send to GPT Trainer
        response = gpt_trainer_api.send_message(
            message=prefixed_message,
            session_id="1c9b9c7f72b14e07bd2c625ab1d12c90",
            conversation_id=conversation_id
        )
        
        if response:
            logger.info(f"Got response from GPT Trainer: '{response[:100]}...'")
            
            # Send response back to Intercom
            logger.info(f"Sending test response to Intercom conversation {conversation_id}")
            intercom_api.reply_to_conversation(
                conversation_id, 
                f"TEST RESPONSE: {response}",
                admin_id=intercom_api.admin_id
            )
            
            # Update rate counter
            rate_limiter.increment_rate_counter(conversation_id)
            
            # Mark that we sent an AI response
            session_id = "1c9b9c7f72b14e07bd2c625ab1d12c90"
            state_manager.mark_ai_response_sent(conversation_id, session_id)
            logger.info(f"Conversation state updated to AWAITING_USER_REPLY")
            
            logger.info("Test message was processed successfully!")
        else:
            logger.error("Failed to get response from GPT Trainer")
        
    except Exception as e:
        logger.error(f"Error processing specific conversation: {str(e)}", exc_info=True)

def main():
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    intercom_token = os.getenv("INTERCOM_ACCESS_TOKEN")
    intercom_admin_id = os.getenv("INTERCOM_ADMIN_ID")
    gpt_trainer_key = os.getenv("GPT_TRAINER_API_KEY")
    chatbot_uuid = os.getenv("CHATBOT_UUID")
    gpt_trainer_url = os.getenv("GPT_TRAINER_API_URL", "https://app.gpt-trainer.com/api/v1")
    
    # Log configuration (with sensitive data partially masked)
    logger.info(f"Intercom Admin ID: {intercom_admin_id}")
    if intercom_token:
        logger.info(f"Intercom Token (truncated): {intercom_token[:10]}...")
    if gpt_trainer_key:
        logger.info(f"GPT Trainer Key (truncated): {gpt_trainer_key[:10]}...")
    logger.info(f"GPT Trainer Chatbot UUID: {chatbot_uuid}")
    logger.info(f"GPT Trainer API URL: {gpt_trainer_url}")
    
    # Validate environment
    if not all([intercom_token, intercom_admin_id, gpt_trainer_key, chatbot_uuid]):
        logger.error("Missing required environment variables. Please check .env file.")
        return 1
    
    try:
        # Initialize components
        logger.info("Initializing services...")
        intercom_api = IntercomAPI(intercom_token, intercom_admin_id)
        gpt_trainer_api = GPTTrainerAPI(gpt_trainer_key, chatbot_uuid, gpt_trainer_url)
        session_store = SessionStore()
        
        # Get the conversation ID to debug
        conversation_id = input("Enter the Intercom conversation ID to debug (or leave empty to run normal poller): ")
        
        if conversation_id:
            # Process the specific conversation directly
            process_specific_conversation(intercom_api, gpt_trainer_api, conversation_id, session_store)
            
            # Ask if user wants to also run the normal poller
            run_poller = input("Do you also want to run the normal polling process? (y/n): ").lower() == 'y'
            
            if not run_poller:
                logger.info("Debug complete. Exiting.")
                return 0
        
        # Initialize and start poller with a short polling interval for testing
        polling_interval = 30  # Use a shorter interval for testing
        logger.info(f"Starting conversation poller with {polling_interval}s interval")
        poller = ConversationPoller(
            intercom_api,
            gpt_trainer_api,
            session_store,
            polling_interval=polling_interval
        )
        
        # Start the polling process
        poller.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        return 0
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
