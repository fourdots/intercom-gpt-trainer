#!/usr/bin/env python3
"""
Tests for the RateLimiter class.
"""

import unittest
import time
from services.rate_limiter import RateLimiter

class TestRateLimiter(unittest.TestCase):
    """Test cases for the RateLimiter class."""
    
    def setUp(self):
        """Set up a fresh RateLimiter instance for each test."""
        self.rate_limiter = RateLimiter(
            max_responses_per_conversation=3,
            max_responses_per_minute=5
        )
    
    def test_check_rate_limits_initially_allowed(self):
        """Test that rate limits are not exceeded initially."""
        self.assertTrue(self.rate_limiter.check_rate_limits("conversation1"))
    
    def test_global_rate_limit(self):
        """Test that global rate limit works."""
        # Send 5 messages (the limit)
        for i in range(5):
            self.assertTrue(self.rate_limiter.check_rate_limits(f"conversation{i}"))
            self.rate_limiter.increment_rate_counter(f"conversation{i}")
        
        # The 6th message should be blocked by the global rate limit
        self.assertFalse(self.rate_limiter.check_rate_limits("conversation6"))
    
    def test_per_conversation_rate_limit(self):
        """Test that per-conversation rate limit works."""
        conversation_id = "conversation1"
        
        # Send 3 messages to the same conversation (the limit)
        for i in range(3):
            self.assertTrue(self.rate_limiter.check_rate_limits(conversation_id))
            self.rate_limiter.increment_rate_counter(conversation_id)
        
        # The 4th message to the same conversation should be blocked
        self.assertFalse(self.rate_limiter.check_rate_limits(conversation_id))
    
    def test_reset_minute_counter(self):
        """Test that the per-minute rate limit counter resets properly."""
        # Mock the time to force reset
        self.rate_limiter.minute_start_time = time.time() - 61  # Set to 61 seconds ago
        
        # Send 5 messages (the limit)
        for i in range(5):
            self.rate_limiter.increment_rate_counter(f"conversation{i}")
        
        # Verify we've hit the limit
        self.assertEqual(self.rate_limiter.responses_sent, 5)
        self.assertFalse(self.rate_limiter.check_rate_limits("conversation6"))
        
        # Reset the counter
        reset = self.rate_limiter.reset_minute_counter()
        
        # Verify it was reset
        self.assertTrue(reset)
        self.assertEqual(self.rate_limiter.responses_sent, 0)
        self.assertTrue(self.rate_limiter.check_rate_limits("conversation6"))
    
    def test_different_conversations_separate_limits(self):
        """Test that different conversations have separate rate limits."""
        # Send 3 messages to conversation1 (hitting its limit)
        for i in range(3):
            self.assertTrue(self.rate_limiter.check_rate_limits("conversation1"))
            self.rate_limiter.increment_rate_counter("conversation1")
        
        # Verify conversation1 is now limited
        self.assertFalse(self.rate_limiter.check_rate_limits("conversation1"))
        
        # But conversation2 should still be allowed
        self.assertTrue(self.rate_limiter.check_rate_limits("conversation2"))
        
if __name__ == "__main__":
    unittest.main() 
