<h1 align="center"> Online-Mind2Web Benchmark </h1>

<p align="center">
  <a href="https://xuetianci.github.io/" style="text-decoration: none;">Tianci Xue<sup>,1</sup></a>,
  <a href="https://x.com/weijian_qi" style="text-decoration: none;">Weijian Qi<sup>*,1</sup></a>,
  <a href="https://tnshi.com/" style="text-decoration: none;">Tianneng Shi<sup>*2</sup></a>,
  <a href="https://chanh.ee/" style="text-decoration: none;">Chan Hee Song<sup>1</sup></a>,
  <a href="https://boyugou.github.io/" style="text-decoration: none;">Boyu Gou<sup>1</sup></a>,
  <a href="https://dawnsong.io/" style="text-decoration: none;">Dawn Song<sup>,2</sup></a>,
  <a href="https://u.osu.edu/ihudas/people/" style="text-decoration: none;">Huan Sun<sup>†,1</sup></a>
  <a href="https://ysu1989.github.io/" style="text-decoration: none;">Yu Su<sup>†,1</sup></a>
</p>

<p align="center">
  <sup>1</sup>The Ohio State University, <sup>2</sup>University of California, Berkeley </br>
  <sub><sup>*</sup>Equal contribution, <sup>†</sup>Equal advising</sub>
</p>

<p align="center">
<a href="https://arxiv.org/abs/2504.01382">📃 Paper</a>
•
<a href="https://tiancixue.notion.site/An-Illusion-of-Progress-Assessing-the-Current-State-of-Web-Agents-1ac6cd2b9aac80719cd6f68374aaf4b4?pvs=4">📃 Blog</a>
•
<a href="https://huggingface.co/spaces/osunlp/Online_Mind2Web_Leaderboard" >🏆 Leaderboard</a>
•
<a href="https://huggingface.co/datasets/osunlp/Online-Mind2Web" >🤗 Data</a>
</p>

---

## AgentBeats Deployment

This repository includes an A2A-compatible agent deployed for AgentBeats evaluation.

**Live Agent:** https://tripmind-agent-production.up.railway.app

**What was done:**
1. Created an A2A (Agent-to-Agent) protocol compatible agent using `a2a-sdk`
2. Wrapped the browser-use automation library for travel-related tasks
3. Deployed to Railway with public HTTPS endpoint
4. Added `/status` and `/health` endpoints for controller checks

**Agent capabilities:** Flight search, hotel search, itinerary creation via browser automation.

**Files added:**
- `src/a2a_agent.py` - Main A2A agent implementation
- `Dockerfile` - Container configuration for deployment
- `test_local.py` - Local testing script

---

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
python src/agents/browser_use_example.py \
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

# Online-Mind2Web benchmark

