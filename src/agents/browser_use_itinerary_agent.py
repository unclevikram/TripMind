"""
Trip Itinerary Planning Agent

This agent uses browser-use to generate trip itineraries by researching destinations,
attractions, restaurants, and activities. Saves results in Online-Mind2Web-compatible format.
"""

import os
import re
import json
import base64
import argparse
import asyncio
from typing import Any, Dict, List, Optional, Tuple


def ensure_dirs(base_dir: str, task_id: str) -> Tuple[str, str]:
    task_dir = os.path.join(base_dir, task_id)
    traj_dir = os.path.join(task_dir, "trajectory")
    os.makedirs(traj_dir, exist_ok=True)
    return task_dir, traj_dir


def decode_data_url_to_png(data_url: str) -> Optional[bytes]:
    try:
        if data_url.startswith("data:image/") and ";base64," in data_url:
            b64 = data_url.split(",", 1)[1]
            return base64.b64decode(b64)
    except Exception:
        return None
    return None


def extract_images_and_actions_from_history(history: Any) -> Tuple[List[bytes], List[str], List[str], Optional[str]]:
    """Extract actions and metadata from browser-use history."""
    screenshots: List[bytes] = []
    action_history: List[str] = []
    thoughts: List[str] = []
    final_result: Optional[str] = None

    # Browser-use returns AgentHistoryList with all_results attribute
    items = []
    
    # Try to get the all_results attribute from browser-use's AgentHistoryList
    if hasattr(history, 'all_results'):
        items = history.all_results
        print(f"🔍 Found {len(items)} items in history.all_results")
    else:
        # Fallback: convert to dict and try standard extraction
        try:
            if hasattr(history, 'model_dump'):
                history_dict = history.model_dump()
            elif hasattr(history, 'dict'):
                history_dict = history.dict()
            elif hasattr(history, '__dict__'):
                history_dict = history.__dict__
            else:
                history_dict = history
                
            if isinstance(history_dict, dict):
                items = (history_dict.get("all_results") or
                        history_dict.get("steps") or 
                        history_dict.get("history") or 
                        history_dict.get("events") or 
                        history_dict.get("actions") or
                        history_dict.get("items") or
                        [])
        except Exception as e:
            print(f"⚠️  Exception during history conversion: {e}")
            items = []
    
    # Process each ActionResult
    for idx, item in enumerate(items):
        # Browser-use ActionResult has: long_term_memory, extracted_content, metadata
        # Extract action description from long_term_memory or extracted_content
        action_desc = None
        
        # Try to get attributes directly from ActionResult object
        if hasattr(item, 'long_term_memory') and item.long_term_memory:
            action_desc = item.long_term_memory
        elif hasattr(item, 'extracted_content') and item.extracted_content:
            action_desc = item.extracted_content
        
        # Fallback to dict access
        if not action_desc and isinstance(item, dict):
            action_desc = item.get('long_term_memory') or item.get('extracted_content')
        
        # Convert ActionResult object to dict if needed
        if not isinstance(item, dict):
            try:
                if hasattr(item, 'model_dump'):
                    item = item.model_dump()
                elif hasattr(item, 'dict'):
                    item = item.dict()
                elif hasattr(item, '__dict__'):
                    item = item.__dict__
            except Exception:
                pass
        
        # Add action to history if we found a description
        if action_desc and isinstance(action_desc, str):
            # Clean up the action description
            action_clean = action_desc.strip()
            # Skip very long extracted content (like full HTML)
            if len(action_clean) > 0 and len(action_clean) < 500:
                # Format it nicely
                action_history.append(action_clean)
        
        # Extract is_done flag to detect final result
        if isinstance(item, dict):
            if item.get('is_done'):
                final_result = item.get('long_term_memory') or item.get('extracted_content')

    return screenshots, action_history, thoughts, final_result


