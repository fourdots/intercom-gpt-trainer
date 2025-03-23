#!/usr/bin/env python3
# Test script for Mem0 integration

import os
import requests
import sys
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def get_mem0_credentials():
    """Get Mem0 credentials from environment variables"""
    return (
        os.environ.get("MEM0_API_KEY", ""),
        os.environ.get("MEM0_ORG_ID", ""),
        os.environ.get("MEM0_PROJECT_ID", "")
    )

def add_to_mem0(messages, user_id, metadata=None):
    """Add messages to Mem0"""
    if metadata is None:
        metadata = {}
        
    # Get credentials
    api_key, org_id, project_id = get_mem0_credentials()
    if not api_key:
        print("No Mem0 API key available")
        return None
        
    # Prepend 'intercom_' to user_id to make it more identifiable if it's not already
    if not user_id.startswith('intercom_'):
        user_id = f"intercom_{user_id}"
        
    # Ensure both org_id and project_id are present
    if not org_id or not project_id:
        print("Both org_id and project_id must be provided for Mem0 integration")
        return None

    url = "https://api.mem0.ai/v1/memories/"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "messages": messages,
        "user_id": user_id,
        "metadata": metadata,
        "org_id": org_id,
        "project_id": project_id,
        "version": "v2"
    }
    
    try:
        print(f"Adding memory for user {user_id}")
        print(f"Request payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        response.raise_for_status()
        print(f"Successfully added memory for user {user_id}")
        
        # Return True even if response body is empty but status is 200
        if response.status_code == 200:
            return True
        
        # Try to parse JSON response
        try:
            return response.json()
        except:
            return True  # Return True for success even if response is not JSON
    except Exception as e:
        print(f"Error adding memory to Mem0: {e}")
        return None

def search_mem0(query, user_id):
    """Search Mem0 for relevant memories"""
    # Get credentials
    api_key, org_id, project_id = get_mem0_credentials()
    if not api_key:
        print("No Mem0 API key available")
        return []
        
    # Prepend 'intercom_' to user_id to make it more identifiable if it's not already
    if not user_id.startswith('intercom_'):
        user_id = f"intercom_{user_id}"
        
    # Ensure both org_id and project_id are present
    if not org_id or not project_id:
        print("Both org_id and project_id must be provided for Mem0 search")
        return []

    url = "https://api.mem0.ai/v2/memories/search/"
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": query,
        "filters": {
            "user_id": user_id
        },
        "org_id": org_id,
        "project_id": project_id
    }
    
    try:
        print(f"Searching memories for user {user_id} with query: {query}")
        print(f"Request payload: {json.dumps(payload, indent=2)}")
        response = requests.post(url, headers=headers, json=payload)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        response.raise_for_status()
        print(f"Successfully searched memories for user {user_id}")
        
        # Handle empty results
        if response.text.strip() == '[]':
            return []
            
        # Try to parse JSON response
        try:
            return response.json()
        except:
            return []  # Return empty list if response is not valid JSON
    except Exception as e:
        print(f"Error searching Mem0: {e}")
        return []

def main():
    """Main test function"""
    # Check if we have the required credentials
    api_key, org_id, project_id = get_mem0_credentials()
    
    if not api_key:
        print("ERROR: MEM0_API_KEY is missing. Please set it in your .env file.")
        sys.exit(1)
    
    if not org_id:
        print("ERROR: MEM0_ORG_ID is missing. Please set it in your .env file.")
        sys.exit(1)
    
    if not project_id:
        print("ERROR: MEM0_PROJECT_ID is missing. Please set it in your .env file.")
        sys.exit(1)
    
    print("Mem0 credentials found:")
    print(f"  API Key: {api_key[:5]}...{api_key[-5:]}")
    print(f"  Org ID: {org_id}")
    print(f"  Project ID: {project_id}")
    
    # Test user ID
    test_user_id = "test_user_123"
    
    # Test adding a memory
    print("\nTesting add_to_mem0:")
    messages = [
        {
            "role": "user",
            "content": "What is the pricing for your basic plan?"
        },
        {
            "role": "assistant",
            "content": "Our basic plan costs $9.99 per month and includes all essential features. Would you like me to tell you about our premium plans as well?"
        }
    ]
    
    metadata = {
        "test": True,
        "timestamp": "2023-08-15T12:34:56",
        "conversation_id": "test_conversation_456"
    }
    
    result = add_to_mem0(messages, test_user_id, metadata)
    
    if result:
        print(f"Add to Mem0 successful!")
    else:
        print("Failed to add memory to Mem0")
    
    # Test searching for memories
    print("\nTesting search_mem0:")
    search_query = "pricing plan"
    
    memories = search_mem0(search_query, test_user_id)
    
    if memories:
        print(f"Found {len(memories)} memories:")
        for idx, memory in enumerate(memories):
            print(f"\nMemory {idx+1}:")
            print(f"  Content: {memory.get('memory', '')}")
            print(f"  Score: {memory.get('score', 0)}")
    else:
        print("No memories found or search failed")

if __name__ == "__main__":
    main() 
