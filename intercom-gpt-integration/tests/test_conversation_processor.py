#!/usr/bin/env python3
"""
Tests for the ConversationProcessor class.
"""

import unittest
from unittest.mock import MagicMock, patch, call
import time
from datetime import datetime

from services.conversation_processor import ConversationProcessor
from services.intercom_api import IntercomAPI
from services.gpt_trainer import GPTTrainerAPI
from services.message_processor import MessageProcessor
from services.rate_limiter import RateLimiter
from utils.session_store import SessionStore, AWAITING_USER_REPLY, READY_FOR_RESPONSE

class TestConversationProcessor(unittest.TestCase):
    """Test the ConversationProcessor class."""
    
    def setUp(self):
        """Set up for tests."""
        # Create mock dependencies
        self.mock_intercom = MagicMock(spec=IntercomAPI)
        self.mock_gpt_trainer = MagicMock(spec=GPTTrainerAPI)
        self.mock_session_store = MagicMock(spec=SessionStore)
        self.mock_message_processor = MagicMock(spec=MessageProcessor)
        self.mock_rate_limiter = MagicMock(spec=RateLimiter)
        
        # Create processor instance
        self.processor = ConversationProcessor(
            self.mock_intercom,
            self.mock_gpt_trainer,
            self.mock_session_store,
            self.mock_message_processor,
            self.mock_rate_limiter
        )
        
        # Replace the state_manager with a mock
        self.mock_state_manager = MagicMock()
        self.processor.state_manager = self.mock_state_manager
        
        # Test data
        self.conversation_id = "test_conv_123"
        self.session_id = "test_session_456"
        self.last_processed_time = int(time.time()) - 3600  # 1 hour ago
        
        # Sample conversation with messages
        self.test_conversation = {
            'id': self.conversation_id,
            'updated_at': int(time.time()),
            'conversation_message': {
                'id': 'msg1',
                'author': {'type': 'user', 'id': 'user123'},
                'body': '<p>Hello, I need help with my order.</p>',
                'created_at': int(time.time())
            }
        }
        
        # Sample extracted messages
        self.extracted_messages = [
            {
                'id': 'msg1',
                'author_type': 'user',
                'text': 'Hello, I need help with my order.',
                'created_at': int(time.time())
            }
        ]
    
    def test_init(self):
        """Test initialization."""
        self.assertEqual(self.processor.intercom_api, self.mock_intercom)
        self.assertEqual(self.processor.gpt_trainer_api, self.mock_gpt_trainer)
        self.assertEqual(self.processor.session_store, self.mock_session_store)
        self.assertEqual(self.processor.message_processor, self.mock_message_processor)
        self.assertEqual(self.processor.rate_limiter, self.mock_rate_limiter)
        self.assertIsNotNone(self.processor.state_manager)
    
    def test_process_conversation_no_messages(self):
        """Test processing a conversation with no new messages."""
        # Set up mocks
        self.mock_message_processor.extract_messages.return_value = []
        
        # Process the conversation
        result = self.processor.process_conversation(self.test_conversation, self.last_processed_time)
        
        # Verify behavior
        self.mock_message_processor.extract_messages.assert_called_once_with(
            self.test_conversation, self.last_processed_time
        )
        self.assertTrue(result)
        
        # Verify no further processing occurred
        self.processor.state_manager.mark_user_reply_received.assert_not_called()
        self.processor.state_manager.can_send_ai_response.assert_not_called()
        self.mock_rate_limiter.check_rate_limits.assert_not_called()
        self.mock_gpt_trainer.create_session.assert_not_called()
        self.mock_gpt_trainer.send_message.assert_not_called()
        self.mock_intercom.reply_to_conversation.assert_not_called()
    
    def test_process_conversation_happy_path(self):
        """Test successful conversation processing."""
        # Set up mocks
        self.mock_message_processor.extract_messages.return_value = self.extracted_messages
        self.processor.state_manager.can_send_ai_response = MagicMock(return_value=True)
        self.mock_rate_limiter.check_rate_limits.return_value = True
        self.mock_session_store.get_session.return_value = self.session_id
        self.mock_gpt_trainer.send_message.return_value = "I'll help you with your order."
        self.mock_intercom.reply_to_conversation.return_value = {'id': 'reply1'}
        
        # Process the conversation
        result = self.processor.process_conversation(self.test_conversation, self.last_processed_time)
        
        # Verify behavior
        self.mock_message_processor.extract_messages.assert_called_once()
        self.processor.state_manager.mark_user_reply_received.assert_called_once_with(self.conversation_id)
        self.processor.state_manager.can_send_ai_response.assert_called_once_with(self.conversation_id)
        self.mock_rate_limiter.check_rate_limits.assert_called_once_with(self.conversation_id)
        self.mock_session_store.get_session.assert_called_once_with(self.conversation_id)
        
        # Verify message was sent to GPT Trainer with prefix
        self.mock_gpt_trainer.send_message.assert_called_once()
        call_args = self.mock_gpt_trainer.send_message.call_args[0]
        self.assertIn(f"[Intercom Conversation {self.conversation_id}]", call_args[0])
        self.assertEqual(call_args[1], self.session_id)
        
        # Verify response was sent back to Intercom
        self.mock_intercom.reply_to_conversation.assert_called_once_with(
            self.conversation_id, "I'll help you with your order."
        )
        
        # Verify state was updated and rate counter incremented
        self.mock_rate_limiter.increment_rate_counter.assert_called_once_with(self.conversation_id)
        self.processor.state_manager.mark_ai_response_sent.assert_called_once_with(
            self.conversation_id, self.session_id
        )
        
        # Verify success
        self.assertTrue(result)
    
    def test_process_conversation_awaiting_user_reply(self):
        """Test processing a conversation that is awaiting user reply."""
        # Set up mocks
        self.mock_message_processor.extract_messages.return_value = self.extracted_messages
        self.processor.state_manager.can_send_ai_response = MagicMock(return_value=False)
        
        # Process the conversation
        result = self.processor.process_conversation(self.test_conversation, self.last_processed_time)
        
        # Verify behavior
        self.processor.state_manager.mark_user_reply_received.assert_called_once()
        self.processor.state_manager.can_send_ai_response.assert_called_once()
        
        # Verify no further processing occurred
        self.mock_rate_limiter.check_rate_limits.assert_not_called()
        self.mock_session_store.get_session.assert_not_called()
        self.mock_gpt_trainer.send_message.assert_not_called()
        self.mock_intercom.reply_to_conversation.assert_not_called()
        
        # Verify success
        self.assertTrue(result)
    
    def test_process_conversation_rate_limited(self):
        """Test processing a conversation that is rate limited."""
        # Set up mocks
        self.mock_message_processor.extract_messages.return_value = self.extracted_messages
        self.processor.state_manager.can_send_ai_response = MagicMock(return_value=True)
        self.mock_rate_limiter.check_rate_limits.return_value = False  # Rate limited
        
        # Process the conversation
        result = self.processor.process_conversation(self.test_conversation, self.last_processed_time)
        
        # Verify behavior
        self.processor.state_manager.mark_user_reply_received.assert_called_once()
        self.processor.state_manager.can_send_ai_response.assert_called_once()
        self.mock_rate_limiter.check_rate_limits.assert_called_once()
        
        # Verify no further processing occurred
        self.mock_session_store.get_session.assert_not_called()
        self.mock_gpt_trainer.send_message.assert_not_called()
        self.mock_intercom.reply_to_conversation.assert_not_called()
        
        # Verify failure due to rate limiting
        self.assertFalse(result)
    
    def test_process_conversation_no_ai_response(self):
        """Test processing a conversation where GPT Trainer returns no response."""
        # Set up mocks
        self.mock_message_processor.extract_messages.return_value = self.extracted_messages
        self.processor.state_manager.can_send_ai_response = MagicMock(return_value=True)
        self.mock_rate_limiter.check_rate_limits.return_value = True
        self.mock_session_store.get_session.return_value = self.session_id
        self.mock_gpt_trainer.send_message.return_value = None  # No response
        
        # Process the conversation
        result = self.processor.process_conversation(self.test_conversation, self.last_processed_time)
        
        # Verify behavior
        self.mock_gpt_trainer.send_message.assert_called_once()
        
        # Verify no further processing occurred
        self.mock_intercom.reply_to_conversation.assert_not_called()
        self.mock_rate_limiter.increment_rate_counter.assert_not_called()
        self.processor.state_manager.mark_ai_response_sent.assert_not_called()
        
        # Verify success (function shouldn't fail even if no response)
        self.assertTrue(result)
    
    def test_process_conversation_intercom_reply_failure(self):
        """Test processing a conversation where sending the reply to Intercom fails."""
        # Set up mocks
        self.mock_message_processor.extract_messages.return_value = self.extracted_messages
        self.processor.state_manager.can_send_ai_response = MagicMock(return_value=True)
        self.mock_rate_limiter.check_rate_limits.return_value = True
        self.mock_session_store.get_session.return_value = self.session_id
        self.mock_gpt_trainer.send_message.return_value = "I'll help you with your order."
        self.mock_intercom.reply_to_conversation.return_value = None  # Failed to send
        
        # Process the conversation
        result = self.processor.process_conversation(self.test_conversation, self.last_processed_time)
        
        # Verify behavior
        self.mock_intercom.reply_to_conversation.assert_called_once()
        
        # Verify no state or rate counter updates
        self.mock_rate_limiter.increment_rate_counter.assert_not_called()
        self.processor.state_manager.mark_ai_response_sent.assert_not_called()
        
        # Verify success (function shouldn't fail even if sending reply fails)
        self.assertTrue(result)
    
    def test_process_conversation_error(self):
        """Test error handling in process_conversation."""
        # Set up mock to raise an exception
        self.mock_message_processor.extract_messages.side_effect = Exception("Test error")
        
        # Process the conversation
        result = self.processor.process_conversation(self.test_conversation, self.last_processed_time)
        
        # Verify failure
        self.assertFalse(result)
    
    def test_get_or_create_session_existing(self):
        """Test getting an existing session."""
        # Set up mock to return an existing session
        self.mock_session_store.get_session.return_value = self.session_id
        
        # Get the session
        session_id = self.processor._get_or_create_session(self.conversation_id)
        
        # Verify behavior
        self.mock_session_store.get_session.assert_called_once_with(self.conversation_id)
        self.mock_gpt_trainer.create_session.assert_not_called()
        self.assertEqual(session_id, self.session_id)
    
    def test_get_or_create_session_new(self):
        """Test creating a new session."""
        # Set up mocks
        self.mock_session_store.get_session.return_value = None  # No existing session
        self.mock_gpt_trainer.create_session.return_value = self.session_id
        
        # Get or create the session
        session_id = self.processor._get_or_create_session(self.conversation_id)
        
        # Verify behavior
        self.mock_session_store.get_session.assert_called_once()
        self.mock_gpt_trainer.create_session.assert_called_once()
        self.mock_session_store.save_session.assert_called_once_with(
            self.conversation_id, self.session_id
        )
        self.assertEqual(session_id, self.session_id)
    
    def test_get_or_create_session_failure(self):
        """Test failure to create a new session."""
        # Set up mocks
        self.mock_session_store.get_session.return_value = None  # No existing session
        self.mock_gpt_trainer.create_session.return_value = None  # Failed to create
        
        # Get or create the session
        session_id = self.processor._get_or_create_session(self.conversation_id)
        
        # Verify behavior
        self.mock_gpt_trainer.create_session.assert_called_once()
        self.mock_session_store.save_session.assert_not_called()
        self.assertIsNone(session_id)
    
    def test_get_or_create_session_error(self):
        """Test error handling in _get_or_create_session."""
        # Set up mocks
        self.mock_session_store.get_session.return_value = None
        self.mock_gpt_trainer.create_session.side_effect = Exception("Test error")
        
        # Get or create the session
        session_id = self.processor._get_or_create_session(self.conversation_id)
        
        # Verify failure
        self.assertIsNone(session_id)
    
    def test_recreate_session_success(self):
        """Test successfully recreating a session."""
        # Set up mocks
        self.mock_gpt_trainer.create_session.return_value = "new_session_id"
        
        # Recreate the session
        session_id = self.processor._recreate_session(self.conversation_id)
        
        # Verify behavior
        self.mock_session_store.remove_session.assert_called_once_with(self.conversation_id)
        self.mock_gpt_trainer.create_session.assert_called_once()
        self.mock_session_store.save_session.assert_called_once_with(
            self.conversation_id, "new_session_id"
        )
        self.assertEqual(session_id, "new_session_id")
    
    def test_recreate_session_failure(self):
        """Test failure to recreate a session."""
        # Set up mocks
        self.mock_gpt_trainer.create_session.return_value = None  # Failed to create
        
        # Recreate the session
        session_id = self.processor._recreate_session(self.conversation_id)
        
        # Verify behavior
        self.mock_session_store.remove_session.assert_called_once()
        self.mock_gpt_trainer.create_session.assert_called_once()
        self.mock_session_store.save_session.assert_not_called()
        self.assertIsNone(session_id)
    
    def test_recreate_session_error(self):
        """Test error handling in _recreate_session."""
        # Set up mocks
        self.mock_gpt_trainer.create_session.side_effect = Exception("Test error")
        
        # Recreate the session
        session_id = self.processor._recreate_session(self.conversation_id)
        
        # Verify failure
        self.assertIsNone(session_id)
    
    def test_verify_active_sessions_no_sessions(self):
        """Test verifying active sessions when none exist."""
        # Set up mocks
        self.mock_session_store.get_all_sessions.return_value = {}
        
        # Verify sessions
        result = self.processor.verify_active_sessions()
        
        # Verify behavior
        self.mock_session_store.get_all_sessions.assert_called_once()
        self.mock_gpt_trainer.send_message.assert_not_called()
        self.assertTrue(result)
    
    def test_verify_active_sessions_success(self):
        """Test successful verification of active sessions."""
        # Set up mocks
        self.mock_session_store.get_all_sessions.return_value = {
            self.conversation_id: self.session_id
        }
        self.mock_gpt_trainer.send_message.return_value = "Test response"
        
        # Verify sessions
        result = self.processor.verify_active_sessions()
        
        # Verify behavior
        self.mock_session_store.get_all_sessions.assert_called_once()
        self.mock_gpt_trainer.send_message.assert_called_once()
        self.assertIn("TEST_SESSION_VERIFY_", self.mock_gpt_trainer.send_message.call_args[0][0])
        self.assertEqual(self.mock_gpt_trainer.send_message.call_args[0][1], self.session_id)
        self.assertTrue(result)
    
    def test_verify_active_sessions_failed_response(self):
        """Test verification of active sessions with failed response."""
        # Set up mocks
        self.mock_session_store.get_all_sessions.return_value = {
            self.conversation_id: self.session_id
        }
        self.mock_gpt_trainer.send_message.return_value = None  # Failed response
        
        # Mock the _recreate_session method
        self.processor._recreate_session = MagicMock(return_value="new_session_id")
        
        # Verify sessions
        result = self.processor.verify_active_sessions()
        
        # Verify behavior
        self.mock_gpt_trainer.send_message.assert_called_once()
        self.processor._recreate_session.assert_called_once_with(self.conversation_id)
        self.assertFalse(result)
    
    def test_verify_active_sessions_error(self):
        """Test error handling in verify_active_sessions."""
        # Set up mocks
        self.mock_session_store.get_all_sessions.side_effect = Exception("Test error")
        
        # Verify sessions
        result = self.processor.verify_active_sessions()
        
        # Verify failure
        self.assertFalse(result)
    
    def test_save_processed_messages(self):
        """Test saving processed messages."""
        # Call the method
        self.processor.save_processed_messages()
        
        # Verify behavior
        self.mock_message_processor.save_processed_messages.assert_called_once()

if __name__ == "__main__":
    unittest.main() 
