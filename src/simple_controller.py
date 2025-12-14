"""
Simple AgentBeats Controller - Mimics earthshaker/agentbeats controller exactly

Based on analysis of /opt/homebrew/lib/python3.14/site-packages/agentbeats/controller.py

Key endpoints AgentBeats expects:
- GET /status - {"maintained_agents": N, "running_agents": N, "starting_command": "..."}
- GET /agents - {agent_id: {"url": "...", "internal_port": N, "state": "running"}}
- GET /agents/{agent_id} - {"state": "...", "stdout_log": "...", "stderr_log": "...", "agent_card": "JSON string"}
- POST /agents/{agent_id}/reset
- * /to_agent/{agent_id}/{path} - proxy to agent
"""

import os
import json
import uuid
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
import uvicorn

# Configuration
AGENT_ID = os.getenv("AGENT_ID", uuid.uuid4().hex)
AGENT_HOST = os.getenv("AGENT_HOST", "localhost")
AGENT_PORT = int(os.getenv("AGENT_PORT", "9002"))
CONTROLLER_PORT = int(os.getenv("CONTROLLER_PORT", "8010"))
BASE_URL = os.getenv("BASE_URL", f"http://localhost:{CONTROLLER_PORT}")

# Compute agent URL (what goes in the agent card)
AGENT_URL = f"{BASE_URL}/to_agent/{AGENT_ID}"

# Cache the agent card
_agent_card_cache = None

app = FastAPI(title="TripMind Controller")


async def fetch_agent_card():
    """Fetch agent card from the actual agent."""
    global _agent_card_cache
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"http://{AGENT_HOST}:{AGENT_PORT}/.well-known/agent-card.json")
            if resp.status_code == 200:
                card = resp.json()
                # Override the URL in the card to use the controller's proxy URL
                card["url"] = AGENT_URL
                _agent_card_cache = card
                return card
        except Exception as e:
            print(f"[CONTROLLER] Error fetching agent card: {e}")
    return None


@app.on_event("startup")
async def startup_event():
    """Fetch agent card on startup."""
    print(f"[CONTROLLER] Agent URL will be: {AGENT_URL}")
    await fetch_agent_card()


@app.get("/")
async def root():
    """Redirect to info page."""
    return RedirectResponse(url="/info")


@app.get("/info", response_class=HTMLResponse)
async def get_info_page():
    """Simple info page."""
    return f"""
    <html>
    <head><title>TripMind Controller</title></head>
    <body>
        <h1>TripMind Controller</h1>
        <p>Agent ID: {AGENT_ID}</p>
        <p>Agent URL: {AGENT_URL}</p>
        <p><a href="/agents">View Agents</a></p>
    </body>
    </html>
    """


@app.get("/status")
async def get_status():
    """
    Status endpoint - EXACT format from earthshaker controller.
    AgentBeats checks this to verify controller is reachable.
    """
    return {
        "maintained_agents": 1,
        "running_agents": 1,
        "starting_command": "python3 main.py green",
    }


@app.get("/agents")
async def list_agents():
    """
    List agents - EXACT format from earthshaker controller.
    Returns: {agent_id: {"url": "...", "internal_port": N, "state": "running"}}
    """
    return {
        AGENT_ID: {
            "url": AGENT_URL,
            "internal_port": AGENT_PORT,
            "state": "running",
        }
    }


@app.get("/agents/{agent_id}")
async def get_agent_info(agent_id: str):
    """
    Get agent details - EXACT format from earthshaker controller.
    THIS is where AgentBeats gets the agent_card!
    
    Returns: {"state": "...", "stdout_log": "...", "stderr_log": "...", "agent_card": "JSON string"}
    """
    if agent_id != AGENT_ID:
        return JSONResponse({"error": "Agent not found"}, status_code=404)
    
    # Fetch fresh agent card
    card = await fetch_agent_card()
    
    # agent_card must be a JSON STRING, not an object!
    agent_card_str = json.dumps(card, indent=2) if card else "Agent card not available"
    
    return {
        "state": "running",
        "stdout_log": "Agent running normally",
        "stderr_log": "",
        "agent_card": agent_card_str,  # This is a STRING containing JSON
    }


@app.post("/agents/{agent_id}/reset")
async def reset_agent(agent_id: str):
    """Reset agent endpoint."""
    if agent_id != AGENT_ID:
        return JSONResponse({"error": "Agent not found"}, status_code=404)
    return {"message": f"Agent {agent_id} reset requested."}


@app.api_route(
    "/to_agent/{agent_id}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy_to_agent_root(agent_id: str, request: Request):
    """Proxy root path to agent."""
    return await proxy_to_agent(agent_id, "", request)


@app.api_route(
    "/to_agent/{agent_id}/{full_path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def proxy_to_agent(agent_id: str, full_path: str, request: Request):
    """
    Proxy all requests to the agent - EXACT behavior from earthshaker.
    """
    if agent_id != AGENT_ID:
        return JSONResponse({"error": "Agent not found"}, status_code=404)
    
    # Build target URL
    agent_url = f"http://{AGENT_HOST}:{AGENT_PORT}/{full_path}"
    
    # Get request body
    body = await request.body()
    
    # Forward headers
    headers = dict(request.headers)
    headers.pop("host", None)
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=1800.0) as client:
        try:
            response = await client.request(
                method=request.method,
                url=agent_url,
                content=body,
                headers=headers,
                params=request.query_params,
            )
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
            )
        except httpx.ConnectError:
            return JSONResponse({"error": "Agent not reachable"}, status_code=502)
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)


def start_controller(host: str = "0.0.0.0", port: int = None):
    """Start the controller server."""
    port = port or CONTROLLER_PORT
    
    print(f"\n{'='*60}")
    print(f"  TripMind Controller (earthshaker-compatible)")
    print(f"{'='*60}")
    print(f"  Controller: http://{host}:{port}")
    print(f"  Agent: http://{AGENT_HOST}:{AGENT_PORT}")
    print(f"  Agent ID: {AGENT_ID}")
    print(f"  Agent URL: {AGENT_URL}")
    print(f"{'='*60}")
    print(f"  Endpoints:")
    print(f"    GET /status")
    print(f"    GET /agents")
    print(f"    GET /agents/{AGENT_ID}")
    print(f"    * /to_agent/{AGENT_ID}/...")
    print(f"{'='*60}\n")
    
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8010)
    args = parser.parse_args()
    start_controller(host=args.host, port=args.port)
