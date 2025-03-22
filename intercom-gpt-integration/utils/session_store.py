import json
import os
import logging
from datetime import datetime, timedelta
from utils.persistence import PersistenceManager

logger = logging.getLogger(__name__)

# Conversation states
AWAITING_USER_REPLY = "awaiting_user_reply"  # Waiting for user to reply to an AI message
READY_FOR_RESPONSE = "ready_for_response"    # User has replied, AI can respond
ADMIN_TAKEOVER = "admin_takeover"            # A human admin has taken over the conversation

class SessionStore:
    """Manages GPT Trainer session IDs for Intercom conversations"""
    
    def __init__(self, storage_path=None, expiry_hours=24):
        self.storage_path = storage_path or "sessions.json"
        self.expiry_hours = expiry_hours
        self.sessions = {}
        self._load_sessions()
    
    def get_session(self, conversation_id):
        """Get session ID for a conversation"""
        self._cleanup_expired()
        
        session_data = self.sessions.get(conversation_id)
        if not session_data:
            return None
            
        # Check if session is expired
        expiry = datetime.fromisoformat(session_data['expiry'])
        if expiry < datetime.now():
            logger.info(f"Session for conversation {conversation_id} expired")
            del self.sessions[conversation_id]
            self._save_sessions()
            return None
            
        return session_data['session_id']
    
    def get_conversation_state(self, conversation_id):
        """Get the current state of a conversation"""
        self._cleanup_expired()
        
        session_data = self.sessions.get(conversation_id)
        if not session_data:
            # If no session exists, it's ready for a response
            return READY_FOR_RESPONSE
            
        # Return the conversation state or default to ready
        return session_data.get('state', READY_FOR_RESPONSE)
    
    def is_awaiting_user_reply(self, conversation_id):
        """Check if we're waiting for a user reply for this conversation"""
        return self.get_conversation_state(conversation_id) == AWAITING_USER_REPLY
    
    def mark_awaiting_user_reply(self, conversation_id, session_id):
        """Mark a conversation as waiting for user reply after sending an AI response"""
        session_data = self.sessions.get(conversation_id)
        
        # Create or update the session data
        if not session_data:
            self.save_session(conversation_id, session_id, AWAITING_USER_REPLY)
        else:
            session_data['state'] = AWAITING_USER_REPLY
            session_data['last_ai_response_time'] = datetime.now().isoformat()
            self._save_sessions()
            
        logger.info(f"Marked conversation {conversation_id} as awaiting user reply")
    
    def mark_ready_for_response(self, conversation_id):
        """Mark a conversation as ready for an AI response after user has replied"""
        session_data = self.sessions.get(conversation_id)
        
        if session_data:
            session_data['state'] = READY_FOR_RESPONSE
            session_data['last_user_reply_time'] = datetime.now().isoformat()
            self._save_sessions()
            
            logger.info(f"Marked conversation {conversation_id} as ready for response")
            return True
        
        return False
    
    def get_all_sessions(self):
        """Get all active sessions as a dictionary of conversation_id -> session_id"""
        self._cleanup_expired()
        
        active_sessions = {}
        for conv_id, session_data in self.sessions.items():
            active_sessions[conv_id] = session_data['session_id']
        
        return active_sessions
    
    def remove_session(self, conversation_id):
        """Remove a session for a conversation."""
        if conversation_id in self.sessions:
            del self.sessions[conversation_id]
            self._save_sessions()
            logger.info(f"Removed session for conversation {conversation_id}")
            return True
        return False
    
    def save_session(self, conversation_id, session_id, state=READY_FOR_RESPONSE):
        """Save a session ID for a conversation"""
        expiry = datetime.now() + timedelta(hours=self.expiry_hours)
        
        self.sessions[conversation_id] = {
            'session_id': session_id,
            'created': datetime.now().isoformat(),
            'expiry': expiry.isoformat(),
            'state': state,
            'last_user_reply_time': datetime.now().isoformat(),
            'last_ai_response_time': None
        }
        
        logger.info(f"Saved session {session_id} for conversation {conversation_id} with state {state}")
        self._save_sessions()
        return True
    
    def _cleanup_expired(self):
        """Remove expired sessions"""
        now = datetime.now()
        expired = []
        
        for conv_id, session_data in self.sessions.items():
            expiry = datetime.fromisoformat(session_data['expiry'])
            if expiry < now:
                expired.append(conv_id)
                
        if expired:
            for conv_id in expired:
                del self.sessions[conv_id]
            logger.info(f"Cleaned up {len(expired)} expired sessions")
            self._save_sessions()
    
    def _load_sessions(self):
        """Load sessions from storage"""
        self.sessions = PersistenceManager.load_json_data(self.storage_path, default={})
            
        # Ensure all sessions have a state field (backward compatibility)
        for conv_id, session_data in self.sessions.items():
            if 'state' not in session_data:
                session_data['state'] = READY_FOR_RESPONSE
                session_data['last_user_reply_time'] = session_data.get('created')
                session_data['last_ai_response_time'] = None
                
        logger.info(f"Loaded {len(self.sessions)} sessions from storage")
    
    def _save_sessions(self):
        """Save sessions to storage"""
        PersistenceManager.save_json_data(self.storage_path, self.sessions)
        logger.debug(f"Saved {len(self.sessions)} sessions to storage")
    
    def mark_admin_takeover(self, conversation_id, admin_id):
        """Mark a conversation as taken over by a human admin
        
        Args:
            conversation_id: The ID of the conversation
            admin_id: The ID of the admin who took over
            
        Returns:
            bool: True if successfully marked, False otherwise
        """
        self._cleanup_expired()
        
        if conversation_id not in self.sessions:
            # Create a new session entry for this conversation
            self.sessions[conversation_id] = {
                'session_id': None,  # No GPT Trainer session needed
                'state': ADMIN_TAKEOVER,
                'expiry': (datetime.now() + timedelta(hours=self.expiry_hours)).isoformat(),
                'admin_id': admin_id
            }
        else:
            # Update existing session
            self.sessions[conversation_id]['state'] = ADMIN_TAKEOVER
            self.sessions[conversation_id]['admin_id'] = admin_id
            # Refresh expiry
            self.sessions[conversation_id]['expiry'] = (datetime.now() + timedelta(hours=self.expiry_hours)).isoformat()
        
        self._save_sessions()
        logger.info(f"Marked conversation {conversation_id} as taken over by admin {admin_id}")
        return True 
