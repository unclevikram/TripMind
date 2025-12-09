<h1 align="center"> Online-Mind2Web — Developer Guide </h1>

<p align="center">
  <a href="https://arxiv.org/abs/2504.01382">📃 Paper</a>
  •
  <a href="https://tiancixue.notion.site/An-Illusion-of-Progress-Assessing-the-Current-State-of-Web-Agents-1ac6cd2b9aac80719cd6f68374aaf4b4?pvs=4">📃 Blog</a>
  •
  <a href="https://huggingface.co/spaces/osunlp/Online_Mind2Web_Leaderboard">🏆 Leaderboard</a>
  •
  <a href="https://huggingface.co/datasets/osunlp/Online-Mind2Web">🤗 Data</a>
</p>

## TL;DR
- **What this repo is**: Code and data to evaluate web agents on the Online‑Mind2Web benchmark, plus an LLM‑as‑a‑Judge evaluator (WebJudge).
- **What you can do quickly**:
  - Install deps (Python 3.13+), install Playwright browser, set API keys.
  - Generate an example trajectory folder (`result.json` + `trajectory/*.png`) with a minimal Browser‑Use agent.
  - Run WebJudge and other auto‑eval baselines over your trajectories.
- **Outputs**: Line‑delimited JSON under `data/*_result` with per‑task decisions and records.

---

## Quickstart

### 1) Requirements
- Python 3.13+
- macOS/Linux/WSL2 recommended
- OpenAI API access (for `gpt-4o`, `gpt-4o-mini`, `o4-mini`, etc.)
- Optional: Browser‑Use API key if you want to generate new trajectories with the included example agent

### 2) Setup environment

Option A — pip + requirements.txt:
```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install -r requirements.txt
# Install a browser engine for Playwright once
python -m playwright install chromium
```

Option B — uv (fast/lockfile‑friendly):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# create & activate a venv with Python 3.13
uv venv --python 3.13
source .venv/bin/activate
# install from requirements (project also provides a uv.lock)
uv pip install -r requirements.txt
python -m playwright install chromium
```

### 3) Set credentials
```bash
# Required by evaluators (OpenAI Chat Completions)
export OPENAI_API_KEY="sk-..."
# Optional: only needed to run the Browser‑Use example agent
export BROWSER_USE_API_KEY="your-browser-use-key"
# Keep Playwright browsers local to the repo (optional)
export PLAYWRIGHT_BROWSERS_PATH="$(pwd)/.playwright-browsers"
```

### 4) End‑to‑end walkthrough (generate → evaluate)

Step A — Generate an example trajectory folder with the included agent:
```bash
# Visible browser; customize TASK_ID/TASK_TEXT as needed
python src/agents/browser_use_flight_agent.py \
  --task "Find a round-trip flight from NYC to SFO next month and show results." \
  --task_id "browser_use_search_flights" \
  --base_dir "./data/example" \
  --visible
```
This creates:
- `data/example/browser_use_search_flights/result.json`
- `data/example/browser_use_search_flights/trajectory/` (screenshots if captured)

Step B — Run WebJudge (recommended) and other auto‑eval modes:
```bash
# WebJudge tuned for Online‑Mind2Web (uses screenshots + action history)
python src/run.py \
  --mode "WebJudge_Online_Mind2Web_eval" \
  --model "gpt-4o-mini" \
  --trajectories_dir "./data/example" \
  --api_key "$OPENAI_API_KEY" \
  --output_path "./data/test_output" \
  --num_worker 1 \
  --score_threshold 3

# Alternative baselines you can also try:
python src/run.py --mode "WebJudge_general_eval" --model "gpt-4o-mini" \
  --trajectories_dir "./data/example" --api_key "$OPENAI_API_KEY" \
  --output_path "./data/test_output" --num_worker 1 --score_threshold 3

python src/run.py --mode "Autonomous_eval" --model "gpt-4o-mini" \
  --trajectories_dir "./data/example" --api_key "$OPENAI_API_KEY" \
  --output_path "./data/test_output" --num_worker 1

