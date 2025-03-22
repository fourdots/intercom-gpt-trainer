#!/usr/bin/env python3
"""
Conversation Processor

This module handles the processing of Intercom conversations, including
session management, message forwarding to GPT Trainer, and response handling.
"""

import logging
import random
import string
import os
import time
from services.conversation_state_manager import ConversationStateManager

logger = logging.getLogger(__name__)

class ConversationProcessor:
    """
    Processes Intercom conversations and manages interactions with GPT Trainer.
    """
    
    def __init__(self, intercom_api, gpt_trainer_api, session_store, message_processor, rate_limiter):
        """
        Initialize the conversation processor.
        
        Args:
            intercom_api: An instance of IntercomAPI
            gpt_trainer_api: An instance of GPTTrainerAPI
            session_store: An instance of SessionStore
            message_processor: An instance of MessageProcessor
            rate_limiter: An instance of RateLimiter
        """
        self.intercom_api = intercom_api
        self.gpt_trainer_api = gpt_trainer_api
        self.session_store = session_store
        self.message_processor = message_processor
        self.rate_limiter = rate_limiter
        self.state_manager = ConversationStateManager(session_store)
    
    def process_conversation(self, conversation, last_processed_time):
        """
        Process a single Intercom conversation.
        
        Args:
            conversation: The Intercom conversation object
            last_processed_time: Unix timestamp to filter messages newer than this time
            
        Returns:
            bool: True if processing was successful, False otherwise
        """
        try:
            conversation_id = conversation.get('id')
            logger.info(f"Processing conversation {conversation_id}")
            
            # Extract messages that need to be processed
            messages = self.message_processor.extract_messages(
                conversation, 
                last_processed_time
            )
            
            if not messages:
                logger.debug(f"No new messages to process in conversation {conversation_id}")
                return True
                
            logger.info(f"Found {len(messages)} new messages to process in conversation {conversation_id}")
            
            # Check if any user messages - if so, mark the conversation as ready for response
            if messages:
                self.state_manager.mark_user_reply_received(conversation_id)
            
            # Check if we can send an AI response
            if not self.state_manager.can_send_ai_response(conversation_id):
                logger.info(f"Conversation {conversation_id} is awaiting user reply - skipping AI response")
                return True
            
            # Check rate limits
            if not self.rate_limiter.check_rate_limits(conversation_id):
                logger.warning(f"Rate limit reached for conversation {conversation_id} - skipping")
                return False
            
            # Get or create session for this conversation
            session_id = self._get_or_create_session(conversation_id)
            if not session_id:
                logger.error(f"Failed to get or create session for conversation {conversation_id}")
                return False
            
            # Process each message
            for message in messages:
                author_type = message['author_type']
                message_text = message['text']
                
                logger.info(f"Processing message from {author_type} in conversation {conversation_id}")
                
                # Add conversation context to the message
                prefixed_message = f"[Intercom Conversation {conversation_id}] {message_text}"
                
                # Send message to GPT Trainer
                ai_response = self.gpt_trainer_api.send_message(
                    prefixed_message, 
                    session_id,
                    conversation_id=conversation_id
                )
                
                if not ai_response:
                    logger.error(f"No response from GPT Trainer for message in conversation {conversation_id}")
                    continue
                
                # Send response back to Intercom
                success = self.intercom_api.reply_to_conversation(conversation_id, ai_response)
                
                if success:
                    # Update rate counters
                    self.rate_limiter.increment_rate_counter(conversation_id)
                    
                    # Mark that we sent an AI response and are awaiting user reply
                    self.state_manager.mark_ai_response_sent(conversation_id, session_id)
                    logger.info(f"Successfully sent reply to conversation {conversation_id} and updated state")
                else:
                    logger.error(f"Failed to send reply to Intercom for conversation {conversation_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing conversation {conversation.get('id')}: {str(e)}", exc_info=True)
            return False
    
    def _get_or_create_session(self, conversation_id):
        """
        Get an existing session or create a new one for this conversation.
        
        Args:
            conversation_id: The ID of the conversation
            
        Returns:
            str: The session ID if successful, None otherwise
        """
        session_id = self.session_store.get_session(conversation_id)
        
        if not session_id:
            logger.info(f"Creating new GPT Trainer session for conversation {conversation_id}")
            try:
                session_id = self.gpt_trainer_api.create_session()
                if session_id:
                    self.session_store.save_session(conversation_id, session_id)
                    logger.info(f"Created new session {session_id} for conversation {conversation_id}")
                else:
                    logger.error(f"Failed to create new session for conversation {conversation_id}")
            except Exception as e:
                logger.error(f"Error creating session: {str(e)}", exc_info=True)
                return None
        else:
            logger.debug(f"Using existing session {session_id} for conversation {conversation_id}")
            
        return session_id
    
    def _recreate_session(self, conversation_id):
        """
        Recreate a session if the current one has failed.
        
        Args:
            conversation_id: The ID of the conversation
            
        Returns:
            str: The new session ID if successful, None otherwise
        """
        logger.warning(f"Recreating session for conversation {conversation_id}")
        
        try:
            # Remove old session
            self.session_store.remove_session(conversation_id)
            
            # Create new session
            session_id = self.gpt_trainer_api.create_session()
            if session_id:
                self.session_store.save_session(conversation_id, session_id)
                logger.info(f"Recreated new session {session_id} for conversation {conversation_id}")
                return session_id
            else:
                logger.error(f"Failed to recreate session for conversation {conversation_id}")
                return None
        except Exception as e:
            logger.error(f"Error recreating session: {str(e)}", exc_info=True)
            return None
    
    def verify_active_sessions(self):
        """
        Verify that active sessions are working by sending a test message to a random one.
        
        Returns:
            bool: True if verification was successful, False otherwise
        """
        try:
            # Get a list of active sessions from the session store
            active_sessions = self.session_store.get_all_sessions()
            if not active_sessions:
                logger.info("No active sessions to verify")
                return True
                
            # Select a random session to test
            conversation_id, session_id = random.choice(list(active_sessions.items()))
            logger.info(f"Verifying session {session_id} for conversation {conversation_id}")
            
            # Generate a random marker for this test
            test_marker = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            test_message = f"TEST_SESSION_VERIFY_{test_marker} - This is an automated test message to verify session is active"
            
            # Try to send a test message
            response = self.gpt_trainer_api.send_message(test_message, session_id)
            
            if response:
                logger.info(f"Session verification successful. Got response: '{response[:50]}...'")
                return True
            else:
                logger.warning(f"Session verification failed for {session_id} - no response received")
                self._recreate_session(conversation_id)
                return False
                
        except Exception as e:
            logger.error(f"Error verifying sessions: {str(e)}", exc_info=True)
            return False
    
    def save_processed_messages(self):
        """Save processed message IDs to file."""
        self.message_processor.save_processed_messages() 
