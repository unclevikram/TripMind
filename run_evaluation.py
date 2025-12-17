#!/usr/bin/env python3
"""
TripMind Evaluation Script

This script:
1. Organizes screenshots from white agent execution into task-specific folders
2. Runs WebJudge evaluation on the completed assessments
3. Displays formatted results

Usage:
    python run_evaluation.py [--trajectories_dir DIR] [--model MODEL] [--score_threshold N]
    
Example:
    python run_evaluation.py --trajectories_dir ./data/assessment_results --model gpt-4o-mini
"""

import os
import json
import shutil
import subprocess
import sys
import argparse
import hashlib
from pathlib import Path

def organize_screenshots(assessment_dir):
    """
    Organize screenshots from white agent folders into task-specific folders.
    Returns the number of tasks processed and total screenshots.
    """
    print("="*70)
    print("Step 1: Organizing Screenshots")
    print("="*70)
    
    if not os.path.exists(assessment_dir):
        print(f"❌ Assessment directory not found: {assessment_dir}")
        return 0, 0
    
    # Find all task directories (those with result.json)
    task_dirs = []
    for item in os.listdir(assessment_dir):
        item_path = os.path.join(assessment_dir, item)
        if os.path.isdir(item_path):
            result_json = os.path.join(item_path, "result.json")
            if os.path.exists(result_json):
                task_dirs.append((item, item_path, result_json))
    
    if not task_dirs:
        print(f"⚠️  No task directories with result.json found in {assessment_dir}")
        return 0, 0
    
    print(f"\n✓ Found {len(task_dirs)} task(s) to process\n")
    
    total_screenshots = 0
    
    for task_id, task_path, result_json_path in task_dirs:
        print(f"📁 Processing task: {task_id}")
        
        # Read result.json
        try:
            with open(result_json_path, 'r') as f:
                result_data = json.load(f)
        except Exception as e:
            print(f"   ❌ Failed to read result.json: {e}")
            continue
        
        # Get trajectory path from white agent
        trajectory_path = result_data.get("trajectory_path")
        
        # If no trajectory_path, try to find it by searching for matching agent folder
        if not trajectory_path:
            print(f"   ⚠️  No trajectory_path in result.json, searching...")
            
            # Extract port from assessee_url (e.g., "http://localhost:9001" -> "9001")
            assessee_url = result_data.get("assessee_url", "")
            if assessee_url:
                try:
                    port = assessee_url.split(":")[-1]
                    
                    # Look for agent folders matching this port
                    task_text = result_data.get("task", "")
                    task_hash = hashlib.md5(task_text.encode()).hexdigest()[:8]
                    
                    # Search for matching folders
                    pattern = f"agent_{port}_task_"
                    matching_folders = []
                    
                    for item in os.listdir(assessment_dir):
                        if item.startswith(pattern) and task_hash in item:
                            candidate_path = os.path.join(assessment_dir, item, "trajectory")
                            if os.path.exists(candidate_path):
                                # Check if it has screenshots
                                screenshots = [f for f in os.listdir(candidate_path) if f.endswith(('.png', '.jpg', '.jpeg'))]
                                if screenshots:
                                    matching_folders.append((candidate_path, len(screenshots)))
                    
                    if matching_folders:
                        # Use the folder with the most screenshots (most recent/complete)
                        trajectory_path = max(matching_folders, key=lambda x: x[1])[0]
                        print(f"   ✓ Found matching trajectory: {trajectory_path}")
                    else:
                        print(f"   ⚠️  Could not find matching trajectory folder")
                        continue
                        
                except Exception as e:
                    print(f"   ⚠️  Error searching for trajectory: {e}")
                    continue
            else:
                print(f"   ⚠️  No assessee_url to search with")
                continue
        
        if not os.path.exists(trajectory_path):
            print(f"   ⚠️  Trajectory path doesn't exist: {trajectory_path}")
            continue
        
        print(f"   ✓ Source: {trajectory_path}")
        
        # Create trajectory directory in task folder
        dest_trajectory_dir = os.path.join(task_path, "trajectory")
        os.makedirs(dest_trajectory_dir, exist_ok=True)
        
        # Copy all screenshot files
        screenshot_count = 0
        try:
            for filename in os.listdir(trajectory_path):
                if filename.endswith(('.png', '.jpg', '.jpeg')):
                    src = os.path.join(trajectory_path, filename)
                    dst = os.path.join(dest_trajectory_dir, filename)
                    shutil.copy2(src, dst)
                    screenshot_count += 1
            
            print(f"   📸 Copied {screenshot_count} screenshot(s)")
            total_screenshots += screenshot_count
            
            # Update result.json with screenshot count
            result_data["screenshots_organized"] = True
            result_data["screenshot_count"] = screenshot_count
            with open(result_json_path, 'w') as f:
                json.dump(result_data, f, indent=2)
            
        except Exception as e:
            print(f"   ❌ Failed to copy screenshots: {e}")
            continue
    
    print(f"\n✅ Organized {total_screenshots} screenshots across {len(task_dirs)} task(s)\n")
    return len(task_dirs), total_screenshots


