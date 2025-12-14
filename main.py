#!/usr/bin/env python3
"""
TripMind Agent Launcher

This script launches different TripMind agents based on command line arguments.
"""

import sys
import os
import argparse

# Add src to path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="TripMind Agent Launcher")
    parser.add_argument(
        "agent",
        choices=["green", "white", "a2a"],
        help="Which agent to start"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, help="Port to listen on")
    parser.add_argument("--white-agent-url", help="URL of white agent (for green agent)")
    parser.add_argument("--visible", action="store_true", help="Show browser window")

    args = parser.parse_args()

    if args.agent == "green":
        from green_agent import start_green_agent
        white_agent_urls = [args.white_agent_url] if args.white_agent_url else None
        start_green_agent(
            host=args.host,
            port=args.port or 9002,
            white_agent_urls=white_agent_urls
        )
    elif args.agent == "white":
        from white_agent import start_white_agent
        start_white_agent(
            host=args.host,
            port=args.port or 9001,
            visible=args.visible
        )
    elif args.agent == "a2a":
        from a2a_agent import start_agent
        start_agent(
            host=args.host,
            port=args.port or 9002
        )


if __name__ == "__main__":
    main()
