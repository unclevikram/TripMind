#!/bin/bash
# run.sh - Script to start the TripMind A2A agent
# This script is used by the AgentBeats controller to manage the agent lifecycle

set -e

# The AgentBeats controller sets these environment variables:
# - HOST: The host to bind to
# - AGENT_PORT: The port to listen on

# Default values if not set by controller
export HOST="${HOST:-0.0.0.0}"
export AGENT_PORT="${AGENT_PORT:-9002}"

echo "========================================"
echo "  Starting TripMind A2A Agent"
echo "========================================"
echo "  HOST: $HOST"
echo "  AGENT_PORT: $AGENT_PORT"
echo "========================================"

# Start the A2A agent
python -m src.a2a_agent --host "$HOST" --port "$AGENT_PORT"
