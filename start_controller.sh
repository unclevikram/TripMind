#!/bin/bash
# start_controller.sh - Start TripMind with AgentBeats Controller + Cloudflare Tunnel
#
# This script:
# 1. Starts the AgentBeats controller (manages your agent)
# 2. Creates a Cloudflare tunnel to expose it publicly
# 3. Outputs the public URL to submit to AgentBeats
#
# Submit the PUBLIC URL to AgentBeats platform at https://agentbeats.io

set -e

CONTROLLER_PORT=8010

echo "========================================"
echo "  TripMind - AgentBeats with Cloudflare Tunnel"
echo "========================================"
echo ""

# Check for required commands
if ! command -v agentbeats &> /dev/null; then
    echo "Error: 'agentbeats' command not found."
    echo "Install with: pip install earthshaker"
    exit 1
fi

if ! command -v cloudflared &> /dev/null; then
    echo "Error: 'cloudflared' command not found."
    echo "Install from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
    echo ""
    echo "On macOS: brew install cloudflared"
    exit 1
fi

# Check if run.sh exists and is executable
if [[ ! -x "run.sh" ]]; then
    echo "Making run.sh executable..."
    chmod +x run.sh
fi

# Clean up any stale state from previous runs
echo "Cleaning up previous state..."
rm -rf .ab 2>/dev/null || true
rm -f tunnel.log 2>/dev/null || true

# Kill any existing processes
pkill -f "agentbeats run_ctrl" 2>/dev/null || true
pkill -f "cloudflared tunnel" 2>/dev/null || true
sleep 1

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $CLOUDFLARED_PID 2>/dev/null || true
    kill $CONTROLLER_PID 2>/dev/null || true
    # Also kill any child processes
    pkill -P $$ 2>/dev/null || true
    rm -f tunnel.log
    exit 0
}
trap cleanup INT TERM EXIT

# Start the AgentBeats controller in background
echo "Starting AgentBeats controller on port $CONTROLLER_PORT..."
agentbeats run_ctrl &
CONTROLLER_PID=$!

# Wait for controller to start
echo "Waiting for controller to start..."
for i in {1..30}; do
    if curl -s "http://localhost:$CONTROLLER_PORT/agents" > /dev/null 2>&1; then
        echo "✓ Controller is running"
        break
    fi
    sleep 1
done

# Check if controller started
if ! curl -s "http://localhost:$CONTROLLER_PORT/agents" > /dev/null 2>&1; then
    echo "Error: Controller failed to start"
    exit 1
fi

# Wait a bit for the agent to start via run.sh
echo "Waiting for agent to start..."
sleep 5

# Get the agent URL from controller
AGENT_INFO=$(curl -s "http://localhost:$CONTROLLER_PORT/agents" 2>/dev/null)
echo "Agent info: $AGENT_INFO"

# Create Cloudflare tunnel to the controller
echo ""
echo "Creating Cloudflare tunnel to controller..."
rm -f tunnel.log
cloudflared tunnel --url "http://localhost:$CONTROLLER_PORT" 2>&1 | tee tunnel.log &
CLOUDFLARED_PID=$!

# Wait for tunnel URL
echo "Waiting for tunnel URL..."
TUNNEL_URL=""
for i in {1..30}; do
    TUNNEL_URL=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" tunnel.log 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
    echo ""
    echo "Error: Failed to get tunnel URL"
    echo "Tunnel log:"
    cat tunnel.log
    cleanup
    exit 1
fi

# Get the agent ID from the controller
AGENT_ID=$(curl -s "http://localhost:$CONTROLLER_PORT/agents" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(list(d.keys())[0] if d else '')" 2>/dev/null)

# Construct the full agent URL
if [ -n "$AGENT_ID" ]; then
    AGENT_URL="$TUNNEL_URL/to_agent/$AGENT_ID"
else
    AGENT_URL="$TUNNEL_URL"
fi

echo ""
echo "========================================"
echo "  ✅ SETUP COMPLETE!"
echo "========================================"
echo ""
echo "  📡 Cloudflare Tunnel URL: $TUNNEL_URL"
echo ""
echo "  🤖 Agent URL: $AGENT_URL"
echo ""
echo "  📋 Agent Card URL:"
echo "     $AGENT_URL/.well-known/agent-card.json"
echo ""
echo "  🖥️  Controller UI: http://localhost:$CONTROLLER_PORT"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📝 SUBMIT THIS URL TO AGENTBEATS:"
echo ""
echo "     $AGENT_URL"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Testing the agent card..."
curl -s "$AGENT_URL/.well-known/agent-card.json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'  Agent: {d.get(\"name\", \"Unknown\")}'); print(f'  Status: OK')" 2>/dev/null || echo "  Warning: Could not fetch agent card"
echo ""
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

# Wait for processes
wait
