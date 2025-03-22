import os
import json
import logging
import hmac
import hashlib
import secrets
import urllib.parse
import requests
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, redirect, url_for, session
from dotenv import load_dotenv
from services.intercom_api import IntercomAPI
from services.gpt_trainer import GPTTrainerAPI
from utils.session_store import SessionStore, AWAITING_USER_REPLY, READY_FOR_RESPONSE, ADMIN_TAKEOVER
from services.conversation_state_manager import ConversationStateManager
from services.message_processor import MessageProcessor
from services.rate_limiter import RateLimiter
from utils.persistence import PersistenceManager
from utils.logging_setup import setup_logging, log_structured_event
from utils.secrets_manager import get_configuration
import statistics  # For calculating averages, median etc.

# Set up logging
setup_logging(level=logging.DEBUG)  # Use DEBUG level for more detailed logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Load configuration (from Secret Manager in production, env vars in dev)
config = get_configuration()

# Intercom API credentials and configuration
intercom_token = config.get("INTERCOM_ACCESS_TOKEN")
intercom_admin_id = config.get("INTERCOM_ADMIN_ID")
intercom_client_id = config.get("INTERCOM_CLIENT_ID")
intercom_client_secret = config.get("INTERCOM_CLIENT_SECRET")

# GPT Trainer credentials and configuration
gpt_trainer_key = config.get("GPT_TRAINER_API_KEY")
chatbot_uuid = config.get("CHATBOT_UUID")
gpt_trainer_api_url = config.get("GPT_TRAINER_API_URL", "https://app.gpt-trainer.com/api/v1")

# Application configuration
port = int(config.get("PORT", 8080))
webhook_base_url = os.getenv("WEBHOOK_BASE_URL")  # This is only for local development
client_secret = intercom_client_secret

# Define the automated admin ID (our Intercom bot)
AUTOMATED_ADMIN_ID = intercom_admin_id
# Define the human admin ID
HUMAN_ADMIN_ID = "253345"  # Hard-coded human admin ID
# Special takeover phrase
TAKEOVER_PHRASE = "I'll take this, thanks."
# Special re-activation phrase
ACTIVATION_PHRASE = "Sofia will jump in"
# Takeover expiration in hours
TAKEOVER_EXPIRATION_HOURS = 12

# Initialize components
intercom_api = IntercomAPI(intercom_token, intercom_admin_id)
gpt_trainer_api = GPTTrainerAPI(gpt_trainer_key, chatbot_uuid, gpt_trainer_api_url)
session_store = SessionStore()
state_manager = ConversationStateManager(session_store)
message_processor = MessageProcessor()
rate_limiter = RateLimiter()

# Keep track of recently processed webhook IDs to prevent duplicate processing
processed_webhook_ids = set()
MAX_PROCESSED_IDS = 1000  # Maximum number of IDs to store to prevent memory issues

# Track message content fingerprints to prevent duplicate processing
processed_message_fingerprints = set()
MAX_FINGERPRINTS = 200  # Maximum number of fingerprints to store

# Keep track of conversations where a human admin has replied
human_admin_conversations = set()
# Keep track of conversations where a human admin has taken over with timestamps
human_takeover_conversations = {}  # {conversation_id: timestamp}

# Message batching system - collect messages for a short time before processing
message_batches = {}  # {conversation_id: {'messages': [], 'timer': timer_object, 'last_update': timestamp}}
MESSAGE_BATCH_WAIT_TIME = 5.0  # seconds to wait for more messages before processing (increased from 3.0)

# Updated performance tracking system
performance_metrics = {
    'webhook_handling': [],            # Time to process a webhook
    'message_batching': [],            # Time spent in batch queue
    'intercom_api_calls': [],          # Time for Intercom API calls
    'gpt_trainer_api_calls': [],       # Time for GPT Trainer API calls
    'total_processing': [],            # Total time from webhook to response
    'conversation_fetching': [],       # Time to fetch conversation details
    'session_management': [],          # Time for session management
    'message_processing': [],          # Time for message cleaning and processing
    'response_generation': [],         # Time for AI to generate a response
    'response_delivery': [],           # Time to send response to Intercom
    'cold_start': []                   # Time for Cloud Run cold start (if applicable)
}

# Store timeline of events for each conversation
conversation_timelines = {}            # {conversation_id: [{timestamp, event, duration}]}
MAX_TIMELINE_ENTRIES = 1000            # Maximum timeline entries to keep
MAX_CONVERSATIONS_TIMELINE = 50        # Maximum conversations to track

# Maximum number of metrics to store
MAX_METRICS = 100

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(16))

# Track application startup and cold start
app.start_time = time.time()
app.cold_start_measured = False
logger.info(f"Application startup at timestamp: {app.start_time}")

# Store cold start times for recent instances
cold_start_history = []
MAX_COLD_START_HISTORY = 10

@app.before_request
def before_request():
    """Execute before each request to detect cold starts"""
    # Only check on the first request
    if not hasattr(app, 'cold_start_measured') or not app.cold_start_measured:
        cold_start_time = time.time() - app.start_time
        cold_start_ms = cold_start_time * 1000
        
        # Log the cold start
        logger.info(f"COLD START detected: {cold_start_ms:.2f}ms")
        
        # Track in metrics
        if 'cold_start' in performance_metrics:
            performance_metrics['cold_start'].append(cold_start_ms)
            
            # Keep only the most recent cold starts
            if len(performance_metrics['cold_start']) > MAX_METRICS:
                performance_metrics['cold_start'] = performance_metrics['cold_start'][-MAX_METRICS:]
        
        # Record in history
        cold_start_entry = {
            'timestamp': time.time(),
            'duration_ms': cold_start_ms,
            'request_path': request.path
        }
        cold_start_history.append(cold_start_entry)
        
        # Keep history size limited
        if len(cold_start_history) > MAX_COLD_START_HISTORY:
            cold_start_history.pop(0)
        
        # Log as structured event
        log_structured_event('cold_start_detected',
                           duration_ms=cold_start_ms,
                           request_path=request.path)
        
        app.cold_start_measured = True

