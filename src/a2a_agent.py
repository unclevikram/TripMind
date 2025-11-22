"""
TripMind A2A-Compatible White Agent

This module implements an A2A (Agent-to-Agent) protocol compatible agent
that wraps the browser-use functionality for the AgentBeats platform.

The agent can receive travel-related tasks (flights, hotels, itineraries)
and execute them using browser automation via browser-use cloud.
"""

import os
import json
import asyncio
import uuid
from typing import Any, Dict, Optional
from dataclasses import dataclass

# A2A SDK imports
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Part,
    TextPart,
    Message,
)
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.utils.errors import ServerError

import uvicorn


@dataclass
class TripMindAgentConfig:
    """Configuration for the TripMind agent."""
    host: str = "0.0.0.0"
    port: int = 9002
    base_url: Optional[str] = None  # Public URL for cloud deployments
    browser_use_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    visible_browser: bool = False


def create_agent_card(host: str, port: int, base_url: str = None) -> AgentCard:
    """Create the A2A agent card describing this agent's capabilities."""
    # Use BASE_URL env var if set (for cloud deployments), otherwise construct from host:port
    if base_url:
        agent_url = base_url
    else:
        agent_url = f"http://{host}:{port}"

    return AgentCard(
        name="TripMind Travel Agent",
        description=(
            "An AI-powered travel assistant that can search for flights, "
            "find hotels, and create travel itineraries using real-time "
            "web browsing capabilities."
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
                id="flight_search",
                name="Flight Search",
                description=(
                    "Search for flights between cities. Can find round-trip "
                    "or one-way flights with specific dates and preferences."
                ),
                tags=["travel", "flights", "booking"],
                examples=[
                    "Find a round-trip flight from NYC to SFO next month",
                    "Search for cheap flights from Los Angeles to Tokyo",
                ],
            ),
            AgentSkill(
                id="hotel_search",
                name="Hotel Search",
                description=(
                    "Search for hotel accommodations. Can filter by location, "
                    "dates, price range, amenities, and star rating."
                ),
                tags=["travel", "hotels", "accommodation"],
                examples=[
                    "Find a hotel in Seattle for 2 nights with free WiFi",
                    "Search for 4-star hotels in Paris under $200/night",
                ],
            ),
            AgentSkill(
                id="itinerary_creation",
                name="Itinerary Creation",
                description=(
                    "Create travel itineraries including activities, "
                    "restaurants, and attractions for a destination."
                ),
                tags=["travel", "planning", "itinerary"],
                examples=[
                    "Plan a 3-day trip to San Francisco",
                    "Create an itinerary for a weekend in New York",
                ],
            ),
        ],
    )


