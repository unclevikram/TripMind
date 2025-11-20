#!/bin/bash
# Convenience script to run the hotel browsing agent

# Check for BROWSER_USE_API_KEY
if [[ -z "$BROWSER_USE_API_KEY" ]]; then
  echo "⚠️  BROWSER_USE_API_KEY is not set."
  echo "Set it with: export BROWSER_USE_API_KEY=your-key"
  echo "Continuing anyway (agent will show error if needed)..."
  echo ""
fi

# Default task if not provided
TASK="${1:-Find a hotel in Seattle for 2 adults checking in tomorrow and checking out in 3 days with free WiFi and breakfast included. Show results sorted by price.}"
TASK_ID="${2:-hotel_search_seattle}"
BASE_DIR="${3:-./data/example}"

echo "🏨 Running Hotel Browsing Agent"
echo "================================"
echo "Task: $TASK"
echo "Task ID: $TASK_ID"
echo "Output dir: $BASE_DIR/$TASK_ID"
echo ""

python src/agents/browser_use_hotel_agent.py \
  --task "$TASK" \
  --task_id "$TASK_ID" \
  --base_dir "$BASE_DIR" \
  --visible

echo ""
echo "✅ Done! Results saved to: $BASE_DIR/$TASK_ID"