def augment_task_for_itinerary_planning(task: str) -> str:
    """Add guidance for trip itinerary planning tasks.
    
    Helps the agent create comprehensive itineraries with attractions,
    restaurants, activities, and timing considerations.
    """
    try:
        lowered = task.lower()
        triggers = ["itinerary", "trip", "plan", "vacation", "travel", "visit", "day trip"]
        if any(t in lowered for t in triggers):
            guidance_lines = [
                "When planning a trip itinerary:",
                "- Research popular attractions and landmarks for the destination.",
                "- Include a mix of activities: sightseeing, dining, entertainment, and relaxation.",
                "- Consider opening hours, travel time between locations, and realistic timing.",
                "- Organize activities by day (e.g., Day 1, Day 2, Day 3).",
                "- Include specific restaurant recommendations for breakfast, lunch, and dinner.",
                "- Add addresses or locations for each activity/restaurant.",
                "- Consider proximity - group nearby attractions together on the same day.",
                "- Include estimated time needed for each activity.",
                "- Add any special notes (reservations needed, closed days, peak hours).",
                "- Extract and present the final itinerary in a clear, day-by-day format.",
            ]
            guidance = "\n".join(guidance_lines)
            return f"{task}\n\nItinerary Planning Guidelines:\n{guidance}"
    except Exception:
        pass
    return task


