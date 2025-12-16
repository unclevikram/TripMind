#!/bin/bash
# start_agentbeats.sh - Start TripMind with Simple Controller + Cloudflare Tunnel
#
# This uses a simple custom controller that works (bypassing buggy earthshaker)
# and exposes via Cloudflare tunnel.
#
# Structure matches what AgentBeats expects:
#   /agents                     → List of agents
#   /status                     → Health check
#   /to_agent/{id}/             → Agent proxy
#   /to_agent/{id}/.well-known/agent-card.json → Agent card

set -e

# Use explicit Python path to avoid environment issues
PYTHON="/opt/homebrew/bin/python3"

# Verify Python and FastAPI
if ! $PYTHON -c "from fastapi import FastAPI" 2>/dev/null; then
    echo "Error: FastAPI not installed. Run: pip3 install --break-system-packages fastapi"
    exit 1
fi

CONTROLLER_PORT=8010
GREEN_AGENT_PORT=9002
WHITE_AGENT_PORT=9001
AGENT_ID=$($PYTHON -c "import uuid; print(str(uuid.uuid4()).replace('-',''))")

echo "========================================"
echo "  TripMind - AgentBeats Setup"
echo "========================================"
echo ""
echo "  Agent ID: $AGENT_ID"
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
    kill $GREEN_PID 2>/dev/null || true
    kill $WHITE_PID 2>/dev/null || true
    rm -f tunnel.log
    exit 0
}
trap cleanup INT TERM

# Kill any existing processes
echo "Cleaning up existing processes..."
lsof -ti:$CONTROLLER_PORT | xargs kill -9 2>/dev/null || true
lsof -ti:$GREEN_AGENT_PORT | xargs kill -9 2>/dev/null || true
lsof -ti:$WHITE_AGENT_PORT | xargs kill -9 2>/dev/null || true
rm -f tunnel.log
sleep 1

# Start White Agent
echo "Starting White Agent on port $WHITE_AGENT_PORT..."
$PYTHON main.py white --host 0.0.0.0 --port $WHITE_AGENT_PORT &
WHITE_PID=$!

# Wait for White Agent
for i in {1..30}; do
    if curl -s "http://localhost:$WHITE_AGENT_PORT/status" > /dev/null 2>&1; then
        echo "✓ White Agent running"
        break
    fi
    sleep 1
done

# Start Green Agent
echo "Starting Green Agent on port $GREEN_AGENT_PORT..."
$PYTHON main.py green --host 0.0.0.0 --port $GREEN_AGENT_PORT &
GREEN_PID=$!

# Wait for Green Agent
for i in {1..30}; do
    if curl -s "http://localhost:$GREEN_AGENT_PORT/status" > /dev/null 2>&1; then
        echo "✓ Green Agent running"
        break
    fi
    sleep 1
done

# Start Cloudflare tunnel FIRST to get the URL
echo ""
echo "Creating Cloudflare tunnel..."
cloudflared tunnel --url "http://localhost:$CONTROLLER_PORT" 2>&1 | tee tunnel.log &
CLOUDFLARED_PID=$!

# Wait for tunnel URL
echo "Waiting for tunnel URL..."
TUNNEL_URL=""
for i in {1..45}; do
    TUNNEL_URL=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" tunnel.log 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 1
done

if [ -z "$TUNNEL_URL" ]; then
    echo "Error: Failed to get tunnel URL"
    cat tunnel.log
    cleanup
    exit 1
fi

echo "✓ Tunnel URL: $TUNNEL_URL"

# Now start the controller with the BASE_URL set
echo ""
echo "Starting Controller on port $CONTROLLER_PORT..."
export AGENT_ID="$AGENT_ID"
export AGENT_HOST="localhost"
export AGENT_PORT="$GREEN_AGENT_PORT"
export CONTROLLER_PORT="$CONTROLLER_PORT"
export BASE_URL="$TUNNEL_URL"

# The AGENT_URL is what the agent should use as its URL in the agent card
export AGENT_URL="$TUNNEL_URL/to_agent/$AGENT_ID"
echo "Agent URL: $AGENT_URL"

$PYTHON -m src.simple_controller --host 0.0.0.0 --port $CONTROLLER_PORT &
CONTROLLER_PID=$!

# Wait for controller
for i in {1..15}; do
    if curl -s "http://localhost:$CONTROLLER_PORT/status" > /dev/null 2>&1; then
        echo "✓ Controller running"
        break
    fi
    sleep 1
done

# Give everything a moment to stabilize
sleep 3

# Test the endpoints
echo ""
echo "Testing endpoints..."

# Test /status (what AgentBeats checks first)
echo ""
echo "  GET /status:"
curl -s "http://localhost:$CONTROLLER_PORT/status" 2>/dev/null | $PYTHON -m json.tool 2>/dev/null

# Test /agents
echo ""
echo "  GET /agents:"
curl -s "http://localhost:$CONTROLLER_PORT/agents" 2>/dev/null | $PYTHON -m json.tool 2>/dev/null

# Test /agents/{agent_id} (THIS is where AgentBeats gets the agent_card!)
echo ""
echo "  GET /agents/$AGENT_ID:"
AGENT_INFO=$(curl -s "http://localhost:$CONTROLLER_PORT/agents/$AGENT_ID" 2>/dev/null)
echo "$AGENT_INFO" | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print('  state:', d.get('state')); card=json.loads(d.get('agent_card','{}')); print('  agent_card.name:', card.get('name')); print('  agent_card.url:', card.get('url'))" 2>/dev/null || echo "  Failed to parse"

# Test proxy
echo ""
echo "  GET /to_agent/$AGENT_ID/.well-known/agent-card.json:"
CARD_RESP=$(curl -s "http://localhost:$CONTROLLER_PORT/to_agent/$AGENT_ID/.well-known/agent-card.json" 2>/dev/null | $PYTHON -c "import sys,json; d=json.load(sys.stdin); print(f'  name: {d.get(\"name\")}, url: {d.get(\"url\")}') " 2>/dev/null || echo "  FAILED")
echo "$CARD_RESP"

# Test via tunnel
echo ""
echo "Testing via tunnel..."
sleep 2
TUNNEL_STATUS=$(curl -s "$TUNNEL_URL/status" 2>/dev/null || echo "waiting...")
echo "  Tunnel /status: $TUNNEL_STATUS"

TUNNEL_AGENTS=$(curl -s "$TUNNEL_URL/agents" 2>/dev/null || echo "waiting...")
echo "  Tunnel /agents: $TUNNEL_AGENTS"

echo ""
echo "========================================"
echo "  ✅ SETUP COMPLETE!"
echo "========================================"
echo ""
echo "  📡 CONTROLLER URL (submit this to AgentBeats):"
echo ""
echo "     $TUNNEL_URL"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  AgentBeats will check these endpoints:"
echo "    • $TUNNEL_URL/status"
echo "    • $TUNNEL_URL/agents"
echo "    • $TUNNEL_URL/to_agent/$AGENT_ID/.well-known/agent-card.json"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  🖥️  Local endpoints:"
echo "     Controller: http://localhost:$CONTROLLER_PORT"
echo "     Green Agent: http://localhost:$GREEN_AGENT_PORT"
echo "     White Agent: http://localhost:$WHITE_AGENT_PORT"
echo ""
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

# Wait
wait $CLOUDFLARED_PID
