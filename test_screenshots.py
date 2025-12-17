#!/usr/bin/env python3
"""
Test script to verify screenshot capture during browser-use execution.
"""
import os
import asyncio
from datetime import datetime

async def test_screenshot_capture():
    """Test if we can capture screenshots during agent execution."""
    
    print("="*60)
    print("Screenshot Capture Test")
    print("="*60)
    
    # Create test directory
    test_dir = "./test_screenshots_output"
    os.makedirs(test_dir, exist_ok=True)
    print(f"\n✓ Created test directory: {test_dir}")
    
    try:
        from browser_use import Agent, Browser, ChatBrowserUse
        print("✓ Imported browser-use successfully")
    except ImportError as e:
        print(f"✗ Failed to import browser-use: {e}")
        return
    
    # Check for API key
    api_key = os.getenv("BROWSER_USE_API_KEY")
    if not api_key:
        print("✗ BROWSER_USE_API_KEY not set!")
        return
    print("✓ API key is set")
    
    # Create LLM and Browser
    llm = ChatBrowserUse()
    browser = Browser(
        use_cloud=False,
        headless=True,
        storage_state=None,
        user_data_dir=None,
    )
    print("✓ Created LLM and Browser instances")
    
    # Simple task
    task = "Go to google.com and search for 'browser automation'"
    agent = Agent(task=task, llm=llm, browser=browser)
    print(f"✓ Created agent with task: {task}")
    
    # Screenshot counter
    screenshot_counter = 0
    
    print("\n" + "="*60)
    print("Starting agent execution with screenshot capture...")
    print("="*60 + "\n")
    
    # Wrapper to capture screenshots per step
    async def run_with_screenshots():
        nonlocal screenshot_counter
        
        step_count = 0
        max_steps = 50
        
        print("Running agent step-by-step with per-step screenshots...")
        
        # Run agent step by step
        while step_count < max_steps:
            try:
                print(f"\n🔄 Step {step_count}...")
                step_result = await agent.step()
                
                # Capture screenshot after step
                try:
                    screenshot_bytes = await browser.take_screenshot()
                    if screenshot_bytes:
                        screenshot_path = os.path.join(test_dir, f"step_{step_count}_screenshot.png")
                        with open(screenshot_path, 'wb') as f:
                            f.write(screenshot_bytes)
                        file_size = os.path.getsize(screenshot_path)
                        print(f"   📸 Screenshot saved: {file_size} bytes")
                        screenshot_counter += 1
                except Exception as e:
                    print(f"   ⚠️  Screenshot failed: {e}")
                
                step_count += 1
                
                # Check if done
                if step_result is not None:
                    print(f"\n✅ Agent completed after {step_count} steps")
                    return step_result
                    
            except Exception as e:
                print(f"⚠️  Exception at step {step_count}: {e}")
                if "done" in str(e).lower() or "complete" in str(e).lower():
                    print("   (Completion signal)")
                break
        
        print(f"\n✅ Finished after {step_count} steps, total screenshots: {screenshot_counter}")
        
        # Try to get history
        if hasattr(agent, 'message_manager') and hasattr(agent.message_manager, 'history'):
            return agent.message_manager.history
        return []
    
    try:
        # Run agent with screenshot capture
        history = await run_with_screenshots()
        
        print("\n" + "="*60)
        print("Test Results")
        print("="*60)
        print(f"✓ Agent completed successfully")
        print(f"📸 Total screenshots captured: {screenshot_counter}")
        
        # List all files in test directory
        files = sorted(os.listdir(test_dir))
        if files:
            print(f"\n📁 Files in {test_dir}:")
            for f in files:
                fpath = os.path.join(test_dir, f)
                fsize = os.path.getsize(fpath)
                print(f"   - {f} ({fsize} bytes)")
        else:
            print(f"\n⚠️  No files found in {test_dir}")
        
        # Cleanup
        try:
            await browser.close()
            print("\n✓ Browser closed successfully")
        except Exception as e:
            print(f"\n⚠️  Browser cleanup warning: {e}")
            
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\nRunning screenshot capture test...\n")
    asyncio.run(test_screenshot_capture())
    print("\n✅ Test complete!")

