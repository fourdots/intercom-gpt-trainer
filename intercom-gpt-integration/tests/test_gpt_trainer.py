#!/usr/bin/env python3
"""
Tests for the GPTTrainerAPI class.
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import requests
from requests.exceptions import RequestException

from services.gpt_trainer import GPTTrainerAPI

class TestGPTTrainerAPI(unittest.TestCase):
    """Tests for the GPTTrainerAPI class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.api_key = "test_api_key_123"
        self.chatbot_uuid = "test_bot_uuid_456"
        self.api_url = "https://test.gpt-trainer.com/api/v1"
        
        # Create the API client
        self.api_client = GPTTrainerAPI(
            api_key=self.api_key,
            chatbot_uuid=self.chatbot_uuid,
            api_url=self.api_url
        )
        
        # Create mock response for requests
        self.mock_response = MagicMock()
        self.mock_response.status_code = 200
        self.mock_response.json.return_value = {"session_id": "test_session_789"}
        self.mock_response.text = json.dumps({"session_id": "test_session_789"})
        
    @patch('requests.post')
    def test_create_session_success(self, mock_post):
        """Test successful session creation."""
        # Set up mock
        mock_post.return_value = self.mock_response
        
        # Call the method
        session_id = self.api_client.create_session()
        
        # Verify behavior
        expected_url = f"{self.api_url}/chatbot/{self.chatbot_uuid}/session/create"
        expected_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        mock_post.assert_called_once_with(expected_url, headers=expected_headers)
        self.assertEqual(session_id, "test_session_789")
    
    @patch('requests.post')
    def test_create_session_with_uuid_response(self, mock_post):
        """Test session creation when API returns 'uuid' instead of 'session_id'."""
        # Set up mock with different response format
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"uuid": "test_uuid_789"}
        mock_post.return_value = mock_response
        
        # Call the method
        session_id = self.api_client.create_session()
        
        # Verify behavior
        mock_post.assert_called_once()
        self.assertEqual(session_id, "test_uuid_789")
    
    @patch('requests.post')
    def test_create_session_http_error(self, mock_post):
        """Test handling of HTTP error in session creation."""
        # Set up mock to return error
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": "Access denied"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Access Denied")
        mock_post.return_value = mock_response
        
        # Call the method and verify exception handling
        with self.assertRaises(requests.exceptions.HTTPError):
            self.api_client.create_session()
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_post.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.post')
    def test_create_session_connection_error(self, mock_post):
        """Test handling of connection error in session creation."""
        # Set up mock to raise exception
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        # Call the method and verify exception handling
        with self.assertRaises(requests.exceptions.RequestException):
            self.api_client.create_session()
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_post.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.post')
    def test_create_session_json_error(self, mock_post):
        """Test handling of invalid JSON response."""
        # Set up mock with invalid JSON
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "Not valid JSON"
        mock_post.return_value = mock_response
        
        # Call the method and verify exception handling
        with self.assertRaises(ValueError):
            self.api_client.create_session()
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_post.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.post')
    def test_create_session_missing_id(self, mock_post):
        """Test handling of response without session ID."""
        # Set up mock with no session ID
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": {}}
        mock_post.return_value = mock_response
        
        # Call the method and verify exception handling
        with self.assertRaises(ValueError):
            self.api_client.create_session()
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_post.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.post')
    def test_send_message_success(self, mock_post):
        """Test successful message sending."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "This is an AI response."}
        mock_post.return_value = mock_response
        
        # Call the method
        session_id = "test_session_789"
        message = "Hello, this is a test message."
        response = self.api_client.send_message(message, session_id)
        
        # Verify behavior
        expected_url = f"{self.api_url}/session/{session_id}/message/stream"
        expected_payload = {
            "query": message,
            "stream": False
        }
        expected_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        mock_post.assert_called_once_with(
            expected_url, 
            headers=expected_headers, 
            json=expected_payload
        )
        self.assertEqual(response, "This is an AI response.")
    
    @patch('requests.post')
    def test_send_message_with_conversation_id(self, mock_post):
        """Test sending message with conversation ID."""
        # Set up mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "This is an AI response."}
        mock_post.return_value = mock_response
        
        # Call the method
        session_id = "test_session_789"
        message = "Hello, this is a test message."
        conversation_id = "intercom_conv_123"
        response = self.api_client.send_message(message, session_id, conversation_id)
        
        # Verify behavior
        expected_url = f"{self.api_url}/session/{session_id}/message/stream"
        expected_payload = {
            "query": message,
            "stream": False,
            "conversation_id": "intercom_conv_123"
        }
        
        mock_post.assert_called_once_with(
            expected_url, 
            headers=self.api_client.headers, 
            json=expected_payload
        )
        self.assertEqual(response, "This is an AI response.")
    
    @patch('requests.post')
    def test_send_message_with_alternative_response_fields(self, mock_post):
        """Test sending message with different response field names."""
        # Test with 'text' field
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "This is the text response."}
        mock_post.return_value = mock_response
        
        response = self.api_client.send_message("Hello", "session_id")
        self.assertEqual(response, "This is the text response.")
        
        # Test with 'message' field
        mock_response.json.return_value = {"message": "This is the message response."}
        response = self.api_client.send_message("Hello", "session_id")
        self.assertEqual(response, "This is the message response.")
        
        # Test with 'answer' field
        mock_response.json.return_value = {"answer": "This is the answer response."}
        response = self.api_client.send_message("Hello", "session_id")
        self.assertEqual(response, "This is the answer response.")
        
        # Test with 'content' field
        mock_response.json.return_value = {"content": "This is the content response."}
        response = self.api_client.send_message("Hello", "session_id")
        self.assertEqual(response, "This is the content response.")
    
    @patch('requests.post')
    def test_send_message_raw_text_response(self, mock_post):
        """Test sending message with non-JSON response."""
        # Set up mock with non-JSON response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.text = "This is a plain text response."
        mock_post.return_value = mock_response
        
        # Call the method
        response = self.api_client.send_message("Hello", "session_id")
        
        # Verify behavior
        self.assertEqual(response, "This is a plain text response.")
    
    @patch('requests.post')
    def test_send_message_http_error(self, mock_post):
        """Test handling of HTTP error in send_message."""
        # Set up mock to return error
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.json.return_value = {"error": "Access denied"}
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Access Denied")
        mock_post.return_value = mock_response
        
        # Call the method and verify exception handling
        with self.assertRaises(requests.exceptions.HTTPError):
            self.api_client.send_message("Hello", "session_id")
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_post.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.post')
    def test_send_message_connection_error(self, mock_post):
        """Test handling of connection error in send_message."""
        # Set up mock to raise exception
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        # Call the method and verify exception handling
        with self.assertRaises(requests.exceptions.RequestException):
            self.api_client.send_message("Hello", "session_id")
        
        # Verify behavior - changed to assert_called instead of assert_called_once
        mock_post.assert_called()  # The retry mechanism will call it multiple times
    
    @patch('requests.post')
    def test_send_message_with_no_matching_response_field(self, mock_post):
        """Test sending message with response that has no expected fields."""
        # Set up mock with response that doesn't have expected fields
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success"}
        mock_post.return_value = mock_response
        
        # Call the method
        response = self.api_client.send_message("Hello", "session_id")
        
        # Looking at the implementation, it seems to default to the first string field
        self.assertEqual(response, "success")

if __name__ == "__main__":
    unittest.main() 
