#!/usr/bin/env python3
"""
Test script to verify that hmac signature generation and verification works correctly.
"""

import os
import hmac
import hashlib
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def generate_signature(payload, secret):
    """Generate signature for webhook payload"""
    logger.debug(f"Generating signature with secret starting with: {secret[:5]}...")
    logger.debug(f"Payload to sign (first 100 chars): {payload[:100]}...")
    
    mac = hmac.new(
        secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha1
    )
    signature = mac.hexdigest()
    logger.debug(f"Generated signature: {signature}")
    return signature

def verify_signature(payload, signature, secret):
    """Verify that the signature matches the payload and secret"""
    calculated = generate_signature(payload, secret)
    
    result = hmac.compare_digest(calculated, signature)
    logger.debug(f"Signature verification result: {result}")
    logger.debug(f"Expected: {signature}")
    logger.debug(f"Calculated: {calculated}")
    
    return result

def main():
    # Load environment variables
    load_dotenv()
    
    # Get client secrets
    reportz_secret = os.getenv("INTERCOM_CLIENT_SECRET")
    base_secret = os.getenv("BASE_INTERCOM_CLIENT_SECRET")
    
    logger.info(f"Reportz secret available: {bool(reportz_secret)}")
    logger.info(f"Base secret available: {bool(base_secret)}")
    
    # Test payload
    test_payload = '{"type":"notification_event","topic":"ping","data":{"item":{"id":"test"}}}'
    
    # Test with Reportz secret
    if reportz_secret:
        logger.info("=== Testing signature with Reportz secret ===")
        signature = generate_signature(test_payload, reportz_secret)
        
        # Verify the signature with the same secret
        logger.info("Verifying with same secret (should succeed)")
        verify_signature(test_payload, signature, reportz_secret)
        
        # Verify with Base secret (should fail)
        if base_secret:
            logger.info("Verifying with different secret (should fail)")
            verify_signature(test_payload, signature, base_secret)
    
    # Test with Base secret
    if base_secret:
        logger.info("=== Testing signature with Base secret ===")
        signature = generate_signature(test_payload, base_secret)
        
        # Verify the signature with the same secret
        logger.info("Verifying with same secret (should succeed)")
        verify_signature(test_payload, signature, base_secret)
        
        # Verify with Reportz secret (should fail)
        if reportz_secret:
            logger.info("Verifying with different secret (should fail)")
            verify_signature(test_payload, signature, reportz_secret)

if __name__ == "__main__":
    main() 
