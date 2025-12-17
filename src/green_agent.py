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
        "task": "Find the cheapest round-trip flight from New York (JFK) to San Francisco (SFO) departing on December 23, 2025 and returning on December 27, 2025.",
        "category": "flight_search",
        "expected_actions": ["navigate", "input_origin", "input_destination", "select_dates", "search"]
    },
    {
        "id": "hotel_search_1",
        "task": "Find a hotel in San Fransisco for 2 adults from December 23-27, 2025 with a rating of 4 stars or higher.",
        "category": "hotel_search",
        "expected_actions": ["navigate", "input_location", "select_dates", "filter_rating", "search"]
    },
    {
        "id": "itinerary_1",
        "task": "Plan a 3-day itinerary for San Francisco including top attractions, restaurants, and transportation options.",
        "category": "itinerary",
        "expected_actions": ["navigate", "search_attractions", "find_restaurants", "plan_route", "research"]
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


def create_agent_card(host: str, port: int, base_url: str = None, agent_id: str = None) -> AgentCard:
    """Create the A2A agent card for the green agent."""
    agent_url = base_url if base_url else f"http://{host}:{port}"
    # If agent_id is provided (from AgentBeats), include it in the URL
    if agent_id:
        agent_url = f"{agent_url}/to_agent/{agent_id}"

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
        """Run the assessment by sending tasks to white agents.
        
        Supports two modes:
        1. Comparison mode: Send same task to all agents (for benchmarking)
        2. Assignment mode: Send different tasks to different agents
        """
        results = []
        white_agent_urls = config.get("white_agent_urls", self.config.white_agent_urls)
        assessment_mode = config.get("mode", "comparison")  # "comparison" or "assignment"
        save_trajectories = config.get("save_trajectories", True)
        output_dir = config.get("output_dir", "./data/assessment_results")

        print(f"[GREEN AGENT] Starting assessment with {len(config['tasks'])} task(s)")
        print(f"[GREEN AGENT] Mode: {assessment_mode}")
        print(f"[GREEN AGENT] Assessees (White Agents): {len(white_agent_urls)}")
        for i, url in enumerate(white_agent_urls, 1):
            print(f"  {i}. {url}")

        if assessment_mode == "assignment":
            # Assignment mode: Each task goes to a specific agent
            tasks_to_execute = []
            for task_data in config["tasks"]:
                task_id = task_data["id"]
                task_text = task_data["task"]
                assigned_url = task_data.get("assign_to", white_agent_urls[len(tasks_to_execute) % len(white_agent_urls)])
                
                print(f"\n[GREEN AGENT] Task {task_id}: {task_text[:80]}...")
                print(f"[GREEN AGENT] Assigned to: {assigned_url}")
                
                tasks_to_execute.append((assigned_url, task_text, task_id, task_data))
            
            # Execute all assigned tasks in parallel
            task_futures = [
                self._send_task_to_white_agent_with_metadata(url, task, tid)
                for url, task, tid, _ in tasks_to_execute
            ]
            assessee_results = await asyncio.gather(*task_futures, return_exceptions=True)
            
            # Process results
            for (assigned_url, task_text, task_id, task_data), assessee_result in zip(tasks_to_execute, assessee_results):
                result_entry = await self._process_single_result(
                    assigned_url, task_text, task_id, task_data, assessee_result
                )
                results.append(result_entry)
                
                # Save trajectory if enabled
                if save_trajectories and not isinstance(assessee_result, Exception):
                    await self._save_trajectory(result_entry, assessee_result[1], output_dir)
        
        else:
            # Comparison mode: Send each task to ALL agents (original behavior)
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
                    result_entry = await self._process_single_result(
                        white_agent_url, task_text, task_id, task_data, assessee_result
                    )
                    results.append(result_entry)
                    
                    # Save trajectory if enabled
                    if save_trajectories and not isinstance(assessee_result, Exception):
                        await self._save_trajectory(result_entry, assessee_result[1], output_dir)

        return results

    async def _process_single_result(
        self, 
        white_agent_url: str, 
        task_text: str, 
        task_id: str, 
        task_data: Dict,
        assessee_result: Any
    ) -> AssessmentResult:
        """Process a single agent result and return AssessmentResult."""
        # Determine agent name from URL
        assessee_name = f"Assessee"
        if ":" in white_agent_url:
            port = white_agent_url.split(":")[-1].split("/")[0]
            assessee_name = f"White-Agent-{port}"

        if isinstance(assessee_result, Exception):
            # Error occurred
            print(f"[GREEN AGENT] {assessee_name} ({white_agent_url}): ERROR - {assessee_result}")
            return AssessmentResult(
                task_id=task_id,
                task=task_text,
                assessee_name=assessee_name,
                assessee_url=white_agent_url,
                success=False,
                time_used=0.0,
                action_count=0,
                final_response="",
                error=str(assessee_result)
            )
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

            print(f"[GREEN AGENT] {assessee_name} ({white_agent_url}): {'SUCCESS' if success else 'FAILED'} ({time_used:.2f}s)")
            
            return AssessmentResult(
                task_id=task_id,
                task=task_text,
                assessee_name=assessee_name,
                assessee_url=white_agent_url,
                success=success,
                time_used=time_used,
                action_count=len(result.get("action_history", [])),
                final_response=result.get("final_result_response", "")[:500],
            )

    async def _save_trajectory(
        self, 
        result: AssessmentResult, 
        raw_result: Dict,
        output_dir: str
    ) -> None:
        """Save trajectory to disk in WebJudge-compatible format."""
        try:
            # Create output directory structure
            task_dir = os.path.join(output_dir, result.task_id)
            os.makedirs(task_dir, exist_ok=True)
            trajectory_dir = os.path.join(task_dir, "trajectory")
            os.makedirs(trajectory_dir, exist_ok=True)

            # Parse result if it's a string
            if isinstance(raw_result, str):
                try:
                    raw_result = json.loads(raw_result)
                except json.JSONDecodeError:
                    raw_result = {"final_result_response": raw_result, "action_history": []}

            # Note: Screenshots will be copied by post-processing script
            white_agent_traj_path = raw_result.get("trajectory_path")
            if white_agent_traj_path:
                print(f"[GREEN AGENT] White agent trajectory path: {white_agent_traj_path}")

            # Create result.json in WebJudge format
            result_data = {
                "task": result.task,
                "action_history": raw_result.get("action_history", []),
                "final_result_response": raw_result.get("final_result_response", ""),
                "status": "completed" if result.success else "failed",
                "time_used": result.time_used,
                "assessee_name": result.assessee_name,
                "assessee_url": result.assessee_url,
                "screenshot_count": raw_result.get("screenshot_count", 0),
            }

            # Save result.json
            result_json_path = os.path.join(task_dir, "result.json")
            with open(result_json_path, "w") as f:
                json.dump(result_data, f, indent=2)

            print(f"[GREEN AGENT] Saved trajectory: {result_json_path}")

        except Exception as e:
            print(f"[GREEN AGENT] Error saving trajectory: {e}")
            import traceback
            traceback.print_exc()

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
        
        Comparison mode (original - sends same task to all agents):
        {
            "white_agent_urls": ["http://localhost:9001", "http://localhost:9003"],
            "task_count": 1,
            "mode": "comparison"
        }
        
        Assignment mode (new - assigns different tasks to different agents):
        
        Option 1 - Use task IDs from SAMPLE_TASKS (easiest):
        {
            "mode": "assignment",
            "tasks": [
                {"id": "flight_search_1", "assign_to": "http://localhost:9001"},
                {"id": "hotel_search_1", "assign_to": "http://localhost:9003"},
                {"id": "itinerary_1", "assign_to": "http://localhost:9005"}
            ]
        }
        
        Option 2 - Auto-assign to agents in order:
        {
            "mode": "assignment",
            "tasks": [
                {"id": "flight_search_1"},
                {"id": "hotel_search_1"},
                {"id": "itinerary_1"}
            ]
        }
        
        Option 3 - Full task text (custom tasks):
        {
            "mode": "assignment",
            "tasks": [
                {
                    "id": "custom_task_1",
                    "task": "Find flights from SFO to NYC",
                    "assign_to": "http://localhost:9001"
                }
            ]
        }
        """
        try:
            body = await request.json()
            
            # Determine mode
            mode = body.get("mode", "comparison")
            
            if mode == "assignment":
                # Assignment mode: use tasks from request
                tasks_input = body.get("tasks", [])
                
                # Support task IDs: if only "id" is provided, look up from SAMPLE_TASKS
                tasks_resolved = []
                for task_spec in tasks_input:
                    if isinstance(task_spec, str):
                        # Just a task ID string - look it up
                        task_id = task_spec
                        sample_task = next((t for t in SAMPLE_TASKS if t["id"] == task_id), None)
                        if sample_task:
                            tasks_resolved.append(sample_task)
                        else:
                            raise ValueError(f"Task ID '{task_id}' not found in SAMPLE_TASKS")
                    elif "task" not in task_spec and "id" in task_spec:
                        # Has ID but no task text - look up from SAMPLE_TASKS
                        task_id = task_spec["id"]
                        sample_task = next((t for t in SAMPLE_TASKS if t["id"] == task_id), None)
                        if sample_task:
                            # Merge with any other fields from task_spec (like assign_to)
                            resolved = sample_task.copy()
                            resolved.update(task_spec)
                            tasks_resolved.append(resolved)
                        else:
                            raise ValueError(f"Task ID '{task_id}' not found in SAMPLE_TASKS")
                    else:
                        # Full task spec provided
                        tasks_resolved.append(task_spec)
                
                assessment_config = {
                    "mode": "assignment",
                    "tasks": tasks_resolved,
                    "white_agent_urls": config.white_agent_urls,  # Default agents
                    "save_trajectories": body.get("save_trajectories", True),
                    "output_dir": body.get("output_dir", "./data/assessment_results"),
                }
            else:
                # Comparison mode (backward compatible)
                white_agent_urls = body.get("white_agent_urls", config.white_agent_urls)
                if "white_agent_url" in body:
                    white_agent_urls = [body["white_agent_url"]]
                if not isinstance(white_agent_urls, list):
                    white_agent_urls = [white_agent_urls]
                
                task_count = min(body.get("task_count", 1), len(SAMPLE_TASKS))

                assessment_config = {
                    "mode": "comparison",
                    "white_agent_urls": white_agent_urls,
                    "tasks": SAMPLE_TASKS[:task_count],
                    "task_count": task_count,
                    "save_trajectories": body.get("save_trajectories", False),
                    "output_dir": body.get("output_dir", "./data/assessment_results"),
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

    def _detect_base_url_from_request(request: Request) -> Optional[str]:
        """
        Detect the public base URL from request headers.
        This is used when the agent is behind a proxy/controller (like AgentBeats controller).
        
        Checks for (in order of priority):
        - X-AgentBeats-URL (set by AgentBeats controller)
        - X-Forwarded-Host (set by reverse proxy)
        - X-Original-Host (set by some proxies)
        - Forwarded header (RFC 7239 standard)
        - Host header (direct request)
        - X-Forwarded-Proto (http/https)
        - X-Forwarded-Port (if non-standard port)
        - CF-Connecting-IP and related Cloudflare headers
        """
        # Debug: Log all relevant headers
        print(f"[GREEN AGENT] URL Detection - Headers received:")
        for header in ['Host', 'X-Forwarded-Host', 'X-Forwarded-Proto', 'X-Forwarded-Port',
                       'X-AgentBeats-URL', 'X-Original-Host', 'Forwarded', 'X-Real-IP',
                       'CF-Connecting-IP', 'X-Forwarded-For']:
            value = request.headers.get(header)
            if value:
                print(f"[GREEN AGENT]   {header}: {value}")
        
        # Priority 1: Check for AgentBeats-specific URL header
        agentbeats_url = request.headers.get("X-AgentBeats-URL")
        if agentbeats_url:
            print(f"[GREEN AGENT] Using X-AgentBeats-URL: {agentbeats_url}")
            return agentbeats_url.rstrip("/")
        
        # Priority 2: Check for forwarded headers (set by controller/proxy)
        forwarded_host = request.headers.get("X-Forwarded-Host") or request.headers.get("X-Original-Host")
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower() or "http"
        forwarded_port = request.headers.get("X-Forwarded-Port")
        
        # Priority 3: Parse RFC 7239 Forwarded header
        forwarded_header = request.headers.get("Forwarded")
        if forwarded_header and not forwarded_host:
            # Parse Forwarded header (e.g., "for=192.0.2.60;proto=https;host=example.com")
            for part in forwarded_header.split(";"):
                part = part.strip()
                if part.lower().startswith("host="):
                    forwarded_host = part[5:].strip('"')
                elif part.lower().startswith("proto="):
                    forwarded_proto = part[6:].strip('"').lower()
        
        if forwarded_host:
            # Handle Cloudflare tunnel URLs (*.trycloudflare.com)
            # These always use HTTPS on port 443
            if "trycloudflare.com" in forwarded_host.lower():
                forwarded_proto = "https"
                forwarded_port = None
            
            # Remove port if included in forwarded_host
            if ":" in forwarded_host:
                host = forwarded_host.split(":")[0]
                embedded_port = forwarded_host.split(":")[1]
            else:
                host = forwarded_host
                embedded_port = None
            
            # Use forwarded port if provided, otherwise use embedded port or default
            port = forwarded_port or embedded_port
            
            # For HTTPS on port 443 or HTTP on port 80, don't include port in URL
            if forwarded_proto == "https" and (port == "443" or port is None):
                base_url = f"https://{host}"
            elif forwarded_proto == "http" and (port == "80" or port is None):
                base_url = f"http://{host}"
            elif port:
                base_url = f"{forwarded_proto}://{host}:{port}"
            else:
                base_url = f"{forwarded_proto}://{host}"
            
            print(f"[GREEN AGENT] Using forwarded URL: {base_url}")
            return base_url.rstrip("/")
        
        # Fallback to Host header if no forwarded headers
        host_header = request.headers.get("Host")
        if host_header:
            # Check if it's a well-known tunnel/cloud URL
            is_tunnel = any(domain in host_header.lower() for domain in [
                "trycloudflare.com", "ngrok.io", "loca.lt", "localtunnel.me",
                "serveo.net", "localhost.run", "cloudflare.com"
            ])
            
            # Check if it includes port
            if ":" in host_header:
                host, port = host_header.split(":", 1)
            else:
                host = host_header
                port = None
            
            # Determine scheme - default to https for tunnel URLs
            scheme = request.url.scheme
            if is_tunnel:
                scheme = "https"
            
            # Build URL
            if (scheme == "https" and port in ["443", None]) or (scheme == "http" and port in ["80", None]):
                base_url = f"{scheme}://{host}"
            elif port:
                base_url = f"{scheme}://{host}:{port}"
            else:
                base_url = f"{scheme}://{host}"
            
            print(f"[GREEN AGENT] Using Host header URL: {base_url}")
            return base_url.rstrip("/")
        
        print("[GREEN AGENT] No URL could be detected from request headers")
        return None

    def _build_agent_card(request: Request = None, agent_id: str = None):
        """
        Construct agent card data with verbose logging.
        
        Args:
            request: The HTTP request (used to detect controller URL)
            agent_id: Optional agent ID for agent-specific URLs
        """
        # Try to detect base URL from request if available
        detected_base_url = None
        if request:
            detected_base_url = _detect_base_url_from_request(request)
        
        # Use detected URL, then config base_url, then fallback to host:port
        base_url_to_use = detected_base_url or config.base_url
        
        print("\n[GREEN AGENT] Building agent card")
        print(f"[GREEN AGENT] host={config.host} port={config.port}")
        print(f"[GREEN AGENT] config.base_url={config.base_url}")
        print(f"[GREEN AGENT] detected_base_url={detected_base_url}")
        print(f"[GREEN AGENT] base_url_to_use={base_url_to_use}")
        print(f"[GREEN AGENT] agent_id={agent_id}")
        
        card = create_agent_card(
            host=config.host,
            port=config.port,
            base_url=base_url_to_use,
            agent_id=agent_id,
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
    async def agent_card_endpoint(request: Request):
        """Serve agent card at standard well-known path."""
        try:
            print("[GREEN AGENT] Agent card request: /.well-known/agent-card.json")
            print(f"[GREEN AGENT] Request headers: Host={request.headers.get('Host')}, X-Forwarded-Host={request.headers.get('X-Forwarded-Host')}")
            data = _build_agent_card(request=request)
            return JSONResponse(data)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse({"error": f"Failed to generate agent card: {str(e)}"}, status_code=500)

    async def agent_card_with_prefix_endpoint(request: Request):
        """
        Serve agent card under to_agent/<agent_id>/.well-known/agent-card.json
        to match AgentBeats expectations.
        """
        try:
            agent_id = request.path_params.get("agent_id", "")
            print(f"[GREEN AGENT] Agent card request with prefix: agent_id={agent_id}")
            print(f"[GREEN AGENT] Request headers: Host={request.headers.get('Host')}, X-Forwarded-Host={request.headers.get('X-Forwarded-Host')}")
            data = _build_agent_card(request=request, agent_id=agent_id)
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
    
    # AGENT_URL is set by the AgentBeats controller - use it as the base URL
    # This is the URL that should appear in the agent card
    agent_url = os.getenv("AGENT_URL")
    if agent_url:
        base_url = agent_url
        print(f"[GREEN AGENT] Using AGENT_URL from controller: {agent_url}")
    
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
