"""
Google Cloud Secret Manager integration for Intercom-GPT Trainer.
"""
import os
from dotenv import load_dotenv

# Try to load from .env file for local development
load_dotenv()

class SecretsManager:
    """Manage Google Cloud Secret Manager access"""
    
    def __init__(self, project_id=None):
        self.use_secret_manager = os.getenv('USE_SECRET_MANAGER', 'false').lower() == 'true'
        self.project_id = project_id or os.getenv('PROJECT_ID', 'intercom-gpt-integration')
        self.project_path = f"projects/{self.project_id}"
        self.client = None
        
        if self.use_secret_manager:
            from google.cloud import secretmanager
            self.client = secretmanager.SecretManagerServiceClient()
    
    def get_secret(self, secret_id, version_id="latest"):
        """Get a secret value from Secret Manager"""
        if not self.use_secret_manager or not self.client:
            # Fall back to environment variable
            return os.getenv(secret_id.replace('-', '_').upper())
            
        try:
            name = f"{self.project_path}/secrets/{secret_id}/versions/{version_id}"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            print(f"Error accessing secret {secret_id}: {e}")
            # Fall back to environment variable
            return os.getenv(secret_id.replace('-', '_').upper())
    
    def load_application_secrets(self):
        """Load all application secrets"""
        # Secret names in Secret Manager
        secret_mappings = {
            "INTERCOM_ACCESS_TOKEN": "intercom-access-token",
            "INTERCOM_ADMIN_ID": "intercom-admin-id",
            "INTERCOM_CLIENT_ID": "intercom-client-id",
            "INTERCOM_CLIENT_SECRET": "intercom-client-secret",
            "GPT_TRAINER_API_KEY": "gpt-trainer-api-key",
            "CHATBOT_UUID": "chatbot-uuid"
        }
        
        secrets = {}
        
        # If using Secret Manager, get secrets from there
        if self.use_secret_manager and self.client:
            for env_var, secret_id in secret_mappings.items():
                secrets[env_var] = self.get_secret(secret_id)
        else:
            # Otherwise, use environment variables
            for env_var in secret_mappings.keys():
                secrets[env_var] = os.getenv(env_var)
                
        return secrets

def get_configuration():
    """Get application configuration from environment or Secret Manager"""
    # Create SecretsManager instance
    secrets_manager = SecretsManager()
    
    # Load secrets
    secrets = secrets_manager.load_application_secrets()
    
    # Add non-secret configuration
    config = {
        # Secrets
        **secrets,
        
        # Non-secret configuration
        'POLLING_INTERVAL': int(os.getenv('POLLING_INTERVAL', '60')),
        'MAX_CONVERSATIONS': int(os.getenv('MAX_CONVERSATIONS', '25')),
        'PORT': int(os.getenv('PORT', '8080')),
        'USE_SECRET_MANAGER': secrets_manager.use_secret_manager,
        'GPT_TRAINER_API_URL': os.getenv('GPT_TRAINER_API_URL', 'https://app.gpt-trainer.com/api/v1')
    }
    
    return config
