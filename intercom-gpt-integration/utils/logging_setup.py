"""
Logging setup for Intercom-GPT Trainer integration.
Configures logging for both local development and Google Cloud deployment.
"""
import logging
import os
import json
import time

def setup_logging(level=logging.INFO):
    """Configure application logging"""
    # Determine if running in cloud environment (Cloud Run sets this env var)
    in_cloud = os.getenv('K_SERVICE') is not None
    use_cloud_logging = os.getenv('USE_CLOUD_LOGGING', 'false').lower() == 'true'
    
    # Set up root logger
    logger = logging.getLogger()
    logger.setLevel(level)
    
    # Clear existing handlers
    logger.handlers = []
    
    # Cloud environment and cloud logging enabled: use Cloud Logging
    if in_cloud and use_cloud_logging:
        try:
            import google.cloud.logging
            from google.cloud.logging.handlers import CloudLoggingHandler
            
            client = google.cloud.logging.Client()
            handler = CloudLoggingHandler(client, name="intercom_gpt_bridge")
            
            # Create and add formatter
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            
            # Add handler to logger
            logger.addHandler(handler)
            
            # Add standard error handler for critical items
            console = logging.StreamHandler()
            console.setLevel(logging.ERROR)
            console.setFormatter(formatter)
            logger.addHandler(console)
            
            logger.info("Cloud Logging initialized")
        except Exception as e:
            # Fallback to console logging
            print(f"Failed to initialize Cloud Logging: {e}")
            _setup_console_logging(logger, level)
    else:
        # Local environment: use console logging
        _setup_console_logging(logger, level)
    
    return logger

def _setup_console_logging(logger, level=logging.INFO):
    """Set up console logging for local development"""
    console = logging.StreamHandler()
    console.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console.setFormatter(formatter)
    logger.addHandler(console)
    logger.info("Console logging initialized")

def log_structured_event(event_type, **kwargs):
    """Log a structured event to Cloud Logging"""
    logger = logging.getLogger()
    
    # Build structured log entry
    payload = {
        'event_type': event_type,
        'timestamp': time.time(),
        **kwargs
    }
    
    # Check if Google Cloud Logging is enabled
    in_cloud = os.getenv('K_SERVICE') is not None
    if in_cloud:
        logger.info(payload)
    else:
        # For local development, format as JSON
        logger.info(f"EVENT: {json.dumps(payload)}")
    
    return payload
