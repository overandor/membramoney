#!/usr/bin/env python3
"""
Visual demonstration of how the autonomous agent works
Shows each step with clear formatting
"""

import json
from pathlib import Path

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_section(title):
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}{title}{RESET}")
    print(f"{BOLD}{'='*60}{RESET}\n")

def print_component(name, role, features):
    print(f"{CYAN}┌─ {name} {'─'*40}{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}Role:{RESET} {role}")
    print(f"{CYAN}│{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}Features:{RESET}")
    for feat in features:
        print(f"{CYAN}│{RESET}   • {feat}")
    print(f"{CYAN}└{'─'*48}{RESET}\n")

def print_flow_step(step_num, component, action, details, status="pending"):
    status_icon = "⏳" if status == "pending" else "✅" if status == "success" else "❌"
    status_color = YELLOW if status == "pending" else GREEN if status == "success" else RED
    
    print(f"{BLUE}Step {step_num}:{RESET} {BOLD}{component}{RESET}")
    print(f"  {status_color}{status_icon}{RESET} {action}")
    for key, val in details.items():
        print(f"     {key}: {val}")
    print()

def print_architecture():
    print_section("SYSTEM ARCHITECTURE")
    
    print("""
    ┌─────────────────────────────────────────────────────────────┐
    │              AUTONOMOUS CLEANSTAT AGENT                      │
    ├─────────────────────────────────────────────────────────────┤
    │                                                              │
    │   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
    │   │  GOVERNOR    │◄───│    AGENT     │◄───│   EXECUTOR   │ │
    │   │   🛡️ Safety   │    │   🧠 Brain   │    │   🤲 Hands   │ │
    │   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘ │
    │          │                   │                   │         │
    │          │                   │                   │         │
    │     Enforces limits    Plans actions        Executes work   │
    │     - Max iterations   - Uses Ollama        - File ops      │
    │     - Max cost         - Outputs JSON       - Commands      │
    │     - Error tracking   - Rule fallback      - API calls     │
    │                                                              │
    └─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   CLEANSTAT API   │
                    │  🌐 Backend       │
                    └───────────────────┘
    """)

def print_components():
    print_section("COMPONENT BREAKDOWN")
    
    print_component(
        "1. GOVERNOR",
        "Safety controller - prevents runaway execution",
        [
            "Max iterations: 25 (stop if exceeded)",
            "Max cost: $1.50 (stop if exceeded)",
            "Max errors: 3 (stop if exceeded)",
            "Error rate: 30% (stop if exceeded)",
            "Tracks every action and decision"
        ]
    )
    
    print_component(
        "2. AGENT",
        "Brain - decides what to do next",
        [
            "Uses Ollama (local LLM)",
            "Outputs strict JSON only",
            "No explanations, no text",
            "Rule-based fallback if LLM fails",
            "5 actions only (domain-specific)"
        ]
    )
    
    print_component(
        "3. EXECUTOR",
        "Hands - does the actual work",
        [
            "File operations (read/write)",
            "Command execution (subprocess)",
            "API calls (HTTP requests)",
            "No UI automation whatsoever",
            "Works headless (no screen needed)"
        ]
    )

def print_execution_flow():
    print_section("EXECUTION FLOW (Live Example)")
    
    print(f"{YELLOW}Starting with task:{RESET}")
    task = {
        "observation_id": "obs_001",
        "image_path": "data/images/obs_001.jpg",
        "location": {"lat": 40.7128, "lng": -74.0060}
    }
    print(json.dumps(task, indent=2))
    print()
    
    # Step 1
    print_flow_step(
        1, "AGENT (Ollama)", "Plan first action",
        {"Prompt": "Current state: step=0, need to load observation",
         "Response": '{"action": "load_observation", "input": {"observation_id": "obs_001"}}'},
        "success"
    )
    
    print_flow_step(
        1, "GOVERNOR", "Check limits",
        {"Iterations": "0/25", "Cost": "$0.00/$1.50", "Errors": "0/3"},
        "success"
    )
    
    print_flow_step(
        1, "EXECUTOR", "Execute load_observation",
        {"Input": "observation_id: obs_001",
         "Output": "Loaded observation data",
         "Duration": "2.5ms"},
        "success"
    )
    
    # Step 2
    print()
    print_flow_step(
        2, "AGENT (Ollama)", "Plan next action",
        {"Prompt": "Current state: step=1, loaded obs, need to process image",
         "Response": '{"action": "process_image", "input": {"image_path": "data/images/obs_001.jpg"}}'},
        "success"
    )
    
    print_flow_step(
        2, "GOVERNOR", "Check limits",
        {"Iterations": "1/25", "Cost": "$0.00/$1.50", "Errors": "0/3"},
        "success"
    )
    
    print_flow_step(
        2, "EXECUTOR", "Execute process_image",
        {"Input": "image_path: data/images/obs_001.jpg",
         "Output": '{"classification": "cigarette_butts", "count": 5, "confidence": 0.85}',
         "Duration": "150ms"},
        "success"
    )
    
    # Step 3
    print()
    print_flow_step(
        3, "AGENT (Ollama)", "Plan next action",
        {"Prompt": "Current state: step=2, image processed, need to create payload",
         "Response": '{"action": "create_observation_payload", "input": {...}}'},
        "success"
    )
    
    print_flow_step(
        3, "EXECUTOR", "Execute create_observation_payload",
        {"Input": "observation_id, image_result, location",
         "Output": "CleanStat formatted payload",
         "Duration": "5ms"},
        "success"
    )
    
    # Step 4 - Error example
    print()
    print_flow_step(
        4, "AGENT (Ollama)", "Plan next action",
        {"Response": '{"action": "send_to_cleanstat", "input": {"payload": {...}}}'},
        "success"
    )
    
    print_flow_step(
        4, "EXECUTOR", "Execute send_to_cleanstat",
        {"API URL": "http://localhost:8000/observations",
         "Error": "Connection refused (backend not running)"},
        "error"
    )
    
    print_flow_step(
        4, "GOVERNOR", "Record error",
        {"Error count": "1/3", "Error rate": "25%"},
        "success"
    )
    
    # Step 5 - Finish
    print()
    print_flow_step(
        5, "AGENT (Ollama)", "Plan final action",
        {"Response": '{"action": "finish", "input": {}}'},
        "success"
    )
    
    print_flow_step(
        5, "EXECUTOR", "Execute finish",
        {"Status": "done", "Message": "Task completed"},
        "success"
    )

