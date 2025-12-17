#!/usr/bin/env python3
"""
Test script to verify step-by-step screenshot capture works.
"""
import os
import asyncio

async def test_step_screenshots():
    """Test if we can capture screenshots per step."""
    
    print("="*60)
    print("Step-by-Step Screenshot Test")
    print("="*60)
    
    test_dir = "./test_step_screenshots"
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
    
    # Test step-by-step execution
    async def test_steps():
        print("\n" + "="*60)
        print("Testing step() method...")
        print("="*60 + "\n")
        
        step_count = 0
        screenshot_count = 0
        max_steps = 10
        
        while step_count < max_steps:
            try:
                print(f"\n🔄 Executing step {step_count}...")
                step_result = await agent.step()
                print(f"   ✓ Step {step_count} completed")
                print(f"   - Result type: {type(step_result)}")
                print(f"   - Result value: {step_result}")
                
                # Try to capture screenshot
                try:
                    screenshot_bytes = await browser.take_screenshot()
                    if screenshot_bytes:
                        screenshot_path = os.path.join(test_dir, f"step_{step_count}_screenshot.png")
                        with open(screenshot_path, 'wb') as f:
                            f.write(screenshot_bytes)
                        file_size = os.path.getsize(screenshot_path)
                        print(f"   📸 Screenshot saved: {file_size} bytes")
                        screenshot_count += 1
                except Exception as e:
                    print(f"   ⚠️  Screenshot failed: {e}")
                
                step_count += 1
                
                # Check if done
                if step_result is not None:
                    print(f"\n✅ Agent completed after {step_count} steps")
                    print(f"📸 Total screenshots: {screenshot_count}")
                    return step_result
                    
            except Exception as e:
                print(f"\n⚠️  Exception at step {step_count}: {type(e).__name__}: {e}")
                # Check if it's a completion signal
                if "done" in str(e).lower() or "complete" in str(e).lower():
                    print("   (This appears to be a completion signal)")
                break
        
        print(f"\n✅ Finished after {step_count} steps")
        print(f"📸 Total screenshots: {screenshot_count}")
        
        # Try to get history
        if hasattr(agent, 'message_manager'):
            print(f"   - Agent has message_manager")
            if hasattr(agent.message_manager, 'history'):
                print(f"   - message_manager has history")
                return agent.message_manager.history
        
        return None
    
    try:
        result = await test_steps()
        
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
    asyncio.run(test_step_screenshots())
    print("\n✅ Test complete!")

