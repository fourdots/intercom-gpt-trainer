import requests
import logging
import json
from utils.retry import retry

logger = logging.getLogger(__name__)

class GPTTrainerAPI:
    """Client for interacting with the GPT Trainer API"""
    
    def __init__(self, api_key, chatbot_uuid, api_url="https://app.gpt-trainer.com/api/v1"):
        self.api_key = api_key
        self.chatbot_uuid = chatbot_uuid
        self.api_url = api_url
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        logger.info(f"Initialized GPT Trainer API client with endpoint: {api_url}")
        logger.info(f"Using chatbot UUID: {chatbot_uuid}")
        # Log a truncated version of the API key for debugging (first 10 chars)
        logger.info(f"API Key (truncated): {api_key[:10]}...")
    
    @retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0, max_delay=10.0)
    def create_session(self):
        """Create a new GPT Trainer session"""
        try:
            url = f"{self.api_url}/chatbot/{self.chatbot_uuid}/session/create"
            logger.info(f"Creating new session at: {url}")
            
            response = requests.post(url, headers=self.headers)
            
            # Log response status and headers for debugging
            logger.info(f"Session creation response status: {response.status_code}")
            logger.debug(f"Response headers: {dict(response.headers)}")
            
            # Handle non-200 responses with detailed logging
            if response.status_code != 200:
                error_msg = f"Failed to create session. Status: {response.status_code}"
                try:
                    error_detail = response.json()
                    logger.error(f"{error_msg}. Details: {json.dumps(error_detail)}")
                except:
                    logger.error(f"{error_msg}. Response text: {response.text}")
                response.raise_for_status()
            
            # Try to parse the response
            try:
                data = response.json()
                logger.debug(f"Session creation response: {json.dumps(data)}")
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {response.text}")
                raise ValueError("Invalid JSON response from GPT Trainer API")
            
            # Look for session ID in response (API returns 'uuid' instead of 'session_id')
            session_id = data.get('session_id') or data.get('uuid')
            
            if not session_id:
                logger.error(f"No session_id or uuid in response: {json.dumps(data)}")
                raise ValueError("No session ID returned from GPT Trainer API")
                
            logger.info(f"Created new GPT Trainer session: {session_id}")
            return session_id
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error creating session: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Error creating session: {e}", exc_info=True)
            raise
    
    @retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0, max_delay=10.0)
    def send_message(self, message, session_id, conversation_id=None):
        """Send a message to GPT Trainer and get a response with detailed performance tracking"""
        try:
            import time
            from utils.logging_setup import log_structured_event
            
            start_time = time.time()
            stage_timings = {}
            
            # Record start time
            stage_timings['start'] = start_time
            
            # Prepare request
            url = f"{self.api_url}/session/{session_id}/message/stream"
            logger.info(f"Sending message to session {session_id} at: {url}")
            
            # Use a simplified payload with only the essential fields
            payload = {
                "query": message,
                "stream": False
            }
            
            # Add conversation_id directly in the payload if provided
            if conversation_id:
                payload["conversation_id"] = str(conversation_id)
                logger.info(f"Including Intercom conversation ID ({conversation_id}) in payload")
            
            # Record request preparation time
            stage_timings['request_prepared'] = time.time()
            request_prep_ms = (stage_timings['request_prepared'] - stage_timings['start']) * 1000
            logger.info(f"PERFORMANCE: GPT request preparation took {request_prep_ms:.2f}ms")
            
            logger.debug(f"Request payload: {json.dumps(payload)}")
            
            # Send the request and record the time
            stage_timings['request_sent'] = time.time()
            request_time_ms = (stage_timings['request_sent'] - stage_timings['request_prepared']) * 1000
            logger.info(f"PERFORMANCE: GPT request preparation to sending took {request_time_ms:.2f}ms")
            
            # Make the actual API call with timeout
            logger.info(f"PERFORMANCE: Sending request to GPT Trainer API at {time.time()}")
            logger.info(f"DEBUG - Sending to GPT Trainer - URL: {url}")
            logger.info(f"DEBUG - Payload: {json.dumps(payload)}")
            logger.info(f"DEBUG - Headers: {json.dumps({k: v if k != 'Authorization' else 'Bearer [REDACTED]' for k, v in self.headers.items()})}")
            response = requests.post(url, headers=self.headers, json=payload, timeout=120)  # 2 minute timeout
            
            # Record response received time
            stage_timings['response_received'] = time.time()
            api_call_time_ms = (stage_timings['response_received'] - stage_timings['request_sent']) * 1000
            logger.info(f"PERFORMANCE: GPT API call took {api_call_time_ms:.2f}ms for conversation {conversation_id}")
            
            # Log response status and headers for debugging
            logger.info(f"Message response status: {response.status_code}")
            logger.info(f"DEBUG - Response headers: {dict(response.headers)}")
            logger.info(f"DEBUG - Response content (first 500 chars): {response.text[:500]}")
            
            # Handle non-200 responses with detailed logging
            if response.status_code != 200:
                error_msg = f"Failed to send message. Status: {response.status_code}"
                try:
                    error_detail = response.json()
                    logger.error(f"{error_msg}. Details: {json.dumps(error_detail)}")
                except:
                    logger.error(f"{error_msg}. Response text: {response.text}")
                
                # Log the error timing
                log_structured_event('gpt_trainer_error_timing', 
                                 conversation_id=conversation_id,
                                 session_id=session_id,
                                 status_code=response.status_code,
                                 total_time_ms=api_call_time_ms)
                
                response.raise_for_status()
            
            # Get the raw response text
            raw_response = response.text
            logger.debug(f"Raw response text: {raw_response[:100]}...")  # Print first 100 chars
            
            # Record parsing start time
            stage_timings['parsing_start'] = time.time()
            response_fetch_ms = (stage_timings['parsing_start'] - stage_timings['response_received']) * 1000
            logger.info(f"PERFORMANCE: GPT response text fetch took {response_fetch_ms:.2f}ms")
            
            # Try to parse as JSON, but don't fail if it's not valid JSON
            ai_message = None
            try:
                data = response.json()
                logger.debug(f"Message response parsed as JSON: {json.dumps(data)}")
                
                # Check common response fields
                if 'response' in data:
                    ai_message = data.get('response')
                elif 'text' in data:
                    ai_message = data.get('text')
                elif 'message' in data:
                    ai_message = data.get('message')
                elif 'answer' in data:
                    ai_message = data.get('answer')
                elif 'content' in data:
                    ai_message = data.get('content')
                
                # If we still couldn't find a response, log everything
                if not ai_message:
                    logger.warning(f"Could not find AI response in the message data structure")
                    
                    # Try to find any string fields that might contain the response
                    for key, value in data.items():
                        if isinstance(value, str) and len(value) > 5:  # Looks like it could be content
                            logger.info(f"Possible response field '{key}': {value[:50]}...")
                            if not ai_message:  # Use the first one we find
                                ai_message = value
            
            except json.JSONDecodeError:
                # If not JSON, use the raw response text as the AI message
                logger.info("Response is not valid JSON, using raw text as response")
                ai_message = raw_response
            
            # Record parsing complete time
            stage_timings['parsing_complete'] = time.time()
            parsing_time_ms = (stage_timings['parsing_complete'] - stage_timings['parsing_start']) * 1000
            logger.info(f"PERFORMANCE: GPT response parsing took {parsing_time_ms:.2f}ms")
            
            # Record total time
            stage_timings['complete'] = time.time()
            total_time_ms = (stage_timings['complete'] - stage_timings['start']) * 1000
            
            if not ai_message:
                logger.warning(f"Empty response received from GPT Trainer for session {session_id}")
            
            # Log detailed timing for this API call
            log_structured_event('gpt_trainer_timing', 
                             conversation_id=conversation_id,
                             session_id=session_id,
                             total_time_ms=total_time_ms,
                             api_call_time_ms=api_call_time_ms,
                             response_size=len(raw_response),
                             request_size=len(message),
                             stage_timings={k: v - start_time for k, v in stage_timings.items()})
            
            # Log comprehensive summary message for easy filtering in logs
            logger.info(f"GPT TIMING SUMMARY for {conversation_id}: " +
                       f"Total={total_time_ms:.0f}ms, " +
                       f"API Call={api_call_time_ms:.0f}ms, " +
                       f"Prep={request_time_ms:.0f}ms, " +
                       f"Parse={parsing_time_ms:.0f}ms")
            
            return ai_message or ""
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error sending message to session {session_id}: {e}", exc_info=True)
            
            # Log the error with timing if we have conversation_id
            if conversation_id and 'start_time' in locals():
                error_time_ms = (time.time() - start_time) * 1000
                log_structured_event('gpt_trainer_request_error', 
                                 conversation_id=conversation_id,
                                 session_id=session_id,
                                 error=str(e),
                                 time_ms=error_time_ms)
            
            raise
        except Exception as e:
            logger.error(f"Error sending message to session {session_id}: {e}", exc_info=True)
            
            # Log the error with timing if we have conversation_id
            if conversation_id and 'start_time' in locals():
                error_time_ms = (time.time() - start_time) * 1000
                log_structured_event('gpt_trainer_general_error', 
                                 conversation_id=conversation_id,
                                 session_id=session_id,
                                 error=str(e),
                                 time_ms=error_time_ms)
            
            raise 
