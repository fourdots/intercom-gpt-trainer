#!/usr/bin/env python3
"""
Tests for the IntercomAPI class.
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import requests
import time

from services.intercom_api import IntercomAPI

class TestIntercomAPI(unittest.TestCase):
    """Tests for the IntercomAPI class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.access_token = "test_access_token_123"
        self.admin_id = "test_admin_456"
        
        # Create the API client
        self.api_client = IntercomAPI(
            access_token=self.access_token,
            admin_id=self.admin_id
        )
        
        # Create mock response for requests
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_response.headers = {
            'X-RateLimit-Remaining': '1000',
            'X-RateLimit-Reset': str(int(time.time()) + 3600)
        }
        
        # Sample conversation data
        self.sample_conversations = {
            "conversations": [
                {
                    "id": "conv123",
                    "updated_at": int(time.time()),
                    "user": {"id": "user123"},
                    "conversation_message": {
                        "id": "msg1",
                        "body": "<p>Hello</p>"
                    }
                },
                {
                    "id": "conv456",
                    "updated_at": int(time.time()),
                    "user": {"id": "user456"},
                    "conversation_message": {
                        "id": "msg2",
                        "body": "<p>Need help</p>"
                    }
                }
            ]
        }
        
        # Sample conversation data
        self.sample_conversation = {
            "id": "conv123",
            "updated_at": int(time.time()),
            "user": {"id": "user123"},
            "conversation_message": {
                "id": "msg1",
                "body": "<p>Hello</p>"
            },
            "conversation_parts": {
                "conversation_parts": [
                    {
                        "id": "part1",
                        "body": "<p>First reply</p>"
                    }
                ]
            }
        }
    
    def test_init(self):
        """Test initialization of IntercomAPI."""
        self.assertEqual(self.api_client.access_token, self.access_token)
        self.assertEqual(self.api_client.admin_id, self.admin_id)
        self.assertEqual(self.api_client.base_url, "https://api.intercom.io")
        self.assertEqual(self.api_client.headers["Authorization"], f"Bearer {self.access_token}")
        self.assertEqual(self.api_client.headers["Accept"], "application/json")
        self.assertEqual(self.api_client.headers["Content-Type"], "application/json")
    
    @patch('requests.get')
    def test_list_conversations_success(self, mock_get):
        """Test successful listing of conversations."""
        # Set up mock
        self.mock_response.json.return_value = self.sample_conversations
        mock_get.return_value = self.mock_response
        
        # Call the method
        conversations = self.api_client.list_conversations(
            per_page=25,
            state="open",
            sort="updated_at",
            order="desc"
        )
        
        # Verify behavior
        expected_url = f"{self.api_client.base_url}/conversations"
        expected_params = {
            "per_page": 25,
            "state": "open",
            "sort": "updated_at",
            "order": "desc"
        }
        
        mock_get.assert_called_once_with(
            expected_url, 
            headers=self.api_client.headers, 
            params=expected_params
        )
        
        # Check results
        self.assertEqual(len(conversations), 2)
        self.assertEqual(conversations[0]["id"], "conv123")
        self.assertEqual(conversations[1]["id"], "conv456")
    
    @patch('requests.get')
    def test_list_conversations_http_error(self, mock_get):
        """Test handling of HTTP error in list_conversations."""
        # Set up mock to return error
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = self.mock_response.headers
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Access Denied")
        mock_get.return_value = mock_response
        
        # Call the method and verify exception handling
        with self.assertRaises(requests.exceptions.HTTPError):
            self.api_client.list_conversations()
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_get.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.get')
    def test_list_conversations_connection_error(self, mock_get):
        """Test handling of connection error in list_conversations."""
        # Set up mock to raise exception
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        # Call the method and verify exception handling
        with self.assertRaises(Exception):
            self.api_client.list_conversations()
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_get.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.get')
    def test_get_conversation_success(self, mock_get):
        """Test successful retrieval of a conversation."""
        # Set up mock
        self.mock_response.json.return_value = self.sample_conversation
        mock_get.return_value = self.mock_response
        
        # Call the method
        conversation = self.api_client.get_conversation("conv123")
        
        # Verify behavior
        expected_url = f"{self.api_client.base_url}/conversations/conv123"
        
        mock_get.assert_called_once_with(
            expected_url, 
            headers=self.api_client.headers
        )
        
        # Check results
        self.assertEqual(conversation["id"], "conv123")
        self.assertEqual(conversation["conversation_message"]["id"], "msg1")
    
    @patch('requests.get')
    def test_get_conversation_http_error(self, mock_get):
        """Test handling of HTTP error in get_conversation."""
        # Set up mock to return error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = self.mock_response.headers
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_get.return_value = mock_response
        
        # Call the method and verify exception handling
        with self.assertRaises(requests.exceptions.HTTPError):
            self.api_client.get_conversation("non_existent_conv")
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_get.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.post')
    def test_reply_to_conversation_success(self, mock_post):
        """Test successful reply to a conversation."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = self.mock_response.headers
        mock_response.json.return_value = {"id": "reply1", "type": "admin"}
        mock_post.return_value = mock_response
        
        # Call the method
        conversation_id = "conv123"
        message = "This is a test reply."
        result = self.api_client.reply_to_conversation(conversation_id, message)
        
        # Verify behavior
        expected_url = f"{self.api_client.base_url}/conversations/{conversation_id}/reply"
        expected_payload = {
            "type": "admin",
            "admin_id": self.admin_id,
            "message_type": "comment",
            "body": "<p>This is a test reply.</p>"
        }
        
        mock_post.assert_called_once_with(
            expected_url, 
            headers=self.api_client.headers, 
            json=expected_payload
        )
        
        # Check results
        self.assertEqual(result["id"], "reply1")
        self.assertEqual(result["type"], "admin")
    
    @patch('requests.post')
    def test_reply_to_conversation_with_custom_admin(self, mock_post):
        """Test reply to conversation with custom admin ID."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = self.mock_response.headers
        mock_response.json.return_value = {"id": "reply1", "type": "admin"}
        mock_post.return_value = mock_response
        
        # Call the method
        conversation_id = "conv123"
        message = "This is a test reply."
        custom_admin_id = "custom_admin_789"
        result = self.api_client.reply_to_conversation(conversation_id, message, custom_admin_id)
        
        # Verify behavior
        expected_payload = {
            "type": "admin",
            "admin_id": custom_admin_id,  # Should use the custom admin ID
            "message_type": "comment",
            "body": "<p>This is a test reply.</p>"
        }
        
        mock_post.assert_called_once_with(
            mock_post.call_args[0][0],  # URL (doesn't matter for this test)
            headers=self.api_client.headers, 
            json=expected_payload
        )
    
    @patch('requests.post')
    def test_reply_to_conversation_http_error(self, mock_post):
        """Test handling of HTTP error in reply_to_conversation."""
        # Set up mock to return error
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = self.mock_response.headers
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Forbidden")
        mock_post.return_value = mock_response
        
        # Call the method and verify exception handling
        with self.assertRaises(requests.exceptions.HTTPError):
            self.api_client.reply_to_conversation("conv123", "Test message")
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_post.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.put')
    def test_mark_conversation_read_success(self, mock_put):
        """Test successfully marking a conversation as read."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = self.mock_response.headers
        mock_put.return_value = mock_response
        
        # Call the method
        conversation_id = "conv123"
        result = self.api_client.mark_conversation_read(conversation_id)
        
        # Verify behavior
        expected_url = f"{self.api_client.base_url}/conversations/{conversation_id}/read"
        
        mock_put.assert_called_once_with(
            expected_url, 
            headers=self.api_client.headers
        )
        
        # Check results
        self.assertTrue(result)
    
    @patch('requests.put')
    def test_mark_conversation_read_http_error(self, mock_put):
        """Test handling HTTP error in mark_conversation_read."""
        # Set up mock to return error
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.headers = self.mock_response.headers
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Not Found")
        mock_put.return_value = mock_response
        
        # Call the method
        result = self.api_client.mark_conversation_read("non_existent_conv")
        
        # Verify behavior - should return False on error
        self.assertFalse(result)
        mock_put.assert_called_once()
    
    @patch('time.sleep')
    def test_handle_rate_limits_near_limit(self, mock_sleep):
        """Test rate limit handling when near the limit."""
        # Create response with low remaining calls
        mock_response = MagicMock()
        mock_response.headers = {
            'X-RateLimit-Remaining': '5',  # Low remaining calls
            'X-RateLimit-Reset': str(int(time.time()) + 60)  # Reset in 60 seconds
        }
        
        # Call the method
        self.api_client._handle_rate_limits(mock_response)
        
        # Verify behavior - should sleep 
        mock_sleep.assert_called_once()
    
    def test_handle_rate_limits_not_near_limit(self):
        """Test rate limit handling when not near the limit."""
        # Create response with plenty of remaining calls
        mock_response = MagicMock()
        mock_response.headers = {
            'X-RateLimit-Remaining': '1000',  # Plenty of remaining calls
            'X-RateLimit-Reset': str(int(time.time()) + 3600)
        }
        
        # Call the method with time.sleep mocked to verify it's not called
        with patch('time.sleep') as mock_sleep:
            self.api_client._handle_rate_limits(mock_response)
            mock_sleep.assert_not_called()
    
    def test_handle_rate_limits_with_missing_headers(self):
        """Test rate limit handling with missing headers."""
        # Create response with missing rate limit headers
        mock_response = MagicMock()
        mock_response.headers = {}
        
        # Call the method with time.sleep mocked to verify it's not called
        with patch('time.sleep') as mock_sleep:
            # Should not raise an exception and should not sleep
            self.api_client._handle_rate_limits(mock_response)
            mock_sleep.assert_not_called()
    
    def test_handle_rate_limits_with_invalid_headers(self):
        """Test rate limit handling with invalid headers."""
        # Create response with invalid rate limit headers
        mock_response = MagicMock()
        mock_response.headers = {
            'X-RateLimit-Remaining': 'not-a-number',
            'X-RateLimit-Reset': 'not-a-timestamp'
        }
        
        # Call the method with time.sleep mocked
        with patch('time.sleep') as mock_sleep:
            # Should catch the exception and not sleep
            self.api_client._handle_rate_limits(mock_response)
            mock_sleep.assert_not_called()

if __name__ == "__main__":
    unittest.main() 