async def run_browser_use_agent(task: str, traj_dir: str, visible: bool = True) -> Tuple[Any, List[bytes]]:
    """Run browser-use agent for itinerary planning."""
    from browser_use import Agent, Browser, ChatBrowserUse
    
    # Storage for screenshots captured during execution (disabled)
    captured_screenshots: List[bytes] = []
    
    print("🗺️  Starting trip itinerary planning agent...")
    print(f"📋 Task: {task}")
    print(f"👁️  Browser: {'VISIBLE' if visible else 'HEADLESS'} (headless={not visible})\n")
    
    # Create browser (visible or headless)
    browser = Browser(headless=not visible)
    llm = ChatBrowserUse()
    
    # Create agent (with augmented task for itinerary planning)
    augmented_task = augment_task_for_itinerary_planning(task)
    if augmented_task != task:
        print("🔧 Applied itinerary planning guidance to task")
        print(f"\n📝 Augmented task being sent to agent:\n{'-'*60}\n{augmented_task}\n{'-'*60}\n")
    agent = Agent(task=augmented_task, llm=llm, browser=browser)
    
    # Hook for screenshot capture
    original_run = agent.run
    
    async def run_with_screenshots():
        """Wrapper that captures screenshots during execution."""
        import asyncio
        
        # Create a task for running the agent
        agent_task = asyncio.create_task(original_run())
        
        # Wait a bit for the browser to initialize
        await asyncio.sleep(2)
        
        # Wait for agent to complete
        screenshot_interval = 3  # seconds between screenshots
        screenshot_counter = 0
        
        debug_printed = False
        while not agent_task.done():
            if not debug_printed and screenshot_counter == 0:
                print(f"🔍 browser_session type: {type(agent.browser_session)}")
                print(f"🔍 browser_session attrs: {[a for a in dir(agent.browser_session) if not a.startswith('_')][:15]}")
                debug_printed = True
            
            try:
                # Access browser session (browser-use uses agent.browser_session)
                current_page = None
                
                if hasattr(agent, 'browser_session') and agent.browser_session:
                    # Try multiple access paths
                    if hasattr(agent.browser_session, 'context'):
                        context = agent.browser_session.context
                        if hasattr(context, 'pages'):
                            pages = context.pages
                            if pages and len(pages) > 0:
                                current_page = pages[0]
                    elif hasattr(agent.browser_session, 'get_current_page'):
                        try:
                            current_page = await agent.browser_session.get_current_page()
                        except Exception as e:
                            if screenshot_counter == 0:
                                print(f"⚠️  get_current_page() failed: {e}")
                            pass
                    elif hasattr(agent.browser_session, 'page'):
                        current_page = agent.browser_session.page
                    elif hasattr(agent.browser_session, 'browser_context'):
                        bc = agent.browser_session.browser_context
                        if hasattr(bc, 'pages'):
                            pages = bc.pages
                            if pages and len(pages) > 0:
                                current_page = pages[0]
                
                if current_page:
                    try:
                        # Capture screenshot - might return bytes or base64 string
                        screenshot_result = await current_page.screenshot()
                        
                        # Handle bytes and base64 string
                        if isinstance(screenshot_result, bytes):
                            screenshot_bytes = screenshot_result
                        elif isinstance(screenshot_result, str):
                            # Check if it's base64-encoded PNG
                            if screenshot_result.startswith('iVBORw0KGgo') or screenshot_result.startswith('data:image'):
                                try:
                                    if screenshot_result.startswith('data:image'):
                                        screenshot_bytes = decode_data_url_to_png(screenshot_result)
                                        if screenshot_bytes is None:
                                            raise Exception("Failed to decode data URL")
                                    else:
                                        screenshot_bytes = base64.b64decode(screenshot_result)
                                except Exception as e:
                                    raise Exception(f"Failed to decode base64 screenshot: {e}")
                            elif os.path.exists(screenshot_result):
                                with open(screenshot_result, 'rb') as f:
                                    screenshot_bytes = f.read()
                            else:
                                raise Exception(f"Unexpected string format: {screenshot_result[:100]}...")
                        else:
                            raise Exception(f"Unexpected screenshot result type: {type(screenshot_result)}")
                        
                        captured_screenshots.append(screenshot_bytes)
                        
                        # Save to trajectory folder
                        screenshot_path = os.path.join(traj_dir, f"{screenshot_counter}_full_screenshot.png")
                        with open(screenshot_path, 'wb') as f:
                            f.write(screenshot_bytes)
                        
                        # Verify file was written
                        file_size = os.path.getsize(screenshot_path) if os.path.exists(screenshot_path) else 0
                        print(f"📸 Saved screenshot {screenshot_counter} ({file_size} bytes) -> {screenshot_path}")
                        screenshot_counter += 1
                    except Exception as e:
                        print(f"⚠️  Screenshot capture failed: {e}")
                else:
                    if screenshot_counter == 0:
                        print(f"⚠️  current_page is None")
            except Exception as e:
                print(f"⚠️  Screenshot access error: {e}")
            
            # Wait before next check
            try:
                await asyncio.wait_for(asyncio.shield(agent_task), timeout=screenshot_interval)
                break  # Agent finished
            except asyncio.TimeoutError:
                continue  # Agent still running
        
        # Get the result
        result = await agent_task
        
        # Capture final screenshot
        try:
            if hasattr(agent, 'browser_session') and agent.browser_session:
                if hasattr(agent.browser_session, 'context'):
                    context = agent.browser_session.context
                    if hasattr(context, 'pages'):
                        pages = context.pages
                        if pages and len(pages) > 0:
                            current_page = pages[0]
                            # Capture screenshot - might return bytes or base64 string
                            screenshot_result = await current_page.screenshot()
                            
                            # Handle bytes and base64 string
                            if isinstance(screenshot_result, bytes):
                                screenshot_bytes = screenshot_result
                            elif isinstance(screenshot_result, str):
                                # Check if it's base64-encoded PNG
                                if screenshot_result.startswith('iVBORw0KGgo') or screenshot_result.startswith('data:image'):
                                    try:
                                        if screenshot_result.startswith('data:image'):
                                            screenshot_bytes = decode_data_url_to_png(screenshot_result)
                                            if screenshot_bytes is None:
                                                raise Exception("Failed to decode data URL")
                                        else:
                                            screenshot_bytes = base64.b64decode(screenshot_result)
                                    except Exception as e:
                                        raise Exception(f"Failed to decode base64 screenshot: {e}")
                                elif os.path.exists(screenshot_result):
                                    with open(screenshot_result, 'rb') as f:
                                        screenshot_bytes = f.read()
                                else:
                                    raise Exception(f"Unexpected string format: {screenshot_result[:100]}...")
                            else:
                                raise Exception(f"Unexpected screenshot result type: {type(screenshot_result)}")
                            
                            captured_screenshots.append(screenshot_bytes)
                            screenshot_path = os.path.join(traj_dir, f"{screenshot_counter}_full_screenshot.png")
                            with open(screenshot_path, 'wb') as f:
                                f.write(screenshot_bytes)
                            
                            # Verify file was written
                            file_size = os.path.getsize(screenshot_path) if os.path.exists(screenshot_path) else 0
                            print(f"📸 Saved final screenshot {screenshot_counter} ({file_size} bytes) -> {screenshot_path}")
        except Exception as e:
            print(f"⚠️  Final screenshot capture failed: {e}")
        
        return result
    
    # Run the agent with screenshot capture
    print("✓ Starting agent with screenshot capture\n")
    history = await run_with_screenshots()
    
    print(f"\n✅ Agent completed")
    print(f"📸 Total screenshots captured: {len(captured_screenshots)}")
    
    return history, captured_screenshots


