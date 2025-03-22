import os
import logging
import time
from dotenv import load_dotenv
from services.intercom_api import IntercomAPI
from services.gpt_trainer import GPTTrainerAPI
from services.poller import ConversationPoller
from utils.session_store import SessionStore
from services.conversation_state_manager import ConversationStateManager

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Set to DEBUG for more detailed logs
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Reduce logging noise from external libraries
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('requests').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = {
        "INTERCOM_ACCESS_TOKEN": os.getenv("INTERCOM_ACCESS_TOKEN"),
        "INTERCOM_ADMIN_ID": os.getenv("INTERCOM_ADMIN_ID"),
        "GPT_TRAINER_API_KEY": os.getenv("GPT_TRAINER_API_KEY"),
        "CHATBOT_UUID": os.getenv("CHATBOT_UUID"),
    }
    
    missing = [key for key, value in required_vars.items() if not value]
    
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        logger.error("Please update your .env file with these variables.")
        return False
    
    logger.info("All required environment variables are present")
    return True

def main():
    # Load environment variables
    load_dotenv()
    
    # Required environment variables
    intercom_token = os.getenv("INTERCOM_ACCESS_TOKEN")
    intercom_admin_id = os.getenv("INTERCOM_ADMIN_ID")
    gpt_trainer_key = os.getenv("GPT_TRAINER_API_KEY")
    chatbot_uuid = os.getenv("CHATBOT_UUID")
    gpt_trainer_api_url = os.getenv("GPT_TRAINER_API_URL", "https://app.gpt-trainer.com/api/v1")
    
    # Optional configuration
    polling_interval = int(os.getenv("POLLING_INTERVAL", "60"))
    
    # Log configuration (with sensitive data partially masked)
    logger.info(f"Intercom Admin ID: {intercom_admin_id}")
    if intercom_token:
        logger.info(f"Intercom Token (truncated): {intercom_token[:10]}...")
    if gpt_trainer_key:
        logger.info(f"GPT Trainer Key (truncated): {gpt_trainer_key[:10]}...")
    logger.info(f"GPT Trainer Chatbot UUID: {chatbot_uuid}")
    logger.info(f"GPT Trainer API URL: {gpt_trainer_api_url}")
    logger.info(f"Polling Interval: {polling_interval} seconds")
    
    # Validate environment
    if not validate_environment():
        return 1
    
    try:
        # Initialize components
        logger.info("Initializing services...")
        intercom_api = IntercomAPI(intercom_token, intercom_admin_id)
        gpt_trainer_api = GPTTrainerAPI(gpt_trainer_key, chatbot_uuid, gpt_trainer_api_url)
        session_store = SessionStore()
        
        # Verify session store is working
        logger.info("Testing session store...")
        
        # Create a conversation state manager
        logger.info("Initializing conversation state manager...")
        state_manager = ConversationStateManager(session_store)
        logger.info("Conversation state management active - preventing multiple messages without user replies")
        
        # Initialize and start poller
        logger.info(f"Starting conversation poller with {polling_interval}s interval")
        poller = ConversationPoller(
            intercom_api,
            gpt_trainer_api,
            session_store,
            polling_interval=polling_interval
        )
        
        # Start the polling process
        poller.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
        return 0
    except Exception as e:
        logger.error(f"Error in main application: {str(e)}", exc_info=True)
        return 1

if __name__ == "__main__":
    exit(main()) 
