import schedule
import time
import logging
import os
import json
from services.message_processor import MessageProcessor
from services.conversation_processor import ConversationProcessor
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

class ConversationPoller:
    def __init__(self, intercom_api, gpt_trainer_api, session_store, polling_interval=60):
        self.intercom_api = intercom_api
        self.gpt_trainer_api = gpt_trainer_api
        self.session_store = session_store
        self.polling_interval = polling_interval
        self.is_running = False
        self.last_processed_time = int(time.time()) - 3600  # Start checking from 1 hour ago for first run
        self.session_heartbeat_counter = 0
        
        # Initialize components
        self.message_processor = MessageProcessor()
        self.rate_limiter = RateLimiter()
        self.conversation_processor = ConversationProcessor(
            intercom_api,
            gpt_trainer_api,
            session_store,
            self.message_processor,
            self.rate_limiter
        )
        
        # Emergency safety
        self.emergency_stop_file = "EMERGENCY_STOP"
        if os.path.exists(self.emergency_stop_file):
            logger.warning(f"Emergency stop file {self.emergency_stop_file} exists! Remove this file to enable processing.")
    
    def start(self):
        """Start the polling service"""
        logger.info(f"Starting conversation poller with {self.polling_interval}s interval")
        self.is_running = True
        
        # Schedule the polling task
        schedule.every(self.polling_interval).seconds.do(self.poll_and_process)
        
        # Immediate first run
        self.poll_and_process()
        
        # Run continuously
        while self.is_running:
            # Check for emergency stop
            if os.path.exists(self.emergency_stop_file):
                logger.error("EMERGENCY STOP detected. Stopping all processing!")
                break
                
            schedule.run_pending()
            time.sleep(1)
    
    def stop(self):
        """Stop the polling service"""
        logger.info("Stopping conversation poller")
        self.conversation_processor.save_processed_messages()
        self.is_running = False
    
    def poll_and_process(self):
        """Poll for new conversations and process them"""
        try:
            # Check for emergency stop
            if os.path.exists(self.emergency_stop_file):
                logger.error("EMERGENCY STOP detected. Stopping all processing!")
                return
                
            logger.info("Polling for new conversations")
            
            # Reset rate limiting if minute has passed
            self.rate_limiter.reset_minute_counter()
                
            # Verify sessions periodically (every 5 polling cycles)
            self.session_heartbeat_counter += 1
            if self.session_heartbeat_counter >= 5:
                self.conversation_processor.verify_active_sessions()
                self.session_heartbeat_counter = 0
            
            # Get open conversations - use a larger number to ensure we don't miss any
            conversations = self.intercom_api.list_conversations(
                per_page=25,
                state="open",
                sort="updated_at",
                order="desc"
            )
            
            if not conversations:
                logger.info("No conversations found")
                return
                
            logger.info(f"Found {len(conversations)} conversations to check")
            
            # Save the current time to mark processed messages
            current_time = int(time.time())
            
            # Process each conversation
            for conversation in conversations:
                try:
                    self.conversation_processor.process_conversation(conversation, self.last_processed_time)
                except Exception as e:
                    logger.error(f"Error processing conversation: {str(e)}", exc_info=True)
                    continue
                
            logger.info("Polling cycle completed")
            self.last_processed_time = current_time
            
            # Save processed message IDs to disk
            self.conversation_processor.save_processed_messages()
            
        except Exception as e:
            logger.error(f"Error in polling cycle: {str(e)}", exc_info=True) 
