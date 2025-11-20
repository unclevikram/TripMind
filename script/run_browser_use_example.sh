#!/usr/bin/env bash

set -euo pipefail

# Optional: install chromium for playwright if needed (one-time)
# uvx playwright install chromium --with-deps --no-shell || true

# Ensure Playwright uses the local browser path (installed earlier)
export PLAYWRIGHT_BROWSERS_PATH=/Users/minkush/Desktop/Online-Mind2Web/.playwright-browsers

TASK_ID=${TASK_ID:-browser_use_search_flights}
TASK_TEXT=${TASK_TEXT:-"Find a round-trip flight from NYC to SFO next month and show results."}

PYFILE="/Users/minkush/Desktop/Online-Mind2Web/src/agents/browser_use_example.py"
# Prefer uv if available (real Browser-Use env), else fall back to repo venv python
UV_BIN="/Users/minkush/Desktop/Online-Mind2Web/.uvbin/uv"
if [[ -x "$UV_BIN" ]]; then
  CMD=("$UV_BIN" run python)
else
  CMD=("/Users/minkush/Desktop/Online-Mind2Web/venv/bin/python")
fi

"${CMD[@]}" "$PYFILE" \
  --task "$TASK_TEXT" \
  --task_id "$TASK_ID" \
  --base_dir "/Users/minkush/Desktop/Online-Mind2Web/data/example" \
  --visible

echo "Generated: /Users/minkush/Desktop/Online-Mind2Web/data/example/${TASK_ID}"


