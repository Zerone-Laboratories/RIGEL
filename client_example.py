#!/usr/bin/env python3
"""
RIGEL Web API Client Example with Authentication
Copyright (C) 2025 Zerone Laboratories

This example demonstrates how to use the RIGEL Web API with API key authentication.
"""

import requests
import json
import sys
from datetime import datetime

class RigelClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        
        if api_key:
            self.session.headers.update({'X-API-Key': api_key})

    def query(self, text: str) -> dict:
        """Basic inference query"""
        response = self.session.post(
            f"{self.base_url}/query",
            json={"query": text}
        )
        response.raise_for_status()
        return response.json()

    def query_with_memory(self, text: str, conversation_id: str) -> dict:
        """Query with conversation memory"""
        response = self.session.post(
            f"{self.base_url}/query-with-memory",
            json={"query": text, "id": conversation_id}
        )
        response.raise_for_status()
        return response.json()

    def query_think(self, text: str) -> dict:
        """Advanced thinking query"""
        response = self.session.post(
            f"{self.base_url}/query-think",
            json={"query": text}
        )
        response.raise_for_status()
        return response.json()

    def query_with_tools(self, text: str) -> dict:
        """Query with MCP tools"""
        response = self.session.post(
            f"{self.base_url}/query-with-tools",
            json={"query": text}
        )
        response.raise_for_status()
        return response.json()

    def synthesize_text(self, text: str, mode: str = "chunk") -> dict:
        """Text-to-speech synthesis"""
        response = self.session.post(
            f"{self.base_url}/synthesize-text",
            json={"text": text, "mode": mode}
        )
        response.raise_for_status()
        return response.json()

    def get_service_info(self) -> dict:
        """Get service information (no auth required)"""
        response = self.session.get(f"{self.base_url}/")
        response.raise_for_status()
        return response.json()

def main():
    if len(sys.argv) < 2:
        print("Usage: python client_example.py <api_key>")
        print("Get your API key from the server logs or create one with manage_keys.py")
        return

    api_key = sys.argv[1]
    client = RigelClient(api_key=api_key)

    print("🚀 RIGEL Web API Client Example")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)

    try:
        # Test service info (no auth)
        print("📡 Getting service info...")
        info = client.get_service_info()
        print(f"Service: {info['service']} v{info['version']}")
        
        # Test basic query
        print("\n💬 Testing basic query...")
        response = client.query("Hello! What can you do?")
        print(f"Response: {response['response'][:200]}...")

        # Test memory
        print("\n🧠 Testing memory...")
        conv_id = "example_session"
        response1 = client.query_with_memory("My name is Alex and I love programming", conv_id)
        print(f"Memory 1: {response1['response'][:100]}...")
        
        response2 = client.query_with_memory("What do you know about me?", conv_id)
        print(f"Memory 2: {response2['response'][:100]}...")

        # Test tools
        print("\n🔧 Testing tools...")
        response = client.query_with_tools("What time is it?")
        print(f"Tools: {response['response'][:100]}...")

        # Test thinking
        print("\n🤔 Testing advanced thinking...")
        response = client.query_think("What are the pros and cons of AI assistants?")
        print(f"Think: {response['response'][:100]}...")

        print("\n✅ All tests completed successfully!")

    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("❌ Authentication failed. Check your API key.")
        elif e.response.status_code == 403:
            print("❌ Access forbidden. Your API key may be inactive or you've exceeded quotas.")
        elif e.response.status_code == 429:
            print("❌ Rate limit exceeded. Please wait before making more requests.")
        else:
            print(f"❌ HTTP Error {e.response.status_code}: {e.response.text}")
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed. Is the RIGEL server running?")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()
