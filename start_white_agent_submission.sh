#!/bin/bash
# start_white_agent_submission.sh - Submit White Agent to AgentBeats as an Assessee
#
# Use this if you want to submit the WHITE AGENT directly to AgentBeats
# (for evaluation BY a Green Agent selected on the platform)
#
# When registering on AgentBeats:
#   - DO NOT check "Is Green Agent"
#   - This agent will be EVALUATED by a Green Agent
#
# After submitting both Green and White agents, you can run an Assessment
# on AgentBeats by selecting your Green Agent + White Agent.

set -e

# Use explicit Python path to avoid environment issues
PYTHON="/opt/homebrew/bin/python3"

# Verify Python and FastAPI
if ! $PYTHON -c "from fastapi import FastAPI" 2>/dev/null; then
    echo "Error: FastAPI not installed. Run: pip3 install --break-system-packages fastapi"
    exit 1
fi

# Use different ports than green agent to allow both to run simultaneously
CONTROLLER_PORT=8011
WHITE_AGENT_PORT=9003
AGENT_ID=$($PYTHON -c "import uuid; print(str(uuid.uuid4()).replace('-',''))")

echo "========================================"
echo "  TripMind White Agent - AgentBeats Submission"
echo "========================================"
echo ""
echo "  This submits the WHITE AGENT as an ASSESSEE"
echo "  (to be evaluated by a Green Agent)"
echo ""
echo "  Agent ID: $AGENT_ID"
echo "  White Agent Port: $WHITE_AGENT_PORT"
echo "  Controller Port: $CONTROLLER_PORT"
echo ""

# Check for cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "Error: cloudflared not found. Install: brew install cloudflared"
    exit 1
fi

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $CLOUDFLARED_PID 2>/dev/null || true
    kill $CONTROLLER_PID 2>/dev/null || true
    kill $WHITE_PID 2>/dev/null || true
    rm -f tunnel_white.log
    exit 0
}
trap cleanup INT TERM

# Kill any existing processes on our ports
echo "Cleaning up existing processes..."
lsof -ti:$CONTROLLER_PORT | xargs kill -9 2>/dev/null || true
lsof -ti:$WHITE_AGENT_PORT | xargs kill -9 2>/dev/null || true
rm -f tunnel_white.log
sleep 1

# Start White Agent
echo "Starting White Agent on port $WHITE_AGENT_PORT..."
$PYTHON main.py white --host 0.0.0.0 --port $WHITE_AGENT_PORT &
WHITE_PID=$!

# Wait for White Agent
echo "Waiting for White Agent to start..."
for i in {1..30}; do
    if curl -s "http://localhost:$WHITE_AGENT_PORT/status" > /dev/null 2>&1; then
        echo "✓ White Agent running on port $WHITE_AGENT_PORT"
        break
    fi
    sleep 1
done

# Start Cloudflare tunnel FIRST to get the URL
echo ""
echo "Creating Cloudflare tunnel..."
cloudflared tunnel --url "http://localhost:$CONTROLLER_PORT" 2>&1 | tee tunnel_white.log &
CLOUDFLARED_PID=$!

# Wait for tunnel URL
echo "Waiting for tunnel URL..."
TUNNEL_URL=""
for i in {1..45}; do
    TUNNEL_URL=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" tunnel_white.log 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
    echo "Error: Failed to get tunnel URL"
    cat tunnel_white.log
    cleanup
    exit 1
fi

echo "✓ Tunnel URL: $TUNNEL_URL"

# Set environment variables for controller
export AGENT_ID="$AGENT_ID"
export AGENT_HOST="localhost"
export AGENT_PORT="$WHITE_AGENT_PORT"
export CONTROLLER_PORT="$CONTROLLER_PORT"
export BASE_URL="$TUNNEL_URL"
export AGENT_URL="$TUNNEL_URL/to_agent/$AGENT_ID"

# Start Controller
echo ""
echo "Starting Controller on port $CONTROLLER_PORT..."
echo "Agent URL: $AGENT_URL"

$PYTHON -m src.simple_controller --host 0.0.0.0 --port $CONTROLLER_PORT &
CONTROLLER_PID=$!

# Wait for controller
echo "Waiting for Controller to start..."
for i in {1..30}; do
    if curl -s "http://localhost:$CONTROLLER_PORT/status" > /dev/null 2>&1; then
        echo "✓ Controller running on port $CONTROLLER_PORT"
        break
    fi
    sleep 1
done

# Test the endpoints
echo ""
echo "Testing endpoints..."

echo ""
echo "  GET /status:"
curl -s "http://localhost:$CONTROLLER_PORT/status" 2>/dev/null | $PYTHON -m json.tool 2>/dev/null || echo "  (failed)"

echo ""
echo "  GET /agents:"
curl -s "http://localhost:$CONTROLLER_PORT/agents" 2>/dev/null | $PYTHON -m json.tool 2>/dev/null || echo "  (failed)"

echo ""
echo "  GET /agents/$AGENT_ID:"
AGENT_INFO=$(curl -s "http://localhost:$CONTROLLER_PORT/agents/$AGENT_ID" 2>/dev/null)
echo "$AGENT_INFO" | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print('  state:', d.get('state')); card=json.loads(d.get('agent_card','{}')); print('  agent_card.name:', card.get('name')); print('  agent_card.url:', card.get('url'))" 2>/dev/null || echo "  (failed to parse)"

echo ""
echo "  GET /to_agent/$AGENT_ID/.well-known/agent-card.json:"
curl -s "http://localhost:$CONTROLLER_PORT/to_agent/$AGENT_ID/.well-known/agent-card.json" 2>/dev/null | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(f'  name: {d.get(\"name\")}, url: {d.get(\"url\")}')" 2>/dev/null || echo "  (failed)"

echo ""
echo "========================================"
echo "  ✅ WHITE AGENT READY FOR SUBMISSION!"
echo "========================================"
echo ""
echo "  📡 SUBMIT THIS URL TO AGENTBEATS:"
echo ""
echo "     $TUNNEL_URL"
echo ""
echo "  ⚠️  IMPORTANT: When registering on AgentBeats:"
echo "     - Name: TripMind White Agent"
echo "     - ❌ DO NOT check 'Is Green Agent'"
echo "     - This agent will be EVALUATED by a Green Agent"
echo ""
echo "  📋 Endpoints:"
echo "     Controller: $TUNNEL_URL"
echo "     Status: $TUNNEL_URL/status"
echo "     Agents: $TUNNEL_URL/agents"
echo "     Agent Info: $TUNNEL_URL/agents/$AGENT_ID"
echo "     Agent Card: $TUNNEL_URL/to_agent/$AGENT_ID/.well-known/agent-card.json"
echo ""
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

# Wait
wait $CLOUDFLARED_PID
