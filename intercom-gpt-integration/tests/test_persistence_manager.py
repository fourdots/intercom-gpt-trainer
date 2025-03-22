#!/usr/bin/env python3
"""
Tests for the PersistenceManager class.
"""

import unittest
import os
import tempfile
import json
import shutil
from utils.persistence import PersistenceManager

class TestPersistenceManager(unittest.TestCase):
    """Test cases for the PersistenceManager class."""
    
    def setUp(self):
        """Set up temporary files and directories for testing."""
        # Create a temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, 'test_data.json')
    
    def tearDown(self):
        """Clean up temporary files and directories after testing."""
        shutil.rmtree(self.temp_dir)
    
    def test_load_json_data_file_not_exists(self):
        """Test loading data when the file doesn't exist."""
        data = PersistenceManager.load_json_data(self.test_file)
        self.assertEqual(data, {})
        
        # Test with custom default
        custom_default = {'test': 'value'}
        data = PersistenceManager.load_json_data(self.test_file, default=custom_default)
        self.assertEqual(data, custom_default)
    
    def test_save_and_load_json_data(self):
        """Test saving and loading JSON data."""
        test_data = {'key1': 'value1', 'key2': 42, 'key3': [1, 2, 3]}
        
        # Save the data
        result = PersistenceManager.save_json_data(self.test_file, test_data)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(self.test_file))
        
        # Load the data
        loaded_data = PersistenceManager.load_json_data(self.test_file)
        self.assertEqual(loaded_data, test_data)
    
    def test_save_json_data_invalid_dir(self):
        """Test saving data to an invalid directory."""
        invalid_file = '/nonexistent/directory/data.json'
        result = PersistenceManager.save_json_data(invalid_file, {'key': 'value'})
        self.assertFalse(result)
    
    def test_load_json_data_invalid_json(self):
        """Test loading data from a file with invalid JSON."""
        # Create a file with invalid JSON
        with open(self.test_file, 'w') as f:
            f.write('{invalid json')
        
        # Load should return the default value
        data = PersistenceManager.load_json_data(self.test_file)
        self.assertEqual(data, {})
    
    def test_processed_messages_functions(self):
        """Test the processed messages convenience functions."""
        test_message_ids = {'msg1', 'msg2', 'msg3'}
        
        # Save the message IDs
        result = PersistenceManager.save_processed_messages(test_message_ids, self.test_file)
        self.assertTrue(result)
        
        # Load the message IDs
        loaded_ids = PersistenceManager.load_processed_messages(self.test_file)
        self.assertEqual(loaded_ids, test_message_ids)
    
    def test_ensure_directory_exists(self):
        """Test ensuring a directory exists."""
        test_dir = os.path.join(self.temp_dir, 'test_subdir')
        
        # Directory should not exist initially
        self.assertFalse(os.path.exists(test_dir))
        
        # Ensure it exists
        result = PersistenceManager.ensure_directory_exists(test_dir)
        self.assertTrue(result)
        self.assertTrue(os.path.exists(test_dir))
        
        # Test again with existing directory
        result = PersistenceManager.ensure_directory_exists(test_dir)
        self.assertTrue(result)
    
    def test_ensure_directory_exists_permission_error(self):
        """Test ensuring a directory exists with permission error."""
        # This will fail on most systems due to permissions
        test_dir = '/root/test_dir_no_permission'
        result = PersistenceManager.ensure_directory_exists(test_dir)
        self.assertFalse(result)
        
if __name__ == "__main__":
    unittest.main() 
