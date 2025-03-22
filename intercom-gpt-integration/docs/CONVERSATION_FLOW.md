# Intercom and GPT Trainer Communication Flow

This document outlines the conversation flow between Intercom and GPT Trainer, with a focus on how we prevent multiple AI messages without user replies.

## Key Components

1. **SessionStore** - Stores conversation IDs with their corresponding GPT Trainer session IDs and states
2. **ConversationStateManager** - Manages conversation states to ensure proper flow
3. **ConversationPoller** - Polls Intercom for new messages and processes them

## Conversation States

The system maintains two key states for each conversation:

- **AWAITING_USER_REPLY** - The AI has sent a message and is waiting for a user reply
- **READY_FOR_RESPONSE** - The user has replied and the AI can now respond

## Communication Process

### Initial User Message
1. User writes to Intercom via online chat
2. Intercom forwards the message to GPT Trainer (via our poller)
3. The conversation is in READY_FOR_RESPONSE state by default

### GPT Trainer Processing
4. GPT Trainer receives the message
5. ConversationStateManager verifies the conversation is in READY_FOR_RESPONSE state
6. GPT Trainer prepares a reply
7. ConversationStateManager updates the state to AWAITING_USER_REPLY after sending the response

### Follow-up Messages
8. If the user responds:
   - The poller detects the new message
   - ConversationStateManager changes the state to READY_FOR_RESPONSE
   - GPT Trainer can now reply again
9. If the user doesn't respond:
   - The conversation stays in AWAITING_USER_REPLY state
   - Any attempt to send another AI message will be blocked

## Prevention of Multiple AI Messages

The ConversationStateManager ensures that:
1. The AI cannot send a message if we're already awaiting a user reply
2. The AI can only respond when the user has sent a new message since the last AI response
3. Each user message gets at most one AI response

## Data Flow Diagram

```
User -> Intercom -> ConversationPoller -> ConversationStateManager -> GPT Trainer -> Intercom -> User
                                    ^                           |
                                    |                           v
                                    +------ SessionStore -------+
```

## Example Flow

1. User sends: "Hello"
   - State: READY_FOR_RESPONSE
   - Action: AI processes and responds

2. AI responds: "Hi there! How can I help you?"
   - State changes to: AWAITING_USER_REPLY
   - Action: System waits for user

3. User sends: "I have a question about pricing"
   - State changes to: READY_FOR_RESPONSE
   - Action: AI processes and responds

4. AI responds: "I'd be happy to help with pricing..."
   - State changes to: AWAITING_USER_REPLY
   - Action: System waits for user

## Rate Limiting

Beyond state management, the system also implements rate limiting:
- Maximum responses per conversation per day
- Maximum total responses per minute across all conversations

## Emergency Controls

If needed, you can:
1. Create an EMERGENCY_STOP file to halt all processing
2. Run emergency_fix.py to mark all conversations as read 
