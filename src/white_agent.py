"""
TripMind White Agent - Browser Automation Agent

This is the "participant" agent that executes browser automation tasks.
It receives tasks via A2A protocol and uses browser-use to interact with websites.

Run on port 9001 (local machine).
"""

import os
import json
import uuid
import asyncio
from dataclasses import dataclass
from typing import Any, Optional

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


@dataclass
class WhiteAgentConfig:
    """Configuration for the White Agent."""
    host: str = "0.0.0.0"
    port: int = 9001
    browser_use_api_key: Optional[str] = None
    visible_browser: bool = False


def create_agent_card(host: str, port: int) -> AgentCard:
    """Create the A2A agent card for the white agent."""
    return AgentCard(
        name="TripMind White Agent",
        description=(
            "Browser automation agent that executes web tasks using real-time "
            "browser interaction. Capable of searching flights, hotels, and "
            "navigating travel websites."
        ),
        url=f"http://{host}:{port}",
        version="1.0.0",
        defaultInputModes=["text"],
        defaultOutputModes=["text"],
        capabilities=AgentCapabilities(
            streaming=False,
            pushNotifications=False,
        ),
        skills=[
            AgentSkill(
                id="web-browsing",
                name="Web Browsing",
                description="Navigate websites and interact with web pages",
                tags=["browser", "web", "automation"],
            ),
            AgentSkill(
                id="flight-search",
                name="Flight Search",
                description="Search for flights on Google Flights, Kayak, etc.",
                tags=["flights", "travel", "search"],
            ),
            AgentSkill(
                id="hotel-search",
                name="Hotel Search",
                description="Search for hotels on Booking.com, Hotels.com, etc.",
                tags=["hotels", "travel", "search"],
            ),
        ],
    )


