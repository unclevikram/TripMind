#!/bin/bash
# Convenience script to run the trip itinerary planning agent

# Check for BROWSER_USE_API_KEY
if [[ -z "$BROWSER_USE_API_KEY" ]]; then
  echo "⚠️  BROWSER_USE_API_KEY is not set."
  echo "Set it with: export BROWSER_USE_API_KEY=your-key"
  echo "Continuing anyway (agent will show error if needed)..."
  echo ""
fi

# Default task if not provided
TASK="${1:-Plan a 3-day itinerary for visiting San Francisco. Include top attractions, recommended restaurants for each meal, and organize activities by day with estimated timing.}"
TASK_ID="${2:-itinerary_san_francisco_3days}"
BASE_DIR="${3:-./data/example}"

echo "🗺️  Running Trip Itinerary Planning Agent"
echo "========================================"
echo "Task: $TASK"
echo "Task ID: $TASK_ID"
echo "Output dir: $BASE_DIR/$TASK_ID"
echo ""

python src/agents/browser_use_itinerary_agent.py \
  --task "$TASK" \
  --task_id "$TASK_ID" \
  --base_dir "$BASE_DIR" \
  --visible

echo ""
echo "✅ Done! Results saved to: $BASE_DIR/$TASK_ID"
echo ""
echo "📄 View the itinerary:"
echo "   cat $BASE_DIR/$TASK_ID/result.json | python -m json.tool"

