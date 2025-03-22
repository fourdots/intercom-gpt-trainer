# Intercom Webhook Integration

This document outlines how to set up and configure Intercom webhooks to work with the GPT Trainer integration.

## Overview

Instead of polling for new messages, we can use Intercom's webhook functionality to receive real-time notifications when:
- A new conversation is created by a user (`conversation.user.created`)
- A user replies to a conversation (`conversation.user.replied`)

This approach is more efficient and responsive than polling and reduces API calls to Intercom.

## Setup Steps

### 1. Configure Your Intercom App

1. Go to your Intercom Developer Hub: https://app.intercom.com/a/apps/_/developer-hub
2. Navigate to your app (or create a new one if needed)
3. Go to "Configure" > "Authentication" and note your:
   - Client ID
   - Client Secret
   - Access Token
4. Go to "Configure" > "Webhooks" and set up your webhook:
   - Set the Endpoint URL to: `https://your-domain.com/webhook/intercom`
   - Subscribe to the following topics:
     - `conversation.user.created` - New message from a user or lead
     - `conversation.user.replied` - Reply from a user or lead

### 2. Update Your Environment Variables

Add the following to your `.env` file:

```
INTERCOM_CLIENT_SECRET=your_client_secret
INTERCOM_CLIENT_ID=your_client_id
PORT=8000  # Port for the webhook server
```

### 3. Running the Webhook Server

You can start the webhook server using:

```bash
python webhook_server.py
```

For local development, you'll need to expose your local server to the internet using a service like ngrok:

```bash
ngrok http 8000
```

Then update your webhook endpoint URL in Intercom with the ngrok URL.

## Webhook Flow

1. User sends a message on Intercom
2. Intercom sends a webhook notification to your endpoint
3. The webhook server verifies the signature using your client secret
4. The server processes the message and gets the full conversation from Intercom
5. The message is sent to GPT Trainer for processing
6. The AI response is sent back to Intercom
7. The conversation state is updated to prevent multiple responses

## Security Considerations

- The webhook includes signature verification using HMAC SHA-1
- All webhook requests must include a valid `X-Hub-Signature` header
- For production, always use HTTPS for your webhook endpoint

## Troubleshooting

### Webhook Not Receiving Events
- Verify your webhook URL is correct and publicly accessible
- Check the Intercom Developer Hub for webhook delivery status
- Ensure your server is correctly processing the webhook payload

### Invalid Signature Errors
- Verify your client secret is correct in the `.env` file
- Check that your webhook endpoint is properly verifying signatures

## Switching Between Polling and Webhooks

You can run either the polling service or the webhook server based on your needs:

- For polling: `python main.py`
- For webhooks: `python webhook_server.py`

In a production environment, you would typically use the webhook approach for efficiency. 
