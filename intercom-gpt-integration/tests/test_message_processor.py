#!/usr/bin/env python3
"""
Tests for the MessageProcessor class.
"""

import unittest
import os
import tempfile
import json
from services.message_processor import MessageProcessor

class TestMessageProcessor(unittest.TestCase):
    """Test cases for the MessageProcessor class."""
    
    def setUp(self):
        """Set up a fresh MessageProcessor instance for each test."""
        # Create a temporary file for processed messages
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w')
        json.dump([], self.temp_file)
        self.temp_file.close()
        
        self.message_processor = MessageProcessor(processed_messages_file=self.temp_file.name)
    
    def tearDown(self):
        """Clean up temporary files after each test."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_clean_message_body(self):
        """Test cleaning HTML from message bodies."""
        # Test with HTML
        html_body = "<p>This is a test</p>"
        self.assertEqual(self.message_processor.clean_message_body(html_body), "This is a test")
        
        # Test with multiple HTML tags
        html_body = "<p>This is</p><p>a test</p>"
        self.assertEqual(self.message_processor.clean_message_body(html_body), "This is a test")
        
        # Test with None
        self.assertEqual(self.message_processor.clean_message_body(None), "")
        
        # Test with empty string
        self.assertEqual(self.message_processor.clean_message_body(""), "")
    
    def test_extract_messages_empty_conversation(self):
        """Test extracting messages from an empty conversation."""
        empty_conversation = {}
        messages = self.message_processor.extract_messages(empty_conversation)
        self.assertEqual(len(messages), 0)
    
    def test_extract_messages_initial_message(self):
        """Test extracting the initial message from a conversation."""
        conversation = {
            'conversation_message': {
                'id': 'msg1',
                'author': {'type': 'user'},
                'body': '<p>Hello</p>',
                'created_at': 1234567890
            },
            'created_at': 1234567890
        }
        
        messages = self.message_processor.extract_messages(conversation)
        
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['id'], 'msg1')
        self.assertEqual(messages[0]['author_type'], 'user')
        self.assertEqual(messages[0]['text'], 'Hello')
        self.assertEqual(messages[0]['timestamp'], 1234567890)
    
    def test_extract_messages_conversation_parts(self):
        """Test extracting messages from conversation parts."""
        conversation = {
            'conversation_message': {
                'id': 'msg1',
                'author': {'type': 'user'},
                'body': '<p>Hello</p>',
                'created_at': 1234567890
            },
            'created_at': 1234567890,
            'conversation_parts': {
                'conversation_parts': [
                    {
                        'id': 'part1',
                        'author': {'type': 'user'},
                        'body': '<p>How are you?</p>',
                        'created_at': 1234567891
                    },
                    {
                        'id': 'part2',
                        'author': {'type': 'admin'},
                        'body': "<p>I'm fine, thanks!</p>",
                        'created_at': 1234567892
                    }
                ]
            }
        }
        
        messages = self.message_processor.extract_messages(conversation)
        
        # Should only contain user messages, not admin messages
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]['id'], 'msg1')
        self.assertEqual(messages[0]['text'], 'Hello')
        self.assertEqual(messages[1]['id'], 'part1')
        self.assertEqual(messages[1]['text'], 'How are you?')
    
    def test_skip_processed_messages(self):
        """Test that already processed messages are skipped."""
        # Add a message ID to the set of processed messages
        self.message_processor.add_processed_message_id('msg1')
        
        conversation = {
            'conversation_message': {
                'id': 'msg1',  # This should be skipped
                'author': {'type': 'user'},
                'body': '<p>Hello</p>',
                'created_at': 1234567890
            },
            'created_at': 1234567890,
            'conversation_parts': {
                'conversation_parts': [
                    {
                        'id': 'part1',  # This should be processed
                        'author': {'type': 'user'},
                        'body': '<p>How are you?</p>',
                        'created_at': 1234567891
                    }
                ]
            }
        }
        
        messages = self.message_processor.extract_messages(conversation)
        
        # Should only contain the unprocessed message
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['id'], 'part1')
        self.assertEqual(messages[0]['text'], 'How are you?')
    
    def test_save_processed_messages(self):
        """Test saving and loading processed message IDs."""
        # Add some message IDs
        self.message_processor.add_processed_message_id('msg1')
        self.message_processor.add_processed_message_id('msg2')
        
        # Save them
        self.message_processor.save_processed_messages()
        
        # Create a new processor that should load these IDs
        new_processor = MessageProcessor(processed_messages_file=self.temp_file.name)
        
        # Verify the IDs were loaded
        self.assertIn('msg1', new_processor.get_processed_message_ids())
        self.assertIn('msg2', new_processor.get_processed_message_ids())
    
    def test_messages_sorted_by_timestamp(self):
        """Test that extracted messages are sorted by timestamp."""
        conversation = {
            'conversation_message': {
                'id': 'msg1',
                'author': {'type': 'user'},
                'body': '<p>First message</p>',
                'created_at': 1000  # Earlier timestamp
            },
            'created_at': 1000,
            'conversation_parts': {
                'conversation_parts': [
                    {
                        'id': 'part2',
                        'author': {'type': 'user'},
                        'body': '<p>Third message</p>',
                        'created_at': 3000  # Latest timestamp
                    },
                    {
                        'id': 'part1',
                        'author': {'type': 'user'},
                        'body': '<p>Second message</p>',
                        'created_at': 2000  # Middle timestamp
                    }
                ]
            }
        }
        
        messages = self.message_processor.extract_messages(conversation)
        
        # Should be sorted by timestamp
        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[0]['text'], 'First message')
        self.assertEqual(messages[1]['text'], 'Second message')
        self.assertEqual(messages[2]['text'], 'Third message')

if __name__ == "__main__":
    unittest.main() 
