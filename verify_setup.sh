#!/bin/bash
# verify_setup.sh - Verify TripMind AgentBeats setup is correct
#
# Run this script to check that everything is properly configured
# before submitting to AgentBeats.

set -e

echo "========================================"
echo "  TripMind Setup Verification"
echo "========================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0

# Check 1: Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2)
echo "  Python version: $PYTHON_VERSION"

# Check 2: Required packages
echo ""
echo "Checking required packages..."

check_package() {
    local pkg=$1
    if python3 -c "import $pkg" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $pkg installed"
        return 0
    else
        echo -e "  ${RED}✗${NC} $pkg NOT installed"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

check_package "a2a" || true
check_package "uvicorn" || true
check_package "starlette" || true
check_package "httpx" || true

# Check agentbeats command
echo ""
echo "Checking AgentBeats controller..."
if command -v agentbeats &> /dev/null; then
    echo -e "  ${GREEN}✓${NC} agentbeats command available"
else
    echo -e "  ${RED}✗${NC} agentbeats command NOT found"
    echo "    Install with: pip install earthshaker"
    ERRORS=$((ERRORS + 1))
fi

# Check 3: Required files
echo ""
echo "Checking required files..."

check_file() {
    local file=$1
    if [[ -f "$file" ]]; then
        echo -e "  ${GREEN}✓${NC} $file exists"
        return 0
    else
        echo -e "  ${RED}✗${NC} $file NOT found"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

check_file "run.sh" || true
check_file "main.py" || true
check_file "src/green_agent.py" || true
check_file "src/white_agent.py" || true
check_file "Procfile" || true

# Check 4: run.sh is executable
echo ""
echo "Checking run.sh permissions..."
if [[ -x "run.sh" ]]; then
    echo -e "  ${GREEN}✓${NC} run.sh is executable"
else
    echo -e "  ${YELLOW}!${NC} run.sh is not executable, fixing..."
    chmod +x run.sh
    echo -e "  ${GREEN}✓${NC} Fixed"
fi

# Check 5: Environment variables
echo ""
echo "Checking environment variables..."

if [[ -n "$BROWSER_USE_API_KEY" ]]; then
    echo -e "  ${GREEN}✓${NC} BROWSER_USE_API_KEY is set"
else
    echo -e "  ${YELLOW}!${NC} BROWSER_USE_API_KEY is not set (needed for browser automation)"
fi

if [[ -n "$OPENAI_API_KEY" ]]; then
    echo -e "  ${GREEN}✓${NC} OPENAI_API_KEY is set"
else
    echo -e "  ${YELLOW}!${NC} OPENAI_API_KEY is not set (may be needed)"
fi

# Check 6: Test local agent startup
echo ""
echo "Testing local agent startup (quick test)..."

# Start agents in background
timeout 15 python3 main.py green --host 0.0.0.0 --port 9099 &>/dev/null &
TEST_PID=$!
sleep 5

# Test endpoint
if curl -s "http://localhost:9099/.well-known/agent-card.json" > /dev/null 2>&1; then
    echo -e "  ${GREEN}✓${NC} Agent can start and serve agent card"
    
    # Check agent card content
    AGENT_NAME=$(curl -s "http://localhost:9099/.well-known/agent-card.json" | python3 -c "import sys,json; print(json.load(sys.stdin).get('name',''))" 2>/dev/null)
    if [[ -n "$AGENT_NAME" ]]; then
        echo "  Agent name: $AGENT_NAME"
    fi
else
    echo -e "  ${RED}✗${NC} Agent failed to start or serve agent card"
    ERRORS=$((ERRORS + 1))
fi

# Cleanup test
kill $TEST_PID 2>/dev/null || true
wait $TEST_PID 2>/dev/null || true

# Summary
echo ""
echo "========================================"
if [[ $ERRORS -eq 0 ]]; then
    echo -e "  ${GREEN}✓ All checks passed!${NC}"
    echo ""
    echo "  Your setup looks good. To submit to AgentBeats:"
    echo ""
    echo "  1. Start the controller:"
    echo "     ./start_controller.sh"
    echo "     OR"
    echo "     agentbeats run_ctrl"
    echo ""
    echo "  2. Look for the public URL in the output"
    echo ""
    echo "  3. Submit that URL to https://agentbeats.io"
else
    echo -e "  ${RED}✗ $ERRORS issue(s) found${NC}"
    echo ""
    echo "  Please fix the issues above before submitting."
fi
echo "========================================"