class WhiteAgentExecutor(AgentExecutor):
    """Executor that handles browser automation tasks."""

    def __init__(self, config: WhiteAgentConfig):
        self.config = config

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """Execute a browser automation task."""
        # Extract task text from the request
        task_text = None
        if context.message and context.message.parts:
            for part in context.message.parts:
                if hasattr(part, 'root') and hasattr(part.root, 'text'):
                    task_text = part.root.text
                    break
                elif hasattr(part, 'text'):
                    task_text = part.text
                    break

        if not task_text:
            await self._send_error_response(event_queue, context, "No task text provided")
            return

        print(f"\n{'='*60}")
        print(f"[WHITE AGENT] Received task:")
        print(f"{task_text[:200]}...")
        print(f"{'='*60}\n")

        try:
            # Execute browser task
            result = await self._execute_browser_task(task_text)
            await self._send_success_response(event_queue, context, result)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await self._send_error_response(event_queue, context, str(e))

    async def _execute_browser_task(self, task_text: str) -> str:
        """Execute a browser automation task using browser-use."""
        api_key = self.config.browser_use_api_key or os.getenv("BROWSER_USE_API_KEY")

        if not api_key:
            return json.dumps({
                "task": task_text,
                "action_history": [],
                "final_result_response": "ERROR: BROWSER_USE_API_KEY not configured",
                "status": "failed"
            })

        try:
            from browser_use import Agent, Browser, ChatBrowserUse

            print(f"[WHITE AGENT] Starting browser-use for task: {task_text[:100]}...")

            # Create LLM (browser-use cloud)
            llm = ChatBrowserUse()

            # Use cloud browser for better stealth
            browser = Browser(use_cloud=True)

            # Create and run agent
            agent = Agent(task=task_text, llm=llm, browser=browser)
            history = await agent.run()

            # Extract results
            result = self._extract_result(history, task_text)

            print(f"[WHITE AGENT] Task completed. Result length: {len(result)} chars")
            return result

        except Exception as e:
            import traceback
            traceback.print_exc()
            return json.dumps({
                "task": task_text,
                "action_history": [],
                "final_result_response": f"Error: {str(e)}",
                "status": "failed"
            })

    def _extract_result(self, history: Any, original_task: str) -> str:
        """Extract structured result from browser-use history."""
        try:
            items = []

            if hasattr(history, 'all_results'):
                items = history.all_results
            elif hasattr(history, 'model_dump'):
                history_dict = history.model_dump()
                items = history_dict.get('all_results', [])

            actions = []
            final_result = None

            for item in items:
                # Extract action description
                action_desc = None
                if hasattr(item, 'long_term_memory') and item.long_term_memory:
                    action_desc = item.long_term_memory
                elif hasattr(item, 'extracted_content') and item.extracted_content:
                    action_desc = item.extracted_content
                elif isinstance(item, dict):
                    action_desc = item.get('long_term_memory') or item.get('extracted_content')

                if action_desc and len(str(action_desc)) < 500:
                    actions.append(str(action_desc))

                # Check for completion
                is_done = False
                if hasattr(item, 'is_done'):
                    is_done = item.is_done
                elif isinstance(item, dict):
                    is_done = item.get('is_done', False)

                if is_done:
                    final_result = action_desc

            result_data = {
                "task": original_task,
                "action_history": actions[-50:] if actions else [],
                "final_result_response": final_result or "Task execution completed.",
                "status": "completed"
            }

            return json.dumps(result_data, indent=2)

        except Exception as e:
            return json.dumps({
                "task": original_task,
                "action_history": [],
                "final_result_response": f"Error extracting results: {str(e)}",
                "status": "failed"
            })

    async def _send_success_response(
        self,
        event_queue: EventQueue,
        context: RequestContext,
        result: str
    ) -> None:
        """Send successful response."""
        message = Message(
            role="agent",
            parts=[Part(root=TextPart(text=result))],
            messageId=str(uuid.uuid4()),
            contextId=context.context_id,
            taskId=context.task_id,
        )
        await event_queue.enqueue_event(message)

    async def _send_error_response(
        self,
        event_queue: EventQueue,
        context: RequestContext,
        error_msg: str
    ) -> None:
        """Send error response."""
        error_data = {
            "task": "",
            "action_history": [],
            "final_result_response": f"ERROR: {error_msg}",
            "status": "failed"
        }
        message = Message(
            role="agent",
            parts=[Part(root=TextPart(text=json.dumps(error_data)))],
            messageId=str(uuid.uuid4()),
            contextId=context.context_id,
            taskId=context.task_id,
        )
        await event_queue.enqueue_event(message)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Handle task cancellation."""
        raise ServerError(error={"message": "Task cancellation not supported"})


def create_app(config: WhiteAgentConfig):
    """Create the Starlette application."""
    from starlette.responses import JSONResponse
    from starlette.routing import Route
    from starlette.requests import Request

    agent_card = create_agent_card(config.host, config.port)
    executor = WhiteAgentExecutor(config)

    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    a2a_app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    app = a2a_app.build()

    # Add status endpoint
    async def status_endpoint(request):
        return JSONResponse({
            "status": "ok",
            "name": "TripMind White Agent",
            "version": "1.0.0",
            "type": "white_agent",
            "capabilities": ["web-browsing", "flight-search", "hotel-search"]
        })

    # Add health endpoint
    async def health_endpoint(request):
        return JSONResponse({"healthy": True})

    # Add direct execute endpoint (for green agent fallback)
    async def execute_endpoint(request: Request):
        """
        Direct task execution endpoint.

        POST /execute
        Body: {"task": "Find flights from NYC to SFO"}
        """
        try:
            body = await request.json()
            task_text = body.get("task")

            if not task_text:
                return JSONResponse(
                    {"error": "Missing 'task' field"},
                    status_code=400
                )

            print(f"\n[WHITE AGENT /execute] Task: {task_text[:100]}...")

            # Execute the task
            result_json = await executor._execute_browser_task(task_text)

            # Parse and return
            try:
                result_data = json.loads(result_json)
            except json.JSONDecodeError:
                result_data = {
                    "task": task_text,
                    "action_history": [],
                    "final_result_response": result_json,
                    "status": "completed"
                }

            return JSONResponse(result_data)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JSONResponse({
                "task": body.get("task", "") if 'body' in dir() else "",
                "action_history": [],
                "final_result_response": f"Error: {str(e)}",
                "status": "failed"
            }, status_code=500)

    app.routes.insert(0, Route("/status", status_endpoint, methods=["GET"]))
    app.routes.insert(0, Route("/health", health_endpoint, methods=["GET"]))
    app.routes.insert(0, Route("/execute", execute_endpoint, methods=["POST"]))

    return app


def start_white_agent(
    host: str = None,
    port: int = None,
    visible: bool = False,
):
    """Start the White Agent server."""
    config = WhiteAgentConfig(
        host=host or os.getenv("HOST", "0.0.0.0"),
        port=int(port or os.getenv("WHITE_AGENT_PORT", "9001")),
        browser_use_api_key=os.getenv("BROWSER_USE_API_KEY"),
        visible_browser=visible,
    )

    print(f"\n{'='*60}")
    print(f"  TripMind WHITE AGENT (Browser Automation)")
    print(f"{'='*60}")
    print(f"  Host: {config.host}")
    print(f"  Port: {config.port}")
    print(f"  Browser-Use API Key: {'[SET]' if config.browser_use_api_key else '[NOT SET]'}")
    print(f"  Visible Browser: {config.visible_browser}")
    print(f"{'='*60}")
    print(f"  Agent Card: http://{config.host}:{config.port}/.well-known/agent-card.json")
    print(f"  Status: http://{config.host}:{config.port}/status")
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

    parser = argparse.ArgumentParser(description="TripMind White Agent")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=9001)
    parser.add_argument("--visible", action="store_true")

    args = parser.parse_args()
    start_white_agent(host=args.host, port=args.port, visible=args.visible)