def print_actions():
    print_section("THE 5 ACTIONS (Domain-Specific)")
    
    actions = [
        ("1. load_observation", "Read observation data from file or input",
         '{"observation_id": "obs_001"}',
         '{"id": "obs_001", "image_path": "...", "location": {...}}'),
        
        ("2. process_image", "AI classification and counting",
         '{"image_path": "data/images/obs_001.jpg"}',
         '{"classification": "cigarette_butts", "count": 5, "confidence": 0.85}'),
        
        ("3. create_observation_payload", "Format for CleanStat API",
         '{"observation_id": "...", "image_result": {...}, "location": {...}}',
         '{"payload": {"id": "...", "gps_lat": 40.7, "fill_level": 5}}'),
        
        ("4. send_to_cleanstat", "POST to backend API",
         '{"payload": {...}}',
         '{"id": "obs_001", "status": "created"}'),
        
        ("5. finish", "Complete the task and end loop",
         '{}',
         '{"message": "Task completed"}')
    ]
    
    for name, desc, input_ex, output_ex in actions:
        print(f"{CYAN}{name}{RESET}")
        print(f"  {desc}")
        print(f"  {YELLOW}Input:{RESET}  {input_ex}")
        print(f"  {GREEN}Output:{RESET} {output_ex}")
        print()

def print_safety():
    print_section("GOVERNOR SAFETY SYSTEM")
    
    print(f"{BOLD}Hard Limits:{RESET}")
    print("  • Max iterations: 25 (prevents infinite loops)")
    print("  • Max cost: $1.50 (prevents API bankruptcy)")
    print("  • Max errors: 3 (prevents error spam)")
    print("  • Max error rate: 30% (prevents flailing)")
    print()
    
    print(f"{BOLD}Decision Points:{RESET}")
    print("""
    1. Before each action:
       Governor.allow(action) → True/False
       
    2. After each action:
       Governor.observe(result) → Track stats
       
    3. Before planning:
       Governor.should_stop() → True/False
    """)
    
    print(f"{BOLD}Example Stats:{RESET}")
    print(f"  {GREEN}✅ Healthy:{RESET} 5 iterations, $0.001 cost, 0 errors")
    print(f"  {YELLOW}⚠️  Warning:{RESET} 20 iterations, $1.20 cost, 2 errors")
    print(f"  {RED}❌ Stopped:{RESET} 25 iterations, $1.50 cost, 3 errors")

def print_why_better():
    print_section("WHY THIS IS BETTER THAN UI AUTOMATION")
    
    print(f"{RED}❌ OLD WAY (Fragile):{RESET}")
    print("  • pyautogui.click(x=500, y=300)  ← Breaks if window moves")
    print("  • pyautogui.copy() / paste()     ← Fails if UI changes")
    print("  • Screen coordinates             ← Resolution-dependent")
    print("  • Visual layout dependent        ← Breaks on updates")
    print()
    
    print(f"{GREEN}✅ NEW WAY (Robust):{RESET}")
    print("  • file.read() / file.write()     ← Always works")
    print("  • subprocess.run()                 ← Direct execution")
    print("  • requests.post()                  ← API calls")
    print("  • No UI dependencies               ← Headless capable")
    print()
    
    print(f"{BOLD}Result:{RESET}")
    print("  • Scales to thousands of observations")
    print("  • Runs on servers (no screen needed)")
    print("  • Integrates with CleanStat directly")
    print("  • Costs controlled by Governor")
    print("  • Errors tracked and limited")

def main():
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}     AUTONOMOUS CLEANSTAT AGENT - VISUAL DEMO{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    
    print_architecture()
    print_components()
    print_execution_flow()
    print_actions()
    print_safety()
    print_why_better()
    
    print_section("SUMMARY")
    print(f"""
    {BOLD}What:{RESET} An autonomous agent that processes waste observations
    {BOLD}How:{RESET}  Ollama LLM plans actions → Executor does work → Governor enforces safety
    {BOLD}Why:{RESET}  No UI automation = reliable, scalable, headless
    
    {GREEN}✅ Ready for:{RESET}
    • Processing thousands of observations
    • Running 24/7 on servers
    • City-scale deployments
    • CleanStat integration
    """)

if __name__ == "__main__":
    main()
