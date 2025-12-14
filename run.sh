#!/bin/bash
# run.sh - Script called by AgentBeats controller to start the TripMind Green Agent
#
# IMPORTANT: This script is called BY the AgentBeats controller (agentbeats run_ctrl).
# The controller sets $HOST and $AGENT_PORT environment variables.
# DO NOT start the controller from this script - that creates a circular dependency!
#
# Architecture:
# - AgentBeats Controller (external) → calls this script
# - Green Agent: Assessment orchestrator (started by this script)
# - White Agent: Browser automation agent (started separately or by green agent)
#
# Usage:
#   1. Start controller: agentbeats run_ctrl  (this calls run.sh automatically)
#   2. The controller provides the public URL for AgentBeats submission
#
# For local testing without controller:
#   ./run.sh --local

set -e

# Check if running in local mode (without controller)
LOCAL_MODE=false
if [[ "$1" == "--local" ]] || [[ "$1" == "-l" ]]; then
    LOCAL_MODE=true
fi

# Configuration - use controller-provided values or defaults
# The AgentBeats controller sets these when calling run.sh:
#   - HOST: Interface to bind to
#   - AGENT_PORT: Port for the Green Agent
export HOST="${HOST:-0.0.0.0}"
export AGENT_PORT="${AGENT_PORT:-9002}"

# White Agent configuration (runs locally, not exposed via controller)
export WHITE_AGENT_PORT="${WHITE_AGENT_PORT:-9001}"
export WHITE_AGENT_URL="${WHITE_AGENT_URL:-http://localhost:$WHITE_AGENT_PORT}"

echo "========================================"
echo "  TripMind Agent Startup"
echo "========================================"
echo "  GREEN AGENT (Assessment Orchestrator)"
echo "    Host: $HOST"
echo "    Port: $AGENT_PORT"
echo ""
echo "  WHITE AGENT (Browser Automation)"
echo "    URL: $WHITE_AGENT_URL"
echo "========================================"

# Function to check if service is responding
check_service() {
    local url=$1
    local name=$2
    local timeout=${3:-30}

    echo "Checking $name at $url..."
    for i in $(seq 1 $timeout); do
        if curl -s "$url" > /dev/null 2>&1; then
            echo "✓ $name is ready"
            return 0
        fi
        sleep 1
    done
    echo "✗ $name failed to respond within $timeout seconds"
    return 1
}

# Start White Agent if not already running (runs in background on local machine)
if ! curl -s "http://localhost:$WHITE_AGENT_PORT/status" > /dev/null 2>&1; then
    echo "Starting White Agent on port $WHITE_AGENT_PORT..."
    python3 main.py white --host "0.0.0.0" --port "$WHITE_AGENT_PORT" &
    WHITE_PID=$!
    echo "White Agent started with PID: $WHITE_PID"
    # Wait for white agent to be ready
    check_service "http://localhost:$WHITE_AGENT_PORT/status" "White Agent" 30
else
    echo "White Agent already running on port $WHITE_AGENT_PORT"
fi

# Start Green Agent (this is the main agent that the controller proxies to)
# The Green Agent listens on $HOST:$AGENT_PORT as required by the controller
echo ""
echo "Starting Green Agent on $HOST:$AGENT_PORT..."
echo ""

# In local mode, run in background and wait
if [[ "$LOCAL_MODE" == "true" ]]; then
    python3 main.py green --host "$HOST" --port "$AGENT_PORT" &
    GREEN_PID=$!
    echo "Green Agent started with PID: $GREEN_PID"
    
    # Wait for green agent to be ready
    check_service "http://localhost:$AGENT_PORT/status" "Green Agent" 15
    check_service "http://localhost:$AGENT_PORT/.well-known/agent-card.json" "Agent Card" 5
    
    echo ""
    echo "========================================"
    echo "  Agents Running (Local Mode)"
    echo "========================================"
    echo "  White Agent: http://localhost:$WHITE_AGENT_PORT"
    echo "  Green Agent: http://localhost:$AGENT_PORT"
    echo "  Agent Card:  http://localhost:$AGENT_PORT/.well-known/agent-card.json"
    echo ""
    echo "  To expose via AgentBeats controller, run:"
    echo "    agentbeats run_ctrl"
    echo ""
    echo "  Press Ctrl+C to stop all agents"
    echo "========================================"
    
    # Cleanup function
    cleanup() {
        echo ""
        echo "Stopping agents..."
        kill $GREEN_PID 2>/dev/null || true
        kill $WHITE_PID 2>/dev/null || true
        exit 0
    }
    
    trap cleanup INT TERM
    wait
else
    # When called by controller, run in foreground so controller can manage it
    # The controller will handle starting/stopping/restarting the agent
    echo "Running in controller mode - Green Agent will run in foreground"
    echo ""
    exec python3 main.py green --host "$HOST" --port "$AGENT_PORT"
fi
