#!/usr/bin/env bash

# Check for BROWSER_USE_API_KEY
if [[ -z "$BROWSER_USE_API_KEY" ]]; then
  echo "⚠️  BROWSER_USE_API_KEY is not set."
  echo "Set it with: export BROWSER_USE_API_KEY=your-key"
  echo "Continuing anyway (agent will show error if needed)..."
  echo ""
fi

# Default task if not provided
TASK="${1:-Find a round-trip flight from NYC to SFO next month and show results.}"
TASK_ID="${2:-flight_search}"
BASE_DIR="${3:-./data/examples}"

echo "✈️  Running Flight Search Agent"
echo "==============================="
echo "Task: $TASK"
echo "Task ID: $TASK_ID"
echo "Output dir: $BASE_DIR/$TASK_ID"
echo ""

python src/agents/browser_use_flight_agent.py \
  --task "$TASK" \
  --task_id "$TASK_ID" \
  --base_dir "$BASE_DIR" \
  --visible

echo ""
echo "✅ Done! Results saved to: $BASE_DIR/$TASK_ID"
echo ""
echo "📄 View results:"
echo "   cat $BASE_DIR/$TASK_ID/result.json | python -m json.tool"
echo ""
echo "📸 View screenshots:"
SCREENSHOT_COUNT=$(ls -1 "$BASE_DIR/$TASK_ID/trajectory"/*.png 2>/dev/null | wc -l | tr -d ' ')
if [ "$SCREENSHOT_COUNT" -gt 0 ]; then
    echo "   ✓ $SCREENSHOT_COUNT screenshots saved to: $BASE_DIR/$TASK_ID/trajectory/"
    echo "   Open folder: open $BASE_DIR/$TASK_ID/trajectory/"
else
    echo "   ⚠️  No screenshots found (may need BROWSER_USE_API_KEY)"
fi

