"""
TripMind Green Agent - Assessment Orchestrator

This is the "hosting" agent that orchestrates assessments.
It receives assessment requests from AgentBeats, sends tasks to white agents,
evaluates results, and reports metrics.

Run on port 9002 (exposed via Cloudflare tunnel to AgentBeats).
"""

import os
import json
import uuid
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Optional, List, Dict, Tuple

import httpx
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Message,
    Part,
    TextPart,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils.errors import ServerError
import uvicorn


# Sample test tasks for travel assessments
SAMPLE_TASKS = [
    {
        "id": "flight_search_1",
        "task": "Find the cheapest round-trip flight from New York (JFK) to San Francisco (SFO) departing on December 15, 2024 and returning on December 22, 2024.",
        "category": "flight_search",
        "expected_actions": ["navigate", "input_origin", "input_destination", "select_dates", "search"]
    },
    {
        "id": "hotel_search_1",
        "task": "Find a hotel in Paris, France for 2 adults from January 10-15, 2025 with a rating of 4 stars or higher.",
        "category": "hotel_search",
        "expected_actions": ["navigate", "input_location", "select_dates", "filter_rating", "search"]
    },
    {
        "id": "flight_search_2",
        "task": "Search for one-way flights from Los Angeles (LAX) to Tokyo (NRT) on March 1, 2025, sorted by price.",
        "category": "flight_search",
        "expected_actions": ["navigate", "select_one_way", "input_origin", "input_destination", "select_date", "sort_price"]
    },
]


@dataclass
class GreenAgentConfig:
    """Configuration for the Green Agent."""
    host: str = "0.0.0.0"
    port: int = 9002
    base_url: Optional[str] = None  # Public URL for cloud (Cloudflare tunnel)
    white_agent_urls: List[str] = field(default_factory=lambda: ["http://localhost:9001"])  # List of white agent URLs (assessees)


@dataclass
class AssessmentResult:
    """Result of a single task assessment."""
    task_id: str
    task: str
    assessee_name: str  # Name/URL of the white agent (assessee) that produced this result
    assessee_url: str  # URL of the white agent
    success: bool
    time_used: float
    action_count: int
    final_response: str
    error: Optional[str] = None


def create_agent_card(host: str, port: int, base_url: str = None) -> AgentCard:
    """Create the A2A agent card for the green agent."""
    agent_url = base_url if base_url else f"http://{host}:{port}"

    return AgentCard(
        name="TripMind Green Agent",
        description=(
            "Assessment orchestrator for travel agent evaluation. "
            "Manages WebJudge-style assessments for browser automation agents. "
            "Sends tasks to white agents, evaluates results, and reports metrics."
        ),
        url=agent_url,
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
        ),
        skills=[
            AgentSkill(
                id="travel-assessment",
                name="Travel Agent Assessment",
                description="Evaluate travel booking agents on flight/hotel search tasks",
                tags=["assessment", "evaluation", "travel"],
            ),
            AgentSkill(
                id="webjudge-eval",
                name="WebJudge Evaluation",
                description="LLM-based evaluation of web navigation results",
                tags=["evaluation", "webjudge", "llm"],
            ),
        ],
    )


