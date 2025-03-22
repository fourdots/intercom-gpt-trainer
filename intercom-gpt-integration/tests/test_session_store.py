#!/usr/bin/env python3
"""
Tests for the SessionStore class.
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open
import json
import os
import tempfile
from datetime import datetime, timedelta

from utils.session_store import SessionStore, AWAITING_USER_REPLY, READY_FOR_RESPONSE

class TestSessionStore(unittest.TestCase):
    """Test the SessionStore class."""
    
    def setUp(self):
        """Set up for tests."""
        # Create a temporary file for session storage
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w')
        self.temp_file.write('{}')
        self.temp_file.close()
        
        # Create a session store with the temporary file
        self.session_store = SessionStore(storage_path=self.temp_file.name)
        
        # Test data
        self.conversation_id = "test_conversation_123"
        self.session_id = "test_session_456"
    
    def tearDown(self):
        """Clean up after tests."""
        if os.path.exists(self.temp_file.name):
            os.unlink(self.temp_file.name)
    
    def test_init_default_values(self):
        """Test initialization with default values."""
        store = SessionStore()
        self.assertEqual(store.storage_path, "sessions.json")
        self.assertEqual(store.expiry_hours, 24)
    
    def test_init_custom_values(self):
        """Test initialization with custom values."""
        store = SessionStore(storage_path="custom_path.json", expiry_hours=48)
        self.assertEqual(store.storage_path, "custom_path.json")
        self.assertEqual(store.expiry_hours, 48)
    
    def test_save_and_get_session(self):
        """Test saving and retrieving a session."""
        # Save a session
        self.session_store.save_session(self.conversation_id, self.session_id)
        
        # Get the session
        retrieved_session_id = self.session_store.get_session(self.conversation_id)
        
        # Verify
        self.assertEqual(retrieved_session_id, self.session_id)
    
    def test_remove_session(self):
        """Test removing a session."""
        # Save a session
        self.session_store.save_session(self.conversation_id, self.session_id)
        
        # Remove the session
        result = self.session_store.remove_session(self.conversation_id)
        
        # Verify
        self.assertTrue(result)
        self.assertIsNone(self.session_store.get_session(self.conversation_id))
    
    def test_remove_nonexistent_session(self):
        """Test removing a session that doesn't exist."""
        # Try to remove a session that doesn't exist
        result = self.session_store.remove_session("nonexistent_conversation")
        
        # Verify
        self.assertFalse(result)
    
    def test_get_all_sessions(self):
        """Test getting all sessions."""
        # Save a few sessions
        self.session_store.save_session(self.conversation_id, self.session_id)
        self.session_store.save_session("conv2", "session2")
        self.session_store.save_session("conv3", "session3")
        
        # Get all sessions
        all_sessions = self.session_store.get_all_sessions()
        
        # Verify
        self.assertEqual(len(all_sessions), 3)
        self.assertEqual(all_sessions[self.conversation_id], self.session_id)
        self.assertEqual(all_sessions["conv2"], "session2")
        self.assertEqual(all_sessions["conv3"], "session3")
    
    def test_conversation_state_management(self):
        """Test conversation state management functions."""
        # Save a session with default state (READY_FOR_RESPONSE)
        self.session_store.save_session(self.conversation_id, self.session_id)
        
        # Check initial state
        self.assertEqual(
            self.session_store.get_conversation_state(self.conversation_id),
            READY_FOR_RESPONSE
        )
        self.assertFalse(self.session_store.is_awaiting_user_reply(self.conversation_id))
        
        # Mark as awaiting user reply
        self.session_store.mark_awaiting_user_reply(self.conversation_id, self.session_id)
        
        # Check state after marking
        self.assertEqual(
            self.session_store.get_conversation_state(self.conversation_id),
            AWAITING_USER_REPLY
        )
        self.assertTrue(self.session_store.is_awaiting_user_reply(self.conversation_id))
        
        # Mark as ready for response
        result = self.session_store.mark_ready_for_response(self.conversation_id)
        
        # Check state after marking
        self.assertTrue(result)
        self.assertEqual(
            self.session_store.get_conversation_state(self.conversation_id),
            READY_FOR_RESPONSE
        )
        self.assertFalse(self.session_store.is_awaiting_user_reply(self.conversation_id))
    
    def test_mark_ready_nonexistent_session(self):
        """Test marking a nonexistent session as ready."""
        # Try to mark a nonexistent session as ready
        result = self.session_store.mark_ready_for_response("nonexistent_conversation")
        
        # Verify
        self.assertFalse(result)
    
    def test_save_session_with_state(self):
        """Test saving a session with a specific state."""
        # Save a session with AWAITING_USER_REPLY state
        self.session_store.save_session(
            self.conversation_id, 
            self.session_id, 
            state=AWAITING_USER_REPLY
        )
        
        # Check state
        self.assertEqual(
            self.session_store.get_conversation_state(self.conversation_id),
            AWAITING_USER_REPLY
        )
    
    def test_get_state_nonexistent_session(self):
        """Test getting state for a nonexistent session."""
        # Get state for a nonexistent session
        state = self.session_store.get_conversation_state("nonexistent_conversation")
        
        # Verify default state is returned
        self.assertEqual(state, READY_FOR_RESPONSE)
    
    def test_session_expiry(self):
        """Test session expiry functionality."""
        # Create a session store with a tiny expiry time for testing
        expiry_hours = 1/3600  # 1 second in hours
        store = SessionStore(
            storage_path=self.temp_file.name,
            expiry_hours=expiry_hours
        )
        
        # Save a session
        store.save_session(self.conversation_id, self.session_id)
        
        # Verify it exists
        self.assertEqual(store.get_session(self.conversation_id), self.session_id)
        
        # Manually set the expiry to the past
        store.sessions[self.conversation_id]['expiry'] = (
            datetime.now() - timedelta(hours=1)
        ).isoformat()
        
        # Get the session again - should trigger cleanup
        retrieved_session = store.get_session(self.conversation_id)
        
        # Verify it's gone
        self.assertIsNone(retrieved_session)
    
    def test_cleanup_expired(self):
        """Test explicit cleanup of expired sessions."""
        # Save a session
        self.session_store.save_session(self.conversation_id, self.session_id)
        
        # Manually set the expiry to the past
        self.session_store.sessions[self.conversation_id]['expiry'] = (
            datetime.now() - timedelta(hours=1)
        ).isoformat()
        
        # Call cleanup
        self.session_store._cleanup_expired()
        
        # Verify the session is gone
        self.assertIsNone(self.session_store.get_session(self.conversation_id))
    
    @patch('utils.persistence.PersistenceManager.load_json_data')
    def test_load_sessions(self, mock_load):
        """Test loading sessions from storage."""
        # Set up mock
        mock_load.return_value = {
            "conv1": {
                "session_id": "session1",
                "created": datetime.now().isoformat(),
                "expiry": (datetime.now() + timedelta(hours=24)).isoformat()
            }
        }
        
        # Create a session store to trigger _load_sessions
        store = SessionStore()
        
        # Verify the mock was called
        mock_load.assert_called_once()
        
        # Verify the session was loaded with default state
        self.assertEqual(store.sessions["conv1"]["state"], READY_FOR_RESPONSE)
    
    @patch('utils.persistence.PersistenceManager.save_json_data')
    def test_save_sessions(self, mock_save):
        """Test saving sessions to storage."""
        # Save a session to trigger _save_sessions
        self.session_store.save_session(self.conversation_id, self.session_id)
        
        # Verify the mock was called
        mock_save.assert_called_with(self.session_store.storage_path, self.session_store.sessions)

if __name__ == "__main__":
    unittest.main() 