def run_webjudge_evaluation(trajectories_dir, model, output_path, score_threshold, num_workers):
    """
    Run WebJudge evaluation on the organized trajectories.
    """
    print("="*70)
    print("Step 2: Running WebJudge Evaluation")
    print("="*70)
    
    # Check if OpenAI API key is set
    api_key = os.environ("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY environment variable not set!")
        print("   Please set it: export OPENAI_API_KEY='your-key-here'")
        return False
    
    # Create a clean evaluation directory with only task folders
    # WebJudge expects only folders with result.json, not agent trajectory folders
    eval_dir = os.path.join(trajectories_dir, "..", "webjudge_input")
    eval_dir = os.path.abspath(eval_dir)
    
    if os.path.exists(eval_dir):
        shutil.rmtree(eval_dir)
    os.makedirs(eval_dir, exist_ok=True)
    
    # Copy only task folders (those with result.json) to eval directory
    task_count = 0
    for item in os.listdir(trajectories_dir):
        item_path = os.path.join(trajectories_dir, item)
        if os.path.isdir(item_path):
            result_json = os.path.join(item_path, "result.json")
            if os.path.exists(result_json):
                # This is a valid task folder, copy it
                dest_path = os.path.join(eval_dir, item)
                shutil.copytree(item_path, dest_path, dirs_exist_ok=True)
                task_count += 1
    
    print(f"\n✓ Prepared {task_count} task(s) for evaluation")
    print(f"✓ Evaluation input directory: {eval_dir}")
    print(f"✓ Model: {model}")
    print(f"✓ Output: {output_path}")
    print(f"✓ Score Threshold: {score_threshold}")
    print(f"✓ Workers: {num_workers}\n")
    
    # Build the command - use eval_dir which only contains task folders
    cmd = [
        sys.executable,  # Use the same Python interpreter
        "src/run.py",
        "--mode", "WebJudge_Online_Mind2Web_eval",
        "--model", model,
        "--trajectories_dir", eval_dir,
        "--api_key", api_key,
        "--output_path", output_path,
        "--num_worker", str(num_workers),
        "--score_threshold", str(score_threshold)
    ]
    
    print(f"Running: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False, text=True)
        print("\n✅ WebJudge evaluation completed successfully!\n")
        
        # Cleanup temporary evaluation directory
        try:
            shutil.rmtree(eval_dir)
            print(f"✓ Cleaned up temporary directory: {eval_dir}\n")
        except Exception as e:
            print(f"⚠️  Could not cleanup {eval_dir}: {e}\n")
        
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ WebJudge evaluation failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print("\n❌ Could not find src/run.py - make sure you're in the project root")
        return False


def display_results(output_path, model, score_threshold):
    """
    Display formatted evaluation results.
    """
    print("="*70)
    print("Step 3: Evaluation Results")
    print("="*70)
    
    # Construct the expected results file name
    results_file = os.path.join(
        output_path,
        f"WebJudge_Online_Mind2Web_eval_{model}_score_threshold_{score_threshold}_auto_eval_results.json"
    )
    
    if not os.path.exists(results_file):
        print(f"⚠️  Results file not found: {results_file}")
        return
    
    try:
        with open(results_file, 'r') as f:
            results = json.load(f)
        
        print(f"\n📊 Results from: {results_file}\n")
        
        # Check if it's a list of results or a single result
        if isinstance(results, list):
            # Multiple results
            passed = sum(1 for r in results if r.get("predicted_label") == 1)
            total = len(results)
            
            print(f"{'Task ID':<30} {'Status':<10} {'Score':<10}")
            print("-" * 70)
            
            for result in results:
                task = result.get("task", "unknown")
                predicted_label = result.get("predicted_label", 0)
                status = "✅ PASS" if predicted_label == 1 else "❌ FAIL"
                score = result.get("score", "N/A")
                
                print(f"{task:<30} {status:<10} {score:<10}")
            
            print("-" * 70)
            print(f"\n📈 Summary: {passed}/{total} tasks passed ({passed/total*100:.1f}%)\n")
            
        else:
            # Single result
            task = results.get("task", "unknown")
            predicted_label = results.get("predicted_label", 0)
            status = "✅ PASS" if predicted_label == 1 else "❌ FAIL"
            
            print(f"Task: {task}")
            print(f"Status: {status}")
            print(f"Predicted Label: {predicted_label}")
            
            if "key_points" in results:
                print(f"\nKey Points:")
                for point in results["key_points"]:
                    print(f"  - {point}")
            
            print()
    
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse results JSON: {e}")
    except Exception as e:
        print(f"❌ Error reading results: {e}")


def main():
    parser = argparse.ArgumentParser(description="TripMind Evaluation Script")
    parser.add_argument(
        "--trajectories_dir",
        default="./data/assessment_results",
        help="Directory containing assessment results (default: ./data/assessment_results)"
    )
    parser.add_argument(
        "--model",
        default="gpt-4o-mini",
        help="Model to use for evaluation (default: gpt-4o-mini)"
    )
    parser.add_argument(
        "--output_path",
        default="./data/evaluation_results",
        help="Output directory for evaluation results (default: ./data/evaluation_results)"
    )
    parser.add_argument(
        "--score_threshold",
        type=int,
        default=3,
        help="Score threshold for evaluation (default: 3)"
    )
    parser.add_argument(
        "--num_worker",
        type=int,
        default=1,
        help="Number of workers for parallel evaluation (default: 1)"
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("TripMind Evaluation Pipeline")
    print("="*70 + "\n")
    
    # Step 1: Organize screenshots
    num_tasks, num_screenshots = organize_screenshots(args.trajectories_dir)
    
    if num_tasks == 0:
        print("❌ No tasks to evaluate. Exiting.")
        return 1
    
    # Step 2: Run WebJudge evaluation
    success = run_webjudge_evaluation(
        args.trajectories_dir,
        args.model,
        args.output_path,
        args.score_threshold,
        args.num_worker
    )
    
    if not success:
        print("❌ Evaluation failed. Exiting.")
        return 1
    
    # Step 3: Display results
    display_results(args.output_path, args.model, args.score_threshold)
    
    print("="*70)
    print("✅ Evaluation Complete!")
    print("="*70 + "\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

