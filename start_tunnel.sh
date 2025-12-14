#!/bin/bash
# start_tunnel.sh - Start TripMind with Cloudflare Tunnel (No AgentBeats Controller)
#
# This is a simpler, more reliable approach that:
# 1. Starts your agents directly
# 2. Creates a Cloudflare tunnel
# 3. Gives you the URL to submit to AgentBeats
#
# The AgentBeats controller has bugs with Python 3.14, so we bypass it.

set -e

GREEN_AGENT_PORT=9002
WHITE_AGENT_PORT=9001

echo "========================================"
echo "  TripMind - Direct Cloudflare Tunnel"
echo "========================================"
echo ""

# Check for cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "Error: 'cloudflared' command not found."
    echo "Install: brew install cloudflared"
    exit 1
fi

# Cleanup function
cleanup() {
    echo ""
    echo "Shutting down..."
    kill $CLOUDFLARED_PID 2>/dev/null || true
    kill $GREEN_PID 2>/dev/null || true
    kill $WHITE_PID 2>/dev/null || true
    rm -f tunnel.log
    exit 0
}
trap cleanup INT TERM

# Kill any existing processes on our ports
echo "Cleaning up..."
lsof -ti:$GREEN_AGENT_PORT | xargs kill -9 2>/dev/null || true
lsof -ti:$WHITE_AGENT_PORT | xargs kill -9 2>/dev/null || true
rm -f tunnel.log
sleep 1

# Start White Agent
echo "Starting White Agent on port $WHITE_AGENT_PORT..."
python3 main.py white --host 0.0.0.0 --port $WHITE_AGENT_PORT &
WHITE_PID=$!

# Wait for White Agent
echo "Waiting for White Agent..."
for i in {1..30}; do
    if curl -s "http://localhost:$WHITE_AGENT_PORT/status" > /dev/null 2>&1; then
        echo "✓ White Agent is running"
        break
    fi
    sleep 1
done

# Start Green Agent
echo "Starting Green Agent on port $GREEN_AGENT_PORT..."
python3 main.py green --host 0.0.0.0 --port $GREEN_AGENT_PORT &
GREEN_PID=$!

# Wait for Green Agent
echo "Waiting for Green Agent..."
for i in {1..30}; do
    if curl -s "http://localhost:$GREEN_AGENT_PORT/status" > /dev/null 2>&1; then
        echo "✓ Green Agent is running"
        break
    fi
    sleep 1
done

# Verify agent card works locally
echo ""
echo "Testing local agent card..."
if curl -s "http://localhost:$GREEN_AGENT_PORT/.well-known/agent-card.json" > /dev/null 2>&1; then
    AGENT_NAME=$(curl -s "http://localhost:$GREEN_AGENT_PORT/.well-known/agent-card.json" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name','Unknown'))" 2>/dev/null)
    echo "✓ Agent card working: $AGENT_NAME"
else
    echo "✗ Agent card not accessible"
    exit 1
fi

# Create Cloudflare tunnel
echo ""
echo "Creating Cloudflare tunnel..."
cloudflared tunnel --url "http://localhost:$GREEN_AGENT_PORT" 2>&1 | tee tunnel.log &
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
    echo ""
    echo "Error: Failed to get tunnel URL after 45 seconds"
    echo ""
    echo "Tunnel log:"
    cat tunnel.log
    cleanup
    exit 1
fi

# Test the tunnel
echo ""
echo "Testing tunnel..."
sleep 2
if curl -s "$TUNNEL_URL/.well-known/agent-card.json" > /dev/null 2>&1; then
    echo "✓ Tunnel is working!"
else
    echo "⚠ Tunnel may need a moment to stabilize..."
fi

echo ""
echo "========================================"
echo "  ✅ SETUP COMPLETE!"
echo "========================================"
echo ""
echo "  🌐 PUBLIC URL:"
echo ""
echo "     $TUNNEL_URL"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  📝 SUBMIT THIS URL TO AGENTBEATS:"
echo ""
echo "     $TUNNEL_URL"
echo ""
echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  📋 Test endpoints:"
echo "     Agent Card: $TUNNEL_URL/.well-known/agent-card.json"
echo "     Status:     $TUNNEL_URL/status"
echo ""
echo "  🖥️  Local endpoints:"
echo "     Green Agent: http://localhost:$GREEN_AGENT_PORT"
echo "     White Agent: http://localhost:$WHITE_AGENT_PORT"
echo ""
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

# Keep running
wait $CLOUDFLARED_PID