## News
* [07/08/2025] 🎉 Online-Mind2Web has been accepted to COLM 2025!
* [05/11/2025] Check out our updates in the [paper](https://arxiv.org/abs/2504.01382).
  * The performance of Claude Computer Use 3.7.
  * WebJudge(o4-mini) achieves high agreement (86%) with a low success rate gap (3.8%) compared with humans.
  * Release [WebJudge-7B](https://huggingface.co/osunlp/WebJudge-7B), a robust and reliable reward model for Reinforcement learning.

## Tasks
Online-Mind2Web includes 300 diverse tasks from 136 popular websites across various domains. It covers a diverse set of real-world user tasks, such as clothing, food, housing, and transportation, to evaluate web agents' performance in a real-world online environment.

## Update Tasks

We will regularly update Online-Mind2Web by replacing outdated or invalid tasks (e.g., due to website changes) to maintain its value as a rigorous benchmark for web agents. If you find any tasks are outdated, please reach out to us, and we will update them.

To ensure fair comparisons, we will aim to keep the updated tasks on the same websites as before and with a similar reference length. Additionally, once agent performance saturates on Online-Mind2Web, we will also revise simple tasks to preserve its long-term value.

# Automatic Evaluator via LLM-as-a-Judge (WebJudge)
To enhance the reliability and scalability of the evaluation process in online environments, We propose a more reliable automatic evaluation method called **WebJudge**, which consists of three parts. (1) Key Point Identification: The model is prompted to identify several key points necessary for completing the task, based on the given instruction and task description. (2) Key Screenshot Identification: Important screenshots are selected from the agent’s trajectory to retain relevant visual evidence while discarding uninformative frames. (3) Outcome Judgment: Output the judgement result based on the task description, key points, key screenshots, and the action history. Our method preserves critical intermediate screenshots while mitigating the token overload issue.

<p align="center">
  <img src="./images/WebJudge.jpg" width="100%" alt="pipeline">
</p>

# Results

## Comparison against Existing Evaluation Methods on Online-Mind2Web
<table>
<tr>
  <th>Model</th>
  <th>Auto-Eval</th>
  <td>SeeAct</td>
  <td>Agent-E</td>
  <td>Browser Use</td>
  <td>Claude 3.5 </td>
  <td>Claude 3.7</td>
  <td>Operator</td>
  <th>Avg AR</th>
</tr>
<tr>
  <th rowspan="4">GPT-4o</th>
  <td>Autonomous Eval</td>
  <td>84.7</td>
  <td>85.0</td>
  <td>76.0</td>
  <td>83.7</td>
  <td>75.5</td>
  <td>71.7</td>
  <td>79.4</td>
</tr>
<tr>
  <td>AgentTrek Eval</td>
  <td>73.0</td>
  <td>64.3</td>
  <td>63.3</td>
  <td>--</td>
  <td>--</td>
  <td>--</td>
  <td>66.9</td>
</tr>
<tr>
  <td>WebVoyager</td>
  <td>--</td>
  <td>75.3</td>
  <td>71.3</td>
  <td>74.0</td>
  <td>72.0</td>
  <td>76.7</td>
  <td>73.9</td>
</tr>
<tr>
  <td>WebJudge</td>
  <td>86.7</td>
  <td>86.0</td>
  <td>81.4</td>
  <td>86.3</td>
  <td>79.1</td>
  <td>81.8</td>
  <td><b>83.6</b></td>
</tr>

<tr>
  <th rowspan="3">o4-mini</th>
  <td>Autonomous Eval</td>
  <td>79.7</td>
  <td>85.7</td>
  <td>86.0</td>
  <td>84.3</td>
  <td>68.0</td>
  <td>73.3</td>
  <td>79.5</td>
</tr>
<tr>
  <td>WebVoyager</td>
  <td>--</td>
  <td>80.3</td>
  <td>79.0</td>
  <td>81.7</td>
  <td>74.3</td>
  <td>78.3</td>
  <td>78.7</td>
</tr>
<tr>
  <td>WebJudge</td>
  <td>85.3</td>
  <td>86.3</td>
  <td>89.3</td>
  <td>87.0</td>
  <td>82.3</td>
  <td>83.7</td>
  <td><b>85.7</b></td>
</tr>

<tr>
  <th></th>
  <td>WebJudge-7B</td>
  <td>86.0</td>
  <td>87.3</td>
  <td>88.3</td>
  <td>89.7</td>
  <td>84.3</td>
  <td>86.3</td>
  <td><b>87.0</b></td>
</tr>
</table>
WebJudge powered by GPT-4o and o4-mini consistently achieves the highest agreement, with averages of 83.6% and 85.7%, respectively. Meanwhile, WebJudge-7B even outperforms o4-mini, reaching a high agreement with human judgment of 87%.


## Excellent generalization capabilities on [AgentRewardBench](https://agent-reward-bench.github.io/) (5 OOD benchmarks)
| **Methods** | **AB** | **VWA** | **WA** | **Work** | **Wk++** | **Overall** |
|--------------|--------|--------|--------|----------|----------|--------------|
| *Rule-based** | 25.0 | **85.2** | 79.0 | 100.0 | 83.3 | 83.8 |
| Autonomous Eval* | 83.3 | 61.2 | 67.6 | 96.4 | 59.3 | 67.6 |
| GPT-4o (A11y Tree)* | 77.8 | 63.0 | 70.2 | 94.6 | 63.0 | 69.8 |
| WebJudge (GPT-4o) | 66.7 | 69.8 | 72.6 | 92.3 | 75.0 | 73.7 |
| WebJudge-7B | 80.0 | 66.7 | 77.5 | 100.0 | 70.0 | 75.7 |
| WebJudge (o4-mini) | **100.0** | 74.5 | **81.2** | **100.0** | **90.0** | **82.0** |

WebJudge significantly outperforms existing methods, achieving impressive overall precision of 73.7% 75.7% and 82.0% on WebArena (WA), VisualWebArena (VWA), AssistantBench (AB), WorkArena (Work) and WorkArena++ (Wk++) across 1302 trajectories.

The high precision suggests that WebJudge holds potential as a robust and scalable reward model for downstream applications such as Rejection Sampling Fine-Tuning, Reflection, and Reinforcement Learning.

# Model Release
We have released the fine-tuned [WebJudge-7B](https://huggingface.co/osunlp/WebJudge-7B) weights, which are now available on Hugging Face.

# Setup Environment

Create a conda environment and install dependencies:
```
conda create -n Online_Mind2Web python=3.13 -y
conda activate Online_Mind2Web
pip install -r requirements.txt
# Install browsers for Playwright one time
python -m playwright install chromium
```

# Evaluation
You can run the provided example evaluation script directly to perform the evaluation. Adjust the "mode" parameter to choose among various auto-eval methods.
```bash
# Example (make a safe copy and edit locally)
cp script/eval.sh script/eval.local.sh
$EDITOR script/eval.local.sh
bash ./script/eval.local.sh
```

## Generate a new trajectory using Browser-Use (example task)

This repo now includes a minimal Browser-Use agent that outputs an Online-Mind2Web-compatible folder (`result.json` + `trajectory/*.png`). It can be used to add new use cases and then run WebJudge evaluation.

1. Install dependencies (you may need to install Chromium for Playwright):
```bash
pip install -r requirements.txt
# playwright install (only once)
python -m playwright install chromium
```

2. Set your Browser-Use API key in environment:
```bash
export BROWSER_USE_API_KEY=your-key
```
Refer to the official project for setup details: [browser-use/browser-use](https://github.com/browser-use/browser-use).

3. Run the example agent to generate a new task folder:
```bash
# Default example
python src/agents/browser_use_example.py --visible

# Or customize task and id
python src/agents/browser_use_example.py \
  --task "Find a round-trip flight from NYC to SFO next month and show results." \
  --task_id "my_flights_case" \
  --base_dir "./data/example" \
  --visible
```

This creates `data/example/<TASK_ID>/result.json` and `data/example/<TASK_ID>/trajectory/0_full_screenshot.png`, etc.

4. Evaluate the generated trajectory with WebJudge (recommended o4-mini):
```bash
python src/run.py \
  --mode "WebJudge_Online_Mind2Web_eval" \
  --model "o4-mini" \
  --trajectories_dir "./data/example" \
  --api_key "$OPENAI_API_KEY" \
  --output_path "./data/test_output" \
  --num_worker 1 \
  --score_threshold 3
```

Important: Ensure your task starts from the correct initial website per the benchmark rules if you aim for apples-to-apples comparisons.

## Important Notes for Reliable Evaluation on Online-Mind2Web:
> [!IMPORTANT]
> - **Start from the specified websites, not Google Search**:To enable fair comparisons, please ensure that each task starts from the specified website in our benchmark. Starting from Google Search or alternative websites can lead agents to use different websites to solve the task, resulting in varying difficulty levels and potentially skewed evaluation results.
> - **Include only factual actions, not agent outputs**: The action history should contain only the factual actions taken by the agent to complete the task (e.g., clicking elements and Typing text). Do not include the final response or any other agent's outputs, as they may contain hallucinated content and result in a high rate of false positives.
> - **Use o4-mini for WebJudge**: WebJudge powered by o4-mini demonstrates a higher alignment with human judgment, achieving an average agreement rate of 85.7% and maintaining a narrow success rate gap of just 3.8%. Therefore, please use o4-mini as the backbone for automatic evaluation.

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

# Evaluation Results

In certain scenarios, testing on the full Online-Mind2Web dataset may not be feasible due to cost, privacy, or legal constraints. To facilitate fair and apple-to-apple comparisons, we release both our human evaluation labels and auto-eval details.

- **Human Evaluation**: Task-level human evaluation labels are provided in the [file](https://github.com/OSU-NLP-Group/Online-Mind2Web/tree/main/data/evaluation_results/online_mind2web_evaluation_results/human_label.json).
- **Auto-Evaluation**: The results of WebJudge are available in the [folder](https://github.com/OSU-NLP-Group/Online-Mind2Web/tree/main/data/evaluation_results/online_mind2web_evaluation_results).

## Licensing Information

<a rel="license" href="http://creativecommons.org/licenses/by/4.0/"><img alt="Creative Commons License" style="border-width:0" src="https://i.creativecommons.org/l/by/4.0/88x31.png" /></a><br />The Online-Mind2Web dataset is licensed under a <a rel="license" href="http://creativecommons.org/licenses/by/4.0/">Creative Commons Attribution 4.0 International License</a>.

Code under this repo is licensed under a MIT License.

## 📚 Citation

Note: Online-Mind2Web is derived from the original Mind2Web dataset. We kindly ask that you cite both the original and this work when using or referencing the data.
```
@article{xue2025illusionprogressassessingcurrent,
      title={An Illusion of Progress? Assessing the Current State of Web Agents}, 
      author={Tianci Xue and Weijian Qi and Tianneng Shi and Chan Hee Song and Boyu Gou and Dawn Song and Huan Sun and Yu Su},
      year={2025},
      eprint={2504.01382},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2504.01382}, 
}

@inproceedings{deng2023mind2web,
 author = {Deng, Xiang and Gu, Yu and Zheng, Boyuan and Chen, Shijie and Stevens, Sam and Wang, Boshi and Sun, Huan and Su, Yu},
 booktitle = {Advances in Neural Information Processing Systems},
 editor = {A. Oh and T. Naumann and A. Globerson and K. Saenko and M. Hardt and S. Levine},
 pages = {28091--28114},
 publisher = {Curran Associates, Inc.},
 title = {Mind2Web: Towards a Generalist Agent for the Web},
 url = {https://proceedings.neurips.cc/paper_files/paper/2023/file/5950bf290a1570ea401bf98882128160-Paper-Datasets_and_Benchmarks.pdf},
 volume = {36},
 year = {2023}
}
```
