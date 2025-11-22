# TripMind AgentBeats Integration Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    AgentBeats Platform                          │
│                  (https://agentbeats.io)                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      │ (1) "Start Assessment" sends A2A task
                      │     via Cloudflare Tunnel
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              Your Local Machine                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  GREEN AGENT (Port 9002)                                   │  │
│  │  - Assessment Orchestrator                                 │  │
│  │  - Receives tasks from AgentBeats                          │  │
│  │  - Exposed via Cloudflare Tunnel                           │  │
│  │  - Sends tasks to White Agent                              │  │
│  │  - Evaluates results & reports metrics                     │  │
│  └─────────────────────┬─────────────────────────────────────┘  │
│                        │                                         │
│                        │ (2) Sends task via A2A                  │
│                        ▼                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  WHITE AGENT (Port 9001)                                   │  │
│  │  - Browser Automation                                      │  │
│  │  - Uses browser-use with Playwright                        │  │
│  │  - Executes web tasks (flight search, hotel search, etc.)  │  │
│  │  - Returns structured results                              │  │
│  └─────────────────────┬─────────────────────────────────────┘  │
│                        │                                         │
│                        │ (3) Browser automation                  │
│                        ▼                                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  BROWSER (Playwright/browser-use cloud)                    │  │
│  │  - Google Flights, Kayak, Booking.com, etc.               │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Set Environment Variables

```bash
# Required: Browser-Use API key for web automation
export BROWSER_USE_API_KEY="your-browser-use-api-key"

# Optional: Override default ports
export WHITE_AGENT_PORT=9001
export GREEN_AGENT_PORT=9002
```

### 2. Start Both Agents Locally

```bash
# Option A: Use the launcher script
./start_agents.sh

# Option B: Use run.sh (starts both agents)
./run.sh

# Option C: Start agents separately
# Terminal 1 - White Agent
python -m src.white_agent --port 9001

# Terminal 2 - Green Agent
python -m src.green_agent --port 9002 --white-agent-url http://localhost:9001
```

### 3. Verify Agents Are Running

```bash
# Check White Agent
curl http://localhost:9001/status

# Check Green Agent
curl http://localhost:9002/status

# View available tasks
curl http://localhost:9002/tasks
```

### 4. Set Up Cloudflare Tunnel

The Green Agent needs to be accessible from the internet so AgentBeats can connect to it.

#### Install cloudflared

```bash
# macOS
brew install cloudflared

# Linux
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Windows: Download from https://github.com/cloudflare/cloudflared/releases
```

#### Create a Quick Tunnel (No Cloudflare Account Needed)

```bash
# This creates a temporary public URL for your Green Agent
cloudflared tunnel --url http://localhost:9002
```

You'll see output like:
```
Your quick Tunnel has been created! Visit it at:
https://random-words-here.trycloudflare.com
```

Copy this URL - you'll use it in AgentBeats.

#### Create a Permanent Tunnel (Recommended for Production)

1. Login to Cloudflare:
```bash
cloudflared tunnel login
```

2. Create a tunnel:
```bash
cloudflared tunnel create tripmind-agent
```

3. Configure the tunnel (create `~/.cloudflared/config.yml`):
```yaml
tunnel: tripmind-agent
credentials-file: /path/to/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: tripmind.yourdomain.com
    service: http://localhost:9002
  - service: http_status:404
```

4. Route DNS:
```bash
cloudflared tunnel route dns tripmind-agent tripmind.yourdomain.com
```

5. Run the tunnel:
```bash
cloudflared tunnel run tripmind-agent
```

### 5. Register with AgentBeats

1. Go to [AgentBeats](https://agentbeats.io) and log in
2. Navigate to "Agent Management" → "Create New Agent"
3. Fill in:
   - **Name**: TripMind Travel Agent
   - **Deploy Type**: Remote
   - **Controller URL**: Your Cloudflare tunnel URL (e.g., `https://random-words.trycloudflare.com`)
   - **Is Green Agent**: ✓ Check this box
4. Click "Create Agent"
5. Use the "Check" button to verify connectivity

### 6. Run an Assessment

1. In AgentBeats, go to your agent's page
2. Click "Start Assessment"
3. The platform will:
   - Send an A2A task to your Green Agent
   - Green Agent will send tasks to White Agent
   - White Agent executes browser automation
   - Green Agent evaluates results and reports metrics
   - Results appear in AgentBeats dashboard

## Manual Assessment Testing

You can test the assessment flow locally before connecting to AgentBeats:

```bash
# Start an assessment manually
curl -X POST http://localhost:9002/start-assessment \
  -H "Content-Type: application/json" \
  -d '{
    "white_agent_url": "http://localhost:9001",
    "task_count": 1
  }'
```

## Endpoints Reference

### Green Agent (Port 9002)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Health check (AgentBeats "Check" button) |
| `/health` | GET | Simple health endpoint |
| `/.well-known/agent-card.json` | GET | A2A agent discovery |
| `/message/send` | POST | A2A task submission (AgentBeats "Start Assessment") |
| `/start-assessment` | POST | Manual assessment trigger |
| `/tasks` | GET | List available test tasks |

### White Agent (Port 9001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/status` | GET | Health check |
| `/health` | GET | Simple health endpoint |
| `/.well-known/agent-card.json` | GET | A2A agent discovery |
| `/message/send` | POST | A2A task submission |

## Troubleshooting

### White Agent not executing tasks

1. Check `BROWSER_USE_API_KEY` is set
2. Verify browser-use is installed: `pip install browser-use`
3. Check White Agent logs for errors

### Green Agent can't reach White Agent

1. Verify White Agent is running: `curl http://localhost:9001/status`
2. Check `WHITE_AGENT_URL` environment variable
3. Ensure no firewall blocking local connections

### Cloudflare tunnel not working

1. Check cloudflared is running
2. Verify the tunnel URL is accessible from another device
3. Check cloudflared logs: `cloudflared tunnel --url http://localhost:9002 --loglevel debug`

### AgentBeats "Check" fails

1. Verify tunnel is running and URL is correct
2. Check Green Agent is running on port 9002
3. Test locally: `curl https://your-tunnel-url.trycloudflare.com/status`