class GreenAgentExecutor(AgentExecutor):
    """
    Executor that handles assessment orchestration.

    When AgentBeats sends "Start Assessment", this executor:
    1. Parses the assessment configuration
    2. Sends tasks to the white agent
    3. Evaluates the results
    4. Returns metrics
    """

    def __init__(self, config: GreenAgentConfig):
        self.config = config

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute an assessment."""
        # Extract assessment request
        request_text = None
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, 'root') and hasattr(part.root, 'text'):
                    request_text = part.root.text
                    break
                elif hasattr(part, 'text'):
                    request_text = part.text
                    break

        if not request_text:
            await self._send_response(event_queue, context, {
                "status": "error",
                "message": "No assessment request provided"
            })
            return

        print(f"\n{'='*60}")
        print(f"[GREEN AGENT] Received assessment request:")
        print(f"{request_text[:300]}...")
        print(f"{'='*60}\n")

        try:
            # Parse the assessment request
            config = self._parse_assessment_request(request_text)

            # Run the assessment
            results = await self._run_assessment(config)

            # Calculate metrics
            metrics = self._calculate_metrics(results)

            # Send response with metrics
            await self._send_response(event_queue, context, {
                "status": "completed",
                "metrics": metrics,
                "results": [r.__dict__ for r in results]
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            await self._send_response(event_queue, context, {
                "status": "error",
                "message": str(e)
            })

    def _parse_assessment_request(self, request_text: str) -> Dict[str, Any]:
        """Parse the assessment request from AgentBeats."""
        config = {
            "white_agent_urls": self.config.white_agent_urls.copy(),  # Use configured white agents
            "tasks": SAMPLE_TASKS[:1],  # Default: run first task
            "task_count": 1,
        }

        # Try to parse as JSON
        try:
            if "{" in request_text:
                json_str = request_text[request_text.find("{"):request_text.rfind("}")+1]
                parsed = json.loads(json_str)
                config.update(parsed)
                # Handle both single URL and list of URLs
                if "white_agent_url" in parsed:
                    config["white_agent_urls"] = [parsed["white_agent_url"]]
                elif "white_agent_urls" in parsed:
                    config["white_agent_urls"] = parsed["white_agent_urls"]
        except json.JSONDecodeError:
            pass

        # Check for white agent URLs in text
        if "white_agent" in request_text.lower() or "http://" in request_text or "https://" in request_text:
            import re
            urls = re.findall(r'http[s]?://[^\s<>"]+', request_text)
            white_agent_urls = []
            for url in urls:
                url = url.rstrip("/")
                # Filter for white agent URLs (ports 9001-9010 or contains "white")
                if any(str(port) in url for port in range(9001, 9011)) or "white" in url.lower():
                    white_agent_urls.append(url)
            if white_agent_urls:
                config["white_agent_urls"] = white_agent_urls

        # Check for task count
        if "task_count" in request_text.lower():
            import re
            match = re.search(r'task_count[:\s]+(\d+)', request_text.lower())
            if match:
                count = min(int(match.group(1)), len(SAMPLE_TASKS))
                config["tasks"] = SAMPLE_TASKS[:count]
                config["task_count"] = count

        return config

    async def _run_assessment(self, config: Dict[str, Any]) -> List[AssessmentResult]:
        """Run the assessment by sending tasks to all white agents (assessees) in parallel."""
        results = []
        white_agent_urls = config.get("white_agent_urls", self.config.white_agent_urls)

        print(f"[GREEN AGENT] Starting assessment with {len(config['tasks'])} task(s)")
        print(f"[GREEN AGENT] Assessees (White Agents): {len(white_agent_urls)}")
        for i, url in enumerate(white_agent_urls, 1):
            print(f"  {i}. {url}")

        for task_data in config["tasks"]:
            task_id = task_data["id"]
            task_text = task_data["task"]

            print(f"\n[GREEN AGENT] Running task: {task_id}")
            print(f"[GREEN AGENT] Task: {task_text[:100]}...")
            print(f"[GREEN AGENT] Sending to {len(white_agent_urls)} assessee(s)...")

            # Send task to all white agents in parallel
            tasks = [
                self._send_task_to_white_agent_with_metadata(url, task_text, task_id)
                for url in white_agent_urls
            ]
            
            # Wait for all assessees to complete
            assessee_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results from each assessee
            for idx, (white_agent_url, assessee_result) in enumerate(zip(white_agent_urls, assessee_results)):
                assessee_name = f"Assessee-{idx+1}"
                # Extract name from URL if possible
                if ":" in white_agent_url:
                    port = white_agent_url.split(":")[-1].split("/")[0]
                    assessee_name = f"White-Agent-{port}"

                if isinstance(assessee_result, Exception):
                    # Error occurred
                    results.append(AssessmentResult(
                        task_id=task_id,
                        task=task_text,
                        assessee_name=assessee_name,
                        assessee_url=white_agent_url,
                        success=False,
                        time_used=0.0,
                        action_count=0,
                        final_response="",
                        error=str(assessee_result)
                    ))
                    print(f"[GREEN AGENT] {assessee_name} ({white_agent_url}): ERROR - {assessee_result}")
                else:
                    time_used, result = assessee_result
                    
                    # Parse the result
                    if isinstance(result, str):
                        try:
                            result = json.loads(result)
                        except json.JSONDecodeError:
                            result = {"final_result_response": result, "action_history": []}

                    # Evaluate success (simple heuristic - can be enhanced with WebJudge)
                    success = self._evaluate_result(task_data, result)

                    results.append(AssessmentResult(
                        task_id=task_id,
                        task=task_text,
                        assessee_name=assessee_name,
                        assessee_url=white_agent_url,
                        success=success,
                        time_used=time_used,
                        action_count=len(result.get("action_history", [])),
                        final_response=result.get("final_result_response", "")[:500],
                    ))

                    print(f"[GREEN AGENT] {assessee_name} ({white_agent_url}): {'SUCCESS' if success else 'FAILED'} ({time_used:.2f}s)")

        return results

    async def _send_task_to_white_agent_with_metadata(
        self, white_agent_url: str, task: str, task_id: str
    ) -> Tuple[float, Dict]:
        """
        Send a task to the white agent via A2A protocol and return (time_used, result).
        
        Returns:
            Tuple of (time_used, result_dict)
        """
        start_time = time.time()
        result = await self._send_task_to_white_agent(white_agent_url, task)
        time_used = time.time() - start_time
        return (time_used, result)

    async def _send_task_to_white_agent(self, white_agent_url: str, task: str) -> Dict:
        """Send a task to the white agent via A2A protocol."""
        # Use the A2A message/send endpoint
        a2a_url = f"{white_agent_url}/message/send"

        # Construct A2A message
        message_payload = {
            "message": {
                "role": "user",
                "parts": [{"text": task}],
                "messageId": str(uuid.uuid4()),
            }
        }

        async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min timeout
            try:
                response = await client.post(
                    a2a_url,
                    json=message_payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()

                result = response.json()

                # Extract text from A2A response
                if "result" in result and "parts" in result["result"]:
                    for part in result["result"]["parts"]:
                        if "text" in part:
                            return part["text"]
                        elif "root" in part and "text" in part["root"]:
                            return part["root"]["text"]

                return result

            except httpx.HTTPError as e:
                # Fallback: try direct /execute endpoint
                print(f"[GREEN AGENT] A2A failed for {white_agent_url}, trying /execute endpoint...")
                execute_url = f"{white_agent_url}/execute"
                response = await client.post(
                    execute_url,
                    json={"task": task},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()

    def _evaluate_result(self, task_data: Dict, result: Dict) -> bool:
        """
        Evaluate if the task was completed successfully.

        This is a simple heuristic. For production, integrate WebJudge
        from src/methods/webjudge_general_eval.py
        """
        # Check if we got any actions
        action_count = len(result.get("action_history", []))
        if action_count == 0:
            return False

        # Check status
        status = result.get("status", "")
        if status == "failed":
            return False

        # Check for error in final response
        final_response = result.get("final_result_response", "").lower()
        if "error" in final_response or "failed" in final_response:
            return False

        # Basic success: got actions and didn't fail
        return action_count >= 3

    def _calculate_metrics(self, results: List[AssessmentResult]) -> Dict:
        """Calculate assessment metrics (aggregate and per-assessee)."""
        total = len(results)
        if total == 0:
            return {
                "aggregate": {"pass_rate": 0, "avg_time": 0, "avg_actions": 0},
                "per_assessee": {}
            }

        # Aggregate metrics
        successes = sum(1 for r in results if r.success)
        total_time = sum(r.time_used for r in results)
        total_actions = sum(r.action_count for r in results)

        # Group results by assessee
        assessee_results: Dict[str, List[AssessmentResult]] = {}
        for result in results:
            key = result.assessee_url
            if key not in assessee_results:
                assessee_results[key] = []
            assessee_results[key].append(result)

        # Calculate per-assessee metrics
        per_assessee = {}
        for assessee_url, assessee_res in assessee_results.items():
            assessee_name = assessee_res[0].assessee_name
            assessee_total = len(assessee_res)
            assessee_successes = sum(1 for r in assessee_res if r.success)
            assessee_time = sum(r.time_used for r in assessee_res)
            assessee_actions = sum(r.action_count for r in assessee_res)

            per_assessee[assessee_name] = {
                "url": assessee_url,
                "total_tasks": assessee_total,
                "passed": assessee_successes,
                "failed": assessee_total - assessee_successes,
                "pass_rate": round(assessee_successes / assessee_total * 100, 2) if assessee_total > 0 else 0,
                "avg_time_seconds": round(assessee_time / assessee_total, 2) if assessee_total > 0 else 0,
                "avg_actions": round(assessee_actions / assessee_total, 2) if assessee_total > 0 else 0,
            }

        return {
            "aggregate": {
                "total_tasks": total,
                "passed": successes,
                "failed": total - successes,
                "pass_rate": round(successes / total * 100, 2) if total > 0 else 0,
                "avg_time_seconds": round(total_time / total, 2) if total > 0 else 0,
                "avg_actions": round(total_actions / total, 2) if total > 0 else 0,
            },
            "per_assessee": per_assessee,
            "num_assessees": len(assessee_results)
        }

    async def _send_response(
        self,
        event_queue: EventQueue,
        context: RequestContext,
        data: Dict
    ) -> None:
        """Send response back to AgentBeats."""
        message = Message(
            role="agent",
            parts=[Part(root=TextPart(text=json.dumps(data, indent=2)))],
            messageId=str(uuid.uuid4()),
            contextId=context.context_id,
            taskId=context.task_id,
        )
        await event_queue.enqueue_event(message)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Handle task cancellation."""
        raise ServerError(error={"message": "Assessment cancellation not supported"})


