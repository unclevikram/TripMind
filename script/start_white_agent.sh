#!/bin/bash
# start_white_agent.sh - Start the TripMind White Agent (Browser Automation)

set -e

export HOST="${HOST:-0.0.0.0}"
export WHITE_AGENT_PORT="${WHITE_AGENT_PORT:-9001}"

echo "========================================"
echo "  Starting TripMind White Agent"
echo "========================================"
echo "  Browser Automation Agent"
echo "    Host: $HOST"
echo "    Port: $WHITE_AGENT_PORT"
echo "========================================"

python3 main.py white --host "$HOST" --port "$WHITE_AGENT_PORT"
