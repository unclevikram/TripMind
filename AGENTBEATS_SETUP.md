# TripMind AgentBeats Integration Guide

## 🚀 Quick Start - Submit to AgentBeats

**The fastest way to get your agent running on AgentBeats:**

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Browser-Use API key (required for browser automation)
export BROWSER_USE_API_KEY="your-browser-use-api-key"

# 3. Start the AgentBeats controller
./start_controller.sh
# OR
agentbeats run_ctrl

# 4. Look for the public URL in the output (e.g., https://xxx.trycloudflare.com)

# 5. Submit that URL to https://agentbeats.io
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    AgentBeats Platform                          │
│                  (https://agentbeats.io)                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ (1) Assessment request via HTTPS
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│           AgentBeats Controller (earthshaker)                   │
│  - Creates public tunnel (Cloudflare)                           │
│  - Proxies requests to your agent                               │
│  - Manages agent lifecycle (start/stop/restart)                 │
│  - Provides the URL you submit to AgentBeats                    │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ (2) Calls run.sh → starts your agent
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              Your Local Machine                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  GREEN AGENT (Assessment Orchestrator)                     │  │
│  │  - Listens on $HOST:$AGENT_PORT (set by controller)       │  │
│  │  - Receives tasks from AgentBeats                          │  │
│  │  - Sends tasks to White Agent                              │  │
│  │  - Evaluates results & reports metrics                     │  │
│  └─────────────────────┬─────────────────────────────────────┘  │
│                        │                                         │
│                        │ (3) Sends task via A2A                  │
│                        ▼                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  WHITE AGENT (Port 9001 - local only)                      │  │
│  │  - Browser Automation using browser-use                    │  │
│  │  - Executes web tasks (flight search, hotel search, etc.)  │  │
│  │  - Returns structured results                              │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## How the AgentBeats Controller Works

1. **You run**: `agentbeats run_ctrl` (or `./start_controller.sh`)
2. **The controller**:
   - Calls `run.sh` to start your agent
   - Sets `$HOST` and `$AGENT_PORT` environment variables
   - Creates a Cloudflare tunnel for public access
   - Proxies requests to your local agent
   - Provides a management UI at `http://localhost:8888`
3. **You submit**: The controller's public URL to AgentBeats
4. **AgentBeats**:
   - Fetches `/.well-known/agent-card.json` from your URL
   - Discovers your agent's capabilities
   - Can start assessments via the A2A protocol

## Detailed Setup

### 1. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# The earthshaker package provides the agentbeats command
# It should be installed from requirements.txt
```

### 2. Set Environment Variables

```bash
# Required: Browser-Use API key for web automation
export BROWSER_USE_API_KEY="your-browser-use-api-key"

# Optional: Override default ports (usually not needed)
export WHITE_AGENT_PORT=9001
```

### 3. Start with AgentBeats Controller (RECOMMENDED)

```bash
# Option A: Use the helper script
./start_controller.sh

# Option B: Run controller directly
agentbeats run_ctrl
```

The controller will:
- Start your Green Agent (via `run.sh`)
- Start your White Agent (for browser automation)
- Create a public tunnel URL
- Display the URL to submit to AgentBeats

### 4. Submit to AgentBeats

1. Go to [AgentBeats](https://agentbeats.io) and log in
2. Navigate to "Agent Management" → "Create New Agent"
3. Fill in:
   - **Name**: TripMind Green Agent
   - **Deploy Type**: Remote
   - **Controller URL**: The public URL from step 3 (e.g., `https://xxx.trycloudflare.com`)
   - **Is Green Agent**: ✓ Check this box
4. Click "Create Agent"
5. Use the "Check" button to verify connectivity

### 5. Verify Your Setup

```bash
# Test locally (before using controller)
curl http://localhost:9002/.well-known/agent-card.json

# Test via controller URL
curl https://your-controller-url/.well-known/agent-card.json

# Check status
curl https://your-controller-url/status
```

## Alternative: Local Development Mode

For local testing without the controller:

```bash
# Start agents in local mode
./run.sh --local

# Or start manually
# Terminal 1 - White Agent
python -m src.white_agent --port 9001

# Terminal 2 - Green Agent
python -m src.green_agent --port 9002
```

## Alternative: Manual Cloudflare Tunnel

If you prefer to manage the tunnel yourself:

```bash
# Terminal 1 - Start agents locally
./run.sh --local

# Terminal 2 - Create tunnel
cloudflared tunnel --url http://localhost:9002

# Copy the tunnel URL and set it
export BASE_URL="https://xxx.trycloudflare.com"

# Restart green agent with BASE_URL
pkill -f "main.py green"
BASE_URL="$BASE_URL" python3 main.py green --host 0.0.0.0 --port 9002
```

## How Agent Discovery Works

When you provide your controller URL to AgentBeats:

1. AgentBeats makes a GET request to `https://your-url/.well-known/agent-card.json`
2. Your agent returns a JSON agent card with:
   - Agent name and description
   - Available skills (travel-assessment, webjudge-eval)
   - Capabilities (streaming, notifications)
   - URL for A2A communication
3. AgentBeats can then send assessment tasks via POST to `/message/send`

**Note**: The `.well-known/agent-card.json` endpoint is automatically exposed by the A2A SDK. No manual configuration needed.

## Endpoints Reference

### Green Agent

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | A2A agent discovery (required by AgentBeats) |
| `/status` | GET | Health check (AgentBeats "Check" button) |
| `/health` | GET | Simple health endpoint |
| `/message/send` | POST | A2A task submission (AgentBeats "Start Assessment") |
| `/start-assessment` | POST | Manual assessment trigger |
| `/tasks` | GET | List available test tasks |

### White Agent (Local Only)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/.well-known/agent-card.json` | GET | A2A agent discovery |
| `/status` | GET | Health check |
| `/message/send` | POST | A2A task submission |
| `/execute` | POST | Direct task execution |

## Troubleshooting

### Submission Fails - "Agent card not found"

1. **Check the controller is running**: You should see output from `agentbeats run_ctrl`
2. **Test the agent card endpoint**:
   ```bash
   curl https://your-controller-url/.well-known/agent-card.json
   ```
   Should return JSON with agent name, description, skills, etc.
3. **Check controller logs** for any errors

### Submission Fails - "Connection refused"

1. **Verify tunnel is active**: The controller should show a public URL
2. **Check firewall**: Ensure no firewall blocking the controller
3. **Try restarting**: `Ctrl+C` and run `agentbeats run_ctrl` again

### Agent Card Shows Wrong URL

The agent card URL should match your public tunnel URL. If it shows `localhost`:
1. The controller should set proper forwarded headers
2. Check the green agent logs for URL detection output

### White Agent Not Executing Tasks

1. **Check API key**: `echo $BROWSER_USE_API_KEY`
2. **Verify browser-use**: `pip show browser-use`
3. **Check White Agent logs** for errors

### Green Agent Can't Reach White Agent

1. **Verify White Agent running**: `curl http://localhost:9001/status`
2. **Check URL**: The green agent should use `http://localhost:9001`
3. **Check logs** for connection errors

## File Structure

```
TripMind/
├── run.sh                    # Called by controller to start agents
├── start_controller.sh       # Helper to start AgentBeats controller
├── main.py                   # Agent launcher
├── Procfile                  # For cloud deployment
├── requirements.txt          # Python dependencies
├── src/
│   ├── green_agent.py       # Assessment orchestrator
│   └── white_agent.py       # Browser automation agent
└── agent_cards/
    └── green_agent_card.toml # Reference documentation
```

## References

- [AgentBeats Documentation](https://docs.agentbeats.org/Blogs/blog-3/)
- [A2A Protocol](https://a2a-protocol.org)
- [Earthshaker Package](https://pypi.org/project/earthshaker/)
