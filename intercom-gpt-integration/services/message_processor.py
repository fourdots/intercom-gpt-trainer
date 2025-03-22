#!/usr/bin/env python3
"""
Message Processor

This module handles the processing of messages from Intercom conversations,
including cleaning HTML content and extracting relevant message data.
"""

import logging
import time
from utils.persistence import PersistenceManager

logger = logging.getLogger(__name__)

# All possible author types - we'll process everything except admin
VALID_AUTHOR_TYPES = ['user', 'bot', 'contact', 'lead', 'visitor', None]

class MessageProcessor:
    """
    Processes messages from Intercom conversations.
    """
    
    def __init__(self, processed_messages_file="processed_messages.json"):
        """
        Initialize the message processor.
        
        Args:
            processed_messages_file: Path to the file storing processed message IDs
        """
        self.processed_messages_file = processed_messages_file
        self.processed_message_ids = PersistenceManager.load_processed_messages(processed_messages_file)
    
    def clean_message_body(self, body):
        """
        Safely clean HTML from message body, handling None values.
        
        Args:
            body: The message body text, potentially containing HTML
            
        Returns:
            str: Cleaned text with HTML tags removed
        """
        if body is None:
            return ""
            
        # Replace <br> tags with actual newlines
        body = body.replace('<br>', '\n').replace('<br/>', '\n').replace('<br />', '\n')
        
        # Replace paragraph tags
        body = body.replace('<p>', '').replace('</p>', '\n')
        
        # Handle other common HTML entities
        body = body.replace('&nbsp;', ' ')
        body = body.replace('&lt;', '<').replace('&gt;', '>')
        body = body.replace('&amp;', '&')
        
        # Remove any remaining HTML tags (simple approach)
        import re
        body = re.sub(r'<[^>]+>', '', body)
        
        # Clean up extra whitespace
        body = re.sub(r'\n\s*\n', '\n\n', body)  # Replace multiple blank lines with just one
        
        return body.strip()
    
    def extract_messages(self, conversation, last_processed_time=0):
        """
        Extract messages from an Intercom conversation that need processing.
        
        Args:
            conversation: The Intercom conversation object
            last_processed_time: Unix timestamp to filter messages newer than this time
            
        Returns:
            list: List of extracted message objects with author_type, text, timestamp, and id
        """
        extracted_messages = []
        
        # Check the initial conversation message
        try:
            initial_message = conversation.get('conversation_message', {})
            message_id = initial_message.get('id')
            
            # Skip if we've already processed this message
            if message_id in self.processed_message_ids:
                logger.debug(f"Skipping already processed message {message_id}")
            else:
                created_at = initial_message.get('created_at', 0)
                
                # Process only if newer than our last check
                if created_at > last_processed_time:
                    author_type = initial_message.get('author', {}).get('type')
                    
                    # Skip messages from admins (these are our own replies)
                    if author_type != 'admin':
                        body = initial_message.get('body', '')
                        cleaned_body = self.clean_message_body(body)
                        
                        if cleaned_body:
                            extracted_messages.append({
                                'id': message_id,
                                'author_type': author_type,
                                'text': cleaned_body,
                                'timestamp': created_at
                            })
                            self.processed_message_ids.add(message_id)
        except Exception as e:
            logger.error(f"Error processing initial message: {str(e)}", exc_info=True)
        
        # Check conversation parts (subsequent messages)
        try:
            parts = conversation.get('conversation_parts', {}).get('conversation_parts', [])
            
            for part in parts:
                message_id = part.get('id')
                
                # Skip if we've already processed this message
                if message_id in self.processed_message_ids:
                    logger.debug(f"Skipping already processed message part {message_id}")
                    continue
                    
                created_at = part.get('created_at', 0)
                
                # Process only if newer than our last check
                if created_at > last_processed_time:
                    author_type = part.get('author', {}).get('type')
                    
                    # Skip messages from admins (these are our own replies)
                    if author_type != 'admin':
                        body = part.get('body', '')
                        cleaned_body = self.clean_message_body(body)
                        
                        if cleaned_body:
                            extracted_messages.append({
                                'id': message_id,
                                'author_type': author_type,
                                'text': cleaned_body,
                                'timestamp': created_at
                            })
                            self.processed_message_ids.add(message_id)
        except Exception as e:
            logger.error(f"Error processing conversation parts: {str(e)}", exc_info=True)
        
        # Sort messages by timestamp to maintain chronological order
        extracted_messages.sort(key=lambda x: x['timestamp'])
        
        return extracted_messages
    
    def add_processed_message_id(self, message_id):
        """Add a message ID to the set of processed messages."""
        self.processed_message_ids.add(message_id)
    
    def get_processed_message_ids(self):
        """Get the set of processed message IDs."""
        return self.processed_message_ids
    
    def set_processed_message_ids(self, message_ids):
        """Set the processed message IDs from a list or set."""
        self.processed_message_ids = set(message_ids)
        
    def save_processed_messages(self):
        """Save the processed message IDs to disk."""
        return PersistenceManager.save_processed_messages(self.processed_message_ids, self.processed_messages_file) 
