# How AgentBeats Discovers Agent Cards

## The Discovery Process

When you register an agent on AgentBeats with just a Cloudflare tunnel URL (e.g., `https://xyz.trycloudflare.com`), here's how AgentBeats discovers the agent card:

### Step-by-Step Discovery Flow

```
1. You register agent on AgentBeats:
   ┌─────────────────┐
   │  AgentBeats UI  │
   │  URL: https://  │
   │  xyz.trycloud   │
   │  flare.com      │
   └────────┬────────┘
            │
            │ 2. AgentBeats makes HTTP GET request
            ▼
   ┌─────────────────────────────────────────────┐
   │  GET https://xyz.trycloudflare.com/         │
   │      .well-known/agent-card.json            │
   └────────┬───────────────────────────────────┘
            │
            │ 3. Cloudflare Tunnel forwards to localhost:9002
            ▼
   ┌─────────────────────────────────────────────┐
   │  Your Local Machine                         │
   │  ┌──────────────────────────────────────┐  │
   │  │  Green Agent (Port 9002)               │  │
   │  │  A2AStarletteApplication               │  │
   │  │  ┌──────────────────────────────────┐ │  │
   │  │  │  /.well-known/agent-card.json     │ │  │
   │  │  │  (Auto-exposed by A2A SDK)        │ │  │
   │  │  └──────────────────────────────────┘ │  │
   │  └──────────────────────────────────────┘  │
   └────────┬───────────────────────────────────┘
            │
            │ 4. Returns JSON agent card
            ▼
   ┌─────────────────────────────────────────────┐
   │  AgentBeats receives agent card JSON:       │
   │  {                                           │
   │    "name": "TripMind Green Agent",          │
   │    "description": "...",                    │
   │    "url": "...",                             │
   │    "skills": [...],                         │
   │    "capabilities": {...}                    │
   │  }                                           │
   └─────────────────────────────────────────────┘
```

## How It Works in Code

### 1. Agent Card Creation (Programmatic)

In `src/green_agent.py`, the agent card is created programmatically:

```python
def create_agent_card(host: str, port: int, base_url: str = None) -> AgentCard:
    """Create the A2A agent card for the green agent."""
    agent_url = base_url if base_url else f"http://{host}:{port}"
    
    return AgentCard(
        name="TripMind Green Agent",
        description="Assessment orchestrator...",
        url=agent_url,
        version="1.0.0",
        skills=[...],
        capabilities=...
    )
```

### 2. A2A Application Setup

The `A2AStarletteApplication` automatically exposes the agent card:

```python
a2a_app = A2AStarletteApplication(
    agent_card=agent_card,  # ← Agent card passed here
    http_handler=request_handler,
)

app = a2a_app.build()  # ← This automatically creates /.well-known/agent-card.json
```

### 3. Automatic Endpoint Exposure

The A2A SDK automatically creates the `/.well-known/agent-card.json` endpoint that:
- Returns the agent card as JSON
- Follows the A2A protocol standard
- Is discoverable by AgentBeats and other A2A-compatible platforms

## Testing the Discovery

You can test the agent card discovery yourself:

```bash
# Test locally
curl http://localhost:9002/.well-known/agent-card.json

# Test via Cloudflare tunnel
curl https://your-tunnel.trycloudflare.com/.well-known/agent-card.json
```

Expected response:
```json
{
  "name": "TripMind Green Agent",
  "description": "Assessment orchestrator for travel agent evaluation...",
  "url": "https://your-tunnel.trycloudflare.com",
  "version": "1.0.0",
  "skills": [
    {
      "id": "travel-assessment",
      "name": "Travel Agent Assessment",
      ...
    }
  ],
  "capabilities": {
    "streaming": false,
    "pushNotifications": false
  }
}
```

## Why TOML Files Exist

The TOML files in `agent_cards/` serve two purposes:

1. **Documentation**: They document the agent's capabilities in a human-readable format
2. **AgentBeats SDK**: If you want to use the traditional AgentBeats SDK approach (instead of A2A), you can use these TOML files with `agentbeats run`

However, **the current implementation uses A2A protocol**, which means:
- ✅ Agent cards are automatically exposed via HTTP
- ✅ No need to manually upload TOML files
- ✅ AgentBeats discovers them automatically when you provide the URL
- ✅ The TOML files are optional/reference only

## Key Points

1. **A2A Protocol Standard**: The `/.well-known/agent-card.json` endpoint is part of the A2A (Agent-to-Agent) protocol standard
2. **Automatic Discovery**: AgentBeats automatically fetches the agent card when you register a URL
3. **No Manual Upload**: You don't need to upload TOML files - the JSON is generated dynamically
4. **Cloudflare Tunnel**: The tunnel forwards requests to your local agent, making the discovery endpoint accessible

## Verification Checklist

When registering with AgentBeats:

1. ✅ Green Agent is running on port 9002
2. ✅ Cloudflare tunnel is active and forwarding to localhost:9002
3. ✅ Agent card endpoint is accessible: `curl https://your-tunnel/.well-known/agent-card.json`
4. ✅ AgentBeats "Check" button succeeds (it tests the `/status` endpoint)
5. ✅ Agent appears in AgentBeats with correct name and capabilities

## Troubleshooting

### AgentBeats can't discover agent card

1. **Check endpoint is accessible**:
   ```bash
   curl https://your-tunnel.trycloudflare.com/.well-known/agent-card.json
   ```
   Should return JSON, not 404.

2. **Verify Cloudflare tunnel is running**:
   ```bash
   cloudflared tunnel --url http://localhost:9002
   ```

3. **Check agent is running**:
   ```bash
   curl http://localhost:9002/status
   ```

4. **Verify A2A application is set up correctly**:
   - Check that `A2AStarletteApplication` is used
   - Verify `agent_card` is passed to the application

### Agent card shows wrong URL

The agent card uses `base_url` if set, otherwise constructs from `host:port`. Make sure:
- `BASE_URL` environment variable is set to your Cloudflare tunnel URL, OR
- The `base_url` parameter is passed when creating the app

## References

- [A2A Protocol Specification](https://github.com/agentbeats/a2a)
- [AgentBeats Documentation](https://agentbeats.org/docs/getting-started/quick-start)
- A2A SDK automatically handles `/.well-known/agent-card.json` endpoint

