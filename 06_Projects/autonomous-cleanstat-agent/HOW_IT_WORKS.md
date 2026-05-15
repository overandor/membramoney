# How the Autonomous CleanStat Agent Works

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AUTONOMOUS AGENT                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   GOVERNOR   │◄───│    AGENT     │◄───│   EXECUTOR   │  │
│  │   (Safety)   │    │   (Brain)    │    │   (Hands)    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │          │
│         │                   │                   │          │
│    Enforces limits     Plans actions       Executes work    │
│    - Max iterations    - Uses Ollama      - File ops       │
│    - Max cost          - Outputs JSON       - Commands       │
│    - Error tracking    - Rule fallback      - API calls      │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │   CLEANSTAT API   │
                    │  (Backend Server) │
                    └───────────────────┘
```

## Execution Flow

```
START
  │
  ▼
┌────────────────────────┐
│ Load Task (task.json)  │
│ - observation_id       │
│ - image_path           │
│ - location             │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐     NO     ┌────────────┐
│ Governor: Should stop? │───────────►│    END     │
│ - Max iterations?      │            │ (stopped)  │
│ - Max cost?            │            └────────────┘
│ - Max errors?          │
└──────────┬─────────────┘
           │ YES
           ▼
┌────────────────────────┐
│ Agent: Plan action     │
│ (Ollama LLM)           │
│                        │
│ Prompt: Current state  │
│ Response: JSON action  │
│ {                      │
│   "action": "...",     │
│   "input": {...}       │
│ }                      │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐     NO     ┌────────────┐
│ Governor: Allow action?  │───────────►│    END     │
│ - Under limits?        │            │ (blocked)  │
└──────────┬─────────────┘            └────────────┘
           │ YES
           ▼
┌────────────────────────┐
│ Executor: Run action     │
│                        │
│ 5 Possible Actions:    │
│ 1. load_observation    │
│ 2. process_image       │
│ 3. create_payload      │
│ 4. send_to_cleanstat   │
│ 5. finish              │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│ Governor: Observe      │
│ - Record result        │
│ - Track cost           │
│ - Count errors         │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐
│ Update State           │
│ - increment step       │
│ - store results        │
└──────────┬─────────────┘
           │
           ▼
┌────────────────────────┐     YES    ┌────────────┐
│ Status == "done"?      │───────────►│    END     │
└──────────┴─────────────┘            │ (success)  │
           │ NO                       └────────────┘
           │
           └────────────────┐
                            │
                            ▼
                    ┌───────────────┐
                    │ Wait 0.5s     │
                    │ (throttle)    │
                    └───────────────┘
                            │
                            ▼
                    Back to: Governor should_stop?
```

## The 5 Actions (Domain-Specific)

### 1. load_observation
```python
Input:  {"observation_id": "obs_001"}
Output: {"id": "obs_001", "image_path": "...", "location": {...}}
```
**What it does:**
- Reads observation data from file or input
- Loads image path and metadata
- Returns structured data

### 2. process_image
```python
Input:  {"image_path": "data/images/obs_001.jpg"}
Output: {"classification": "cigarette_butts", 
         "estimated_count": 5, 
         "confidence": 0.85}
```
**What it does:**
- Loads image from filesystem
- Runs AI classification (simulated for now)
- Returns detection results

### 3. create_observation_payload
```python
Input:  {"observation_id": "obs_001", 
         "image_result": {...}, 
         "location": {...}}
Output: {"payload": {
           "id": "obs_001",
           "image_cid": "ipfs://obs_001",
           "gps_lat": 40.7128,
           "gps_lon": -74.0060,
           "fill_level": 5,
           "confidence": 0.85
         }}
