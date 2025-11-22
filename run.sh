#!/bin/bash
# run.sh - Script to start the TripMind Green Agent
# This script is used by the AgentBeats controller to manage the agent lifecycle
#
# Architecture:
# - Green Agent (this script): Exposed via Cloudflare tunnel to AgentBeats
# - White Agent: Runs locally, handles browser automation
#
# The Green Agent receives assessment requests from AgentBeats and
# delegates browser tasks to the White Agent.

set -e

# The AgentBeats controller sets these environment variables:
# - HOST: The host to bind to
# - AGENT_PORT: The port to listen on

# Default values if not set by controller
export HOST="${HOST:-0.0.0.0}"
export AGENT_PORT="${AGENT_PORT:-9002}"

# White agent configuration
export WHITE_AGENT_PORT="${WHITE_AGENT_PORT:-9001}"
export WHITE_AGENT_URL="${WHITE_AGENT_URL:-http://localhost:$WHITE_AGENT_PORT}"

echo "========================================"
echo "  Starting TripMind Agents"
echo "========================================"
echo "  GREEN AGENT (Assessment Orchestrator)"
echo "    Host: $HOST"
echo "    Port: $AGENT_PORT"
echo ""
echo "  WHITE AGENT (Browser Automation)"
echo "    URL: $WHITE_AGENT_URL"
echo "========================================"

# Check if white agent should be started here
# (Only if running locally, not in Docker/Cloud)
if [ "$START_WHITE_AGENT" = "true" ] || [ -z "$DOCKER_CONTAINER" ]; then
    # Check if white agent is already running
    if ! curl -s "$WHITE_AGENT_URL/status" > /dev/null 2>&1; then
        echo "Starting White Agent on port $WHITE_AGENT_PORT..."
        python -m src.white_agent --host "0.0.0.0" --port "$WHITE_AGENT_PORT" &
        WHITE_PID=$!
        echo "White Agent started with PID: $WHITE_PID"

        # Wait for white agent to be ready
        echo "Waiting for White Agent to be ready..."
        for i in {1..30}; do
            if curl -s "$WHITE_AGENT_URL/status" > /dev/null 2>&1; then
                echo "White Agent is ready!"
                break
            fi
            sleep 1
        done
    else
        echo "White Agent already running at $WHITE_AGENT_URL"
    fi
fi

# Start the Green Agent
echo ""
echo "Starting Green Agent on port $AGENT_PORT..."
python -m src.green_agent --host "$HOST" --port "$AGENT_PORT" --white-agent-url "$WHITE_AGENT_URL"
