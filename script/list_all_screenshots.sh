#!/bin/bash
# List all agent runs and their screenshot counts

echo "📸 All Agent Runs and Screenshots"
echo "=================================="
echo ""

TOTAL_TASKS=0
TOTAL_SCREENSHOTS=0

for dir in data/examples/*/; do
    if [ -d "$dir" ]; then
        TASK_ID=$(basename "$dir")
        SCREENSHOT_COUNT=$(ls -1 "$dir/trajectory"/*.png 2>/dev/null | wc -l | tr -d ' ')
        
        TOTAL_TASKS=$((TOTAL_TASKS + 1))
        TOTAL_SCREENSHOTS=$((TOTAL_SCREENSHOTS + SCREENSHOT_COUNT))
        
        if [ "$SCREENSHOT_COUNT" -gt 0 ]; then
            echo "✓ $TASK_ID"
            echo "  📸 $SCREENSHOT_COUNT screenshots"
            echo "  📁 $dir/trajectory/"
            
            # Show task description if result.json exists
            if [ -f "$dir/result.json" ]; then
                TASK_DESC=$(cat "$dir/result.json" | python -c "import sys, json; print(json.load(sys.stdin).get('task', 'N/A'))" 2>/dev/null || echo "N/A")
                echo "  📋 Task: $TASK_DESC"
            fi
            echo ""
        else
            echo "⚠️  $TASK_ID"
            echo "  📸 No screenshots"
            echo ""
        fi
    fi
done

echo "=================================="
echo "Summary:"
echo "  Total tasks: $TOTAL_TASKS"
echo "  Total screenshots: $TOTAL_SCREENSHOTS"
echo ""

if [ "$TOTAL_SCREENSHOTS" -gt 0 ]; then
    TOTAL_SIZE=$(du -sh data/examples/*/trajectory/*.png 2>/dev/null | awk '{sum+=$1} END {print sum}' || echo "0")
    echo "Tip: Use 'bash script/view_screenshots.sh <task_id>' to view screenshots for a specific task"
fi

