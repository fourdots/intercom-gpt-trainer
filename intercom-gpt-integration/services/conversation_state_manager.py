#!/usr/bin/env python3
"""
Conversation State Manager

This module manages conversation states to prevent the AI from sending multiple
messages without receiving a user reply in between. It tracks the state of each
conversation as either:
- AWAITING_USER_REPLY: The AI has sent a message and is waiting for the user to respond
- READY_FOR_RESPONSE: The user has replied and the AI can now respond

This ensures that AI messages are only sent when appropriate and prevents message flooding.
"""

import logging
from utils.session_store import SessionStore, AWAITING_USER_REPLY, READY_FOR_RESPONSE

logger = logging.getLogger(__name__)

class ConversationStateManager:
    """
    Manages the state of conversations to prevent multiple AI messages
    without user replies in between.
    """
    
    def __init__(self, session_store):
        """
        Initialize the conversation state manager.
        
        Args:
            session_store: An instance of SessionStore to use. If not provided,
                          a new instance will be created.
        """
        self.session_store = session_store
        self.AWAITING_USER_REPLY = "AWAITING_USER_REPLY"
        self.READY_FOR_RESPONSE = "READY_FOR_RESPONSE"
        self.ADMIN_TAKEOVER = "ADMIN_TAKEOVER"  # New state for when a human admin takes over
        
        # Default state is READY_FOR_RESPONSE for new conversations
        self.default_state = self.READY_FOR_RESPONSE
        
        logging.info("Initialized ConversationStateManager")
    
    def can_send_ai_response(self, conversation_id):
        """
        Check if it's appropriate to send an AI response for this conversation.
        
        Args:
            conversation_id: The ID of the conversation to check
            
        Returns:
            bool: True if the AI can respond, False otherwise
        """
        state = self.session_store.get_conversation_state(conversation_id)
        
        # Check if an admin has taken over
        if state == self.ADMIN_TAKEOVER:
            logger.info(f"Conversation {conversation_id} has been taken over by a human admin - skipping AI response")
            return False
        
        # Check if we're waiting for a user reply
        if state == self.AWAITING_USER_REPLY:
            logger.info(f"Conversation {conversation_id} is awaiting user reply - skipping AI response")
            return False
            
        # Otherwise, we're ready for a response
        logger.info(f"Conversation {conversation_id} is ready for an AI response")
        return True
    
    def mark_ai_response_sent(self, conversation_id, session_id):
        """
        Mark that an AI response has been sent, changing the state to AWAITING_USER_REPLY.
        
        Args:
            conversation_id: The ID of the conversation
            session_id: The associated session ID
        """
        logger.info(f"Marking conversation {conversation_id} as awaiting user reply")
        self.session_store.mark_awaiting_user_reply(conversation_id, session_id)
    
    def mark_user_reply_received(self, conversation_id):
        """
        Mark that a user reply has been received, changing the state to READY_FOR_RESPONSE.
        
        Args:
            conversation_id: The ID of the conversation
            
        Returns:
            bool: True if the state was successfully updated, False otherwise
        """
        logger.info(f"Marking conversation {conversation_id} as ready for response")
        return self.session_store.mark_ready_for_response(conversation_id)
    
    def get_conversation_state(self, conversation_id):
        """
        Get the current state of a conversation.
        
        Args:
            conversation_id: The ID of the conversation
            
        Returns:
            str: The conversation state (AWAITING_USER_REPLY or READY_FOR_RESPONSE)
        """
        return self.session_store.get_conversation_state(conversation_id)

    def mark_admin_takeover(self, conversation_id, admin_id):
        """
        Mark that a human admin has taken over this conversation.
        This will prevent the AI from sending further responses.
        
        Args:
            conversation_id: The ID of the conversation
            admin_id: The ID of the admin who took over
            
        Returns:
            bool: True if the state was successfully updated, False otherwise
        """
        logger.info(f"Admin {admin_id} has taken over conversation {conversation_id} - AI will stop responding")
        return self.session_store.mark_admin_takeover(conversation_id, admin_id) 
