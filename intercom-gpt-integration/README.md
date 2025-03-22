# Intercom-GPT Trainer Integration

This project integrates Intercom's customer messaging platform with GPT Trainer's AI chatbot service. The integration enables an AI-powered customer support experience by fetching customer messages from Intercom's API, processing them with GPT Trainer, and sending AI-generated responses back to customers through Intercom.

## Features

- Real-time message processing via Intercom webhooks
- AI response generation using GPT Trainer
- Automatic responses sent back to Intercom conversations
- Conversation context maintained across messages
- Human agent takeover detection
- Session management for conversation persistence

## Requirements

- Python 3.8+
- Intercom account with API access
- GPT Trainer account with API access
- For deployment: Google Cloud account

## Installation

1. Clone the repository:
```bash
git clone https://github.com/your-org/intercom-gpt-integration.git
cd intercom-gpt-integration
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up environment variables:
   - Copy `.env.example` to `.env`
   - Fill in your Intercom and GPT Trainer credentials

## Configuration

Edit the `.env` file with your credentials:

```
# Intercom Configuration
INTERCOM_ACCESS_TOKEN=your_intercom_access_token
INTERCOM_ADMIN_ID=your_admin_id
INTERCOM_CLIENT_SECRET=your_intercom_client_secret
INTERCOM_CLIENT_ID=your_intercom_client_id

# GPT Trainer Configuration
GPT_TRAINER_API_KEY=your_gpt_trainer_api_key
CHATBOT_UUID=your_chatbot_uuid
GPT_TRAINER_API_URL=https://app.gpt-trainer.com/api/v1

# Application Configuration
PORT=8080  # Port for the webhook server
```

## Local Usage

Run the webhook server:

```bash
python webhook_server.py
```

For local webhook testing, use ngrok to expose your local server:

```bash
ngrok http 8080
```

Then update your Intercom webhook URL with the ngrok URL.

## Google Cloud Deployment

This project is configured for deployment to Google Cloud Run. Follow these steps:

1. Set up Google Cloud:
```bash
./setup_gcloud.sh
```

2. Deploy to Google Cloud Run:
```bash
./deploy.sh
```

3. Update your Intercom webhook URL with the Cloud Run service URL.

## Docker

For local development with Docker:

```bash
docker-compose up
```

For building the container for Google Cloud:

```bash
docker-compose build cloud-build
```

## Architecture

```
┌───────────┐         ┌──────────────┐         ┌───────────────┐
│  Intercom │         │ Integration  │         │  GPT Trainer  │
│  Platform │◄────────┤ Service      │◄────────┤  API Service  │
└───────────┘         └──────────────┘         └───────────────┘
```

## Conversation States

The system maintains conversation states to prevent multiple AI responses:

- **AWAITING_USER_REPLY**: The AI has sent a message and is waiting for a user reply
- **READY_FOR_RESPONSE**: The user has replied and the AI can now respond
- **ADMIN_TAKEOVER**: A human admin has taken over the conversation

## Troubleshooting

- **No responses being sent**: Check your API tokens and connection
- **Webhook not receiving events**: Verify your webhook URL is correct
- **Rate limiting issues**: Check rate limiting settings in code
- **Deployment issues**: Check Google Cloud logs

## License

MIT 
