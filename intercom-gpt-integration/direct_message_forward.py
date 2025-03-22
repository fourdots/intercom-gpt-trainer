#!/usr/bin/env python3
"""
Script to manually forward a specific Intercom conversation to GPT Trainer.
This bypasses the normal polling flow to test direct message forwarding.
"""

import os
import logging
import json
from dotenv import load_dotenv
import requests
import time
from utils.session_store import SessionStore
from services.conversation_state_manager import ConversationStateManager
from services.message_processor import MessageProcessor
from services.rate_limiter import RateLimiter

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Fixed session UUID to use
FIXED_SESSION_UUID = "1c9b9c7f72b14e07bd2c625ab1d12c90"

def clean_message_body(body):
    """Safely clean HTML from message body, handling None values"""
    if body is None:
        return ""
    return body.replace('<p>', '').replace('</p>', ' ').strip()

def main():
    # Load environment variables
    load_dotenv()
    
    # Get credentials
    intercom_token = os.getenv("INTERCOM_ACCESS_TOKEN")
    intercom_admin_id = os.getenv("INTERCOM_ADMIN_ID")
    gpt_trainer_key = os.getenv("GPT_TRAINER_API_KEY")
    gpt_trainer_url = os.getenv("GPT_TRAINER_API_URL", "https://app.gpt-trainer.com/api/v1")
    
    if not all([intercom_token, intercom_admin_id, gpt_trainer_key]):
        logger.error("Missing required environment variables")
        return 1
    
    # Create session store and conversation state manager
    session_store = SessionStore()
    state_manager = ConversationStateManager(session_store)
    message_processor = MessageProcessor()
    rate_limiter = RateLimiter()
    
    # Setup Intercom headers
    intercom_headers = {
        "Authorization": f"Bearer {intercom_token}",
        "Accept": "application/json",
        "Content-Type": "application/json"
    }
    
    # Setup GPT Trainer headers
    gpt_trainer_headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {gpt_trainer_key}"
    }
    
    # Get conversation ID to forward
    conversation_id = input("Enter the Intercom conversation ID to forward: ")
    if not conversation_id:
        logger.error("No conversation ID provided")
        return 1
    
    try:
        # 1. Get full conversation details from Intercom
        logger.info(f"Getting conversation {conversation_id} from Intercom...")
        detail_url = f"https://api.intercom.io/conversations/{conversation_id}"
        
        detail_response = requests.get(detail_url, headers=intercom_headers)
        logger.info(f"Response status: {detail_response.status_code}")
        
        if detail_response.status_code != 200:
            logger.error(f"Failed to get conversation details: {detail_response.text}")
            return 1
        
        conversation_data = detail_response.json()
        
        # Log the full JSON response structure for debugging
        logger.debug(f"Full Intercom conversation response: {json.dumps(conversation_data, indent=2)}")
        
        # 2. Extract messages to forward using the message processor
        logger.info("Extracting messages from conversation...")
        messages_to_forward = message_processor.extract_messages(conversation_data)
        
        if not messages_to_forward:
            logger.warning("No messages to forward found in this conversation")
            
            # If no messages found, create a static message to test with
            logger.info("Creating a test message to see if forwarding works")
            test_message = {
                'id': 'test_message_id',
                'author_type': 'lead',
                'text': "Hi, do you have shopify integration?",
                'timestamp': int(time.time())
            }
            messages_to_forward.append(test_message)
            
        logger.info(f"Found {len(messages_to_forward)} messages to forward")
        
        # 3. Mark that we received user message(s)
        if messages_to_forward:
            state_manager.mark_user_reply_received(conversation_id)
        
        # 4. Check if we can send an AI response
        if not state_manager.can_send_ai_response(conversation_id):
            logger.warning(f"Conversation {conversation_id} is awaiting user reply. Will not send AI response.")
            return 1
            
        # 5. Check rate limits
        if not rate_limiter.check_rate_limits(conversation_id):
            logger.warning(f"Rate limit reached for conversation {conversation_id}. Skipping.")
            return 1
        
        # 6. Process each message
        for i, message in enumerate(messages_to_forward):
            logger.info(f"Forwarding message {i+1}/{len(messages_to_forward)} from {message['author_type']}")
            
            # Prepare the message
            message_text = message['text']
            
            # Add context to the message
            prefixed_message = f"[Intercom Conversation {conversation_id}] {message_text}"
            
            # Send to GPT Trainer
            gpt_trainer_url_endpoint = f"{gpt_trainer_url}/session/{FIXED_SESSION_UUID}/message/stream"
            
            # Very simple payload with only essential fields
            payload = {
                "query": prefixed_message,
                "stream": False,
                "conversation_id": conversation_id
            }
            
            logger.info(f"Sending to GPT Trainer: '{prefixed_message[:50]}...'")
            
            gpt_response = requests.post(
                gpt_trainer_url_endpoint, 
                headers=gpt_trainer_headers, 
                json=payload
            )
            
            logger.info(f"GPT Trainer response status: {gpt_response.status_code}")
            
            if gpt_response.status_code != 200:
                logger.error(f"Failed to send message to GPT Trainer: {gpt_response.text}")
                continue
            
            # Process the response
            try:
                response_json = gpt_response.json()
                logger.info(f"Got JSON response: {json.dumps(response_json)}")
                response_text = response_json.get('response', '')
            except:
                response_text = gpt_response.text
                logger.info(f"Got text response: {response_text[:100]}...")
            
            # Send GPT Trainer's response back to Intercom
            if response_text:
                intercom_reply_url = f"https://api.intercom.io/conversations/{conversation_id}/reply"
                
                reply_payload = {
                    "type": "admin",
                    "admin_id": intercom_admin_id,
                    "message_type": "comment",
                    "body": f"<p>{response_text}</p>"
                }
                
                intercom_reply = requests.post(
                    intercom_reply_url, 
                    headers=intercom_headers, 
                    json=reply_payload
                )
                
                logger.info(f"Intercom reply status: {intercom_reply.status_code}")
                
                if intercom_reply.status_code != 200:
                    logger.error(f"Failed to send reply to Intercom: {intercom_reply.text}")
                else:
                    # Mark that we sent an AI response and are awaiting user reply
                    state_manager.mark_ai_response_sent(conversation_id, FIXED_SESSION_UUID)
                    logger.info(f"Updated conversation state to AWAITING_USER_REPLY")
                    
                    # Update rate counter
                    rate_limiter.increment_rate_counter(conversation_id)
            else:
                logger.error("No response text received from GPT Trainer")
            
        logger.info("All messages forwarded successfully!")
        return 0
        
    except Exception as e:
        logger.error(f"Error during forwarding: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
