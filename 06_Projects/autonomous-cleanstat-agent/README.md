# Autonomous CleanStat Agent

**Governed autonomous agent with Ollama, file control, and command execution**

---

## Overview

A production-grade autonomous agent that processes waste observations and sends them to the CleanStat backend. **No UI automation** - direct file operations, command execution, and API calls only.

---

## Architecture

### Components

**1. Governor** (`governor.py`)
- Enforces execution policies
- Tracks iterations, costs, and errors
- Prevents runaway execution
- Configurable limits (max iterations, cost, error rate)

**2. Agent** (`agent.py`)
- Plans actions using Ollama LLM
- Outputs strict JSON format only
- Rule-based fallback if LLM fails
- 5 domain-specific actions only

**3. Executor** (`executor.py`)
- Executes domain-specific actions
- File read/write operations
- Command execution via subprocess
- API calls to CleanStat backend
- No UI automation whatsoever

**4. Main Loop** (`main.py`)
- Ties all components together
- Simple, brutal, effective execution
- Task-based processing
- Workspace state awareness

---

## 5 Actions (Domain-Specific Only)

1. **load_observation** - Load observation data
2. **process_image** - AI classification and counting
3. **create_observation_payload** - Format for CleanStat
4. **send_to_cleanstat** - POST to backend
5. **finish** - Complete task

**No generic actions. No file writes. No shell commands.**

---

## Key Features

✅ **No UI Automation**
- No mouse clicks
- No screen coordinates
- No copy/paste loops
- Direct file control only

✅ **File Operations**
- `read_file(path)` - Read file content
- `write_file(path, content)` - Write content to file

✅ **Command Execution**
- `run_command(cmd)` - Run shell commands
- Capture stdout/stderr
- Timeout protection

✅ **Workspace Awareness**
- Reads workspace state
- Tracks pending observations
- File system monitoring

✅ **Governor Safety**
- Max iterations: 25
- Max cost: $1.50
- Max error rate: 30%
- Max errors: 3

---

## Installation

### Prerequisites

- Python 3.11+
- Ollama running locally (http://localhost:11434)
- CleanStat backend running
- API keys in `.env` file (never in code)

### Setup

```bash
# Navigate to directory
cd autonomous-cleanstat-agent

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Environment Variables

```bash
# Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# CleanStat
CLEANSTAT_API_URL=http://localhost:8000
CLEANSTAT_API_KEY=your_cleanstat_api_key_here

# Workspace
WORKSPACE_DIR=.
```

---

## Usage

### Quick Start

```bash
# Run the agent
python main.py
```

The agent will:
1. Load task from `task.json` (or create sample)
2. Process image with AI (simulated for now)
3. Create CleanStat payload
4. Send to backend API
5. Log all actions and statistics

### Task Format

```json
{
  "observation_id": "obs_001",
  "image_path": "data/images/obs_001.jpg",
  "timestamp": "2026-04-19T10:00:00Z",
  "location": {
    "lat": 40.7128,
    "lng": -74.0060
  }
}
```

---

## Workspace Structure

```
workspace/
├── data/
│   ├── images/          # Observation images
│   └── queue/           # Pending observation JSON files
├── backend/            # CleanStat backend files
├── logs/               # Execution logs
└── task.json           # Current task
```

---

## Governor Policies

**Default Limits:**
- Max iterations: 25
- Max cost: $1.50
- Max error rate: 30%
- Max errors: 3

**Stop Conditions:**
- Iteration limit reached
- Cost limit reached
- Error rate exceeded
- Absolute error count exceeded

---

## Scaling

This system can:
- ✅ Run headless (servers, cloud, city infra)
- ✅ Process thousands of observations
- ✅ Integrate with CleanStat directly
- ✅ Scale horizontally

**Cannot:**
- ❌ Break on UI changes
- ❌ Require screen access
- ❌ Depend on visual layout

---

## Next Steps

1. **Integrate actual AI model** - Replace simulated classification with real Ollama/Groq/Hugging Face model
2. **Add batching** - Process multiple observations in one run
3. **Add queue processing** - Watch data/queue/ directory for new tasks
4. **Add IPFS upload** - Upload images to IPFS before sending to CleanStat
5. **Add verification** - Trigger verification workflow after observation

---

## Why This Architecture

**Old Way (Fragile):**
- Click buttons
- Copy/paste
- Screen coordinates
- UI-dependent

**New Way (Robust):**
- Direct file operations
- Command execution
- API calls
- Headless-capable

**Result:**
- Scales
- Reliable
- Production-ready
- No UI dependencies

---

*Autonomous CleanStat Agent v1.0*
*Governed autonomous processing with Ollama*
