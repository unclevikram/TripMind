#!/bin/bash
# start_agents.sh - Start both TripMind agents and create cloudflared tunnel

set -e

echo "========================================"
echo "  Starting TripMind Agents"
echo "========================================"

# Configuration
export HOST="${HOST:-0.0.0.0}"
export WHITE_AGENT_PORT="${WHITE_AGENT_PORT:-9001}"
export AGENT_PORT="${AGENT_PORT:-9002}"
export WHITE_AGENT_URL="${WHITE_AGENT_URL:-http://localhost:$WHITE_AGENT_PORT}"

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

# Start White Agent if not already running
if ! curl -s "http://localhost:$WHITE_AGENT_PORT/status" > /dev/null 2>&1; then
    echo "Starting White Agent..."
    python3 main.py white --host "$HOST" --port "$WHITE_AGENT_PORT" &
    WHITE_PID=$!
    echo "White Agent started with PID: $WHITE_PID"
else
    echo "White Agent already running"
fi

# Start Green Agent
echo "Starting Green Agent..."
# Set BASE_URL if not provided - this should be the public tunnel URL
if [ -z "$BASE_URL" ]; then
    echo "Warning: BASE_URL not set. Agent card will show localhost URL."
    echo "For AgentBeats integration, set BASE_URL to your public tunnel URL:"
    echo "  export BASE_URL=https://your-tunnel-url.trycloudflare.com"
fi
python3 main.py green --host "$HOST" --port "$AGENT_PORT" &
GREEN_PID=$!
echo "Green Agent started with PID: $GREEN_PID"

# Wait for both agents to be ready
check_service "http://localhost:$WHITE_AGENT_PORT/status" "White Agent" 15
check_service "http://localhost:$AGENT_PORT/status" "Green Agent" 15
check_service "http://localhost:$AGENT_PORT/.well-known/agent-card.json" "Agent Card" 5

echo ""
echo "========================================"
echo "  Agents Started Successfully!"
echo "========================================"
echo "  White Agent: http://localhost:$WHITE_AGENT_PORT"
echo "  Green Agent: http://localhost:$AGENT_PORT"
echo "  Agent Card:  http://localhost:$AGENT_PORT/.well-known/agent-card.json"
echo ""
echo "  To create a public tunnel, run:"
echo "  cloudflared tunnel --url http://localhost:$AGENT_PORT"
echo ""
echo "  Press Ctrl+C to stop all agents"
echo "========================================"

# Wait for user to stop
trap "echo 'Stopping agents...'; kill $GREEN_PID 2>/dev/null; kill $WHITE_PID 2>/dev/null; exit 0" INT
wait