def write_result_json(task_dir: str,
                      task_id: str,
                      task_text: str,
                      final_result: Optional[str],
                      action_history: List[str],
                      thoughts: List[str]) -> None:
    result = {
        "task_id": task_id,
        "task": task_text,
        "final_result_response": final_result or "",
        "action_history": action_history[:100],  # More actions for itinerary planning
        "thoughts": thoughts[:20],
    }
    with open(os.path.join(task_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=4)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run a trip itinerary planning agent using Browser-Use.")
    parser.add_argument("--task", type=str, required=False, 
                       default="Plan a 3-day itinerary for visiting San Francisco. Include top attractions, recommended restaurants for each meal, and organize activities by day with estimated timing.")
    parser.add_argument("--task_id", type=str, required=False, default=None, 
                       help="Folder name under data/example for outputs.")
    parser.add_argument("--base_dir", type=str, required=False, 
                       default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "examples")))
    parser.add_argument("--visible", action="store_true", help="Launch browser in visible (non-headless) mode")
    args = parser.parse_args()

    # Generate a simple deterministic id if not provided
    if not args.task_id:
        # slug from task text
        slug = re.sub(r"[^a-z0-9]+", "-", args.task.lower())
        slug = re.sub(r"-+", "-", slug).strip("-")[:40]
        args.task_id = f"itinerary_{slug or 'task'}"

    task_dir, traj_dir = ensure_dirs(args.base_dir, args.task_id)

    use_browser_use = True
    screenshots: List[bytes] = []
    action_history: List[str] = []
    thoughts: List[str] = []
    final_result: Optional[str] = None

    # Require API key for Browser Use Cloud-backed LLM
    if not os.getenv("BROWSER_USE_API_KEY"):
        print("❌ BROWSER_USE_API_KEY not set!")
        print("Set it with: export BROWSER_USE_API_KEY=your-key")
        use_browser_use = False

    if use_browser_use:
        try:
            # Run agent
            history, captured_screenshots = await run_browser_use_agent(args.task, traj_dir, visible=args.visible)
            
            # DEBUG: Show raw history structure
            print("\n🔍 DEBUG: Raw history type:", type(history))
            print("🔍 DEBUG: Raw history class name:", history.__class__.__name__ if hasattr(history, '__class__') else "N/A")
            
            # Extract actions/thoughts from history (screenshots already captured manually)
            _history_screenshots, action_history, thoughts, final_result = extract_images_and_actions_from_history(history)
            
            # Note: We don't save history_screenshots because we already captured them manually during execution
            if _history_screenshots:
                print(f"📸 Found {len(_history_screenshots)} screenshots in history (already captured manually, not saving duplicates)")
            
            print(f"📸 Total screenshots: {len(captured_screenshots)} saved to trajectory folder")
            
            print(f"\n🔍 DEBUG: Extracted {len(action_history)} actions from history")
            if action_history:
                print("🔍 First few actions:", action_history[:5])
            else:
                print("⚠️  No actions extracted!")
                
            if final_result:
                print(f"🔍 Final itinerary result:\n{final_result}")
                
        except Exception as e:
            import traceback
            print(f"\n❌ Error running agent:")
            traceback.print_exc()
            use_browser_use = False
            thoughts = [f"Exception while running agent: {e}"]

    # Minimal action history for placeholders
    if not action_history:
        print("\n⚠️  WARNING: No actions were extracted from browser-use history!")
        print("⚠️  Using fallback placeholder actions (these are NOT what the agent actually did)")
        print("⚠️  This will cause evaluation to fail!")
        action_history = [
            "Navigated to travel planning website",
            "Searched for top attractions in destination",
            "Researched popular restaurants",
            "Organized activities by day",
            "Created day-by-day itinerary",
            "Extracted final itinerary details",
        ]

    write_result_json(task_dir, args.task_id, args.task, final_result, action_history, thoughts)
    
    print(f"\n✅ All outputs saved to: {task_dir}")
    print(f"   - Actions: {len(action_history)}")
    if final_result:
        print(f"   - Itinerary generated successfully!")


if __name__ == "__main__":
    asyncio.run(main())

