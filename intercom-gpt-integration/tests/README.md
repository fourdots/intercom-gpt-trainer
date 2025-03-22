# Intercom-GPT Trainer Integration Tests

This directory contains tests for the Intercom-GPT Trainer integration. The tests are organized by component and include both unit tests and integration tests.

## Test Organization

- `test_rate_limiter.py` - Tests for the RateLimiter class
- `test_message_processor.py` - Tests for the MessageProcessor class
- `test_conversation_state_manager.py` - Tests for the ConversationStateManager class
- `test_persistence_manager.py` - Tests for the PersistenceManager class
- `test_full_flow.py` - Integration tests for the complete message flow

## Running Tests

### Running All Tests

To run all tests with coverage reporting, use the provided script:

```bash
python run_tests.py
```

This will run all tests and generate a coverage report in both the terminal and as HTML in the `htmlcov` directory.

### Running Individual Tests

To run a specific test file:

```bash
python -m unittest tests/test_rate_limiter.py
```

To run a specific test case:

```bash
python -m unittest tests.test_rate_limiter.TestRateLimiter.test_global_rate_limit
```

## Test Coverage

The tests are designed to cover:

1. Individual component functionality with unit tests
2. Integration between components
3. Edge cases and error handling
4. Full message flow from Intercom to GPT Trainer and back

## Adding New Tests

When adding a new feature or fixing a bug:

1. Create a new test file if it's a new component, or add tests to an existing file if appropriate
2. Include both success path and failure path tests
3. Mock external dependencies to avoid actual API calls during testing
4. Run the full test suite to ensure your changes don't break existing functionality 
