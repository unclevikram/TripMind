#!/bin/bash
# start_with_tunnel.sh - Start TripMind agents with manual Cloudflare tunnel
#
# ALTERNATIVE to using AgentBeats controller (agentbeats run_ctrl).
# Use this if you want to manage the cloudflared tunnel yourself.
#
# The recommended approach is to use:
#   ./start_controller.sh
# or:
#   agentbeats run_ctrl

set -e

echo "========================================"
echo "  Starting TripMind with Manual Cloudflare Tunnel"
echo "========================================"
echo ""
echo "  NOTE: The recommended approach is to use:"
echo "    ./start_controller.sh"
echo "  which handles tunneling automatically."
echo ""
echo "========================================"

# Check for cloudflared
if ! command -v cloudflared &> /dev/null; then
    echo "Error: cloudflared not found."
    echo "Install it from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
    exit 1
fi

# Configuration
export HOST="0.0.0.0"
export WHITE_AGENT_PORT="${WHITE_AGENT_PORT:-9001}"
export AGENT_PORT="${AGENT_PORT:-9002}"

# Cleanup any existing processes
cleanup() {
    echo ""
    echo "Cleaning up..."
    kill $GREEN_PID 2>/dev/null || true
    kill $WHITE_PID 2>/dev/null || true
    kill $CLOUDFLARED_PID 2>/dev/null || true
    rm -f tunnel.log
    exit 0
}
trap cleanup INT TERM

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

# Start White Agent
echo "Starting White Agent on port $WHITE_AGENT_PORT..."
python3 main.py white --host "$HOST" --port "$WHITE_AGENT_PORT" &
WHITE_PID=$!
check_service "http://localhost:$WHITE_AGENT_PORT/status" "White Agent" 30

# Start Green Agent (initially without BASE_URL)
echo "Starting Green Agent on port $AGENT_PORT..."
python3 main.py green --host "$HOST" --port "$AGENT_PORT" &
GREEN_PID=$!
check_service "http://localhost:$AGENT_PORT/status" "Green Agent" 15

# Create Cloudflare tunnel
echo ""
echo "Creating Cloudflare tunnel..."
rm -f tunnel.log
cloudflared tunnel --url "http://localhost:$AGENT_PORT" 2>&1 | tee tunnel.log &
CLOUDFLARED_PID=$!

# Wait for tunnel URL to appear
echo "Waiting for tunnel to be established..."
TUNNEL_URL=""
for i in $(seq 1 30); do
    TUNNEL_URL=$(grep -o "https://[a-z0-9-]*\.trycloudflare\.com" tunnel.log 2>/dev/null | head -1)
    if [ -n "$TUNNEL_URL" ]; then
        break
    fi
    sleep 1
done

if [ -n "$TUNNEL_URL" ]; then
    echo ""
    echo "✅ Tunnel established: $TUNNEL_URL"
    echo ""
    
    # Restart Green Agent with BASE_URL set
    echo "Restarting Green Agent with public URL..."
    kill $GREEN_PID 2>/dev/null || true
    sleep 2

    export BASE_URL="$TUNNEL_URL"
    python3 main.py green --host "$HOST" --port "$AGENT_PORT" &
    GREEN_PID=$!
    
    # Wait for green agent to restart
    check_service "http://localhost:$AGENT_PORT/status" "Green Agent" 15

    # Verify the agent card shows correct URL
    echo ""
    echo "Verifying agent card..."
    curl -s "http://localhost:$AGENT_PORT/.well-known/agent-card.json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Agent: {d.get(\"name\")}')" 2>/dev/null || true
    curl -s "http://localhost:$AGENT_PORT/.well-known/agent-card.json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'URL in card: {d.get(\"url\")}')" 2>/dev/null || true

    echo ""
    echo "========================================"
    echo "  ✅ SETUP COMPLETE!"
    echo "========================================"
    echo ""
    echo "  🌐 Public URL: $TUNNEL_URL"
    echo ""
    echo "  📋 Test Agent Card:"
    echo "     curl $TUNNEL_URL/.well-known/agent-card.json"
    echo ""
    echo "  📝 Submit this URL to AgentBeats:"
    echo "     $TUNNEL_URL"
    echo ""
    echo "  Press Ctrl+C to stop"
    echo "========================================"
    echo ""

    # Keep running
    wait
else
    echo ""
    echo "❌ Failed to establish tunnel"
    echo ""
    echo "Tunnel log:"
    cat tunnel.log
    cleanup
    exit 1
fi
