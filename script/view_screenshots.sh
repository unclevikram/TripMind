#!/bin/bash
# Utility script to view screenshots from agent runs

if [ -z "$1" ]; then
    echo "📸 Screenshot Viewer"
    echo "===================="
    echo ""
    echo "Usage: bash script/view_screenshots.sh <task_id>"
    echo ""
    echo "Available tasks with screenshots:"
    echo ""
    
    for dir in data/examples/*/; do
        if [ -d "$dir" ]; then
            TASK_ID=$(basename "$dir")
            SCREENSHOT_COUNT=$(ls -1 "$dir/trajectory"/*.png 2>/dev/null | wc -l | tr -d ' ')
            if [ "$SCREENSHOT_COUNT" -gt 0 ]; then
                echo "  ✓ $TASK_ID ($SCREENSHOT_COUNT screenshots)"
            fi
        fi
    done
    
    echo ""
    echo "Example: bash script/view_screenshots.sh my_flight_test"
    exit 0
fi

TASK_ID=$1
TRAJ_DIR="data/examples/$TASK_ID/trajectory"

if [ ! -d "$TRAJ_DIR" ]; then
    echo "❌ Error: Task '$TASK_ID' not found in data/examples/"
    exit 1
fi

SCREENSHOT_COUNT=$(ls -1 "$TRAJ_DIR"/*.png 2>/dev/null | wc -l | tr -d ' ')

if [ "$SCREENSHOT_COUNT" -eq 0 ]; then
    echo "⚠️  No screenshots found for task: $TASK_ID"
    echo "   Location: $TRAJ_DIR"
    exit 1
fi

echo "📸 Screenshots for task: $TASK_ID"
echo "=================================="
echo ""
echo "Total screenshots: $SCREENSHOT_COUNT"
echo "Location: $TRAJ_DIR"
echo ""

# List all screenshots with size
ls -lh "$TRAJ_DIR"/*.png | awk '{print "  " $9 " (" $5 ")"}'

echo ""
echo "Commands:"
echo "  📂 Open folder: open $TRAJ_DIR"
echo "  🖼️  View first: open $TRAJ_DIR/0_full_screenshot.png"
echo "  🖼️  View last:  open $TRAJ_DIR/$((SCREENSHOT_COUNT-1))_full_screenshot.png"
echo "  🎬 View all:   open $TRAJ_DIR/*.png"

# Ask if user wants to open
read -p "Open screenshot folder? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    open "$TRAJ_DIR"
fi