def create_app(config: GreenAgentConfig):
    """Create the Starlette application."""
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.requests import Request

    agent_card = create_agent_card(config.host, config.port, config.base_url)
    executor = GreenAgentExecutor(config)

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    a2a_app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    app = a2a_app.build()

    # Status endpoint (for AgentBeats "Check" button)
    async def status_endpoint(request):
        return JSONResponse({
            "status": "ok",
            "name": "TripMind Green Agent",
            "version": "1.0.0",
            "type": "green_agent",
            "white_agent_urls": config.white_agent_urls,
            "num_assessees": len(config.white_agent_urls),
            "available_tasks": len(SAMPLE_TASKS),
        })

    # Health endpoint
    async def health_endpoint(request):
        return JSONResponse({"healthy": True})

    # Manual assessment trigger endpoint
    async def start_assessment_endpoint(request: Request):
        """
        Manual endpoint to start an assessment.

        POST /start-assessment
        Body: {
            "white_agent_urls": ["http://localhost:9001", "http://localhost:9003"],
            "task_count": 1
        }
        """
        try:
            body = await request.json()
            # Support both single URL and list of URLs for backward compatibility
            white_agent_urls = body.get("white_agent_urls", config.white_agent_urls)
            if "white_agent_url" in body:
                # Backward compatibility: single URL
                white_agent_urls = [body["white_agent_url"]]
            if not isinstance(white_agent_urls, list):
                white_agent_urls = [white_agent_urls]
            
            task_count = min(body.get("task_count", 1), len(SAMPLE_TASKS))

            assessment_config = {
                "white_agent_urls": white_agent_urls,
                "tasks": SAMPLE_TASKS[:task_count],
                "task_count": task_count,
            }

            results = await executor._run_assessment(assessment_config)
            metrics = executor._calculate_metrics(results)

            return JSONResponse({
                "status": "completed",
                "metrics": metrics,
                "results": [r.__dict__ for r in results]
            })

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse({
                "status": "error",
                "message": str(e)
            }, status_code=500)

    # List available tasks endpoint
    async def tasks_endpoint(request):
        return JSONResponse({
            "tasks": SAMPLE_TASKS
        })

    def _build_agent_card():
        """Construct agent card data with verbose logging."""
        print("\n[GREEN AGENT] Building agent card")
        print(f"[GREEN AGENT] host={config.host} port={config.port} base_url={config.base_url}")
        card = create_agent_card(
            host=config.host,
            port=config.port,
            base_url=config.base_url,
        )
        try:
            data = card.model_dump()
            print("[GREEN AGENT] Serialized agent card via model_dump()")
        except Exception as e_md:
            print(f"[GREEN AGENT] model_dump() failed: {e_md}")
            try:
                data = card.dict()
                print("[GREEN AGENT] Serialized agent card via dict()")
            except Exception as e_dict:
                print(f"[GREEN AGENT] dict() failed: {e_dict}")
                from dataclasses import asdict
                data = asdict(card)
                print("[GREEN AGENT] Serialized agent card via dataclasses.asdict()")

        try:
            print(f"[GREEN AGENT] card.name={data.get('name')}")
            print(f"[GREEN AGENT] card.url={data.get('url')}")
            print(f"[GREEN AGENT] card.version={data.get('version')}")
        except Exception as e_log:
            print(f"[GREEN AGENT] Failed to log card fields: {e_log}")

        return data

    # Agent card endpoints for AgentBeats / discovery
    async def agent_card_endpoint(request):
        """Serve agent card at standard well-known path."""
        try:
            print("[GREEN AGENT] Agent card request: /.well-known/agent-card.json")
            data = _build_agent_card()
            return JSONResponse(data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse({"error": f"Failed to generate agent card: {str(e)}"}, status_code=500)

    async def agent_card_with_prefix_endpoint(request):
        """
        Serve agent card under to_agent/<agent_id>/.well-known/agent-card.json
        to match AgentBeats expectations.
        """
        try:
            agent_id = request.path_params.get("agent_id", "")
            print(f"[GREEN AGENT] Agent card request with prefix: agent_id={agent_id}")
            data = _build_agent_card()
            return JSONResponse(data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse({"error": f"Failed to generate agent card: {str(e)}"}, status_code=500)

    app.routes.insert(0, Route("/.well-known/agent-card.json", agent_card_endpoint, methods=["GET"]))
    app.routes.insert(0, Route("/to_agent/{agent_id}/.well-known/agent-card.json", agent_card_with_prefix_endpoint, methods=["GET"]))
    app.routes.insert(0, Route("/status", status_endpoint, methods=["GET"]))
    app.routes.insert(0, Route("/health", health_endpoint, methods=["GET"]))
    app.routes.insert(0, Route("/start-assessment", start_assessment_endpoint, methods=["POST"]))
    app.routes.insert(0, Route("/tasks", tasks_endpoint, methods=["GET"]))

    return app


def start_green_agent(
    host: str = None,
    port: int = None,
    base_url: str = None,
    white_agent_urls: List[str] = None,
):
    """Start the Green Agent server."""
    # Parse white agent URLs from environment or parameter
    if white_agent_urls is None:
        white_agent_urls_str = os.getenv("WHITE_AGENT_URLS", os.getenv("WHITE_AGENT_URL", "http://localhost:9001"))
        # Support comma-separated list or single URL
        if "," in white_agent_urls_str:
            white_agent_urls = [url.strip() for url in white_agent_urls_str.split(",")]
        else:
            white_agent_urls = [white_agent_urls_str]
    
    config = GreenAgentConfig(
        host=host or os.getenv("HOST", "0.0.0.0"),
        port=int(port or os.getenv("PORT", os.getenv("GREEN_AGENT_PORT", "9002"))),
        base_url=base_url or os.getenv("BASE_URL"),
        white_agent_urls=white_agent_urls,
    )

    print(f"\n{'='*60}")
    print(f"  TripMind GREEN AGENT (Assessment Orchestrator)")
    print(f"{'='*60}")
    print(f"  Host: {config.host}")
    print(f"  Port: {config.port}")
    print(f"  Base URL: {config.base_url or 'Not set (local mode)'}")
    print(f"  Assessees (White Agents): {len(config.white_agent_urls)}")
    for i, url in enumerate(config.white_agent_urls, 1):
        print(f"    {i}. {url}")
    print(f"  Available Tasks: {len(SAMPLE_TASKS)}")
    print(f"{'='*60}")
    print(f"  Agent Card: http://{config.host}:{config.port}/.well-known/agent-card.json")
    print(f"  Status: http://{config.host}:{config.port}/status")
    print(f"  Start Assessment: POST http://{config.host}:{config.port}/start-assessment")
    print(f"{'='*60}\n")

    app = create_app(config)

    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level="info",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="TripMind Green Agent")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9002)
    parser.add_argument("--base-url", type=str, default=None)
    parser.add_argument("--white-agent-urls", type=str, nargs="+", default=None,
                        help="One or more white agent URLs (assessees). Can also use comma-separated string or WHITE_AGENT_URLS env var.")

    args = parser.parse_args()
    
    # Parse white agent URLs
    white_agent_urls = args.white_agent_urls
    if white_agent_urls is None:
        white_agent_urls = None  # Will be parsed from env in start_green_agent
    
    start_green_agent(
        host=args.host,
        port=args.port,
        base_url=args.base_url,
        white_agent_urls=white_agent_urls,
    )
