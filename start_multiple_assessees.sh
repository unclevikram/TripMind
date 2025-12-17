#!/bin/bash
#
# TripMind Multi-Assessee Launcher
# Starts one Green Agent (assessor) and multiple White Agents (assessees)
#
# Usage:
#   ./start_multiple_assessees.sh [NUM_ASSEESEES]
#   Example: ./start_multiple_assessees.sh 3
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

NUM_ASSEESEES=${1:-2}  # Default to 2 assessees
GREEN_AGENT_PORT=${GREEN_AGENT_PORT:-9002}
WHITE_AGENT_START_PORT=${WHITE_AGENT_START_PORT:-9001}

# Function to check if a port is in use and kill the process
kill_port_if_occupied() {
    local PORT=$1
    local PORT_NAME=$2
    
    # Check if port is in use (works on macOS and Linux)
    if command -v lsof > /dev/null 2>&1; then
        PID=$(lsof -ti:$PORT 2>/dev/null || true)
        if [ ! -z "$PID" ]; then
            echo -e "${YELLOW}Port $PORT ($PORT_NAME) is occupied by PID $PID. Killing process...${NC}"
            kill -9 $PID 2>/dev/null || true
            sleep 1  # Give it a moment to release the port
            echo -e "${GREEN}Port $PORT is now free${NC}"
        fi
    elif command -v fuser > /dev/null 2>&1; then
        # Alternative for Linux systems without lsof
        if fuser $PORT/tcp > /dev/null 2>&1; then
            echo -e "${YELLOW}Port $PORT ($PORT_NAME) is occupied. Killing process...${NC}"
            fuser -k $PORT/tcp 2>/dev/null || true
            sleep 1
            echo -e "${GREEN}Port $PORT is now free${NC}"
        fi
    else
        echo -e "${YELLOW}Warning: Cannot check if port $PORT is in use (lsof/fuser not found)${NC}"
    fi
}

echo -e "${BLUE}"
echo "=============================================="
echo "  TripMind Multi-Assessee Launcher"
echo "=============================================="
echo -e "${NC}"

# Check and free up ports before starting
echo -e "${YELLOW}Checking for port conflicts...${NC}"
kill_port_if_occupied $GREEN_AGENT_PORT "Green Agent"

for i in $(seq 1 $NUM_ASSEESEES); do
    # Use odd ports: 9001, 9003, 9005, etc. (skip 9002 for green agent)
    PORT=$((WHITE_AGENT_START_PORT + (i - 1) * 2))
    kill_port_if_occupied $PORT "White Agent $i"
done

echo ""
echo -e "${GREEN}Starting ${NUM_ASSEESEES} White Agent(s) (Assessees)...${NC}"

# Array to store white agent PIDs and URLs
WHITE_PIDS=()
WHITE_URLS=()

# Start multiple white agents
for i in $(seq 1 $NUM_ASSEESEES); do
    # Use odd ports: 9001, 9003, 9005, etc. (skip 9002 for green agent)
    PORT=$((WHITE_AGENT_START_PORT + (i - 1) * 2))
    URL="http://localhost:$PORT"
    WHITE_URLS+=($URL)
    
    echo -e "${GREEN}  Starting White Agent $i on port $PORT...${NC}"
    python -m src.white_agent --port $PORT &
    PID=$!
    WHITE_PIDS+=($PID)
    echo "    White Agent $i PID: $PID"
    sleep 1  # Small delay between starts
done

# Wait a bit for all white agents to start
sleep 2

# Start green agent with all white agent URLs
echo ""
# Green agent port was already checked above, but check again to be safe
kill_port_if_occupied $GREEN_AGENT_PORT "Green Agent"
echo -e "${GREEN}Starting Green Agent (Assessor) on port $GREEN_AGENT_PORT...${NC}"
echo -e "${BLUE}  Assessees: ${WHITE_URLS[@]}${NC}"

# Convert array to space-separated string for argument
WHITE_URLS_STR="${WHITE_URLS[@]}"
python -m src.green_agent --port $GREEN_AGENT_PORT --white-agent-urls $WHITE_URLS_STR &
GREEN_PID=$!

echo ""
echo -e "${BLUE}=============================================="
echo "  All agents are running!"
echo "=============================================="
echo -e "${NC}"
echo "Green Agent (Assessor):"
echo "  - Status: http://localhost:$GREEN_AGENT_PORT/status"
echo "  - Agent Card: http://localhost:$GREEN_AGENT_PORT/.well-known/agent-card.json"
echo "  - Start Assessment: POST http://localhost:$GREEN_AGENT_PORT/start-assessment"
echo ""
echo "White Agents (Assessees):"
for i in $(seq 1 $NUM_ASSEESEES); do
    # Use odd ports: 9001, 9003, 9005, etc. (skip 9002 for green agent)
    PORT=$((WHITE_AGENT_START_PORT + (i - 1) * 2))
    echo "  Assessee $i:"
    echo "    - Status: http://localhost:$PORT/status"
    echo "    - Agent Card: http://localhost:$PORT/.well-known/agent-card.json"
done
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop all agents${NC}"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down agents...${NC}"
    kill $GREEN_PID 2>/dev/null || true
    for PID in "${WHITE_PIDS[@]}"; do
        kill $PID 2>/dev/null || true
    done
    echo -e "${GREEN}Done${NC}"
    exit 0
}

# Set up signal handler
trap cleanup SIGINT SIGTERM

# Wait for all processes
wait

