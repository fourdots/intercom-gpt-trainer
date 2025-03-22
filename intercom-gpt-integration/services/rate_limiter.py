#!/usr/bin/env python3
"""
Rate Limiter

This module provides rate limiting functionality for the Intercom-GPT integration.
It prevents excessive API calls both globally and per-conversation.
"""

import logging
import time

logger = logging.getLogger(__name__)

class RateLimiter:
    """
    Rate limiter to prevent excessive API calls both globally and per-conversation.
    """
    
    def __init__(self, max_responses_per_conversation=15, max_responses_per_minute=10):
        """
        Initialize the rate limiter.
        
        Args:
            max_responses_per_conversation: Maximum responses per individual conversation ID (resets when user starts a new conversation)
            max_responses_per_minute: Maximum total responses per minute across all conversations
        """
        self.MAX_RESPONSES_PER_CONVERSATION = max_responses_per_conversation
        self.MAX_RESPONSES_PER_MINUTE = max_responses_per_minute
        
        # Rate limiting counters
        self.responses_sent = 0
        self.minute_start_time = time.time()
        self.conversation_response_counts = {}
    
    def check_rate_limits(self, conversation_id):
        """
        Check if we've hit rate limits for this conversation or globally.
        
        Args:
            conversation_id: The ID of the conversation to check
            
        Returns:
            bool: True if within rate limits, False otherwise
        """
        # Global rate limit check
        if self.responses_sent >= self.MAX_RESPONSES_PER_MINUTE:
            logger.warning(f"Global rate limit reached: {self.responses_sent}/{self.MAX_RESPONSES_PER_MINUTE} responses per minute")
            return False
            
        # Per-conversation rate limit check
        today = time.strftime("%Y-%m-%d")
        conversation_key = f"{conversation_id}_{today}"
        
        count = self.conversation_response_counts.get(conversation_key, 0)
        if count >= self.MAX_RESPONSES_PER_CONVERSATION:
            logger.warning(f"Conversation rate limit reached for {conversation_id}: {count}/{self.MAX_RESPONSES_PER_CONVERSATION} responses today")
            return False
            
        return True
    
    def increment_rate_counter(self, conversation_id):
        """
        Increment the rate counters after sending a response.
        
        Args:
            conversation_id: The ID of the conversation
        """
        # Global counter
        self.responses_sent += 1
        
        # Per-conversation counter
        today = time.strftime("%Y-%m-%d")
        conversation_key = f"{conversation_id}_{today}"
        
        count = self.conversation_response_counts.get(conversation_key, 0)
        self.conversation_response_counts[conversation_key] = count + 1
        
        logger.info(f"Rate counters: {self.responses_sent}/{self.MAX_RESPONSES_PER_MINUTE} global, {self.conversation_response_counts[conversation_key]}/{self.MAX_RESPONSES_PER_CONVERSATION} for conversation")
    
    def reset_minute_counter(self):
        """Reset the per-minute rate limit counter if a minute has passed."""
        current_time = time.time()
        if current_time - self.minute_start_time > 60:
            self.responses_sent = 0
            self.minute_start_time = current_time
            logger.debug("Reset per-minute rate limit counter")
            return True
        return False 
