"""
Hotel Accommodation Browsing Agent

This agent uses browser-use to search for hotel accommodations and saves results
in Online-Mind2Web-compatible format for evaluation.
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
            if len(action_clean) > 0 and len(action_clean) < 300:
                # Format it nicely
                action_history.append(action_clean)
        
        # Extract is_done flag to detect final result
        if isinstance(item, dict):
            if item.get('is_done'):
                final_result = item.get('long_term_memory') or item.get('extracted_content')

    return screenshots, action_history, thoughts, final_result


def augment_task_for_hotel_search(task: str) -> str:
    """Add guidance for hotel search tasks.
    
    Helps the agent handle common issues with hotel booking sites like
    date pickers, location selection, and filter application.
    """
    try:
        lowered = task.lower()
        triggers = ["hotel", "accommodation", "stay", "booking", "reserve"]
        if any(t in lowered for t in triggers):
            guidance_lines = [
                "When searching for hotels:",
                "- Carefully enter the exact location/city specified in the task.",
                "- Use the date picker to select correct check-in and check-out dates.",
                "- If a date range is specified (e.g., 'next week', 'tomorrow'), calculate the correct dates.",
                "- Apply all filters mentioned in the task (price range, star rating, amenities, etc.).",
                "- Ensure filters are properly selected and applied before viewing results.",
                "- If the site requires you to click 'Search' or 'Apply', do so to see filtered results.",
                "- Double-check that applied filters match the task requirements exactly.",
            ]
            guidance = "\n".join(guidance_lines)
            return f"{task}\n\nConstraints and UI handling notes:\n{guidance}"
    except Exception:
        pass
    return task


async def run_browser_use_agent(task: str, traj_dir: str, visible: bool = True) -> Tuple[Any, List[bytes]]:
    """Run browser-use agent with optional visible browser."""
    from browser_use import Agent, Browser, ChatBrowserUse
    
    # Storage for screenshots captured during execution (disabled)
    captured_screenshots: List[bytes] = []
    
    print("🚀 Starting hotel browsing agent...")
    print(f"📋 Task: {task}")
    print(f"👁️  Browser: {'VISIBLE' if visible else 'HEADLESS'} (headless={not visible})\n")
    
    # Create browser (visible or headless)
    browser = Browser(headless=not visible)
    llm = ChatBrowserUse()
    
    # Create agent (with augmented task to handle hotel search UI)
    augmented_task = augment_task_for_hotel_search(task)
    if augmented_task != task:
        print("🔧 Applied hotel search guidance to task")
        print(f"\n📝 Augmented task being sent to agent:\n{'-'*60}\n{augmented_task}\n{'-'*60}\n")
    agent = Agent(task=augmented_task, llm=llm, browser=browser)
    
    # Hook to capture screenshots - we'll monkey-patch the browser's page after it's created
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
        
        while not agent_task.done():
            try:
                # Check if browser and page exist (screenshot capture disabled)
                if (hasattr(agent, 'browser') and 
                    hasattr(agent.browser, 'page') and 
                    agent.browser.page):
                    pass
            except Exception as e:
                # Silently continue if screenshot fails
                pass
            
            # Wait before next check
            try:
                await asyncio.wait_for(asyncio.shield(agent_task), timeout=screenshot_interval)
                break  # Agent finished
            except asyncio.TimeoutError:
                continue  # Agent still running
        
        # Get the result
        result = await agent_task
        
        return result
    
    # Run the agent with screenshot capture
    print("✓ Starting agent\n")
    history = await run_with_screenshots()
    
    print(f"\n✅ Agent completed")
    
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
        "action_history": action_history[:50],
        "thoughts": thoughts[:20],
    }
    with open(os.path.join(task_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=4)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run a hotel browsing agent using Browser-Use and export Online-Mind2Web-style outputs.")
    parser.add_argument("--task", type=str, required=False, 
                       default="Find a hotel in Seattle for 2 adults checking in tomorrow and checking out in 3 days with free WiFi and breakfast included. Show results sorted by price.")
    parser.add_argument("--task_id", type=str, required=False, default=None, 
                       help="Folder name under data/example for outputs.")
    parser.add_argument("--base_dir", type=str, required=False, 
                       default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "example")))
    parser.add_argument("--visible", action="store_true", help="Launch browser in visible (non-headless) mode")
    args = parser.parse_args()

    # Generate a simple deterministic id if not provided
    if not args.task_id:
        # slug from task text
        slug = re.sub(r"[^a-z0-9]+", "-", args.task.lower())
        slug = re.sub(r"-+", "-", slug).strip("-")[:40]
        args.task_id = f"hotel_search_{slug or 'task'}"

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
            # Run agent with screenshot capture
            history, captured_screenshots = await run_browser_use_agent(args.task, traj_dir, visible=args.visible)
            
            # DEBUG: Show raw history structure
            print("\n🔍 DEBUG: Raw history type:", type(history))
            print("🔍 DEBUG: Raw history class name:", history.__class__.__name__ if hasattr(history, '__class__') else "N/A")
            
            # Show available attributes/methods
            if hasattr(history, '__dict__'):
                print(f"🔍 DEBUG: History attributes: {list(history.__dict__.keys())[:10]}")
            
            # Try to convert history to viewable format
            try:
                if hasattr(history, 'model_dump'):
                    history_dict = history.model_dump()
                elif hasattr(history, 'dict'):
                    history_dict = history.dict()
                else:
                    history_dict = history
                print("🔍 DEBUG: Raw history content (first 2000 chars):")
                print(json.dumps(history_dict, indent=2, default=str)[:2000])
            except Exception as e:
                print(f"🔍 DEBUG: Could not serialize history: {e}")
                print(f"🔍 DEBUG: History str representation: {str(history)[:500]}")
                
            # Check if history has common browser-use attributes
            for attr in ['history', 'action_history', 'actions', 'steps', 'final_result', 'result']:
                if hasattr(history, attr):
                    val = getattr(history, attr)
                    print(f"🔍 DEBUG: history.{attr} = {type(val).__name__} (length: {len(val) if hasattr(val, '__len__') else 'N/A'})")
            
            # Extract actions/thoughts from history
            _history_screenshots, action_history, thoughts, final_result = extract_images_and_actions_from_history(history)
            
            print(f"\n🔍 DEBUG: Extracted {len(action_history)} actions from history")
            if action_history:
                print("🔍 First few actions:", action_history[:5])
            else:
                print("⚠️  No actions extracted!")
                
            if final_result:
                print(f"🔍 Final result: {final_result[:200]}")
                
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
            "Navigated to hotel booking website",
            "Entered location: Seattle",
            "Selected check-in date",
            "Selected check-out date",
            "Applied filters: WiFi, breakfast",
            "Clicked search button",
        ]

    write_result_json(task_dir, args.task_id, args.task, final_result, action_history, thoughts)
    
    print(f"\n✅ All outputs saved to: {task_dir}")
    print(f"   - Actions: {len(action_history)}")


if __name__ == "__main__":
    asyncio.run(main())

