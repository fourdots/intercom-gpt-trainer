#!/usr/bin/env python3
"""
Full integration test for the Intercom-GPT Trainer integration.
This test mocks external API calls to simulate the complete message flow.
"""

import unittest
from unittest.mock import MagicMock, patch
import os
import tempfile
import json
import time

from services.intercom_api import IntercomAPI
from services.gpt_trainer import GPTTrainerAPI
from services.conversation_processor import ConversationProcessor
from services.message_processor import MessageProcessor
from services.rate_limiter import RateLimiter
from services.conversation_state_manager import ConversationStateManager
from utils.session_store import SessionStore, AWAITING_USER_REPLY, READY_FOR_RESPONSE

class TestFullFlow(unittest.TestCase):
    """Test the full message flow from Intercom to GPT Trainer and back."""
    
    def setUp(self):
        """Set up mock objects and test data."""
        # Create temporary session store file
        self.sessions_file = tempfile.NamedTemporaryFile(delete=False, mode='w')
        self.sessions_file.write('{}')
        self.sessions_file.close()
        
        # Create temporary processed messages file
        self.messages_file = tempfile.NamedTemporaryFile(delete=False, mode='w')
        self.messages_file.write('[]')
        self.messages_file.close()
        
        # Mock Intercom API
        self.mock_intercom = MagicMock(spec=IntercomAPI)
        self.mock_intercom.admin_id = "admin123"
        
        # Mock GPT Trainer API
        self.mock_gpt_trainer = MagicMock(spec=GPTTrainerAPI)
        self.mock_gpt_trainer.create_session.return_value = "session123"
        self.mock_gpt_trainer.send_message.return_value = "I'm an AI assistant. How can I help you today?"
        
        # Create session store with file path
        self.session_store = SessionStore(storage_path=self.sessions_file.name)
        
        # Create message processor with file path
        self.message_processor = MessageProcessor(processed_messages_file=self.messages_file.name)
        
        # Create rate limiter
        self.rate_limiter = RateLimiter()
        
        # Create state manager
        self.state_manager = ConversationStateManager(self.session_store)
        
        # Create conversation processor
        self.processor = ConversationProcessor(
            self.mock_intercom,
            self.mock_gpt_trainer,
            self.session_store,
            self.message_processor,
            self.rate_limiter
        )
        
        # Test data: Conversation with user message
        self.test_conversation = {
            'id': 'conv123',
            'updated_at': int(time.time()),
            'conversation_message': {
                'id': 'msg1',
                'author': {'type': 'user', 'id': 'user123'},
                'body': '<p>Hello, I need help with my order.</p>',
                'created_at': int(time.time())
            }
        }
    
    def tearDown(self):
        """Clean up temporary files."""
        if os.path.exists(self.sessions_file.name):
            os.unlink(self.sessions_file.name)
        if os.path.exists(self.messages_file.name):
            os.unlink(self.messages_file.name)
    
    def test_initial_message_flow(self):
        """Test processing an initial user message."""
        # 1. Process the conversation
        self.processor.process_conversation(self.test_conversation, 0)
        
        # Verify the session was created
        self.mock_gpt_trainer.create_session.assert_called_once()
        
        # Verify the message was sent to GPT Trainer
        self.mock_gpt_trainer.send_message.assert_called_once()
        call_args = self.mock_gpt_trainer.send_message.call_args[0]
        self.assertIn("Hello, I need help with my order", call_args[0])
        self.assertEqual(call_args[1], "session123")
        
        # Verify the response was sent back to Intercom
        self.mock_intercom.reply_to_conversation.assert_called_once()
        call_args = self.mock_intercom.reply_to_conversation.call_args[0]
        self.assertEqual(call_args[0], 'conv123')
        self.assertEqual(call_args[1], "I'm an AI assistant. How can I help you today?")
        
        # Verify conversation state was updated to awaiting user reply
        self.assertEqual(
            self.session_store.get_conversation_state('conv123'), 
            AWAITING_USER_REPLY
        )
    
    def test_message_flow_with_state_changes(self):
        """Test the full message flow with state changes."""
        # Initial user message
        self.processor.process_conversation(self.test_conversation, 0)
        
        # Verify conversation is awaiting user reply
        self.assertEqual(
            self.session_store.get_conversation_state('conv123'), 
            AWAITING_USER_REPLY
        )
        
        # Reset the mocks
        self.mock_gpt_trainer.send_message.reset_mock()
        self.mock_intercom.reply_to_conversation.reset_mock()
        
        # Try to process again - should not send message since awaiting user reply
        self.processor.process_conversation(self.test_conversation, 0)
        
        # Verify no message was sent (we're awaiting user reply)
        self.mock_gpt_trainer.send_message.assert_not_called()
        self.mock_intercom.reply_to_conversation.assert_not_called()
        
        # Create a user reply
        self.test_conversation['conversation_parts'] = {
            'conversation_parts': [
                {
                    'id': 'part1',
                    'author': {'type': 'user', 'id': 'user123'},
                    'body': '<p>I ordered item #12345 but received the wrong size.</p>',
                    'created_at': int(time.time())
                }
            ]
        }
        
        # Mark the user reply received to change state
        self.state_manager.mark_user_reply_received('conv123')
        
        # Verify conversation is ready for response
        self.assertEqual(
            self.session_store.get_conversation_state('conv123'), 
            READY_FOR_RESPONSE
        )
        
        # Process again, now with user reply
        self.processor.process_conversation(self.test_conversation, 0)
        
        # Verify new message was sent to GPT Trainer
        self.mock_gpt_trainer.send_message.assert_called_once()
        call_args = self.mock_gpt_trainer.send_message.call_args[0]
        self.assertIn("wrong size", call_args[0])
        
        # Verify response was sent back to Intercom
        self.mock_intercom.reply_to_conversation.assert_called_once()
        
        # Verify conversation state is back to awaiting user reply
        self.assertEqual(
            self.session_store.get_conversation_state('conv123'), 
            AWAITING_USER_REPLY
        )
    
    def test_rate_limiting(self):
        """Test that rate limiting works in the full flow."""
        # Set a strict rate limit for testing
        self.rate_limiter.MAX_RESPONSES_PER_MINUTE = 1
        
        # Process first conversation
        self.processor.process_conversation(self.test_conversation, 0)
        
        # Verify message was sent
        self.mock_gpt_trainer.send_message.assert_called_once()
        self.mock_intercom.reply_to_conversation.assert_called_once()
        
        # Reset mocks
        self.mock_gpt_trainer.send_message.reset_mock()
        self.mock_intercom.reply_to_conversation.reset_mock()
        
        # Create a second conversation
        second_conversation = {
            'id': 'conv456',
            'updated_at': int(time.time()),
            'conversation_message': {
                'id': 'msg2',
                'author': {'type': 'user', 'id': 'user456'},
                'body': '<p>This is a different conversation.</p>',
                'created_at': int(time.time())
            }
        }
        
        # Process second conversation - should be blocked by rate limit
        self.processor.process_conversation(second_conversation, 0)
        
        # Verify no message was sent due to rate limiting
        self.mock_gpt_trainer.send_message.assert_not_called()
        self.mock_intercom.reply_to_conversation.assert_not_called()
    
    def test_skips_admin_messages(self):
        """Test that messages from admins are skipped."""
        # Create conversation with admin message
        admin_conversation = {
            'id': 'conv789',
            'updated_at': int(time.time()),
            'conversation_message': {
                'id': 'msg3',
                'author': {'type': 'admin', 'id': 'admin123'},
                'body': '<p>This is an admin message.</p>',
                'created_at': int(time.time())
            }
        }
        
        # Process conversation
        self.processor.process_conversation(admin_conversation, 0)
        
        # Verify no message was processed (since it's from admin)
        self.mock_gpt_trainer.send_message.assert_not_called()
        self.mock_intercom.reply_to_conversation.assert_not_called()
        
if __name__ == "__main__":
    unittest.main() 
