"""
Main loop - Ties together Governor, Agent, and Executor
Simple, brutal, effective execution
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, Any

from governor import Governor, GovernorConfig, ExecutionResult
from agent import Agent
from executor import Executor


def load_task(task_file: str) -> Dict[str, Any]:
    """Load task from JSON file"""
    with open(task_file, 'r') as f:
        return json.load(f)


def run_autonomous_loop(task: Dict[str, Any], governor: Governor, agent: Agent, executor: Executor):
    """Run the autonomous loop"""
    print("=== CleanStat Autonomous Agent ===")
    print(f"Task ID: {task.get('observation_id')}")
    print(f"Image: {task.get('image_path')}")
    print()
    
    # Initialize state
    state = {
        "step": 0,
        "observation_id": task.get("observation_id"),
        "image_path": task.get("image_path"),
        "location": task.get("location", {}),
        "last_action": "",
        "last_result": {}
    }
    
    iteration = 0
    
    while True:
        iteration += 1
        print(f"\n--- Iteration {iteration} ---")
        
        # Check if governor should stop
        should_stop, reason = governor.should_stop()
        if should_stop:
            print(f"🛑 STOP: {reason}")
            print(f"Stats: {governor.get_stats()}")
            break
        
        # Agent plans next action
        print("🤖 Agent planning...")
        decision = agent.plan(state)
        action = decision.get("action")
        input_data = decision.get("input", {})
        
        print(f"   Action: {action}")
        print(f"   Input: {json.dumps(input_data, indent=2)[:100]}...")
        
        # Check if governor allows this action
        allowed, reason = governor.allow(action, input_data)
        if not allowed:
            print(f"🚫 BLOCKED: {reason}")
            break
        
        # Executor runs the action
        print(f"⚡ Executing {action}...")
        result = executor.execute(action, input_data)
        
        # Governor observes result
        governor.observe(result)
        
        print(f"   Status: {result.status}")
        if result.error:
            print(f"   Error: {result.error}")
        if result.cost_usd > 0:
            print(f"   Cost: ${result.cost_usd:.4f}")
        print(f"   Duration: {result.duration_ms:.2f}ms")
        
        # Update state
        state["step"] += 1
        state["last_action"] = action
        state["last_result"] = {
            "status": result.status,
            "output": result.output_data
        }
        
        # Store intermediate results in state
        if action == "process_image" and result.status == "success":
            state["image_result"] = result.output_data
        elif action == "create_observation_payload" and result.status == "success":
            state["payload"] = result.output_data.get("payload", {})
        
        # Check if done
        if result.status == "done":
            print("\n✅ Task completed successfully")
            break
        
        if result.status == "error":
            print(f"\n❌ Action failed: {result.error}")
            # Continue unless governor says stop
        
        # Small delay between iterations
        time.sleep(0.5)
    
    # Final stats
    print("\n=== Final Statistics ===")
    stats = governor.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    print("\n=== Action History ===")
    for action in governor.action_history:
        print(f"Iteration {action['iteration']}: {action['action']} - {action['status']}")


def main():
    """Main entry point"""
    # Load configuration from environment
    groq_api_key = os.getenv("GROQ_API_KEY")
    cleanstat_api_url = os.getenv("CLEANSTAT_API_URL", "http://localhost:8000")
    cleanstat_api_key = os.getenv("CLEANSTAT_API_KEY")
    
    if not groq_api_key:
        print("❌ ERROR: GROQ_API_KEY environment variable required")
        return
    
    if not cleanstat_api_key:
        print("❌ ERROR: CLEANSTAT_API_KEY environment variable required")
        return
    
    # Initialize components
    print("Initializing components...")
    governor = Governor()
    agent = Agent(groq_api_key=groq_api_key)
    executor = Executor(cleanstat_api_url=cleanstat_api_url, cleanstat_api_key=cleanstat_api_key)
    
    # Load task (for demo, create a sample task)
    task_file = "task.json"
    
    if not Path(task_file).exists():
        # Create sample task
        sample_task = {
            "observation_id": "obs_001",
            "image_path": "data/images/obs_001.jpg",
            "timestamp": "2026-04-19T10:00:00Z",
            "location": {
                "lat": 40.7128,
                "lng": -74.0060
            }
        }
        
        # Create data directory and sample image
        Path("data/images").mkdir(parents=True, exist_ok=True)
        
        # Create a dummy image for testing
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(sample_task["image_path"])
        
        with open(task_file, 'w') as f:
            json.dump(sample_task, f, indent=2)
        
        print(f"Created sample task: {task_file}")
    
    # Load task
    task = load_task(task_file)
    
    # Run autonomous loop
    run_autonomous_loop(task, governor, agent, executor)


if __name__ == "__main__":
    main()
