#!/usr/bin/env python3
"""
Tests for the ConversationStateManager class.
"""

import unittest
from unittest.mock import MagicMock, patch
from services.conversation_state_manager import ConversationStateManager
from utils.session_store import AWAITING_USER_REPLY, READY_FOR_RESPONSE

class TestConversationStateManager(unittest.TestCase):
    """Test cases for the ConversationStateManager class."""
    
    def setUp(self):
        """Set up a fresh ConversationStateManager with a mock SessionStore for each test."""
        self.mock_session_store = MagicMock()
        self.state_manager = ConversationStateManager(self.mock_session_store)
    
    def test_can_send_ai_response_ready(self):
        """Test that AI can respond when the conversation is ready for response."""
        # Set up the mock to indicate ready for response
        self.mock_session_store.is_awaiting_user_reply.return_value = False
        
        # Check if AI can respond
        result = self.state_manager.can_send_ai_response("conversation1")
        
        # Verify the result
        self.assertTrue(result)
        self.mock_session_store.is_awaiting_user_reply.assert_called_once_with("conversation1")
    
    def test_can_send_ai_response_awaiting(self):
        """Test that AI cannot respond when awaiting user reply."""
        # Set up the mock to indicate awaiting user reply
        self.mock_session_store.is_awaiting_user_reply.return_value = True
        
        # Check if AI can respond
        result = self.state_manager.can_send_ai_response("conversation1")
        
        # Verify the result
        self.assertFalse(result)
        self.mock_session_store.is_awaiting_user_reply.assert_called_once_with("conversation1")
    
    def test_mark_ai_response_sent(self):
        """Test marking a conversation as awaiting user reply after AI response."""
        conversation_id = "conversation1"
        session_id = "session1"
        
        # Mark AI response sent
        self.state_manager.mark_ai_response_sent(conversation_id, session_id)
        
        # Verify session store was updated
        self.mock_session_store.mark_awaiting_user_reply.assert_called_once_with(conversation_id, session_id)
    
    def test_mark_user_reply_received(self):
        """Test marking a conversation as ready for response after user reply."""
        conversation_id = "conversation1"
        
        # Set up the mock to return success
        self.mock_session_store.mark_ready_for_response.return_value = True
        
        # Mark user reply received
        result = self.state_manager.mark_user_reply_received(conversation_id)
        
        # Verify result and session store was updated
        self.assertTrue(result)
        self.mock_session_store.mark_ready_for_response.assert_called_once_with(conversation_id)
    
    def test_get_conversation_state(self):
        """Test getting the current state of a conversation."""
        conversation_id = "conversation1"
        
        # Set up the mock to return a specific state
        self.mock_session_store.get_conversation_state.return_value = AWAITING_USER_REPLY
        
        # Get the conversation state
        state = self.state_manager.get_conversation_state(conversation_id)
        
        # Verify the result
        self.assertEqual(state, AWAITING_USER_REPLY)
        self.mock_session_store.get_conversation_state.assert_called_once_with(conversation_id)
    
    def test_full_conversation_flow(self):
        """Test a full conversation flow with state transitions."""
        conversation_id = "conversation1"
        session_id = "session1"
        
        # 1. Initially ready for response
        self.mock_session_store.is_awaiting_user_reply.return_value = False
        self.assertTrue(self.state_manager.can_send_ai_response(conversation_id))
        
        # 2. AI responds, mark as awaiting user reply
        self.state_manager.mark_ai_response_sent(conversation_id, session_id)
        self.mock_session_store.mark_awaiting_user_reply.assert_called_once_with(conversation_id, session_id)
        
        # 3. Now awaiting user reply, AI cannot respond
        self.mock_session_store.is_awaiting_user_reply.return_value = True
        self.assertFalse(self.state_manager.can_send_ai_response(conversation_id))
        
        # 4. User replies, mark as ready for response
        self.mock_session_store.mark_ready_for_response.return_value = True
        self.assertTrue(self.state_manager.mark_user_reply_received(conversation_id))
        self.mock_session_store.mark_ready_for_response.assert_called_once_with(conversation_id)
        
        # 5. Now ready for response again, AI can respond
        self.mock_session_store.is_awaiting_user_reply.return_value = False
        self.assertTrue(self.state_manager.can_send_ai_response(conversation_id))

if __name__ == "__main__":
    unittest.main() 