```
**What it does:**
- Formats raw data into CleanStat API format
- Adds IPFS reference
- Structures for POST request

### 4. send_to_cleanstat
```python
Input:  {"payload": {...}}
Output: {"id": "obs_001", "status": "created", ...}
```
**What it does:**
- POSTs payload to CleanStat API
- Returns API response
- Tracks API cost ($0.001 per call)

### 5. finish
```python
Input:  {}
Output: {"message": "Task completed successfully"}
Status: "done"  # This ends the loop
```
**What it does:**
- Signals task completion
- Ends the autonomous loop
- Returns success status

## Governor Safety Policies

### Default Limits
```python
max_iterations = 25      # Stop after 25 actions
max_cost_usd = 1.50      # Stop after $1.50 spent
max_error_rate = 0.30    # Stop if 30% errors
max_errors = 3           # Stop after 3 errors
```

### Decision Logic
```python
def allow(action, input_data):
    if iterations >= 25:     return False, "Max iterations"
    if cost >= 1.50:         return False, "Max cost"
    if error_rate >= 30%:    return False, "Error rate"
    if errors >= 3:          return False, "Max errors"
    return True, ""
```

## Example Run (Step-by-Step)

### Input Task
```json
{
  "observation_id": "obs_001",
  "image_path": "data/images/obs_001.jpg",
  "location": {"lat": 40.7128, "lng": -74.0060}
}
```

### Iteration 1: load_observation
```
Agent:    {"action": "load_observation", "input": {"observation_id": "obs_001"}}
Executor: Read observation data
Result:   ✅ success
State:    step=1, loaded observation data
```

### Iteration 2: process_image
```
Agent:    {"action": "process_image", "input": {"image_path": "data/images/obs_001.jpg"}}
Executor: Load image, classify (AI)
Result:   ✅ success
State:    step=2, image_result={"classification": "cigarette_butts", "count": 5}
```

### Iteration 3: create_observation_payload
```
Agent:    {"action": "create_observation_payload", "input": {...}}
Executor: Format into CleanStat payload
Result:   ✅ success
State:    step=3, payload={"id": "obs_001", ...}
```

### Iteration 4: send_to_cleanstat
```
Agent:    {"action": "send_to_cleanstat", "input": {"payload": {...}}}
Executor: POST to http://localhost:8000/observations
Result:   ❌ error (API not running)
State:    step=4, error_count=1
```

### Iteration 5: finish
```
Agent:    {"action": "finish", "input": {}}
Executor: Mark complete
Result:   ✅ done
Status:   Loop ends (success)
```

## Key Design Principles

### 1. No UI Automation
```diff
- ❌ pyautogui.click(x, y)
- ❌ pyautogui.copy()
- ❌ screen coordinates
+ ✅ file operations
+ ✅ subprocess commands
+ ✅ API calls
```

### 2. Structured JSON Only
```diff
- ❌ LLM outputs: "I'll help you process this image..."
+ ✅ LLM outputs: {"action": "process_image", "input": {...}}
```

### 3. Fallback Safety
```python
try:
    decision = ollama.plan(state)  # Try LLM
except:
    decision = rule_based_plan(state)  # Fallback to rules
```

### 4. Cost Tracking
```python
# Every API call tracked
send_to_cleanstat: $0.001
process_image:     $0.00 (local)
Total tracked:     $0.001
```

## What Makes This Production-Ready

| Feature | Why It Matters |
|---------|----------------|
| **Governor** | Prevents runaway loops, API bankruptcy |
| **File Ops** | Works headless, no UI dependencies |
| **Command Exec** | Can run tests, deploy, verify |
| **JSON Actions** | Deterministic, parseable, debuggable |
| **Ollama** | Local LLM, no API costs, offline capable |
| **Fallbacks** | LLM fails? Rules take over. System keeps working. |

## Next Steps to Scale

1. **Add AI Model**: Replace simulated classification with real YOLO/OpenCV
2. **Queue Processing**: Watch `data/queue/` for new observations
3. **Batching**: Process multiple observations in parallel
4. **IPFS Upload**: Upload images before sending to CleanStat
5. **Verification Loop**: Trigger verification after observation

---

**Result:** An autonomous agent that can process thousands of environmental observations without human supervision, while staying within cost limits and safety bounds.