class TripMindAgentExecutor(AgentExecutor):
    """
    Executor for the TripMind agent that handles incoming A2A tasks.

    This executor receives task messages, processes them using browser-use
    for web automation, and returns the results.
    """

    def __init__(self, config: TripMindAgentConfig):
        self.config = config
        self.conversation_history: Dict[str, list] = {}

    async def execute(
        self,
        context: RequestContext,
        event_queue: EventQueue,
    ) -> None:
        """
        Execute an incoming task request.

        Args:
            context: The request context containing the task/message
            event_queue: Queue for sending response events
        """
        try:
            # Extract the task text from the request
            task_text = self._extract_task_text(context)

            if not task_text:
                await self._send_error_response(
                    event_queue,
                    context,
                    "No task text provided in the request."
                )
                return

            print(f"\n{'='*60}")
            print(f"Received task: {task_text[:200]}...")
            print(f"{'='*60}\n")

            # Get or create conversation context
            context_id = context.context_id or str(uuid.uuid4())
            if context_id not in self.conversation_history:
                self.conversation_history[context_id] = []

            # Add user message to history
            self.conversation_history[context_id].append({
                "role": "user",
                "content": task_text
            })

            # Execute the task using browser-use
            result = await self._execute_browser_task(task_text)

            # Add assistant response to history
            self.conversation_history[context_id].append({
                "role": "assistant",
                "content": result
            })

            # Send the response
            await self._send_success_response(event_queue, context, result)

        except Exception as e:
            import traceback
            error_msg = f"Error executing task: {str(e)}"
            print(f"ERROR: {error_msg}")
            traceback.print_exc()
            await self._send_error_response(event_queue, context, error_msg)

    def _extract_task_text(self, context: RequestContext) -> Optional[str]:
        """Extract the task text from the request context."""
        # Get message from context
        message = context.message

        if message and hasattr(message, 'parts'):
            for part in message.parts:
                # Handle Part wrapper
                if hasattr(part, 'root') and hasattr(part.root, 'text'):
                    return part.root.text
                # Handle direct TextPart
                elif hasattr(part, 'text'):
                    return part.text

        # Try to get from current task
        if context.current_task:
            task = context.current_task
            if hasattr(task, 'history') and task.history:
                # Get the last user message from history
                for msg in reversed(task.history):
                    if hasattr(msg, 'role') and str(msg.role) == 'user':
                        if hasattr(msg, 'parts'):
                            for part in msg.parts:
                                if hasattr(part, 'root') and hasattr(part.root, 'text'):
                                    return part.root.text
                                elif hasattr(part, 'text'):
                                    return part.text

        return None

    async def _execute_browser_task(self, task_text: str) -> str:
        """
        Execute a browser automation task using browser-use.

        Args:
            task_text: The task description to execute

        Returns:
            The result of the task execution
        """
        # Check for API key
        api_key = self.config.browser_use_api_key or os.getenv("BROWSER_USE_API_KEY")

        if not api_key:
            return (
                "ERROR: BROWSER_USE_API_KEY is not configured. "
                "Please set the BROWSER_USE_API_KEY environment variable "
                "to use browser automation features."
            )

        try:
            # Import browser-use components
            from browser_use import Agent, Browser, ChatBrowserUse

            print(f"Starting browser-use agent for task: {task_text[:100]}...")

            # Create browser and LLM
            browser = Browser(headless=not self.config.visible_browser)
            llm = ChatBrowserUse()

            # Augment task for better handling
            augmented_task = self._augment_task(task_text)

            # Create and run agent
            agent = Agent(task=augmented_task, llm=llm, browser=browser)
            history = await agent.run()

            # Extract results from history
            result = self._extract_result_from_history(history, task_text)

            print(f"Task completed. Result length: {len(result)} chars")
            return result

        except ImportError as e:
            return f"ERROR: Failed to import browser-use: {str(e)}"
        except Exception as e:
            import traceback
            return f"ERROR: Task execution failed: {str(e)}\n{traceback.format_exc()}"

    def _augment_task(self, task: str) -> str:
        """Add guidance to the task for better execution."""
        lowered = task.lower()

        # Flight-related tasks
        if any(t in lowered for t in ["flight", "round-trip", "one-way", "airline"]):
            guidance = """
When searching for flights:
- Navigate to a flight search website (Google Flights, Kayak, etc.)
- Clear any pre-filled fields before entering new data
- Enter the exact origin and destination specified
- Select the correct dates
- Click search and wait for results
- Report the top flight options found
"""
            return f"{task}\n\nExecution guidance:{guidance}"

        # Hotel-related tasks
        if any(t in lowered for t in ["hotel", "accommodation", "stay", "booking"]):
            guidance = """
When searching for hotels:
- Navigate to a hotel booking site (Booking.com, Hotels.com, etc.)
- Enter the exact location specified
- Set the correct check-in and check-out dates
- Apply any mentioned filters (price, amenities, rating)
- Report the top hotel options found
"""
            return f"{task}\n\nExecution guidance:{guidance}"

        # Itinerary tasks
        if any(t in lowered for t in ["itinerary", "plan", "trip", "visit"]):
            guidance = """
When creating an itinerary:
- Research top attractions and activities for the destination
- Organize activities by day
- Include practical information (hours, prices, locations)
- Suggest restaurants and dining options
- Provide a complete day-by-day plan
"""
            return f"{task}\n\nExecution guidance:{guidance}"

        return task

    def _extract_result_from_history(self, history: Any, original_task: str) -> str:
        """Extract a meaningful result from the browser-use history."""
        try:
            # Try to get results from history
            items = []

            if hasattr(history, 'all_results'):
                items = history.all_results
            elif hasattr(history, 'model_dump'):
                history_dict = history.model_dump()
                items = history_dict.get('all_results', [])

            # Collect action descriptions and final result
            actions = []
            final_result = None

            for item in items:
                # Get action description
                action_desc = None
                if hasattr(item, 'long_term_memory') and item.long_term_memory:
                    action_desc = item.long_term_memory
                elif hasattr(item, 'extracted_content') and item.extracted_content:
                    action_desc = item.extracted_content
                elif isinstance(item, dict):
                    action_desc = item.get('long_term_memory') or item.get('extracted_content')

                if action_desc and len(str(action_desc)) < 500:
                    actions.append(str(action_desc))

                # Check for final result
                is_done = False
                if hasattr(item, 'is_done'):
                    is_done = item.is_done
                elif isinstance(item, dict):
                    is_done = item.get('is_done', False)

                if is_done:
                    final_result = action_desc

            # Construct result message
            result_parts = [f"Task: {original_task}\n"]

            if actions:
                result_parts.append("Actions taken:")
                for i, action in enumerate(actions[-10:], 1):  # Last 10 actions
                    result_parts.append(f"  {i}. {action}")

            if final_result:
                result_parts.append(f"\nFinal Result: {final_result}")
            else:
                result_parts.append("\nTask execution completed.")

            return "\n".join(result_parts)

        except Exception as e:
            return f"Task completed but could not extract detailed results: {str(e)}"

    async def _send_success_response(
        self,
        event_queue: EventQueue,
        context: RequestContext,
        result: str
    ) -> None:
        """Send a successful response through the event queue."""
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
        """Send an error response through the event queue."""
        message = Message(
            role="agent",
            parts=[Part(root=TextPart(text=f"ERROR: {error_msg}"))],
            messageId=str(uuid.uuid4()),
            contextId=context.context_id,
            taskId=context.task_id,
        )

        await event_queue.enqueue_event(message)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Handle task cancellation."""
        print(f"Task cancellation requested")
        raise ServerError(error={"message": "Task cancellation not supported"})


def create_app(config: TripMindAgentConfig):
    """Create the Starlette application with A2A and custom endpoints."""
    from starlette.responses import JSONResponse
    from starlette.routing import Route

    # Create agent card
    agent_card = create_agent_card(config.host, config.port, config.base_url)

    # Create executor
    executor = TripMindAgentExecutor(config)

    # Create request handler
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )

    # Create the A2A application
    a2a_app = A2AStarletteApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )

    # Build the app
    app = a2a_app.build()

    # Add status endpoint for health checks
    async def status_endpoint(request):
        return JSONResponse({
            "status": "ok",
            "name": "TripMind Travel Agent",
            "version": "1.0.0",
        })

    # Add health endpoint
    async def health_endpoint(request):
        return JSONResponse({"healthy": True})

    # Insert routes at the beginning
    app.routes.insert(0, Route("/status", status_endpoint, methods=["GET"]))
    app.routes.insert(0, Route("/health", health_endpoint, methods=["GET"]))

    # Return the built app directly (not the A2AStarletteApplication)
    return app


def start_agent(
    host: str = None,
    port: int = None,
    browser_use_api_key: str = None,
    visible: bool = False,
):
    """
    Start the TripMind A2A agent server.

    Args:
        host: Host to bind to (default: from $HOST or 0.0.0.0)
        port: Port to listen on (default: from $AGENT_PORT or 9002)
        browser_use_api_key: Browser-Use API key (default: from env)
        visible: Whether to show browser window (default: False)
    """
    # Get configuration from environment or parameters
    # BASE_URL should be set for cloud deployments (e.g., https://tripmind-agent.up.railway.app)
    config = TripMindAgentConfig(
        host=host or os.getenv("HOST", "0.0.0.0"),
        port=int(port or os.getenv("PORT", os.getenv("AGENT_PORT", "9002"))),
        base_url=os.getenv("BASE_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN"),
        browser_use_api_key=browser_use_api_key or os.getenv("BROWSER_USE_API_KEY"),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        visible_browser=visible,
    )

    # Auto-detect Railway public domain if available
    if not config.base_url:
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")
        if railway_domain:
            config.base_url = f"https://{railway_domain}"

    print(f"\n{'='*60}")
    print(f"  TripMind A2A Agent")
    print(f"{'='*60}")
    print(f"  Host: {config.host}")
    print(f"  Port: {config.port}")
    print(f"  Base URL: {config.base_url or 'Not set (using host:port)'}")
    print(f"  Browser-Use API Key: {'[SET]' if config.browser_use_api_key else '[NOT SET]'}")
    print(f"  OpenAI API Key: {'[SET]' if config.openai_api_key else '[NOT SET]'}")
    print(f"  Visible Browser: {config.visible_browser}")
    print(f"{'='*60}")
    if config.base_url:
        print(f"  Agent Card URL: {config.base_url}/.well-known/agent-card.json")
    else:
        print(f"  Agent Card URL: http://{config.host}:{config.port}/.well-known/agent-card.json")
    print(f"{'='*60}\n")

    # Create and run the application
    app = create_app(config)

    uvicorn.run(
        app,  # app is already built with custom routes
        host=config.host,
        port=config.port,
        log_level="info",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start the TripMind A2A Agent")
    parser.add_argument("--host", type=str, default=None, help="Host to bind to")
    parser.add_argument("--port", type=int, default=None, help="Port to listen on")
    parser.add_argument("--visible", action="store_true", help="Show browser window")

    args = parser.parse_args()

    start_agent(
        host=args.host,
        port=args.port,
        visible=args.visible,
    )
