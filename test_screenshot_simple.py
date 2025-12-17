#!/usr/bin/env python3
"""
Simple test to check if Browser.take_screenshot() works.
"""
import os
import asyncio
from datetime import datetime

async def test_simple_screenshot():
    """Test if we can take a screenshot with browser-use."""
    
    print("="*60)
    print("Simple Screenshot Test")
    print("="*60)
    
    test_dir = "./test_simple_screenshot"
    os.makedirs(test_dir, exist_ok=True)
    
    try:
        from browser_use import Agent, Browser, ChatBrowserUse
        print("✓ Imported browser-use")
    except ImportError as e:
        print(f"✗ Failed to import: {e}")
        return
    
    api_key = os.getenv("BROWSER_USE_API_KEY")
    if not api_key:
        print("✗ BROWSER_USE_API_KEY not set!")
        return
    print("✓ API key is set")
    
    # Create browser and agent
    llm = ChatBrowserUse()
    browser = Browser(use_cloud=False, headless=True)
    task = "Go to example.com"
    agent = Agent(task=task, llm=llm, browser=browser)
    print(f"✓ Created agent with task: {task}")
    
    # Run agent in background, try to screenshot
    async def test_screenshots():
        print("\n" + "="*60)
        print("Starting agent...")
        print("="*60 + "\n")
        
        # Start agent task
        agent_task = asyncio.create_task(agent.run())
        
        # Wait for browser to start
        print("⏳ Waiting 3 seconds for browser to start...")
        await asyncio.sleep(3)
        
        # Try to take screenshot
        print("\n📸 Attempting to take screenshot...")
        print(f"   - Checking agent attributes...")
        
        # List all non-private attributes of agent
        agent_attrs = [attr for attr in dir(agent) if not attr.startswith('_')]
        print(f"   - Agent attributes: {', '.join(agent_attrs[:10])}...")
        
        # Check different possible browser access paths
        browser_obj = None
        if hasattr(agent, 'browser'):
            print(f"   - agent.browser exists: True")
            browser_obj = agent.browser
        else:
            print(f"   - agent.browser exists: False")
        
        # Check if browser_session exists
        if hasattr(agent, 'browser_session'):
            print(f"   - agent.browser_session exists: True")
            print(f"   - browser_session type: {type(agent.browser_session)}")
        else:
            print(f"   - agent.browser_session exists: False")
        
        # Use the original browser we created
        print(f"   - Using original browser object")
        browser_obj = browser
        
        if browser_obj:
            print(f"   - browser type: {type(browser_obj)}")
            print(f"   - browser has take_screenshot: {hasattr(browser_obj, 'take_screenshot')}")
            
            try:
                print("   - Calling browser.take_screenshot()...")
                screenshot_bytes = await browser_obj.take_screenshot()
                print(f"   - Got result: {type(screenshot_bytes)}, length={len(screenshot_bytes) if screenshot_bytes else 0}")
                
                if screenshot_bytes:
                    screenshot_path = os.path.join(test_dir, "test_screenshot.png")
                    with open(screenshot_path, 'wb') as f:
                        f.write(screenshot_bytes)
                    file_size = os.path.getsize(screenshot_path)
                    print(f"   ✅ Screenshot saved: {screenshot_path} ({file_size} bytes)")
                else:
                    print(f"   ⚠️  take_screenshot() returned None or empty")
            except Exception as e:
                print(f"   ❌ take_screenshot() failed:")
                print(f"      Error type: {type(e).__name__}")
                print(f"      Error message: {e}")
                import traceback
                traceback.print_exc()
        
        # Wait for agent to complete (or timeout after 10s)
        print("\n⏳ Waiting for agent to complete (max 10s)...")
        try:
            await asyncio.wait_for(agent_task, timeout=10)
            print("✅ Agent completed")
        except asyncio.TimeoutError:
            print("⏰ Agent timed out, cancelling...")
            agent_task.cancel()
            try:
                await agent_task
            except asyncio.CancelledError:
                print("✅ Agent cancelled")
        
        return True
    
    try:
        result = await test_screenshots()
        print("\n" + "="*60)
        print("Test Results")
        print("="*60)
        
        # List files
        files = sorted(os.listdir(test_dir))
        if files:
            print(f"📁 Files in {test_dir}:")
            for f in files:
                fpath = os.path.join(test_dir, f)
                fsize = os.path.getsize(fpath)
                print(f"   - {f} ({fsize} bytes)")
        else:
            print(f"⚠️  No files in {test_dir}")
        
        # Cleanup
        try:
            await browser.close()
            print("\n✓ Browser closed")
        except:
            pass
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple_screenshot())
    print("\n✅ Test complete!")