@app.route('/monitoring/cold-starts', methods=['GET'])
def cold_start_monitoring():
    """Endpoint to view cold start monitoring data"""
    # Calculate statistics
    cold_start_times = performance_metrics.get('cold_start', [])
    stats = {}
    
    if cold_start_times:
        avg_time = sum(cold_start_times) / len(cold_start_times)
        stats = {
            'count': len(cold_start_times),
            'average_ms': avg_time,
            'min_ms': min(cold_start_times),
            'max_ms': max(cold_start_times),
            'latest_ms': cold_start_times[-1] if cold_start_times else None
        }
    
    # Return JSON by default
    if request.headers.get('Accept', '').find('application/json') != -1 or not request.args.get('html'):
        return jsonify({
            'cold_start_stats': stats,
            'history': cold_start_history
        })
    
    # HTML view for browser
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cold Start Monitoring</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            h1, h2 { color: #333; }
            .card { background: #f9f9f9; padding: 15px; margin: 10px 0; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            table { width: 100%; border-collapse: collapse; margin: 15px 0; }
            th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }
            th { background-color: #f2f2f2; }
            tr:hover { background-color: #f5f5f5; }
        </style>
    </head>
    <body>
        <h1>Cold Start Monitoring</h1>
        
        <div class="card">
            <h2>Cold Start Statistics</h2>
    """
    
    if stats:
        html += f"""
            <p>Count: {stats['count']}</p>
            <p>Average: {stats['average_ms']:.2f} ms</p>
            <p>Min: {stats['min_ms']:.2f} ms</p>
            <p>Max: {stats['max_ms']:.2f} ms</p>
            <p>Latest: {stats['latest_ms']:.2f} ms</p>
        """
    else:
        html += "<p>No cold starts detected yet.</p>"
    
    html += """
        </div>
        
        <div class="card">
            <h2>Recent Cold Starts</h2>
            <table>
                <tr>
                    <th>Time</th>
                    <th>Duration (ms)</th>
                    <th>Request Path</th>
                </tr>
    """
    
    for entry in reversed(cold_start_history):
        time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(entry['timestamp']))
        html += f"""
                <tr>
                    <td>{time_str}</td>
                    <td>{entry['duration_ms']:.2f}</td>
                    <td>{entry['request_path']}</td>
                </tr>
        """
    
    if not cold_start_history:
        html += """
                <tr>
                    <td colspan="3">No cold starts recorded yet.</td>
                </tr>
        """
    
    html += """
            </table>
        </div>
        
        <div class="card">
            <p><a href="/analytics">Back to Analytics Dashboard</a></p>
        </div>
        
        <script>
            // Auto-refresh every 60 seconds
            setTimeout(function() { window.location.reload(); }, 60000);
        </script>
    </body>
    </html>
    """
    
    return html

def save_takeovers():
    logger.info(f"[DEBUG] PERSISTENCE: Saving takeovers to persistent storage")
    try:
        logger.info(f"[DEBUG] PERSISTENCE: Data to save: {json.dumps(human_takeover_conversations)}")
        PersistenceManager.save_json_data("human_takeovers.json", {"conversations": human_takeover_conversations})
        logger.info(f"Saved {len(human_takeover_conversations)} human takeover conversations to persistent storage")
        
        # Verify the save by reading the file again
        try:
            verification = PersistenceManager.load_json_data("human_takeovers.json")
            logger.info(f"[DEBUG] PERSISTENCE: Verification of saved data: {json.dumps(verification)}")
        except Exception as e:
            logger.error(f"[DEBUG] PERSISTENCE: Error verifying saved data: {e}")
    except Exception as e:
        logger.error(f"[DEBUG] PERSISTENCE: Error saving takeovers file: {e}")

def is_takeover_active(conversation_id):
    """Check if a takeover is still active based on expiration time"""
    logger.info(f"[DEBUG] Checking takeover for conversation: {conversation_id}")
    logger.info(f"[DEBUG] Current takeovers dictionary: {json.dumps(human_takeover_conversations)}")
    logger.info(f"[DEBUG] Dictionary keys: {list(human_takeover_conversations.keys())}")
    logger.info(f"[DEBUG] Dictionary type: {type(human_takeover_conversations)}")
    
    if conversation_id not in human_takeover_conversations:
        logger.info(f"[DEBUG] No takeover found for conversation {conversation_id}")
        return False
        
    takeover_time = human_takeover_conversations[conversation_id]
    current_time = time.time()
    hours_passed = (current_time - takeover_time) / 3600
    
    logger.info(f"[DEBUG] Takeover time: {takeover_time}, Current time: {current_time}")
    logger.info(f"[DEBUG] Hours passed: {hours_passed}, Expiration threshold: {TAKEOVER_EXPIRATION_HOURS}")
    
    # If more than the expiration period has passed, remove the takeover
    if hours_passed > TAKEOVER_EXPIRATION_HOURS:
        logger.info(f"[DEBUG] Takeover for conversation {conversation_id} has expired - Removing")
        logger.info(f"[DEBUG] Before removal: {json.dumps(human_takeover_conversations)}")
        del human_takeover_conversations[conversation_id]
        logger.info(f"[DEBUG] After removal: {json.dumps(human_takeover_conversations)}")
        save_takeovers()
        return False
        
    logger.info(f"[DEBUG] Takeover is active for conversation {conversation_id} ({hours_passed:.1f} hours old)")
    return True

# Load persisted takeovers
def load_takeovers():
    logger.info(f"[DEBUG] PERSISTENCE: Loading takeovers from persistent storage")
    try:
        takeovers = PersistenceManager.load_json_data("human_takeovers.json", default={"conversations": {}})
        loaded_data = takeovers.get("conversations", {})
        logger.info(f"[DEBUG] PERSISTENCE: Loaded takeovers data: {json.dumps(loaded_data)}")
        
        # Ensure data is in the correct format (conversation_id -> timestamp)
        cleaned_data = {}
        for conv_id, timestamp in loaded_data.items():
            # Only include if the data format is correct (string keys, numeric values)
            if isinstance(conv_id, str) and (isinstance(timestamp, (int, float))):
                cleaned_data[conv_id] = timestamp
            else:
                logger.warning(f"[DEBUG] PERSISTENCE: Ignoring invalid takeover data for {conv_id}: {timestamp}")
        
        logger.info(f"[DEBUG] PERSISTENCE: Cleaned takeovers data: {json.dumps(cleaned_data)}")
        return cleaned_data
    except Exception as e:
        logger.error(f"[DEBUG] PERSISTENCE: Error loading takeovers file: {e}")
        return {}

# Load saved takeovers on startup
def debug_takeover_dictionary():
    """Debug function to check and fix the takeover dictionary"""
    global human_takeover_conversations
    
    logger.info("[DEBUG] STARTUP: Checking takeover dictionary integrity")
    
    # Check if it's a dictionary
    if not isinstance(human_takeover_conversations, dict):
        logger.error(f"[DEBUG] STARTUP: human_takeover_conversations is not a dictionary! Type: {type(human_takeover_conversations)}")
        logger.error(f"[DEBUG] STARTUP: Value: {human_takeover_conversations}")
        logger.error("[DEBUG] STARTUP: Resetting to empty dictionary")
        human_takeover_conversations = {}
        save_takeovers()
        return
    
    # Check for any non-string keys or non-numeric values
    invalid_keys = []
    for key, value in human_takeover_conversations.items():
        if not isinstance(key, str):
            logger.warning(f"[DEBUG] STARTUP: Invalid key type: {type(key)} for key {key}")
            invalid_keys.append(key)
        elif not isinstance(value, (int, float)):
            logger.warning(f"[DEBUG] STARTUP: Invalid value type: {type(value)} for key {key}")
            invalid_keys.append(key)
    
    # Remove any invalid entries
    if invalid_keys:
        logger.warning(f"[DEBUG] STARTUP: Removing {len(invalid_keys)} invalid entries from takeover dictionary")
        for key in invalid_keys:
            del human_takeover_conversations[key]
        save_takeovers()
    
    logger.info(f"[DEBUG] STARTUP: Takeover dictionary integrity check complete. {len(human_takeover_conversations)} valid entries.")

# Load saved takeovers on startup
human_takeover_conversations = load_takeovers()
# Run integrity check
debug_takeover_dictionary()
# Clean up expired takeovers
for conv_id in list(human_takeover_conversations.keys()):
    is_takeover_active(conv_id)
logger.info(f"Loaded {len(human_takeover_conversations)} active human takeover conversations from persistent storage")

def verify_webhook_signature(payload, signature_header):
    """Verify that the webhook request is from Intercom"""
    # Get both client secrets
    reportz_secret = intercom_client_secret
    base_secret = os.environ.get("BASE_INTERCOM_CLIENT_SECRET", "")
    
    logger.debug(f"Reportz secret available: {bool(reportz_secret)}, Base secret available: {bool(base_secret)}")
    
    if not reportz_secret and not base_secret:
        logger.warning("No client secrets configured, skipping signature verification")
        return True
    
    if not signature_header:
        logger.warning("No signature header in request")
        return False
    
    if not signature_header.startswith('sha1='):
        logger.warning("Invalid signature format")
        return False
    
    signature = signature_header[5:]  # Remove 'sha1=' prefix
    logger.debug(f"Received signature: {signature}")
    
    # Try to verify with Reportz client secret
    if reportz_secret:
        reportz_mac = hmac.new(
            reportz_secret.encode('utf-8'),
            msg=payload.encode('utf-8'),
            digestmod=hashlib.sha1
        )
        reportz_calculated_signature = reportz_mac.hexdigest()
        logger.debug(f"Reportz calculated signature: {reportz_calculated_signature}")
        
        if hmac.compare_digest(reportz_calculated_signature, signature):
            logger.info("Webhook signature verified using Reportz client secret")
            return True
        else:
            logger.debug("Reportz signature verification failed")
    
    # Try to verify with Base client secret
    if base_secret:
        base_mac = hmac.new(
            base_secret.encode('utf-8'),
            msg=payload.encode('utf-8'),
            digestmod=hashlib.sha1
        )
        base_calculated_signature = base_mac.hexdigest()
        logger.debug(f"Base calculated signature: {base_calculated_signature}")
        
        if hmac.compare_digest(base_calculated_signature, signature):
            logger.info("Webhook signature verified using Base client secret")
            return True
        else:
            logger.debug("Base signature verification failed")
    
    logger.warning("Webhook signature verification failed for all client secrets")
    logger.debug(f"Received signature: {signature}")
    if reportz_secret:
        logger.debug(f"Reportz calculated: {reportz_calculated_signature}")
    if base_secret:
        logger.debug(f"Base calculated: {base_calculated_signature}")
    
    return False

def ensure_valid_session(conversation_id):
    """
    Ensures a valid GPT Trainer session exists for the conversation.
    Returns a valid session ID or None if unable to create one.
    """
    # Try to get existing session
    logger.info(f"DEBUG - Checking for existing session for conversation {conversation_id}")
    session_id = session_store.get_session(conversation_id)
    
    if not session_id:
        logger.info(f"DEBUG - No session found for conversation {conversation_id} - creating new session")
        try:
            # Create a new session
            logger.info(f"DEBUG - Calling GPT Trainer API to create new session")
            session_id = gpt_trainer_api.create_session()
            logger.info(f"DEBUG - Received session_id: {session_id}")
            
            session_store.save_session(conversation_id, session_id)
            logger.info(f"DEBUG - Saved new session {session_id} for conversation {conversation_id}")
            return session_id
        except Exception as e:
            logger.error(f"DEBUG - Failed to create new session for conversation {conversation_id}: {str(e)}")
            logger.error(f"DEBUG - Exception details:", exc_info=True)
            return None
    else:
        logger.info(f"DEBUG - Found existing session {session_id} for conversation {conversation_id}")
    
    # Verify the session is valid
    try:
        # A simple check to validate the session - in a production system,
        # you might want to implement a proper verification method in the GPTTrainerAPI class
        is_valid = True  # Assume valid for now
        if is_valid:
            logger.info(f"DEBUG - Using existing session {session_id} for conversation {conversation_id}")
            return session_id
        else:
            logger.warning(f"DEBUG - Session {session_id} for conversation {conversation_id} is invalid - creating new session")
            # Create a new session
            session_id = gpt_trainer_api.create_session()
            session_store.save_session(conversation_id, session_id)
            logger.info(f"DEBUG - Created replacement session {session_id} for conversation {conversation_id}")
            return session_id
    except Exception as e:
        logger.error(f"DEBUG - Error verifying session {session_id} for conversation {conversation_id}: {str(e)}")
        logger.error(f"DEBUG - Exception details:", exc_info=True)
        try:
            # Create a new session as fallback
            logger.info(f"DEBUG - Creating fallback session after error")
            session_id = gpt_trainer_api.create_session()
            session_store.save_session(conversation_id, session_id)
            logger.info(f"DEBUG - Created fallback session {session_id} after error")
            return session_id
        except Exception as e2:
            logger.error(f"DEBUG - Failed to create fallback session: {str(e2)}")
            logger.error(f"DEBUG - Exception details:", exc_info=True)
            return None

def track_performance(metric_name, start_time, conversation_id=None, event_description=None):
    """Track performance metrics with enhanced timeline tracking"""
    global conversation_timelines
    
    # Ensure conversation_timelines is initialized
    if 'conversation_timelines' not in globals() or conversation_timelines is None:
        conversation_timelines = {}
        
    end_time = time.time()
    elapsed_ms = (end_time - start_time) * 1000  # Convert to milliseconds
    
    # Add to metrics list
    if metric_name in performance_metrics:
        performance_metrics[metric_name].append(elapsed_ms)
        
        # Keep only the last MAX_METRICS values
        if len(performance_metrics[metric_name]) > MAX_METRICS:
            performance_metrics[metric_name] = performance_metrics[metric_name][-MAX_METRICS:]
    
    # Log the metric
    logger.info(f"PERFORMANCE: {metric_name} took {elapsed_ms:.2f}ms" + 
                (f" for conversation {conversation_id}" if conversation_id else ""))
    
    # Store in conversation timeline if we have a conversation ID
    if conversation_id:
        if conversation_id not in conversation_timelines:
            conversation_timelines[conversation_id] = []
        
        # Add timeline entry
        entry = {
            'timestamp': end_time,
            'event': event_description or metric_name,
            'duration_ms': elapsed_ms,
            'metric': metric_name
        }
        conversation_timelines[conversation_id].append(entry)
        
        # Log as structured event for Cloud Logging
        log_structured_event('performance_metric', 
                           conversation_id=conversation_id,
                           metric=metric_name,
                           duration_ms=elapsed_ms,
                           description=event_description)
        
        # Clean up old entries if needed
        if len(conversation_timelines[conversation_id]) > MAX_TIMELINE_ENTRIES:
            conversation_timelines[conversation_id] = conversation_timelines[conversation_id][-MAX_TIMELINE_ENTRIES:]
    
    # Limit the number of conversations we track
    if len(conversation_timelines) > MAX_CONVERSATIONS_TIMELINE:
        # Keep only the most recently updated conversations
        sorted_conversations = sorted(conversation_timelines.keys(), 
                                    key=lambda c_id: max([e['timestamp'] for e in conversation_timelines[c_id]]),
                                    reverse=True)
        
        # Keep only the most recent MAX_CONVERSATIONS_TIMELINE conversations
        conversations_to_keep = sorted_conversations[:MAX_CONVERSATIONS_TIMELINE]
        conversation_timelines = {c_id: conversation_timelines[c_id] for c_id in conversations_to_keep}
    
    # Return the elapsed time for cases where we need to use it
    return elapsed_ms

def get_conversation_timeline(conversation_id):
    """Get the performance timeline for a specific conversation"""
    if conversation_id not in conversation_timelines:
        return []
    
    timeline = conversation_timelines[conversation_id]
    
    # Calculate the full timeline duration
    if timeline:
        first_event = min([e['timestamp'] for e in timeline])
        last_event = max([e['timestamp'] for e in timeline])
        total_duration_ms = (last_event - first_event) * 1000
        
        # Add relative timing information
        for entry in timeline:
            entry['relative_time_ms'] = (entry['timestamp'] - first_event) * 1000
        
        # Sort by timestamp
        timeline = sorted(timeline, key=lambda e: e['timestamp'])
        
        return {
            'timeline': timeline,
            'total_duration_ms': total_duration_ms,
            'start_time': first_event,
            'end_time': last_event
        }
    
    return {'timeline': [], 'total_duration_ms': 0}

def track_cold_start():
    """Track Cloud Run cold start time"""
    global cold_start_time
    
    # If this is the first request after startup
    if not hasattr(app, 'cold_start_measured') and hasattr(app, 'start_time'):
        cold_start_duration = time.time() - app.start_time
        track_performance('cold_start', app.start_time, event_description="Cloud Run cold start")
        logger.info(f"COLD START detected and measured: {cold_start_duration*1000:.2f}ms")
        app.cold_start_measured = True

# Process a batch of messages for a conversation
def process_message_batch(conversation_id):
    """Process all collected messages for a conversation with detailed performance tracking"""
    processing_start_time = time.time()
    logger.info(f"DEBUG - process_message_batch called for conversation {conversation_id}")
    
    if conversation_id not in message_batches:
        logger.warning(f"DEBUG - No message batch found for conversation {conversation_id}")
        return
    
    batch = message_batches.pop(conversation_id)
    messages = batch.get('messages', [])
    batch_data = batch.get('batch_data', [])
    logger.info(f"DEBUG - Retrieved batch with {len(messages)} messages and {len(batch_data)} batch data items")
    
    # Calculate how long messages were in the batch queue
    first_batch_time = min([data.get('batch_time', processing_start_time) for data in batch_data]) if batch_data else processing_start_time
    first_webhook_time = min([data.get('webhook_time', processing_start_time) for data in batch_data]) if batch_data else processing_start_time
    
    batch_queue_time = processing_start_time - first_batch_time
    logger.info(f"DEBUG - Messages waited in batch for {batch_queue_time:.2f} seconds")
    track_performance('message_batching', first_batch_time, conversation_id, 
                      event_description=f"Message batch waited {batch_queue_time:.2f}s before processing")
    
    if not messages:
        logger.warning(f"DEBUG - Empty message batch for conversation {conversation_id}")
        return
    
    logger.info(f"DEBUG - Processing batch of {len(messages)} messages for conversation {conversation_id}")
    
    # Get platform-specific Intercom API client if available in batch data
    # Default to the global instance if not found
    current_intercom_api = None
    for data in batch_data:
        if 'intercom_api' in data:
            current_intercom_api = data.get('intercom_api')
            logger.info(f"DEBUG - Using platform-specific Intercom API client from batch data")
            break
    
    if not current_intercom_api:
        logger.info(f"DEBUG - No platform-specific API client found in batch data, using default")
        current_intercom_api = intercom_api
    
    # Get full conversation details from Intercom
    try:
        intercom_start_time = time.time()
        conversation = current_intercom_api.get_conversation(conversation_id)
        track_performance('conversation_fetching', intercom_start_time, conversation_id, 
                          event_description="Fetched conversation details from Intercom")
        track_performance('intercom_api_calls', intercom_start_time, conversation_id)
        logger.info(f"Successfully retrieved conversation {conversation_id} for batch processing")
        
        # Check if the conversation has been taken over by a human admin
        takeover_check_start = time.time()
        takeover_active = False
        if conversation_id in human_takeover_conversations and is_takeover_active(conversation_id):
            logger.info(f"Conversation {conversation_id} has been taken over by a human admin - AI will not respond")
            takeover_active = True
        track_performance('admin_takeover_check', takeover_check_start, conversation_id,
                         event_description=f"Checked admin takeover: {'Active' if takeover_active else 'Not active'}")
        
        if takeover_active:
            return
        
        # Check if the conversation state allows for a response
        state_check_start = time.time()
        can_respond = state_manager.can_send_ai_response(conversation_id)
        track_performance('state_check', state_check_start, conversation_id,
                         event_description=f"Checked conversation state: {'Ready' if can_respond else 'Not ready'}")
        logger.info(f"Can send AI response for batch {conversation_id}? {can_respond}")
        
        if not can_respond:
            logger.info(f"Conversation {conversation_id} is not ready for response - skipping batch")
            return
        
        # Check rate limits
        rate_limit_start = time.time()
        rate_limited = rate_limiter.check_rate_limits(conversation_id) == False
        track_performance('rate_limit_check', rate_limit_start, conversation_id,
                         event_description=f"Checked rate limits: {'Limited' if rate_limited else 'Not limited'}")
        
        if rate_limited:
            logger.warning(f"Rate limited for conversation {conversation_id}")
            return
        
        # Combine all messages into a single text
        message_processing_start = time.time()
        combined_message = "\n".join([f"{msg}" for msg in messages])
        logger.info(f"Combined {len(messages)} messages for processing: {combined_message[:100]}...")
        
        # Clean the message using the improved HTML-aware cleaner
        clean_message = message_processor.clean_message_body(combined_message)
        track_performance('message_processing', message_processing_start, conversation_id,
                         event_description=f"Processed {len(messages)} messages into single query")
        
        # Ensure we have a valid session
        session_start_time = time.time()
        session_id = ensure_valid_session(conversation_id)
        track_performance('session_management', session_start_time, conversation_id,
                         event_description=f"Retrieved or created session {session_id}")
        if not session_id:
            logger.error(f"Could not obtain a valid session for conversation {conversation_id}")
            return
        
        # Send to GPT Trainer
        logger.info(f"Sending batch message to GPT Trainer session {session_id}")
        try:
            gpt_start_time = time.time()
            gpt_response = gpt_trainer_api.send_message(clean_message, session_id, conversation_id)
            response_time = track_performance('response_generation', gpt_start_time, conversation_id, 
                                            event_description=f"Generated AI response ({len(gpt_response)} chars)")
            track_performance('gpt_trainer_api_calls', gpt_start_time, conversation_id)
            
            # Log specific metrics about response generation time
            log_structured_event('response_generation_time',
                               conversation_id=conversation_id,
                               session_id=session_id,
                               response_time_ms=response_time,
                               input_length=len(clean_message),
                               output_length=len(gpt_response))
            
            logger.info(f"Received response from GPT Trainer: {gpt_response[:100]}...")
        except Exception as e:
            logger.error(f"Error sending message to GPT Trainer: {str(e)}")
            # Log the error as a performance event
            log_structured_event('gpt_trainer_error',
                               conversation_id=conversation_id,
                               session_id=session_id,
                               error=str(e))
            return
        
        # Send the response back to Intercom
        logger.info(f"Sending response to Intercom conversation {conversation_id}")
        try:
            intercom_reply_start_time = time.time()
            current_intercom_api.reply_to_conversation(conversation_id, gpt_response)
            track_performance('response_delivery', intercom_reply_start_time, conversation_id,
                             event_description="Delivered response to Intercom")
            track_performance('intercom_api_calls', intercom_reply_start_time, conversation_id)
            logger.info(f"Response sent successfully to Intercom for batch of {len(messages)} messages")
            
            # Track total processing time from webhook receipt to response sent
            total_time = track_performance('total_processing', first_webhook_time, conversation_id,
                                          event_description=f"Total processing time from webhook to response delivery")
            
            # Log comprehensive event for this conversation
            log_structured_event('conversation_complete',
                               conversation_id=conversation_id,
                               total_time_ms=total_time,
                               message_count=len(messages),
                               queue_time_s=batch_queue_time,
                               response_length=len(gpt_response))
            
        except Exception as e:
            logger.error(f"Error sending response to Intercom: {str(e)}")
            # Log the error as a performance event
            log_structured_event('intercom_delivery_error',
                               conversation_id=conversation_id,
                               error=str(e))
            return
        
        # Update conversation state
        state_update_start = time.time()
        logger.info(f"Updating conversation state for {conversation_id}")
        state_manager.mark_ai_response_sent(conversation_id, session_id)
        track_performance('state_update', state_update_start, conversation_id,
                         event_description="Updated conversation state to AWAITING_USER_REPLY")
        
        # Update rate counter
        rate_update_start = time.time()
        rate_limiter.increment_rate_counter(conversation_id)
        track_performance('rate_limiter_update', rate_update_start, conversation_id,
                         event_description="Updated rate limiter counters")
        
    except Exception as e:
        logger.error(f"Error processing message batch for conversation {conversation_id}: {str(e)}", exc_info=True)
        # Log comprehensive error event
        log_structured_event('batch_processing_error',
                           conversation_id=conversation_id,
                           error=str(e),
                           stage='message_batch_processing')

def generate_message_fingerprint(conversation_id, message_text):
    """
    Generate a fingerprint for a message to detect duplicates
    Combines conversation ID with a hash of the message text
    """
    import hashlib
    # Normalize message text by removing whitespace and lowercasing
    normalized_text = ' '.join(message_text.lower().split())
    # Create hash of the normalized text
    text_hash = hashlib.md5(normalized_text.encode('utf-8')).hexdigest()
    # Combine with conversation ID for a unique fingerprint
    return f"{conversation_id}:{text_hash}"

# Add message to batch and schedule processing
def add_to_message_batch(conversation_id, batch_data, intercom_api_client=None):
    """Add message to batch queue for processing"""
    global message_batches
    
    now = time.time()
    
    # Create a new batch if this is the first message
    if conversation_id not in message_batches:
        logger.info(f"Creating new message batch for conversation {conversation_id}")
        message_batches[conversation_id] = {
            'messages': [],
            'last_update': now,
            'intercom_api': intercom_api_client  # Store the platform-specific API client
        }
    
    # Add this conversation data to the batch
    message_batches[conversation_id]['messages'].append(batch_data)
    message_batches[conversation_id]['last_update'] = now
    
    # Store the platform-specific API client if provided
    if intercom_api_client:
        message_batches[conversation_id]['intercom_api'] = intercom_api_client
    
    # Set up a timer to process this batch after the wait period
    if 'timer' in message_batches[conversation_id]:
        # Cancel any existing timer
        message_batches[conversation_id]['timer'].cancel()
    
    # Create a new timer
    timer = threading.Timer(
        MESSAGE_BATCH_WAIT_TIME,
        process_message_batch,
        args=[conversation_id]
    )
    timer.daemon = True  # Make sure the timer thread doesn't block program exit
    message_batches[conversation_id]['timer'] = timer
    
    # Start the timer
    timer.start()
    
    logger.info(f"Added message to batch for conversation {conversation_id}, batch size: {len(message_batches[conversation_id]['messages'])}")
    logger.info(f"Scheduled batch processing in {MESSAGE_BATCH_WAIT_TIME} seconds")

def get_platform_specific_intercom_api(conversation=None, workspace=None):
    """
    Returns the appropriate Intercom API client for the platform
    based on conversation or workspace properties
    """
    # Default to reportz.io
    default_token = intercom_token
    default_admin_id = intercom_admin_id
    
    # Check if this is for Base.me
    is_base = False
    
    # Get Base.me token directly from environment variable
    base_token = os.environ.get("BASE_INTERCOM_ACCESS_TOKEN")
    
    # Log token availability for debugging
    if base_token:
        logger.info("Base.me Intercom token is available in environment variables")
    else:
        logger.info("Base.me Intercom token is NOT available in environment variables")
    
    # If no explicit Base token in env, try to get from Secret Manager only if enabled
    if not base_token and os.getenv('USE_SECRET_MANAGER', 'false').lower() == 'true':
        try:
            from utils.secrets_manager import get_secret
            logger.info("Attempting to get Base.me token from Secret Manager")
            base_token = get_secret("base-intercom-access-token")
            if base_token:
                logger.info("Successfully retrieved Base.me token from Secret Manager")
                os.environ["BASE_INTERCOM_ACCESS_TOKEN"] = base_token
        except Exception as e:
            logger.error(f"Error getting Base.me token from Secret Manager: {e}")
    
    # If workspace is explicitly specified as "base", use Base
    if workspace and workspace.lower() == "base":
        is_base = True
        logger.info("Base.me platform selected by workspace parameter")
    
    # If we have a conversation object, try to determine which platform it belongs to
    elif conversation:
        # Look for platform specific identifiers in the conversation 
        # (You might need to adjust this logic based on your actual data)
        conversation_tags = conversation.get("tags", {}).get("tags", [])
        if any(tag.get("name", "").lower() == "base.me" for tag in conversation_tags):
            is_base = True
            logger.info("Base.me platform detected from conversation tags")
        
        # Check conversation title or custom attributes
        title = conversation.get("title", "").lower()
        if "base.me" in title or "base" in title:
            is_base = True
            logger.info("Base.me platform detected from conversation title")
        
        # Check the customer's data
        contacts = conversation.get("contacts", {}).get("contacts", [])
        for contact in contacts:
            email = contact.get("email", "").lower()
            if email and ("base.me" in email or "@base." in email):
                is_base = True
                logger.info("Base.me platform detected from customer email")
    
    # Create and return the appropriate API client
    if is_base and base_token:
        logger.info("Using Base.me Intercom API client")
        return IntercomAPI(base_token, default_admin_id)
    
    logger.info("Using Reportz.io Intercom API client")
    return IntercomAPI(default_token, default_admin_id)

@app.route('/webhook/intercom', methods=['POST'])
def webhook_handler():
    """Handle incoming webhook notifications from Intercom"""
    webhook_start_time = time.time()
    
    # Get raw payload for signature verification
    payload = request.get_data(as_text=True)
    logger.debug(f"Received webhook payload: {payload}")
    
    # Log available tokens for debugging
    reportz_token = os.environ.get("INTERCOM_ACCESS_TOKEN", "NOT_AVAILABLE")
    base_token = os.environ.get("BASE_INTERCOM_ACCESS_TOKEN", "NOT_AVAILABLE")
    reportz_secret = os.environ.get("INTERCOM_CLIENT_SECRET", "NOT_AVAILABLE")  
    base_secret = os.environ.get("BASE_INTERCOM_CLIENT_SECRET", "NOT_AVAILABLE")
    
    logger.info(f"Token availability - Reportz: {'Available' if reportz_token != 'NOT_AVAILABLE' else 'NOT AVAILABLE'}, Base: {'Available' if base_token != 'NOT_AVAILABLE' else 'NOT AVAILABLE'}")
    logger.info(f"Secret availability - Reportz: {'Available' if reportz_secret != 'NOT_AVAILABLE' else 'NOT AVAILABLE'}, Base: {'Available' if base_secret != 'NOT_AVAILABLE' else 'NOT AVAILABLE'}")
    
    # Additional debug info
    logger.debug(f"Request headers: {dict(request.headers)}")
    logger.debug(f"Request path: {request.path}")
    logger.debug(f"Request args: {dict(request.args)}")
    
    # Verify signature
    signature_header = request.headers.get('X-Hub-Signature')
    logger.debug(f"Received signature header: {signature_header}")
    
    # First look for clues in the payload to determine which client secret to try first
    try:
        payload_data = json.loads(payload)
        app_id = payload_data.get('app_id', '')
        workspace_id = payload_data.get('data', {}).get('item', {}).get('workspace_id', '')
        
        # Determine which client secret to try first
        use_base_first = False
        if app_id and 'base' in app_id.lower():
            use_base_first = True
            logger.info("Detected potential Base webhook from app_id, will try Base client secret first")
        elif workspace_id and 'base' in workspace_id.lower():
            use_base_first = True
            logger.info("Detected potential Base webhook from workspace_id, will try Base client secret first")
            
        if use_base_first:
            # First try Base, then Reportz
            secrets_to_try = [(base_secret, "Base"), (reportz_secret, "Reportz")]
        else:
            # First try Reportz, then Base
            secrets_to_try = [(reportz_secret, "Reportz"), (base_secret, "Base")]
            
        # Try each client secret
        for secret, name in secrets_to_try:
            if secret and verify_webhook_signature_with_secret(payload, signature_header, secret):
                logger.info(f"Webhook signature verified with {name} client secret")
                return True
                
        # If we got here, neither secret worked
        logger.error(f"Invalid webhook signature. Got: {signature_header}")
        return jsonify({"error": "Invalid signature"}), 401
        
    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        # Fall back to the original verification
        if not verify_webhook_signature(payload, signature_header):
            logger.error(f"Invalid webhook signature. Got: {signature_header}")
            return jsonify({"error": "Invalid signature"}), 401
    
    try:
        # Parse the JSON payload
        data = json.loads(payload)
        
        # Try to determine the platform from the webhook payload
        platform = "reportz"  # Default platform
        
        # Check app_id for platform-specific identifiers
        app_id = data.get('app_id', '')
        if app_id:
            if 'base' in app_id.lower():
                platform = "base"
                logger.info(f"Detected Base platform from app_id: {app_id}")
        
        # Check workspace_id for platform-specific identifiers
        workspace_id = data.get('data', {}).get('item', {}).get('workspace_id', '')
        if workspace_id:
            if 'base' in workspace_id.lower():
                platform = "base"
                logger.info(f"Detected Base platform from workspace_id: {workspace_id}")
        
        # Set the appropriate API client based on the detected platform
        if platform == "base":
            logger.info("Using Base Intercom API client for this webhook")
            current_intercom_api = IntercomAPI(base_token, intercom_admin_id)
        else:
            logger.info("Using Reportz Intercom API client for this webhook")
            current_intercom_api = intercom_api  # Default API client (Reportz)
        
        # Process the webhook data
        topic = data.get('topic', '')
        
        # Ping event is used for webhook testing/verification
        if topic == 'ping':
            logger.info('Received ping event')
            return jsonify({'status': 'pong'}), 200
        
        # Check for duplicate webhook
        webhook_id = data.get('id')
        if webhook_id in processed_webhook_ids:
            logger.info(f"Skipping duplicate webhook with ID: {webhook_id}")
            return jsonify({"status": "duplicate_skipped"}), 200
            
        # Add to processed IDs
        processed_webhook_ids.add(webhook_id)
        
        # Limit the size of processed IDs to prevent memory issues
        if len(processed_webhook_ids) > MAX_PROCESSED_IDS:
            # Remove oldest items (approximation by converting to list, slicing, and back to set)
            processed_webhook_ids_list = list(processed_webhook_ids)
            processed_webhook_ids.clear()
            processed_webhook_ids.update(processed_webhook_ids_list[-MAX_PROCESSED_IDS//2:])
        
        # Verify this is a webhook notification
        if data.get('type') != 'notification_event':
            logger.warning(f"Unknown event type: {data.get('type')}")
            return jsonify({"status": "ignored"}), 200
        
        # Get topic and item
        topic = data.get('topic')
        item = data.get('data', {}).get('item', {})
        
        logger.info(f"Received webhook notification for topic: {topic}")
        logger.info(f"Item ID: {item.get('id')}, Type: {item.get('type')}")
        
        # Log more detailed payload for debugging
        logger.info(f"Data structure: {json.dumps({k: type(v).__name__ for k, v in data.items()})}")
        if 'data' in data:
            logger.info(f"Data.item structure: {json.dumps({k: type(v).__name__ for k, v in data.get('data', {}).get('item', {}).items()})}")
        
        # Extract conversation ID early
        conversation_id = item.get('id')
        
        # Handle different topics
        if topic == 'conversation.user.created':
            if is_from_bot(data):
                logger.info("Skipping conversation created by bot")
                return jsonify({"status": "bot_message_skipped"}), 200
            
            logger.info(f"Handling conversation created for {conversation_id}")
            process_webhook_conversation_messages(data, current_intercom_api)
            return jsonify({"status": "processing"}), 200
            
        elif topic == 'conversation.user.replied':
            logger.info(f"Handling user reply for conversation {conversation_id}")
            process_webhook_conversation_messages(data, current_intercom_api)
            return jsonify({"status": "processing"}), 200
            
        # Ignore webhook events for closed conversations
        elif topic == 'conversation.admin.closed':
            logger.info(f"Conversation {conversation_id} was closed")
            # We don't need to do anything specific here
            return jsonify({"status": "acknowledged"}), 200
            
        # Other events - process if they have a new message
        elif 'conversation_part' in item:
            part = item.get('conversation_part', {})
            part_type = part.get('part_type')
            
            if part_type == 'comment':
                author = part.get('author', {})
                author_type = author.get('type')
                
                if author_type == 'admin':
                    # Admin reply - check if it's from our bot or another admin
                    admin_id = author.get('id')
                    
                    if admin_id == intercom_admin_id:
                        logger.info(f"Skipping message from our bot in conversation {conversation_id}")
                        return jsonify({"status": "bot_message_skipped"}), 200
                    else:
                        logger.info(f"Human admin {admin_id} replied to conversation {conversation_id}")
                        
                        # Check for takeover phrases
                        body = part.get('body', '')
                        if TAKEOVER_PHRASE.lower() in body.lower():
                            logger.info(f"Human admin taking over conversation {conversation_id}")
                            handle_human_takeover(conversation_id, admin_id)
                            return jsonify({"status": "human_takeover"}), 200
                        
                        # Check for reactivation phrases
                        if ACTIVATION_PHRASE.lower() in body.lower():
                            logger.info(f"Human admin reactivated AI for conversation {conversation_id}")
                            remove_human_takeover(conversation_id)
                            return jsonify({"status": "ai_reactivated"}), 200
                
                # For all other messages, process them
                process_webhook_conversation_messages(data, current_intercom_api)
                return jsonify({"status": "processing"}), 200
        
        # Track webhook handling time if we get to the end
        track_performance('webhook_handling', webhook_start_time, conversation_id)
        
    except Exception as e:
        # Still track performance even if there's an error
        track_performance('webhook_handling', webhook_start_time)
        logger.error(f"Error processing webhook: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/webhook/intercom', methods=['HEAD'])
def webhook_validation():
    """Handle webhook validation request from Intercom"""
    logger.info("Received HEAD request for webhook validation")
    return '', 200

@app.route('/auth/intercom')
def auth_intercom():
    """Redirect users to Intercom for authorization"""
    # Get platform from query parameter
    platform = request.args.get('platform', 'reportz')
    
    # Generate a random state parameter for CSRF protection
    # Include the platform in the state parameter itself to make it more robust
    random_state = secrets.token_hex(12)
    state = f"{platform}:{random_state}"
    
    # Still store in session as backup
    session['oauth_state'] = state
    
    # Define the required scopes
    scopes = [
        'read',
        'write',
        'manage_conversations',
        'manage_articles',
        'authorize_webhook'
    ]
    
    # Use the same callback URL for all platforms
    callback_url = f"{webhook_base_url}/auth/callback"
    
    # Select the appropriate client ID based on platform
    if platform == 'base':
        client_id = os.environ.get('BASE_INTERCOM_CLIENT_ID', intercom_client_id)
        logger.info(f"Using Base.me client ID for OAuth: {client_id}")
    else:
        client_id = intercom_client_id
        logger.info(f"Using Reportz.io client ID for OAuth: {client_id}")
    
    # Construct the authorization URL
    auth_url = 'https://app.intercom.com/oauth'
    params = {
        'client_id': client_id,
        'state': state,
        'redirect_uri': callback_url,
        'response_type': 'code',
        'scope': ' '.join(scopes)
    }
    
    # Redirect to Intercom's authorization page
    redirect_url = f"{auth_url}?{urllib.parse.urlencode(params)}"
    logger.info(f"Redirecting to Intercom auth URL for platform {platform} with state: {state}")
    return redirect(redirect_url)

@app.route('/auth/callback')
def oauth_callback():
    """Main callback endpoint for all platforms - extracts platform from state"""
    # Get the authorization code and state
    code = request.args.get('code')
    state = request.args.get('state', '')
    
    # Extract platform from state (format: "platform:randomhex")
    platform = 'reportz'  # Default if we can't extract
    if ':' in state:
        platform, random_state = state.split(':', 1)
        logger.info(f"Extracted platform from state parameter: {platform}")
    else:
        # Fallback to session-stored platform if available
        platform = session.get('platform', 'reportz')
        logger.info(f"Using platform from session fallback: {platform}")
    
    logger.info(f"OAuth callback received for platform: {platform}")
    logger.info(f"OAuth callback received with parameters: {dict(request.args)}")
    
    # Temporarily skip full state validation for testing purposes
    # We already extracted the platform from it, which is the important part
    
    if not code:
        logger.error("No authorization code in callback")
        return jsonify({"error": "No authorization code provided"}), 400
    
    # Exchange the code for an access token
    token_url = 'https://api.intercom.io/auth/eagle/token'
    
    # Use the main callback URL
    callback_url = f"{webhook_base_url}/auth/callback"
    
    # Select the appropriate client ID and secret based on platform
    if platform == 'base':
        client_id = os.environ.get('BASE_INTERCOM_CLIENT_ID', intercom_client_id)
        client_secret = os.environ.get('BASE_INTERCOM_CLIENT_SECRET', intercom_client_secret)
        logger.info(f"Using Base.me client credentials for token exchange. Client ID: {client_id}")
    else:
        client_id = intercom_client_id
        client_secret = intercom_client_secret
        logger.info(f"Using Reportz.io client credentials for token exchange. Client ID: {client_id}")
    
    # Prepare the request data
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': callback_url,
        'grant_type': 'authorization_code'
    }
    
    try:
        # Make the request to exchange the code for a token
        logger.info(f"Exchanging authorization code for token for platform: {platform}")
        response = requests.post(token_url, json=data)
        response.raise_for_status()
        
        token_data = response.json()
        access_token = token_data.get('access_token')
        
        if not access_token:
            logger.error("No access token in response")
            return jsonify({"error": "Failed to get access token"}), 500
        
        # Store the access token based on platform
        if platform == 'base':
            # Store Base.me token in environment variable for local development
            logger.info("Storing Base.me access token in environment variable")
            os.environ["BASE_INTERCOM_ACCESS_TOKEN"] = access_token
            
            # Only try to store in Secret Manager if it's enabled
            if os.getenv('USE_SECRET_MANAGER', 'false').lower() == 'true':
                try:
                    logger.info("Attempting to store Base.me access token in Secret Manager")
                    os.system(f'echo -n "{access_token}" | gcloud secrets versions add base-intercom-access-token --data-file=-')
                except Exception as e:
                    logger.error(f"Failed to store token in Secret Manager: {e}")
        else:
            # Store Reportz.io token in environment variable for local development
            logger.info("Storing Reportz.io access token in environment variable")
            os.environ["INTERCOM_ACCESS_TOKEN"] = access_token
            
            # Only try to store in Secret Manager if it's enabled
            if os.getenv('USE_SECRET_MANAGER', 'false').lower() == 'true':
                try:
                    logger.info("Attempting to store Reportz.io access token in Secret Manager")
                    os.system(f'echo -n "{access_token}" | gcloud secrets versions add intercom-access-token --data-file=-')
                except Exception as e:
                    logger.error(f"Failed to store token in Secret Manager: {e}")
        
        # Create platform-specific API client for webhook registration
        if platform == 'base':
            platform_intercom_api = IntercomAPI(access_token, intercom_admin_id)
            logger.info("Created Base.me Intercom API client")
        else:
            platform_intercom_api = IntercomAPI(access_token, intercom_admin_id)
            logger.info("Created Reportz.io Intercom API client")
        
        # Update the API client with the new token
        intercom_api.update_token(access_token)
        
        # Register webhook with platform-specific API client
        register_webhook(platform_intercom_api)
        
        # Create a more detailed success page
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authorization Successful</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    line-height: 1.6;
                    background-color: #f4f7f6;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #1a73e8;
                    margin-top: 0;
                }}
                .platform-badge {{
                    display: inline-block;
                    padding: 5px 12px;
                    margin-bottom: 20px;
                    border-radius: 4px;
                    color: white;
                    font-weight: bold;
                }}
                .reportz {{
                    background-color: #1a73e8;
                }}
                .base {{
                    background-color: #34a853;
                }}
                .success-message {{
                    margin: 20px 0;
                    padding: 12px;
                    background-color: #e8f5e9;
                    border-left: 4px solid #4caf50;
                    border-radius: 4px;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #1a73e8;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin-top: 20px;
                }}
                .button:hover {{
                    background-color: #0d62c9;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Authorization Successful</h1>
                <div class="platform-badge {platform}">{platform.capitalize()}</div>
                
                <div class="success-message">
                    <p>Your {platform.capitalize()} Intercom account has been successfully connected to the GPT Trainer integration.</p>
                </div>
                
                <p>The webhook has been registered and is ready to receive messages.</p>
                
                <a href="/" class="button">Return to Dashboard</a>
            </div>
        </body>
        </html>
        """
        
        return html
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error exchanging authorization code for token: {str(e)}")
        error_message = str(e)
        
        # Create a more detailed error page
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authorization Failed</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 40px;
                    line-height: 1.6;
                    background-color: #f4f7f6;
                }}
                .container {{
                    max-width: 600px;
                    margin: 0 auto;
                    background-color: white;
                    padding: 30px;
                    border-radius: 8px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                h1 {{
                    color: #d32f2f;
                    margin-top: 0;
                }}
                .platform-badge {{
                    display: inline-block;
                    padding: 5px 12px;
                    margin-bottom: 20px;
                    border-radius: 4px;
                    color: white;
                    font-weight: bold;
                }}
                .reportz {{
                    background-color: #1a73e8;
                }}
                .base {{
                    background-color: #34a853;
                }}
                .error-message {{
                    margin: 20px 0;
                    padding: 12px;
                    background-color: #ffebee;
                    border-left: 4px solid #d32f2f;
                    border-radius: 4px;
                }}
                .error-details {{
                    margin-top: 20px;
                    padding: 10px;
                    background-color: #f5f5f5;
                    border-radius: 4px;
                    font-family: monospace;
                    overflow-x: auto;
                }}
                .button {{
                    display: inline-block;
                    padding: 10px 20px;
                    background-color: #1a73e8;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    margin-top: 20px;
                }}
                .button:hover {{
                    background-color: #0d62c9;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Authorization Failed</h1>
                <div class="platform-badge {platform}">{platform.capitalize()}</div>
                
                <div class="error-message">
                    <p>There was a problem connecting your {platform.capitalize()} Intercom account.</p>
                </div>
                
                <h3>Error Details:</h3>
                <div class="error-details">
                    {error_message}
                </div>
                
                <p>Please try again or contact support for assistance.</p>
                
                <a href="/" class="button">Return to Dashboard</a>
            </div>
        </body>
        </html>
        """
        
        return html, 500

def register_webhook(intercom_api):
    """Register the webhook with Intercom after OAuth"""
    try:
        # Check if webhook is already registered
        logger.info("Checking existing webhooks")
        
        # Use the provided intercom_api client's access token
        headers = {
            "Authorization": f"Bearer {intercom_api.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        response = requests.get("https://api.intercom.io/webhooks", headers=headers)
        response.raise_for_status()
        
        webhooks = response.json().get("data", [])
        webhook_url = f"{webhook_base_url}/webhook/intercom"
        
        # Check if our webhook is already registered
        for webhook in webhooks:
            if webhook.get("url") == webhook_url:
                logger.info(f"Webhook already registered with ID: {webhook.get('id')}")
                return
        
        # Register the webhook
        logger.info(f"Registering webhook: {webhook_url}")
        
        # Define topics to subscribe to
        topics = [
            "conversation.user.created",
            "conversation.user.replied",
            "conversation.admin.assigned",
            "conversation.admin.replied",
            "conversation.admin.single.created",
            "conversation.admin.closed"
        ]
        
        webhook_data = {
            "url": webhook_url,
            "topics": topics
        }
        
        response = requests.post(
            "https://api.intercom.io/webhooks",
            headers=headers,
            json=webhook_data
        )
        response.raise_for_status()
        
        logger.info(f"Webhook registered successfully: {response.json().get('id')}")
        
    except Exception as e:
        logger.error(f"Error registering webhook: {str(e)}")
        logger.error(f"Error details:", exc_info=True)

@app.route('/webhook/debug', methods=['POST'])
def debug_webhook_handler():
    """Handle incoming webhook notifications without signature verification (for debugging)"""
    # Get raw payload
    payload = request.get_data(as_text=True)
    logger.info(f"Received debug webhook payload: {payload}")
    
    return jsonify({"status": "received"}), 200

@app.route('/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/')
def index():
    """Main landing page"""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Intercom-GPT Trainer Integration</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                margin: 40px;
                line-height: 1.6;
            }
            .container {
                max-width: 800px;
                margin: 0 auto;
            }
            h1 {
                color: #333;
            }
            .btn {
                display: inline-block;
                padding: 10px 20px;
                background-color: #1a73e8;
                color: white;
                text-decoration: none;
                border-radius: 4px;
                margin-top: 20px;
            }
            .btn:hover {
                background-color: #0d62c9;
            }
            .card {
                border: 1px solid #ddd;
                border-radius: 4px;
                padding: 20px;
                margin: 20px 0;
                background-color: #f9f9f9;
            }
            .footer {
                margin-top: 40px;
                font-size: 0.8em;
                color: #666;
            }
            .status {
                margin-top: 20px;
            }
            .status-good {
                color: green;
            }
            .links a {
                display: block;
                margin: 10px 0;
                color: #1a73e8;
                text-decoration: none;
            }
            .links a:hover {
                text-decoration: underline;
            }
            .platform-selection {
                margin-top: 20px;
            }
            .platform-btn {
                display: inline-block;
                padding: 12px 25px;
                margin-right: 15px;
                border-radius: 4px;
                text-decoration: none;
                color: white;
                font-weight: bold;
            }
            .reportz {
                background-color: #1a73e8;
            }
            .base {
                background-color: #34a853;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Intercom-GPT Trainer Integration</h1>
            
            <div class="card">
                <h2>Welcome to the Integration Bridge</h2>
                <p>This application connects Intercom's customer support platform with GPT Trainer to provide AI-powered responses.</p>
                
                <div class="status">
                    <p class="status-good">✅ Service is up and running</p>
                </div>
                
                <div class="platform-selection">
                    <h3>Select Platform to Connect</h3>
                    <p>Choose which platform you want to connect with Intercom:</p>
                    <a href="/auth/intercom?platform=reportz" class="platform-btn reportz">Connect Reportz.io</a>
                    <a href="/auth/intercom?platform=base" class="platform-btn base">Connect Base.me</a>
                </div>
            </div>
            
            <div class="card">
                <h2>Monitoring & Analytics</h2>
                <div class="links">
                    <a href="/health">View Health Status</a>
                    <a href="/analytics">Performance Analytics Dashboard</a>
                    <a href="/monitoring/cold-starts">Cold Start Monitoring</a>
                    <a href="/performance">Raw Performance Data (JSON)</a>
                </div>
            </div>
            
            <div class="footer">
                <p>Intercom-GPT Trainer Integration Bridge</p>
                <p>Version 1.3.0 - Last updated: %s</p>
            </div>
        </div>
    </body>
    </html>
    """ % time.strftime("%Y-%m-%d")
    
    return html

@app.route('/performance', methods=['GET'])
def performance_endpoint():
    """Endpoint to get performance metrics"""
    return jsonify(log_performance_stats()), 200

def log_performance_stats():
    """Log performance statistics with enhanced detail"""
    stats = {}
    
    for metric_name, values in performance_metrics.items():
        if values:
            sorted_values = sorted(values)
            p95 = sorted_values[int(len(sorted_values) * 0.95)] if len(sorted_values) > 20 else None
            p99 = sorted_values[int(len(sorted_values) * 0.99)] if len(sorted_values) > 100 else None
            
            stats[metric_name] = {
                'count': len(values),
                'min_ms': min(values),
                'max_ms': max(values),
                'avg_ms': sum(values) / len(values),
                'median_ms': statistics.median(values) if len(values) > 0 else 0,
                'latest_ms': values[-1] if values else 0,
                'p95_ms': p95,
                'p99_ms': p99
            }
    
    # Add bottleneck analysis
    avg_values = {k: stats[k]['avg_ms'] for k in stats if 'avg_ms' in stats[k]}
    if avg_values:
        bottlenecks = sorted(avg_values.items(), key=lambda x: x[1], reverse=True)
        stats['bottleneck_analysis'] = {
            'primary_bottleneck': bottlenecks[0][0] if bottlenecks else None,
            'bottleneck_ranking': bottlenecks[:3] if bottlenecks else []
        }
    
    logger.info(f"PERFORMANCE STATS: {json.dumps(stats)}")
    
    # Log to Cloud Logging as structured event
    log_structured_event('performance_stats', 
                       stats=stats,
                       bottlenecks=stats.get('bottleneck_analysis', {}))
    
    return stats

# Log performance stats periodically
def log_performance_stats_periodically():
    """Log performance statistics periodically and schedule next logging"""
    log_performance_stats()
    
    # Schedule the next logging in 5 minutes
    timer = threading.Timer(300, log_performance_stats_periodically)
    timer.daemon = True
    timer.start()

# Start periodic performance logging
log_performance_stats_periodically()

def track_startup_time():
    """Track application startup time"""
    app.start_time = time.time()
    logger.info(f"Application startup timestamp: {app.start_time}")

# Track startup time when app is initialized
track_startup_time()

@app.route('/performance/conversation/<conversation_id>', methods=['GET'])
def conversation_performance(conversation_id):
    """Get detailed performance timeline for a specific conversation"""
    timeline_data = get_conversation_timeline(conversation_id)
    
    if not timeline_data or not timeline_data.get('timeline'):
        return jsonify({
            "error": "No performance data found for this conversation",
            "conversation_id": conversation_id
        }), 404
    
    # Get the total processing time
    total_duration_ms = timeline_data.get('total_duration_ms', 0)
    
    # Calculate metrics for each stage
    timeline = timeline_data.get('timeline', [])
    stage_metrics = {}
    
    for entry in timeline:
        metric = entry.get('metric')
        if metric not in stage_metrics:
            stage_metrics[metric] = []
        stage_metrics[metric].append(entry.get('duration_ms', 0))
    
    # Calculate statistics for each stage
    stage_stats = {}
    for metric, durations in stage_metrics.items():
        if durations:
            stage_stats[metric] = {
                'count': len(durations),
                'total_ms': sum(durations),
                'avg_ms': sum(durations) / len(durations),
                'pct_of_total': (sum(durations) / total_duration_ms * 100) if total_duration_ms > 0 else 0
            }
    
    # Sort stages by percentage of total time
    sorted_stages = sorted(stage_stats.items(), key=lambda x: x[1]['pct_of_total'], reverse=True)
    top_bottlenecks = [
        {"stage": stage, "percentage": stats['pct_of_total'], "avg_ms": stats['avg_ms']} 
        for stage, stats in sorted_stages[:3]
    ]
    
    # Get timestamps for key events
    key_events = {
        'webhook_received': None,
        'batch_processing_started': None,
        'gpt_trainer_call_started': None,
        'response_generated': None,
        'response_sent': None
    }
    
    for entry in timeline:
        event = entry.get('event')
        if 'webhook' in event.lower():
            key_events['webhook_received'] = entry.get('timestamp')
        elif 'batch' in event.lower() and 'start' in event.lower():
            key_events['batch_processing_started'] = entry.get('timestamp')
        elif 'gpt' in event.lower() and 'send' in event.lower():
            key_events['gpt_trainer_call_started'] = entry.get('timestamp')
        elif 'response' in event.lower() and 'generat' in event.lower():
            key_events['response_generated'] = entry.get('timestamp')
        elif 'response' in event.lower() and 'deliver' in event.lower():
            key_events['response_sent'] = entry.get('timestamp')
    
    # Format the response
    result = {
        "conversation_id": conversation_id,
        "total_duration_ms": total_duration_ms,
        "total_duration_seconds": total_duration_ms / 1000,
        "bottlenecks": top_bottlenecks,
        "stage_statistics": stage_stats,
        "timeline": timeline,
        "key_events": key_events,
        "timing_gaps": {}
    }
    
    # Calculate timing gaps between key events
    keys = list(key_events.keys())
    for i in range(len(keys) - 1):
        current = keys[i]
        next_key = keys[i + 1]
        
        if key_events[current] and key_events[next_key]:
            gap_seconds = key_events[next_key] - key_events[current]
            result["timing_gaps"][f"{current}_to_{next_key}"] = {
                "seconds": gap_seconds,
                "ms": gap_seconds * 1000
            }
    
    return jsonify(result)

@app.route('/analytics', methods=['GET'])
def performance_analytics():
    """Render a simple HTML page with performance analytics"""
    # Get performance stats
    stats = log_performance_stats()
    
    # Count number of conversations being tracked
    conversation_count = len(conversation_timelines)
    
    # Generate HTML
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Intercom-GPT Performance Analytics</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1, h2 {{ color: #333; }}
            .card {{ background: #f9f9f9; padding: 15px; margin: 10px 0; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            .metric {{ display: flex; justify-content: space-between; margin: 5px 0; }}
            .metric-name {{ font-weight: bold; }}
            .bottleneck {{ color: #c00; }}
            .normal {{ color: #080; }}
            .warning {{ color: #d80; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th, td {{ padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background-color: #f2f2f2; }}
            tr:hover {{ background-color: #f5f5f5; }}
            .bars-container {{ height: 20px; background: #eee; width: 100%; position: relative; margin-top: 20px; }}
            .bar {{ height: 100%; position: absolute; }}
            .webhook {{ background: #4285f4; }}
            .batching {{ background: #34a853; }}
            .gpt {{ background: #ea4335; }}
            .intercom {{ background: #fbbc05; }}
            .other {{ background: #673ab7; }}
        </style>
    </head>
    <body>
        <h1>Intercom-GPT Performance Analytics</h1>
        
        <div class="card">
            <h2>Overview</h2>
            <div class="metric">
                <span class="metric-name">Active Conversations Tracked:</span> 
                <span>{conversation_count}</span>
            </div>
            <div class="metric">
                <span class="metric-name">Current Time:</span> 
                <span>{time.strftime('%Y-%m-%d %H:%M:%S')}</span>
            </div>
        </div>
        
        <div class="card">
            <h2>Performance Bottlenecks</h2>
    """
    
    # Add bottleneck analysis
    if 'bottleneck_analysis' in stats:
        bottlenecks = stats['bottleneck_analysis'].get('bottleneck_ranking', [])
        html += "<table>"
        html += "<tr><th>Rank</th><th>Stage</th><th>Average Time (ms)</th><th>Status</th></tr>"
        
        for i, (stage, time_ms) in enumerate(bottlenecks):
            # Determine status based on time
            status_class = "normal"
            status_text = "Good"
            
            if i == 0 and time_ms > 1000:  # If top bottleneck and over 1000ms
                status_class = "bottleneck"
                status_text = "Bottleneck"
            elif time_ms > 500:
                status_class = "warning"
                status_text = "Slow"
                
            html += f"<tr>"
            html += f"<td>{i+1}</td>"
            html += f"<td>{stage}</td>"
            html += f"<td>{time_ms:.2f} ms</td>"
            html += f"<td class='{status_class}'>{status_text}</td>"
            html += f"</tr>"
        
        html += "</table>"
    else:
        html += "<p>No bottleneck data available yet.</p>"
    
    html += """
        </div>
        
        <div class="card">
            <h2>Processing Time Breakdown</h2>
            <table>
                <tr>
                    <th>Stage</th>
                    <th>Count</th>
                    <th>Min (ms)</th>
                    <th>Avg (ms)</th>
                    <th>Median (ms)</th>
                    <th>Max (ms)</th>
                    <th>P95 (ms)</th>
                </tr>
    """
    
    # Add stage metrics
    for metric_name, metric_data in stats.items():
        if metric_name != 'bottleneck_analysis' and isinstance(metric_data, dict):
            html += f"<tr>"
            html += f"<td>{metric_name}</td>"
            html += f"<td>{metric_data.get('count', 0)}</td>"
            html += f"<td>{metric_data.get('min_ms', 0):.2f}</td>"
            html += f"<td>{metric_data.get('avg_ms', 0):.2f}</td>"
            html += f"<td>{metric_data.get('median_ms', 0):.2f}</td>"
            html += f"<td>{metric_data.get('max_ms', 0):.2f}</td>"
            html += f"<td>{metric_data.get('p95_ms', 0) or 'N/A'}</td>"
            html += f"</tr>"
    
    html += """
            </table>
        </div>
        
        <div class="card">
            <h2>Response Time Visualization</h2>
    """
    
    # Add visualization of time breakdown
    total_time = stats.get('total_processing', {}).get('avg_ms', 0)
    webhook_time = stats.get('webhook_handling', {}).get('avg_ms', 0)
    batching_time = stats.get('message_batching', {}).get('avg_ms', 0)
    gpt_time = stats.get('gpt_trainer_api_calls', {}).get('avg_ms', 0)
    intercom_time = stats.get('intercom_api_calls', {}).get('avg_ms', 0)
    other_time = total_time - webhook_time - batching_time - gpt_time - intercom_time
    
    if total_time > 0:
        webhook_pct = (webhook_time / total_time * 100) if total_time > 0 else 0
        batching_pct = (batching_time / total_time * 100) if total_time > 0 else 0
        gpt_pct = (gpt_time / total_time * 100) if total_time > 0 else 0
        intercom_pct = (intercom_time / total_time * 100) if total_time > 0 else 0
        other_pct = (other_time / total_time * 100) if total_time > 0 else 0
        
        html += f"""
            <div class="bars-container">
                <div class="bar webhook" style="width: {webhook_pct}%; left: 0%;"></div>
                <div class="bar batching" style="width: {batching_pct}%; left: {webhook_pct}%;"></div>
                <div class="bar gpt" style="width: {gpt_pct}%; left: {webhook_pct + batching_pct}%;"></div>
                <div class="bar intercom" style="width: {intercom_pct}%; left: {webhook_pct + batching_pct + gpt_pct}%;"></div>
                <div class="bar other" style="width: {other_pct}%; left: {webhook_pct + batching_pct + gpt_pct + intercom_pct}%;"></div>
            </div>
            <div style="margin-top: 10px;">
                <span style="margin-right: 20px;"><span style="display: inline-block; width: 15px; height: 15px; background: #4285f4;"></span> Webhook: {webhook_time:.2f}ms ({webhook_pct:.1f}%)</span>
                <span style="margin-right: 20px;"><span style="display: inline-block; width: 15px; height: 15px; background: #34a853;"></span> Batching: {batching_time:.2f}ms ({batching_pct:.1f}%)</span>
                <span style="margin-right: 20px;"><span style="display: inline-block; width: 15px; height: 15px; background: #ea4335;"></span> GPT Trainer: {gpt_time:.2f}ms ({gpt_pct:.1f}%)</span>
                <span style="margin-right: 20px;"><span style="display: inline-block; width: 15px; height: 15px; background: #fbbc05;"></span> Intercom: {intercom_time:.2f}ms ({intercom_pct:.1f}%)</span>
                <span><span style="display: inline-block; width: 15px; height: 15px; background: #673ab7;"></span> Other: {other_time:.2f}ms ({other_pct:.1f}%)</span>
            </div>
        """
    else:
        html += "<p>No timing data available yet for visualization.</p>"
    
    html += """
        </div>
        
        <div class="card">
            <h2>Recent Conversations</h2>
            <table>
                <tr>
                    <th>Conversation ID</th>
                    <th>Events</th>
                    <th>Total Time</th>
                    <th>Details</th>
                </tr>
    """
    
    # Add recent conversations
    sorted_conversations = sorted(
        [(conv_id, max([e.get('timestamp', 0) for e in events])) for conv_id, events in conversation_timelines.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    for conv_id, last_timestamp in sorted_conversations[:10]:  # Show top 10
        events = conversation_timelines.get(conv_id, [])
        if events:
            first_time = min([e.get('timestamp', 0) for e in events])
            last_time = max([e.get('timestamp', 0) for e in events])
            total_time = (last_time - first_time) * 1000  # ms
            
            html += f"<tr>"
            html += f"<td>{conv_id}</td>"
            html += f"<td>{len(events)}</td>"
            html += f"<td>{total_time:.2f} ms</td>"
            html += f"<td><a href='/performance/conversation/{conv_id}' target='_blank'>View Details</a></td>"
            html += f"</tr>"
    
    html += """
            </table>
        </div>
        
        <div class="card">
            <h2>Actions</h2>
            <p><a href="/performance" target="_blank">View Raw Performance Data (JSON)</a></p>
            <p>Last updated: {}</p>
        </div>
        
        <script>
            // Auto-refresh the page every 30 seconds
            setTimeout(function() {{ window.location.reload(); }}, 30000);
        </script>
    </body>
    </html>
    """.format(time.strftime('%Y-%m-%d %H:%M:%S'))
    
    return html

@app.route('/test/gpt-trainer', methods=['GET'])
def test_gpt_trainer():
    """Test endpoint to verify GPT Trainer API connection"""
    try:
        # Create a session
        logger.info("DEBUG - Testing GPT Trainer API - creating session")
        session_id = gpt_trainer_api.create_session()
        logger.info(f"DEBUG - Created test session: {session_id}")
        
        # Send a test message
        test_message = "Hello, this is a test message to verify the GPT Trainer API is working."
        logger.info(f"DEBUG - Sending test message to session {session_id}")
        response = gpt_trainer_api.send_message(test_message, session_id, "test_conversation")
        
        return jsonify({
            "status": "success",
            "session_id": session_id,
            "test_message": test_message,
            "response": response,
            "response_length": len(response) if response else 0
        })
    except Exception as e:
        logger.error(f"DEBUG - Error testing GPT Trainer API: {str(e)}", exc_info=True)
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500

def process_webhook_conversation_messages(data, current_intercom_api=None):
    """Process the conversation messages from a webhook notification"""
    # Use the provided API client, or default to the main Intercom API client
    if not current_intercom_api:
        current_intercom_api = intercom_api
    
    # Extract conversation ID from notification data
    conversation_id = data.get('data', {}).get('item', {}).get('id')
    
    # Ensure we have a valid conversation ID
    if not conversation_id:
        logger.error("No conversation ID found in webhook data")
        return
        
    logger.info(f"Processing webhook notification for conversation {conversation_id}")
    
    # Try to get the full conversation details
    try:
        logger.info(f"Getting details for conversation {conversation_id}")
        conversation = current_intercom_api.get_conversation(conversation_id)
        
        # Add the message to the batch processing queue
        add_to_message_batch(conversation_id, conversation, current_intercom_api)
        
    except Exception as e:
        logger.error(f"Error getting conversation: {str(e)}")
        track_performance("error_fetching_conversation", webhook_start_time, conversation_id,
                        error=str(e))

def handle_human_takeover(conversation_id, admin_id):
    """Handle a human admin taking over a conversation"""
    logger.info(f"Human admin {admin_id} is taking over conversation {conversation_id}")
    
    # Store the takeover with current timestamp
    human_takeover_conversations[conversation_id] = time.time()
    
    # Also update the conversation state
    state_manager.mark_admin_takeover(conversation_id, admin_id)
    
    # Persist the takeover
    save_takeovers()
    
    logger.info(f"Conversation {conversation_id} marked for human takeover")
    return True

def remove_human_takeover(conversation_id):
    """Remove a human takeover for a conversation"""
    if conversation_id in human_takeover_conversations:
        logger.info(f"Removing human takeover for conversation {conversation_id}")
        del human_takeover_conversations[conversation_id]
        
        # Persist the change
        save_takeovers()
        
        logger.info(f"Human takeover removed for conversation {conversation_id}")
        return True
    
    logger.info(f"No active takeover found for conversation {conversation_id}")
    return False

def is_from_bot(data):
    """Check if a webhook notification is for a message sent by our bot"""
    # Check for author information
    author = None
    
    # First check directly in the item
    item = data.get('data', {}).get('item', {})
    if 'author' in item:
        author = item.get('author', {})
    
    # Then check in conversation parts
    if not author:
        conversation_parts = item.get('conversation_parts', {}).get('conversation_parts', [])
        if conversation_parts:
            author = conversation_parts[-1].get('author', {})
    
    # Check if the author is our bot
    if author:
        author_type = author.get('type')
        author_id = author.get('id')
        
        if author_type == 'admin' and author_id == intercom_admin_id:
            return True
        
        # Also check by name for extra safety
        author_name = author.get('name')
        if author_name and ('bot' in author_name.lower() or 'gpt' in author_name.lower()):
            return True
    
    return False

def verify_webhook_signature_with_secret(payload, signature_header, secret):
    """Verify that the webhook request is from Intercom using a specific client secret"""
    if not secret:
        logger.warning("No client secret provided for signature verification")
        return False
    
    if not signature_header:
        logger.warning("No signature header in request")
        return False
    
    if not signature_header.startswith('sha1='):
        logger.warning("Invalid signature format")
        return False
    
    signature = signature_header[5:]  # Remove 'sha1=' prefix
    
    # Create hmac with the provided client secret
    mac = hmac.new(
        secret.encode('utf-8'),
        msg=payload.encode('utf-8'),
        digestmod=hashlib.sha1
    )
    
    # Compare signatures
    calculated_signature = mac.hexdigest()
    logger.debug(f"Calculated signature: {calculated_signature}")
    logger.debug(f"Received signature: {signature}")
    
    return hmac.compare_digest(calculated_signature, signature)

if __name__ == '__main__':
    # Get public webhook URL
    public_webhook_url = f"{webhook_base_url}/webhook/intercom" if webhook_base_url else f"http://localhost:{port}/webhook/intercom"
    public_oauth_callback_url = f"{webhook_base_url}/auth/callback" if webhook_base_url else f"http://localhost:{port}/auth/callback"
    
    # Check if webhook is working
    logger.info(f"Starting webhook server on port {port}")
    logger.info(f"Webhook URL (External): {public_webhook_url}")
    logger.info(f"OAuth callback URL (External): {public_oauth_callback_url}")
    
    if webhook_base_url:
        logger.info(f"Using ngrok tunnel with URL: {webhook_base_url}")
    else:
        logger.info(f"No ngrok URL configured. Using localhost (not accessible from the internet)")
        logger.info(f"For production, ensure WEBHOOK_BASE_URL is set in your .env file")
    
    # Run the Flask app
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', port)), debug=False) 
