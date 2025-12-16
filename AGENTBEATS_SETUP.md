# TripMind AgentBeats Integration Guide

## AgentBeats Has 3 Submission Types

| # | Submission Type | Script | "Is Green Agent"? | Purpose |
|---|----------------|--------|-------------------|---------|
| 1 | **Green Agent** | `./start_agentbeats.sh` | ✅ YES | Upload an agent that EVALUATES others |
| 2 | **White Agent** | `./start_white_agent_submission.sh` | ❌ NO | Upload an agent to BE EVALUATED |
| 3 | **Assessment** | N/A (AgentBeats UI) | N/A | Run evaluation: Green → White |

## How It Works

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AGENTBEATS PLATFORM                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  STEP 1: Submit Green Agent       STEP 2: Submit White Agent               │
│  ./start_agentbeats.sh            ./start_white_agent_submission.sh        │
│           ↓                                  ↓                              │
│  ┌─────────────────┐              ┌─────────────────┐                      │
│  │ TripMind Green  │              │ TripMind White  │                      │
│  │ (Evaluator)     │              │ (Gets evaluated)│                      │
│  │ ✅ Is Green     │              │ ❌ Not Green    │                      │
│  └────────┬────────┘              └────────┬────────┘                      │
│           │                                │                                │
│           └────────────┬───────────────────┘                               │
│                        ▼                                                    │
│           STEP 3: Create Assessment                                         │
│              Select: Green Agent → TripMind Green                          │
│              Select: White Agent → TripMind White                          │
│              Click: "Run Assessment"                                        │
│                        ↓                                                    │
│           AgentBeats sends tasks to Green Agent                            │
│           Green Agent evaluates White Agent                                 │
│           Results displayed on AgentBeats                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Step 1: Submit Green Agent (Assessor)

The Green Agent **evaluates** other agents. It receives assessment tasks from AgentBeats and tests White Agents.

### Run the script:

```bash
# Set your API key
export BROWSER_USE_API_KEY="your-browser-use-api-key"

# Start green agent with controller + tunnel
./start_agentbeats.sh
```

### You'll see:

```
✅ READY FOR AGENTBEATS SUBMISSION!

📡 SUBMIT THIS URL TO AGENTBEATS:
   https://xxx.trycloudflare.com

📋 When registering on AgentBeats:
   Name: TripMind Green Agent
   ✅ CHECK "Is Green Agent"
```

### Register on AgentBeats:

1. Go to [AgentBeats](https://v2.agentbeats.org/) → **Agent Management** → **Create New Agent**
2. Fill in:
   - **Name**: `TripMind Green Agent`
   - **Controller URL**: Paste the cloudflare URL
   - **✅ CHECK "Is Green Agent"**
3. Click **Create Agent**
4. Use **Check** button to verify connectivity

---

## Step 2: Submit White Agent (Assessee)

The White Agent **gets evaluated** by Green Agents. It receives tasks and performs browser automation.

### Run the script (in a NEW terminal):

```bash
# Set your API key
export BROWSER_USE_API_KEY="your-browser-use-api-key"

# Start white agent with tunnel (uses different port)
./start_white_agent_submission.sh
```

### You'll see:

```
✅ WHITE AGENT READY FOR SUBMISSION!

📡 SUBMIT THIS URL TO AGENTBEATS:
   https://yyy.trycloudflare.com

⚠️ IMPORTANT: When registering on AgentBeats:
   - DO NOT check 'Is Green Agent'
```

### Register on AgentBeats:

1. Go to [AgentBeats](https://v2.agentbeats.org/) → **Agent Management** → **Create New Agent**
2. Fill in:
   - **Name**: `TripMind White Agent`
   - **Controller URL**: Paste the cloudflare URL
   - **❌ DO NOT check "Is Green Agent"**
3. Click **Create Agent**
4. Use **Check** button to verify connectivity

---

## Step 3: Run Assessment (on AgentBeats UI)

Once you have BOTH agents submitted:

1. Go to [AgentBeats](https://v2.agentbeats.org/) → **Assessments** → **Create New Assessment**
2. Select **Green Agent**: `TripMind Green Agent`
3. Select **White Agent**: `TripMind White Agent`
4. Click **Run Assessment**

### What happens:

1. AgentBeats sends assessment tasks to your Green Agent
2. Your Green Agent sends tasks to the selected White Agent
3. Your Green Agent evaluates the White Agent's responses
4. Results are reported back to AgentBeats
5. You can view metrics and results on the platform

---

## Architecture: TripMind Code Mapping

| File | Role | Submission Type |
|------|------|-----------------|
| `src/green_agent.py` | Assessment orchestrator | Green Agent |
| `src/white_agent.py` | Browser automation | White Agent |
| `src/simple_controller.py` | Controller proxy | Used by Green Agent |
| `start_agentbeats.sh` | Launch script | Green Agent submission |
| `start_white_agent_submission.sh` | Launch script | White Agent submission |

### Code Flow

```
Green Agent (src/green_agent.py):
  - Receives: Assessment request from AgentBeats
  - Actions: Sends tasks to White Agent(s)
  - Returns: Evaluation metrics (pass/fail, timing, etc.)

White Agent (src/white_agent.py):
  - Receives: Task text (e.g., "Book a flight from NYC to LA")
  - Actions: Uses browser-use to complete the task
  - Returns: Task result (action history, screenshots, etc.)
```

---

## Running Both Agents Simultaneously

You need **2 terminals** to keep both agents running:

**Terminal 1 - Green Agent:**
```bash
export BROWSER_USE_API_KEY="your-key"
./start_agentbeats.sh
# Keep running! Don't close.
```

**Terminal 2 - White Agent:**
```bash
export BROWSER_USE_API_KEY="your-key"
./start_white_agent_submission.sh
# Keep running! Don't close.
```

Now both agents are live and you can run assessments on AgentBeats.

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'fastapi'"

```bash
pip3 install --break-system-packages fastapi
```

### "cloudflared not found"

```bash
brew install cloudflared
```

### Agent not showing up on AgentBeats

1. Check the terminal for errors
2. Verify the cloudflare URL is accessible: `curl https://xxx.trycloudflare.com/status`
3. Make sure you clicked "Check" on AgentBeats after creating the agent

### Assessment not running

1. Make sure BOTH green and white agents are running (2 terminals)
2. Make sure both show "Connected" status on AgentBeats
3. Check terminal logs for any errors during assessment

---

## Quick Reference

| Action | Command |
|--------|---------|
| Submit Green Agent | `./start_agentbeats.sh` |
| Submit White Agent | `./start_white_agent_submission.sh` |
| Run Assessment | AgentBeats UI → Assessments → Create |
| Check API key | `echo $BROWSER_USE_API_KEY` |
| Install deps | `pip3 install --break-system-packages -r requirements.txt` |
