#!/bin/bash
#
# Complete End-to-End Test Script for TripMind
# Tests: White Agents → Green Agent → Trajectory Saving → WebJudge Evaluation
#

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  TripMind End-to-End Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Check environment variables
echo -e "${YELLOW}Step 1: Checking environment variables...${NC}"
if [ -z "$BROWSER_USE_API_KEY" ]; then
    echo -e "${RED}ERROR: BROWSER_USE_API_KEY not set${NC}"
    echo "Please run: export BROWSER_USE_API_KEY='your-key'"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}ERROR: OPENAI_API_KEY not set${NC}"
    echo "Please run: export OPENAI_API_KEY='sk-your-key'"
    exit 1
fi
echo -e "${GREEN}✓ Environment variables set${NC}"
echo ""

# Step 2: Start agents
echo -e "${YELLOW}Step 2: Starting agents (3 white agents + 1 green agent)...${NC}"
echo "Starting in background..."
./start_multiple_assessees.sh 3 > /tmp/tripmind_agents.log 2>&1 &
AGENTS_PID=$!
echo "Agents PID: $AGENTS_PID"
echo "Waiting 15 seconds for agents to start..."
sleep 15

# Check if agents are running
if ! curl -s http://localhost:9001/status > /dev/null; then
    echo -e "${RED}ERROR: White Agent 1 (9001) not responding${NC}"
    kill $AGENTS_PID 2>/dev/null || true
    exit 1
fi
if ! curl -s http://localhost:9002/status > /dev/null; then
    echo -e "${RED}ERROR: Green Agent (9002) not responding${NC}"
    kill $AGENTS_PID 2>/dev/null || true
    exit 1
fi
echo -e "${GREEN}✓ All agents running${NC}"
echo ""

# Step 3: Run assessment with task assignment
echo -e "${YELLOW}Step 3: Running assessment (assigning tasks to agents)...${NC}"
echo "Sending request to green agent..."

curl -s -X POST http://localhost:9002/start-assessment \
  -H "Content-Type: application/json" \
  -d @assessment_config_example.json \
  > /tmp/assessment_response.json

echo -e "${GREEN}✓ Assessment completed${NC}"
echo ""
echo "Basic results from green agent:"
cat /tmp/assessment_response.json | jq '{
  status: .status,
  aggregate_metrics: .metrics.aggregate,
  per_assessee: .metrics.per_assessee
}'
echo ""

# Step 4: Check saved trajectories
echo -e "${YELLOW}Step 4: Checking saved trajectories...${NC}"
TRAJECTORY_COUNT=$(find ./data/my_assessment -name "result.json" 2>/dev/null | wc -l | tr -d ' ')
echo "Found $TRAJECTORY_COUNT trajectory files"

if [ "$TRAJECTORY_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}WARNING: No trajectories saved. This is expected if tasks failed.${NC}"
else
    echo -e "${GREEN}✓ Trajectories saved to: ./data/my_assessment/${NC}"
    find ./data/my_assessment -name "result.json"
fi
echo ""

# Step 5: Run WebJudge evaluation (if trajectories exist)
if [ "$TRAJECTORY_COUNT" -gt 0 ]; then
    echo -e "${YELLOW}Step 5: Running WebJudge evaluation...${NC}"
    python src/run.py \
      --mode "WebJudge_Online_Mind2Web_eval" \
      --model "gpt-4o-mini" \
      --trajectories_dir "./data/my_assessment" \
      --api_key "$OPENAI_API_KEY" \
      --output_path "./data/my_assessment_eval" \
      --num_worker 1 \
      --score_threshold 3

    echo ""
    echo -e "${GREEN}✓ WebJudge evaluation completed${NC}"
    echo ""
    echo "Detailed evaluation results:"
    cat ./data/my_assessment_eval/WebJudge_Online_Mind2Web_eval_gpt-4o-mini_score_threshold_3_auto_eval_results.json | jq '{
      task: .task,
      predicted_label: .predicted_label,
      result: (if .predicted_label == 1 then "PASS ✓" else "FAIL ✗" end),
      key_points: .key_points
    }'
else
    echo -e "${YELLOW}Step 5: Skipping WebJudge evaluation (no trajectories)${NC}"
fi
echo ""

# Step 6: Cleanup
echo -e "${YELLOW}Step 6: Cleaning up...${NC}"
echo "Stopping agents..."
kill $AGENTS_PID 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Assessment Results: /tmp/assessment_response.json"
echo "Saved Trajectories: ./data/my_assessment/"
if [ "$TRAJECTORY_COUNT" -gt 0 ]; then
    echo "WebJudge Results: ./data/my_assessment_eval/"
fi
echo ""
echo -e "${GREEN}End-to-end test completed!${NC}"

