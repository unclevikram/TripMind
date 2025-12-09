# Browser Agents

This folder contains browser automation agents that use the `browser-use` library to perform web navigation tasks and save results in Online-Mind2Web-compatible format for evaluation.

---

## 📁 Available Agents

### 1. **Flight Search Agent** (`browser_use_example.py`)
Searches for flights using Google Flights.

**Example usage:**
```bash
python src/agents/browser_use_flight_agent.py \
  --task "Find a round-trip flight from SFO to Seattle tomorrow without returning flights and show results." \
  --task_id "my_flight_test" \
  --base_dir "./data/example" \
  --visible
```

**Features:**
- Handles Google Flights UI quirks (prefilled locations, date pickers)
- Supports one-way, round-trip, and multi-city searches
- Extracts flight details (price, duration, airline)
- Saves action history for evaluation

---

### 2. **Hotel Search Agent** (`browser_use_hotel_agent.py`) 🆕
Searches for hotel accommodations.

**Example usage:**
```bash
python src/agents/browser_use_hotel_agent.py \
  --task "Find a hotel in Seattle for 2 adults checking in tomorrow and checking out in 3 days with free WiFi and breakfast included. Show results sorted by price." \
  --task_id "hotel_search_seattle" \
  --base_dir "./data/example" \
  --visible
```

**Or use the convenience script:**
```bash
bash script/run_hotel_agent.sh
```

**Features:**
- Handles hotel booking site UI (date pickers, location autocomplete)
- Applies filters (price, star rating, amenities)
- Supports various booking sites (Booking.com, Hotels.com, Google Hotels, etc.)
- Extracts hotel details (name, price, rating, amenities)
- Saves action history for evaluation

---

## 🔧 Setup

### Prerequisites
1. **API Key**: Set your Browser-Use API key:
   ```bash
   export BROWSER_USE_API_KEY="your-key-here"
   ```

2. **Dependencies**: Ensure browser-use and playwright are installed:
   ```bash
   pip install browser-use playwright
   python -m playwright install chromium
   ```

### Command-line Arguments

Both agents support the same arguments:

| Argument | Description | Default |
|----------|-------------|---------|
| `--task` | Task description/instruction for the agent | (See agent file for default) |
| `--task_id` | Unique identifier for this task (folder name) | Auto-generated from task |
| `--base_dir` | Base directory for outputs | `./data/example` |
| `--visible` | Show browser window (helpful for debugging) | False (headless) |

---

## 📂 Output Format

Both agents save results in Online-Mind2Web format:

```
data/example/
└── {task_id}/
    ├── result.json          # Task metadata and action history
    └── trajectory/          # Screenshots (if captured)
        ├── 0_full_screenshot.png
        ├── 1_full_screenshot.png
        └── ...
```

### `result.json` structure:
```json
{
    "task_id": "hotel_search_seattle",
    "task": "Find a hotel in Seattle...",
    "final_result_response": "Found 3 hotels matching criteria...",
    "action_history": [
        "Navigated to https://www.booking.com",
        "Typed 'Seattle' into location field",
        "Selected check-in date",
        "Selected check-out date",
        "Applied filter: Free WiFi",
        "Applied filter: Breakfast included",
        "Clicked sort by price",
        "Extracted top 3 hotels"
    ],
    "thoughts": []
}
```

---

## 🧪 Testing with Evaluation

After running an agent, evaluate its performance:

```bash
# Run agent
python src/agents/browser_use_hotel_agent.py \
  --task "Find a hotel in Seattle..." \
  --task_id "my_hotel_test" \
  --visible

# Evaluate with WebJudge
python src/run.py \
  --mode "WebJudge_Online_Mind2Web_eval" \
  --model "gpt-4o-mini" \
  --trajectories_dir "./data/example" \
  --api_key "$OPENAI_API_KEY" \
  --output_path "./data/test_output" \
  --num_worker 1 \
  --score_threshold 3
```

---

## 🎯 Creating New Agents

To create a new agent for a different domain (e.g., restaurant reservations, car rentals):

1. **Copy an existing agent** as a template
2. **Modify the `augment_task_for_*()` function** with domain-specific guidance
3. **Update default task** in `argparse` setup
4. **Update fallback action history** (if needed)
5. **Test with `--visible` flag** to debug

### Key Functions to Customize:

```python
def augment_task_for_YOUR_DOMAIN(task: str) -> str:
    """Add domain-specific UI handling guidance."""
    # Add guidance for common UI patterns in your domain
    
def run_browser_use_agent(task: str, traj_dir: str, visible: bool = True):
    """Main agent execution loop."""
    # Usually doesn't need modification
    
def extract_images_and_actions_from_history(history: Any):
    """Parse browser-use history into actions."""
    # Usually doesn't need modification
```

---

## 🐛 Debugging

### Problem: "No actions were extracted"
**Solution:** Check that `extract_images_and_actions_from_history()` is parsing the browser-use history correctly. Use `--visible` flag and check debug output.

### Problem: "Agent completed but evaluation failed"
**Solution:** Check `result.json` to see if actions match the task requirements. The evaluator compares actions against key points in the task.

### Problem: "BROWSER_USE_API_KEY not set"
**Solution:** 
```bash
export BROWSER_USE_API_KEY="your-key"
```

---

## 📚 Additional Resources

- [Browser-Use Documentation](https://docs.browser-use.com/)
- [Online-Mind2Web Paper](https://arxiv.org/abs/2504.01382)
- [WebJudge Evaluation Method](https://github.com/OSU-NLP-Group/Online-Mind2Web)

---

## 🚀 Quick Start Examples

### Flight Agent
```bash
# Search for one-way flights
python src/agents/browser_use_flight_agent.py \
  --task "Find one-way flights from NYC to Miami next Friday under $200" \
  --visible

# Search for round-trip flights
python src/agents/browser_use_flight_agent.py \
  --task "Find round-trip flights from LAX to Tokyo in December for 2 passengers" \
  --visible
```

### Hotel Agent
```bash
# Budget hotel search
bash script/run_hotel_agent.sh "Find cheap hotels in Paris for next weekend under 100 euros per night" "paris_budget"

# Luxury hotel search
python src/agents/browser_use_hotel_agent.py \
  --task "Find 5-star hotels in Manhattan with spa and pool for New Year's Eve" \
  --visible
```

---

## 📊 Success Tips

1. ✅ **Be specific** in task descriptions (dates, locations, requirements)
2. ✅ **Use `--visible` flag** when testing to see what the agent is doing
3. ✅ **Check `result.json`** to verify actions were captured correctly
4. ✅ **Run evaluation** to get objective success metrics
5. ✅ **Iterate** based on evaluation feedback

