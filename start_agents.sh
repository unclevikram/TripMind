#!/bin/bash
#
# TripMind Agent Launcher
# Starts both White Agent (browser automation) and Green Agent (assessment orchestrator)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "=============================================="
echo "  TripMind Agent Launcher"
echo "=============================================="
echo -e "${NC}"

# Check for required environment variables
if [ -z "$BROWSER_USE_API_KEY" ]; then
    echo -e "${YELLOW}WARNING: BROWSER_USE_API_KEY not set${NC}"
    echo "White agent will not be able to execute browser tasks"
    echo ""
fi

# Default ports
WHITE_AGENT_PORT=${WHITE_AGENT_PORT:-9001}
GREEN_AGENT_PORT=${GREEN_AGENT_PORT:-9002}

# Parse command line arguments
MODE="both"
while [[ $# -gt 0 ]]; do
    case $1 in
        --white-only)
            MODE="white"
            shift
            ;;
        --green-only)
            MODE="green"
            shift
            ;;
        --white-port)
            WHITE_AGENT_PORT="$2"
            shift 2
            ;;
        --green-port)
            GREEN_AGENT_PORT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --white-only     Start only the white agent"
            echo "  --green-only     Start only the green agent"
            echo "  --white-port N   Set white agent port (default: 9001)"
            echo "  --green-port N   Set green agent port (default: 9002)"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to start white agent
start_white_agent() {
    echo -e "${GREEN}Starting White Agent on port $WHITE_AGENT_PORT...${NC}"
    python -m src.white_agent --port $WHITE_AGENT_PORT &
    WHITE_PID=$!
    echo "White Agent PID: $WHITE_PID"
}

# Function to start green agent
start_green_agent() {
    echo -e "${GREEN}Starting Green Agent on port $GREEN_AGENT_PORT...${NC}"
    WHITE_AGENT_URL="http://localhost:$WHITE_AGENT_PORT" \
    python -m src.green_agent --port $GREEN_AGENT_PORT --white-agent-url "http://localhost:$WHITE_AGENT_PORT" &
    GREEN_PID=$!
    echo "Green Agent PID: $GREEN_PID"
}

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down agents...${NC}"
    if [ ! -z "$WHITE_PID" ]; then
        kill $WHITE_PID 2>/dev/null || true
    fi
    if [ ! -z "$GREEN_PID" ]; then
        kill $GREEN_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Done${NC}"
    exit 0
}

# Set up signal handler
trap cleanup SIGINT SIGTERM

# Start agents based on mode
case $MODE in
    "white")
        start_white_agent
        wait $WHITE_PID
        ;;
    "green")
        start_green_agent
        wait $GREEN_PID
        ;;
    "both")
        start_white_agent
        sleep 2  # Give white agent time to start
        start_green_agent

        echo ""
        echo -e "${BLUE}=============================================="
        echo "  Both agents are running!"
        echo "=============================================="
        echo -e "${NC}"
        echo "White Agent (Browser Automation):"
        echo "  - Status: http://localhost:$WHITE_AGENT_PORT/status"
        echo "  - Agent Card: http://localhost:$WHITE_AGENT_PORT/.well-known/agent-card.json"
        echo ""
        echo "Green Agent (Assessment Orchestrator):"
        echo "  - Status: http://localhost:$GREEN_AGENT_PORT/status"
        echo "  - Agent Card: http://localhost:$GREEN_AGENT_PORT/.well-known/agent-card.json"
        echo "  - Start Assessment: POST http://localhost:$GREEN_AGENT_PORT/start-assessment"
        echo ""
        echo -e "${YELLOW}Press Ctrl+C to stop both agents${NC}"
        echo ""

        # Wait for both processes
        wait
        ;;
esac
