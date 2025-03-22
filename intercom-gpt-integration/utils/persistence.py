#!/usr/bin/env python3
"""
Persistence Utilities

This module provides functionality for persisting data to disk and loading it back,
such as processed message IDs and session data.
"""

import os
import json
import logging

logger = logging.getLogger(__name__)

class PersistenceManager:
    """
    Manages persistence of data to disk and loading it back.
    """
    
    @staticmethod
    def load_json_data(file_path, default=None):
        """Load data from a JSON file, or return default if file doesn't exist"""
        if not os.path.exists(file_path):
            logging.info(f"File {file_path} does not exist, returning default value")
            return default
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            logging.info(f"Loaded data from {file_path}: {data}")
            return data
        except Exception as e:
            logging.error(f"Error loading data from {file_path}: {e}")
            return default
    
    @staticmethod
    def save_json_data(file_path, data):
        """Save data to a JSON file"""
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
            logging.info(f"Successfully saved data to {file_path}: {data}")
            return True
        except Exception as e:
            logging.error(f"Failed to save data to {file_path}: {e}")
            return False
    
    @staticmethod
    def load_processed_messages(filename="processed_messages.json"):
        """
        Load processed message IDs from a file.
        
        Args:
            filename: The name of the file to load from
            
        Returns:
            set: A set of processed message IDs
        """
        data = PersistenceManager.load_json_data(filename, default=[])
        message_ids = set(data)
        logger.info(f"Loaded {len(message_ids)} processed message IDs from {filename}")
        return message_ids
    
    @staticmethod
    def save_processed_messages(message_ids, filename="processed_messages.json"):
        """
        Save processed message IDs to a file.
        
        Args:
            message_ids: A set or list of message IDs to save
            filename: The name of the file to save to
            
        Returns:
            bool: True if saving was successful, False otherwise
        """
        return PersistenceManager.save_json_data(filename, list(message_ids))
    
    @staticmethod
    def ensure_directory_exists(directory):
        """
        Ensure a directory exists, creating it if necessary.
        
        Args:
            directory: The directory path to ensure exists
            
        Returns:
            bool: True if the directory exists or was created, False otherwise
        """
        try:
            if not os.path.exists(directory):
                os.makedirs(directory)
                logger.info(f"Created directory {directory}")
            return True
        except Exception as e:
            logger.error(f"Error creating directory {directory}: {str(e)}", exc_info=True)
            return False 