python src/run.py --mode "WebVoyager_eval" --model "gpt-4o-mini" \
  --trajectories_dir "./data/example" --api_key "$OPENAI_API_KEY" \
  --output_path "./data/test_output" --num_worker 1

python src/run.py --mode "AgentTrek_eval" --model "gpt-4o-mini" \
  --trajectories_dir "./data/example" --api_key "$OPENAI_API_KEY" \
  --output_path "./data/test_output" --num_worker 1
```
Outputs are written as line‑delimited JSON under `--output_path`, e.g.:
- `data/test_output/WebJudge_Online_Mind2Web_eval_gpt-4o-mini_score_threshold_3_auto_eval_results.json`

---

# Online-Mind2Web benchmark (context)
See the main `README.md` for background, results, and citations. This developer guide focuses on setup and usage.

# Setup Environment (conda option)
```bash
conda create -n Online_Mind2Web python=3.13 -y
conda activate Online_Mind2Web
pip install -r requirements.txt
python -m playwright install chromium
```

# Directory layout and I/O
- **Inputs (trajectories)**: Each task must live under a folder like `data/<split>/<task_id>/`, with:
  - `result.json` containing:
    - `task` (string), `action_history` (list[str]), `thoughts` (optional list[str]),
    - `final_result_response` (optional string), `input_image_paths` (optional list[str])
  - `trajectory/` folder with sequential screenshots named like `0_*.png`, `1_*.png`, …
- **Outputs**: For each run, a line‑delimited JSON file is appended under `--output_path`:
  - `<MODE>_<MODEL>_score_threshold_<N>_auto_eval_results.json`
  - Each line repeats the input with fields:
    - `evaluation_details.response`, `evaluation_details.predicted_label`
    - `predicted_label` (1/0), `image_judge_record` (if applicable), `key_points` (if applicable)

# Run all modes (loop example)
```bash
for MODE in WebJudge_Online_Mind2Web_eval WebJudge_general_eval Autonomous_eval WebVoyager_eval AgentTrek_eval; do
  python src/run.py \
    --mode "$MODE" \
    --model "gpt-4o-mini" \
    --trajectories_dir "./data/example" \
    --api_key "$OPENAI_API_KEY" \
    --output_path "./data/test_output" \
    --num_worker 1 \
    --score_threshold 3
done
```

# Performance, cost, and parallelism
- Use `--num_worker` to parallelize across tasks. Each worker initializes its own OpenAI client.
- Token usage depends on the number and size of screenshots passing the score threshold in WebJudge.
- Start with `--num_worker 1` and a small subset to validate your setup and estimate costs.

# Troubleshooting
- Playwright errors: re‑run `python -m playwright install chromium`. Ensure `PLAYWRIGHT_BROWSERS_PATH` is writable.
- OpenAI auth errors: verify `OPENAI_API_KEY` is exported in the same shell running Python.
- No screenshots: the minimal agent focuses on producing `result.json`; screenshot capture is optional and may depend on your environment.
- Path issues: prefer relative paths rooted at the repo (as shown in commands).
- Script defaults contain local absolute paths in some examples; use the direct `python` invocations shown above for portability.

# Example: Generate and evaluate a new case quickly
```bash
export OPENAI_API_KEY="sk-..."         # required
export BROWSER_USE_API_KEY="..."       # optional for the agent

python src/agents/browser_use_flight_agent.py \
  --task "Find a round-trip flight from NYC to SFO next month and show results." \
  --task_id "browser_use_search_flights" \
  --base_dir "./data/example" \
  --visible

python src/run.py \
  --mode "WebJudge_Online_Mind2Web_eval" \
  --model "o4-mini" \
  --trajectories_dir "./data/example" \
  --api_key "$OPENAI_API_KEY" \
  --output_path "./data/test_output" \
  --num_worker 1 \
  --score_threshold 3
```

---

For background, results, and citations, see `README.md`. This file is intended to help developers set up and run the project end‑to‑end quickly. 


