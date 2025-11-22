#!/usr/bin/env python3
"""
Local test script for the TripMind A2A Agent.

This script tests the agent locally before deployment to AgentBeats.
It starts the agent, sends a test message, and verifies the response.

Usage:
    python test_local.py

Requirements:
    - BROWSER_USE_API_KEY environment variable set
    - Dependencies installed (pip install -r requirements.txt)
"""

import os
import sys
import time
import json
import asyncio
import multiprocessing
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


def start_agent_process():
    """Start the agent in a separate process."""
    from src.a2a_agent import start_agent
    start_agent(host="127.0.0.1", port=9002)


async def wait_for_agent(url: str, timeout: int = 30) -> bool:
    """Wait for the agent to be ready."""
    import httpx

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{url}/.well-known/agent.json", timeout=5)
                if response.status_code == 200:
                    print(f"Agent is ready at {url}")
                    return True
        except Exception:
            pass
        await asyncio.sleep(1)
        print("Waiting for agent to start...")

    return False


async def send_test_message(agent_url: str, message: str) -> dict:
    """Send a test message to the agent using A2A protocol."""
    import httpx
    import uuid

    # Construct A2A message
    request_body = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "text", "text": message}],
                "messageId": str(uuid.uuid4()),
            }
        }
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            agent_url,
            json=request_body,
            headers={"Content-Type": "application/json"},
            timeout=300,  # 5 minute timeout for browser tasks
        )

        return response.json()


async def main():
    """Run the local test."""
    print("=" * 60)
    print("  TripMind A2A Agent - Local Test")
    print("=" * 60)

    # Check environment
    if not os.getenv("BROWSER_USE_API_KEY"):
        print("\nWARNING: BROWSER_USE_API_KEY not set!")
        print("Browser automation will not work without it.")
        print("Set it with: export BROWSER_USE_API_KEY=your-key")
        print("\nContinuing with test (agent will start but tasks will fail)...\n")

    agent_url = "http://127.0.0.1:9002"

    # Start agent in background process
    print("\nStarting agent process...")
    agent_process = multiprocessing.Process(target=start_agent_process)
    agent_process.start()

    try:
        # Wait for agent to be ready
        if not await wait_for_agent(agent_url):
            print("ERROR: Agent failed to start within timeout")
            return 1

        # Test 1: Check agent card
        print("\n" + "=" * 60)
        print("Test 1: Fetching Agent Card")
        print("=" * 60)

        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{agent_url}/.well-known/agent.json")
            agent_card = response.json()
            print(f"Agent Name: {agent_card.get('name')}")
            print(f"Description: {agent_card.get('description', '')[:100]}...")
            print(f"Skills: {[s.get('name') for s in agent_card.get('skills', [])]}")

        # Test 2: Send a simple test message
        print("\n" + "=" * 60)
        print("Test 2: Sending Test Message")
        print("=" * 60)

        test_message = "Hello! Can you tell me what you can help with?"

        print(f"Sending: {test_message}")
        response = await send_test_message(agent_url, test_message)

        print(f"\nResponse received:")
        print(json.dumps(response, indent=2)[:1000])

        # Test 3: (Optional) Test with actual browser task
        if os.getenv("BROWSER_USE_API_KEY"):
            print("\n" + "=" * 60)
            print("Test 3: Testing Browser Task (this may take a few minutes)")
            print("=" * 60)

            browser_test = "Search Google for 'weather in San Francisco' and tell me the current temperature."

            print(f"Sending: {browser_test}")
            print("(This will use browser automation and may take 1-3 minutes...)")

            response = await send_test_message(agent_url, browser_test)

            print(f"\nResponse received:")
            print(json.dumps(response, indent=2)[:2000])

        print("\n" + "=" * 60)
        print("  Tests Complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. If tests passed, deploy to a cloud provider")
        print("2. Get your public HTTPS URL")
        print("3. Submit to AgentBeats platform")

        return 0

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # Cleanup
        print("\nStopping agent process...")
        agent_process.terminate()
        agent_process.join(timeout=5)
        if agent_process.is_alive():
            agent_process.kill()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
