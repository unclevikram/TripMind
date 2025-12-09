# Adding Multiple Assessees in AgentBeats

## Overview

AgentBeats supports multiple assessees (agents being evaluated) in a single assessment. The TripMind implementation uses a **one Green Agent (assessor) + multiple White Agents (assessees)** architecture:

- **Green Agent (Assessor)**: Single orchestrator that receives assessment requests from AgentBeats and evaluates multiple white agents
- **White Agents (Assessees)**: Multiple browser automation agents that execute tasks in parallel

This architecture allows you to:
- Register only the Green Agent with AgentBeats
- Run multiple White Agents locally (or remotely)
- Compare performance across different assessees in a single assessment

## Understanding Agent Cards

### What are Agent Cards?

Agent cards are configuration files that define an agent's properties, capabilities, and endpoints. In AgentBeats, there are two approaches:

1. **TOML Agent Cards** (Traditional AgentBeats SDK approach)
   - Static `.toml` files that define agent metadata
   - Used with `agentbeats run` command
   - Format per [AgentBeats documentation](https://agentbeats.org/docs/getting-started/quick-start):
   ```toml
   [agent]
   name = "AgentName"
   description = "Agent description"
   version = "1.0.0"
   url = "http://YOUR_PUBLIC_IP:AGENT_PORT"
   
   [agent.capabilities]
   tools = ["tool1", "tool2"]
   ```
   - **TripMind TOML files**: Available in `agent_cards/` directory
     - `green_agent_card.toml` - Green Agent (Assessor)
     - `white_agent_card.toml` - White Agent (Assessee)

2. **A2A Agent Cards** (Current TripMind Implementation)
   - Programmatically created via `create_agent_card()` function
   - Exposed as JSON via `/.well-known/agent-card.json` endpoint
   - Automatically discovered by AgentBeats when the agent URL is registered

### Current TripMind Implementation

The TripMind codebase uses the **A2A protocol** and creates agent cards programmatically:

- **Green Agent** (`src/green_agent.py`): Assessment orchestrator
  - Agent card created in `create_agent_card()` function
  - Exposed at: `http://host:port/.well-known/agent-card.json`
  - Currently registered as a single assessee on AgentBeats

- **White Agent** (`src/white_agent.py`): Browser automation agent
  - Agent card created in `create_agent_card()` function
  - Used internally by Green Agent, not directly registered with AgentBeats

## Architecture: One Assessor + Multiple Assessees

```
┌─────────────────────────────────────────────────────────────────┐
│                    AgentBeats Platform                          │
│                  (https://agentbeats.io)                        │
└─────────────────────┬───────────────────────────────────────────┘
                      │ A2A Assessment Request
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│              GREEN AGENT (Assessor) - Port 9002                 │
│  - Receives assessment from AgentBeats                          │
│  - Sends tasks to ALL white agents in parallel                 │
│  - Evaluates and compares results                               │
│  - Reports metrics per-assessee and aggregate                 │
└───────┬─────────────────────────────────────────────────────────┘
        │
        │ Sends same task to all assessees in parallel
        │
        ├──────────────────┬──────────────────┬──────────────────┐
        ▼                  ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ WHITE AGENT  │  │ WHITE AGENT  │  │ WHITE AGENT  │  │ WHITE AGENT  │
│  (Assessee 1)│  │  (Assessee 2)│  │  (Assessee 3)│  │  (Assessee N)│
│  Port 9001   │  │  Port 9003   │  │  Port 9005   │  │  Port 900N   │
│              │  │              │  │              │  │              │
│ Browser Auto │  │ Browser Auto │  │ Browser Auto │  │ Browser Auto │
└──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘
```

## How to Add Multiple Assessees

### Method 1: One Green Agent + Multiple White Agents (Recommended)

This is the recommended approach for TripMind. You run one Green Agent (assessor) that manages multiple White Agents (assessees).

#### Step 1: Start Multiple White Agents (Assessees)

Start multiple white agents on different ports:

```bash
# Option A: Use the multi-assessee launcher script
./start_multiple_assessees.sh 3  # Starts 3 white agents

# Option B: Start manually
# Terminal 1 - White Agent 1 (Assessee 1)
python -m src.white_agent --port 9001

# Terminal 2 - White Agent 2 (Assessee 2)
python -m src.white_agent --port 9003

# Terminal 3 - White Agent 3 (Assessee 3)
python -m src.white_agent --port 9005
```

#### Step 2: Start Green Agent (Assessor) with Multiple White Agent URLs

Start the green agent and specify all white agent URLs:

```bash
# Using command line arguments
python -m src.green_agent \
  --port 9002 \
  --white-agent-urls http://localhost:9001 http://localhost:9003 http://localhost:9005

# Or using environment variable (comma-separated)
export WHITE_AGENT_URLS="http://localhost:9001,http://localhost:9003,http://localhost:9005"
python -m src.green_agent --port 9002
```

#### Step 3: Expose Green Agent via Cloudflare Tunnel

Only the Green Agent needs to be exposed (white agents run locally):

```bash
# Create tunnel for Green Agent
cloudflared tunnel --url http://localhost:9002
# Output: https://tripmind-assessor-xyz.trycloudflare.com
```

#### Step 4: Register Green Agent on AgentBeats

1. Go to [AgentBeats](https://v2.agentbeats.org/) and log in
2. Navigate to "Agent Management" → "Create New Agent"
3. Fill in:
   - **Name**: TripMind Multi-Assessee Evaluator
   - **Deploy Type**: Remote
   - **Controller URL**: Your Cloudflare tunnel URL (e.g., `https://tripmind-assessor-xyz.trycloudflare.com`)
   - **Is Green Agent**: ✓ Check this box
4. Click "Create Agent"
5. Use "Check" button to verify connectivity

#### Step 5: Run Assessment

When AgentBeats sends an assessment request:
- The Green Agent receives the task
- It sends the same task to ALL white agents in parallel
- It collects results from all assessees
- It reports metrics per-assessee and aggregate metrics

You can also test locally:

```bash
curl -X POST http://localhost:9002/start-assessment \
  -H "Content-Type: application/json" \
  -d '{
    "white_agent_urls": ["http://localhost:9001", "http://localhost:9003", "http://localhost:9005"],
    "task_count": 1
  }'
```

The response will include:
- `metrics.aggregate`: Overall metrics across all assessees
- `metrics.per_assessee`: Individual metrics for each white agent
- `results`: Detailed results from each assessee for each task

### Method 2: Using AgentBeats SDK with TOML Cards

If you want to use the traditional AgentBeats SDK approach:

#### Step 1: Install AgentBeats SDK

```bash
pip install agentbeats
```

#### Step 2: Create Agent Card Files

Create a `.toml` file for each assessee:

**assessee1_card.toml:**
```toml
name = "TripMind Assessee 1"
url = "http://YOUR_PUBLIC_IP:9002"

[agent.capabilities]
tools = ["flight_search", "hotel_search", "itinerary_creation"]
```

**assessee2_card.toml:**
```toml
name = "TripMind Assessee 2"
url = "http://YOUR_PUBLIC_IP:9003"

[agent.capabilities]
tools = ["flight_search", "hotel_search", "itinerary_creation"]
```

#### Step 3: Run Each Agent with AgentBeats SDK

```bash
# Assessee 1
agentbeats run assessee1_card.toml \
  --launcher_host YOUR_PUBLIC_IP \
  --launcher_port 8002 \
  --agent_host YOUR_PUBLIC_IP \
  --agent_port 9002 \
  --model_type "custom" \
  --model_name "tripmind-v1"

# Assessee 2
agentbeats run assessee2_card.toml \
  --launcher_host YOUR_PUBLIC_IP \
  --launcher_port 8003 \
  --agent_host YOUR_PUBLIC_IP \
  --agent_port 9003 \
  --model_type "custom" \
  --model_name "tripmind-v2"
```

**Note:** This approach requires adapting your current A2A-based agents to work with the AgentBeats SDK launcher, which may require significant changes.

## Key Differences: A2A vs AgentBeats SDK

| Aspect | A2A Protocol (Current) | AgentBeats SDK |
|--------|------------------------|----------------|
| Agent Card | Programmatic (JSON) | TOML file |
| Discovery | `/.well-known/agent-card.json` | Via `agentbeats run` |
| Registration | Manual on AgentBeats UI | Via SDK launcher |
| Flexibility | Full control | SDK-managed lifecycle |

## Best Practices for Multiple Assessees

1. **Unique Ports**: Each assessee must use unique ports to avoid conflicts
2. **Unique Names**: Use descriptive, unique names for each assessee in AgentBeats
3. **Separate Tunnels**: Each assessee needs its own Cloudflare tunnel (or public URL)
4. **Consistent Configuration**: Keep agent configurations consistent for fair comparison
5. **Monitoring**: Monitor each assessee's health independently

## Example: Running 3 Assessees

### Quick Start (Using Launcher Script)

```bash
# Start 3 white agents + 1 green agent
./start_multiple_assessees.sh 3

# In another terminal, expose green agent
cloudflared tunnel --url http://localhost:9002
```

### Manual Start

```bash
# Terminal 1 - White Agent 1 (Assessee 1)
python -m src.white_agent --port 9001

# Terminal 2 - White Agent 2 (Assessee 2)
python -m src.white_agent --port 9003

# Terminal 3 - White Agent 3 (Assessee 3)
python -m src.white_agent --port 9005

# Terminal 4 - Green Agent (Assessor) - manages all 3 white agents
python -m src.green_agent \
  --port 9002 \
  --white-agent-urls http://localhost:9001 http://localhost:9003 http://localhost:9005

# Terminal 5 - Cloudflare Tunnel (expose green agent only)
cloudflared tunnel --url http://localhost:9002
```

### Configuration via Environment Variables

```bash
# Set multiple white agent URLs
export WHITE_AGENT_URLS="http://localhost:9001,http://localhost:9003,http://localhost:9005"
export GREEN_AGENT_PORT=9002

# Start green agent
python -m src.green_agent
```

## Verification

After starting all agents:

1. **Check Green Agent Status**: 
   ```bash
   curl http://localhost:9002/status
   # Should show all white agent URLs in the response
   ```

2. **Check White Agent Status**:
   ```bash
   curl http://localhost:9001/status  # Assessee 1
   curl http://localhost:9003/status  # Assessee 2
   curl http://localhost:9005/status  # Assessee 3
   ```

3. **Test Assessment Locally**:
   ```bash
   curl -X POST http://localhost:9002/start-assessment \
     -H "Content-Type: application/json" \
     -d '{
       "white_agent_urls": ["http://localhost:9001", "http://localhost:9003", "http://localhost:9005"],
       "task_count": 1
     }'
   ```
   
   The response should include:
   - `metrics.aggregate`: Overall pass rate, avg time, etc.
   - `metrics.per_assessee`: Individual metrics for each white agent
   - `results`: Array of results, each tagged with `assessee_name` and `assessee_url`

4. **Verify on AgentBeats**: 
   - Use the "Check" button for the registered Green Agent
   - The status should show the number of assessees configured

5. **Run Assessment from AgentBeats**:
   - Start an assessment from AgentBeats
   - The Green Agent will automatically send tasks to all configured white agents
   - Results will include per-assessee comparisons

## Troubleshooting

### Port Conflicts
- Ensure each assessee uses a unique port
- Check for running processes: `lsof -i :9002`

### Tunnel Issues
- Each tunnel must point to a different local port
- Verify tunnel URLs are accessible from the internet

### Registration Failures
- Ensure agent card endpoint is accessible
- Check that `/.well-known/agent-card.json` returns valid JSON
- Verify Cloudflare tunnel is running

### Assessment Issues
- Ensure all assessees are registered and show "Connected" status
- Check that each assessee can handle tasks independently
- Monitor logs for each assessee separately

## References

- [AgentBeats Documentation](https://docs.agentbeats.org/)
- [AgentBeats GitHub](https://github.com/agentbeats/agentbeats)
- [A2A Protocol Specification](https://github.com/agentbeats/a2a)

