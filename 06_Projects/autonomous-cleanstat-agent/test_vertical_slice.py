#!/usr/bin/env python3
"""
Test Vertical Slice - End-to-end test of the full pipeline
Runs: task.json -> load_observation -> process_image -> create_payload -> send -> finish
"""

import os
import sys
import json
import time
from pathlib import Path

# Set up environment for testing
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434"  # Will fall back to rules
os.environ["CLEANSTAT_API_URL"] = "http://localhost:8000"
os.environ["CLEANSTAT_API_KEY"] = "test_key"
os.environ["WORKSPACE_DIR"] = "."

from governor import Governor
from agent import Agent
from executor import Executor


def setup_test_data():
    """Create test task and image"""
    # Create directories
    Path("data/images").mkdir(parents=True, exist_ok=True)
    Path("data/queue").mkdir(parents=True, exist_ok=True)
    
    # Create test image
    from PIL import Image
    img = Image.new('RGB', (200, 150), color='blue')
    img.save("data/images/test_obs.jpg")
    
    # Create test task
    task = {
        "observation_id": "test_obs_001",
        "image_path": "data/images/test_obs.jpg",
        "timestamp": "2026-04-19T12:00:00Z",
        "location": {
            "lat": 40.7128,
            "lng": -74.0060
        }
    }
    
    with open("task.json", 'w') as f:
        json.dump(task, f, indent=2)
    
    return task


def test_full_pipeline():
    """Test the complete vertical slice"""
    print("=" * 60)
    print("VERTICAL SLICE TEST: Full Pipeline")
    print("=" * 60)
    print()
    
    # Setup
    task = setup_test_data()
    print(f"✓ Test data created: {task['observation_id']}")
    print(f"✓ Image: {task['image_path']}")
    print()
    
    # Initialize components
    governor = Governor()
    agent = Agent()  # Will use rule-based fallback (Ollama not running)
    executor = Executor(
        cleanstat_api_url="http://localhost:8000",
        cleanstat_api_key="test_key",
        workspace_dir="."
    )
    
    # Initialize state
    state = {
        "step": 0,
        "observation_id": task["observation_id"],
        "image_path": task["image_path"],
        "location": task["location"],
        "last_action": "",
        "last_result": {}
    }
    
    # Track results
    results = []
    
    # Run full pipeline
    for iteration in range(1, 7):  # Max 6 iterations
        print(f"--- Iteration {iteration} ---")
        
        # Check governor
        should_stop, reason = governor.should_stop()
        if should_stop:
            print(f"🛑 STOP: {reason}")
            break
        
        # Agent plans
        decision = agent.plan(state)
        action = decision["action"]
        input_data = decision["input"]
        
        print(f"🤖 Action: {action}")
        
        # Governor allows?
        allowed, reason = governor.allow(action, input_data)
        if not allowed:
            print(f"🚫 BLOCKED: {reason}")
            break
        
        # Execute
        result = executor.execute(action, input_data)
        governor.observe(result)
        
        print(f"⚡ Status: {result.status}")
        if result.error:
            print(f"   Error: {result.error}")
        print(f"   Duration: {result.duration_ms:.2f}ms")
        
        # Store result
        results.append({
            "iteration": iteration,
            "action": action,
            "status": result.status,
            "output": result.output_data,
            "error": result.error
        })
        
        # Update state
        state["step"] += 1
        state["last_action"] = action
        state["last_result"] = {"status": result.status, "output": result.output_data}
        
        if action == "process_image" and result.status == "success":
            state["image_result"] = result.output_data
        elif action == "create_observation_payload" and result.status == "success":
            state["payload"] = result.output_data.get("payload", {})
        
        # Check if done
        if result.status == "done":
            print("\n✅ PIPELINE COMPLETE")
            break
        
        print()
        time.sleep(0.3)
    
    # Final stats
    print("\n" + "=" * 60)
    print("FINAL STATISTICS")
    print("=" * 60)
    stats = governor.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("PIPELINE SUMMARY")
    print("=" * 60)
    
    expected_actions = [
        "load_observation",
        "process_image",
        "create_observation_payload",
        "send_to_cleanstat",
        "finish"
    ]
    
    for i, result in enumerate(results):
        expected = expected_actions[i] if i < len(expected_actions) else "unknown"
        match = "✅" if result["action"] == expected else "❌"
        status_icon = "✅" if result["status"] in ["success", "done"] else "❌"
        
        print(f"{match} Step {i+1}: {result['action']}")
        print(f"   Expected: {expected}")
        print(f"   Status: {status_icon} {result['status']}")
        if result["error"]:
            print(f"   Error: {result['error']}")
        print()
    
    # Check if vertical slice worked
    success = all(r["status"] in ["success", "done"] for r in results)
    
    print("=" * 60)
    if success:
        print("✅ VERTICAL SLICE TEST: PASSED")
    else:
        print("❌ VERTICAL SLICE TEST: FAILED")
    print("=" * 60)
    
    return success


if __name__ == "__main__":
    success = test_full_pipeline()
    sys.exit(0 if success else 1)
