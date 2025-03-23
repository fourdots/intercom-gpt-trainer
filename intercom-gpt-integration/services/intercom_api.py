import requests
import time
import logging
import json
from utils.retry import retry

logger = logging.getLogger(__name__)

class IntercomAPI:
    """API client for Intercom"""
    
    def __init__(self, token, admin_id, base_url=None):
        """Initialize the API client
        
        Args:
            token (str): Intercom API token
            admin_id (str): Intercom admin ID for sending replies
            base_url (str, optional): Custom API base URL. Defaults to the standard Intercom API URL.
        """
        self.access_token = token
        self.admin_id = admin_id
        self.base_url = base_url or "https://api.intercom.io"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        logging.info(f"Initialized Intercom API client with admin ID: {admin_id}")
        logging.info(f"Using API base URL: {self.base_url}")
        logging.info(f"API Token (truncated): {token[:10]}...")
    
    def update_token(self, new_token):
        """Update the API token
        
        Args:
            new_token (str): New Intercom API token
        """
        self.access_token = new_token
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json"
        }
        logging.info(f"Updated Intercom API token (truncated): {new_token[:10]}...")
    
    @retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0, max_delay=10.0)
    def list_conversations(self, per_page=25, state="open", sort="updated_at", order="desc"):
        """List conversations from Intercom"""
        try:
            params = {
                "per_page": per_page,
                "state": state,
                "sort": sort,
                "order": order
            }
            
            url = f"{self.base_url}/conversations"
            response = requests.get(url, headers=self.headers, params=params)
            self._handle_rate_limits(response)
            response.raise_for_status()
            
            data = response.json()
            return data.get('conversations', [])
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error listing conversations: {e}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error listing conversations: {e}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout listing conversations: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error listing conversations: {e}")
            raise
    
    @retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0, max_delay=10.0)
    def get_conversation(self, conversation_id):
        """Get a specific conversation by ID"""
        try:
            url = f"{self.base_url}/conversations/{conversation_id}"
            logger.debug(f"Getting conversation {conversation_id} from {url}")
            
            response = requests.get(url, headers=self.headers)
            
            logger.debug(f"Response status code: {response.status_code}")
            
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error retrieving conversation {conversation_id}: {e}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error retrieving conversation {conversation_id}: {e}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout retrieving conversation {conversation_id}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error retrieving conversation {conversation_id}: {e}")
            raise
    
    @retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0, max_delay=10.0)
    def reply_to_conversation(self, conversation_id, message, admin_id=None):
        """Send a reply to a conversation"""
        try:
            url = f"{self.base_url}/conversations/{conversation_id}/reply"
            
            admin_id = admin_id or self.admin_id
            payload = {
                "type": "admin",
                "admin_id": admin_id,
                "message_type": "comment",
                "body": f"<p>{message}</p>"
            }
            
            logger.debug(f"Replying to conversation {conversation_id}")
            response = requests.post(url, headers=self.headers, json=payload)
            
            logger.debug(f"Response status code: {response.status_code}")
            
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error replying to conversation {conversation_id}: {e}")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Connection error replying to conversation {conversation_id}: {e}")
            raise
        except requests.exceptions.Timeout as e:
            logger.error(f"Timeout replying to conversation {conversation_id}: {e}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"Error replying to conversation {conversation_id}: {e}")
            raise
    
    @retry(max_attempts=3, initial_delay=1.0, backoff_factor=2.0, max_delay=10.0)
    def mark_conversation_read(self, conversation_id):
        """Mark a conversation as read"""
        try:
            url = f"{self.base_url}/conversations/{conversation_id}/read"
            response = requests.put(url, headers=self.headers)
            self._handle_rate_limits(response)
            response.raise_for_status()
            
            return True
            
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error marking conversation {conversation_id} as read: {e}")
            return False
        except Exception as e:
            logger.error(f"Error marking conversation {conversation_id} as read: {e}")
            return False
    
    def _handle_rate_limits(self, response):
        """Handle Intercom API rate limits"""
        try:
            remaining = int(response.headers.get('X-RateLimit-Remaining', 1000))
            if remaining < 10:
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                current_time = int(time.time())
                sleep_time = max(0, reset_time - current_time) + 1  # Add 1 second buffer
                
                if sleep_time > 0:
                    logger.warning(f"Rate limit nearly reached ({remaining} remaining). Sleeping for {sleep_time}s")
                    time.sleep(sleep_time)
        except Exception as e:
            logger.warning(f"Error handling rate limits: {e}") 
