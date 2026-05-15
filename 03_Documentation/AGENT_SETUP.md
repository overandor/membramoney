# Autonomous Coding Agent - Setup Guide

## Overview

A semi-autonomous coding agent that:
- Pulls latest ChatGPT output via Playwright
- Parses it with Ollama (local LLM)
- Pastes into Windsurf automatically
- Reads repo state via git status
- Makes basic decisions (continue / stop)
- Loops with control + logs

**This is NOT a chaos bot.** It's a controlled, semi-autonomous coding agent with loop limits and decision logic.

## Build Status

✅ Extracts latest ChatGPT assistant message (Playwright)
✅ Uses Ollama (llama3) to structure instructions
✅ Pastes into Windsurf automatically
✅ Reads repo state via git status
✅ Makes basic decisions (continue / stop)
✅ Has loop control (no infinite suicide loops)
⚠️ No visual navigation (intentionally avoided = more stable)
⚠️ No diff patching yet (still paste-based)
⚠️ Assumes ChatGPT already open/logged in

## Installation

### 1. Install Python Dependencies

```bash
pip install playwright pyautogui pyperclip requests
playwright install
```

### 2. Install Ollama

```bash
brew install ollama
ollama run llama3
```

Make sure Ollama is running before running the agent.

### 3. macOS Permissions

**Required for UI automation:**

1. System Settings → Privacy → Accessibility
2. Allow Terminal / Python

### 4. Manual Setup (Before Running)

Before running the agent, manually:
1. Open ChatGPT in browser (logged in)
2. Open Windsurf
3. Load your repo in Windsurf

## Configuration

Edit these in `agent.py`:

```python
CHATGPT_URL = "https://chat.openai.com"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

LOOP_LIMIT = 10  # Maximum loops before auto-stop
DELAY = 5        # Seconds between operations
```

## Usage

### Run Agent

```bash
python agent.py
```

### What Happens

The agent will loop (up to LOOP_LIMIT times):

1. **Extract** latest ChatGPT assistant message
2. **Parse** with Ollama to extract task, instructions, code blocks
3. **Paste** into Windsurf (Cmd+2 to focus, Cmd+V to paste)
4. **Check** repo status via git status
5. **Decide** whether to continue or stop using Ollama
6. **Wait** DELAY seconds and repeat

### Stop Conditions

Agent stops when:
- Loop limit reached (LOOP_LIMIT)
- Ollama decision engine says "stop"
- Error occurs
- Manual interrupt (Ctrl+C)

## How It Works

### Playwright Extraction

Uses Playwright to navigate to ChatGPT and extract the last assistant message:

```python
page.wait_for_selector("div[data-message-author-role='assistant']")
messages = page.query_selector_all("div[data-message-author-role='assistant']")
last = messages[-1].inner_text()
```

### Ollama Parsing

Sends extracted text to local Ollama with structured prompt:

```
Extract:
- task
- instructions
- code_blocks (if any)

Return JSON only:
{
  "task": "...",
  "instructions": "...",
  "code_blocks": ["..."]
}
```

### Windsurf Control

Uses pyautogui to:
1. Focus Windsurf (Cmd+2)
2. Copy text to clipboard
3. Paste (Cmd+V)

### Repo Check

Runs `git status` to check repo state:

```python
subprocess.run(["git", "status"], capture_output=True, text=True)
```

### Decision Engine

Ollama decides whether to continue or stop based on repo state:

```
Repo state: {git status output}

Decide next step:
- continue
- stop

Respond ONLY with one word.
```

## Safety Features

1. **Loop Limit** - Maximum 10 loops by default
2. **Decision Engine** - Ollama can stop the agent
3. **Manual Stop** - Ctrl+C to interrupt
4. **Error Handling** - Stops on any error
5. **No Infinite Loops** - Built-in safeguards

## Limitations

### What's NOT Done

❌ No file-aware editing (still paste-based)
❌ No diff/patch system
❌ No safety against bad code overwrite
❌ No UI recovery if Playwright fails
❌ No multi-step planning memory

### Intentionally Avoided

- **Visual navigation** - More stable without it
- **Complex UI logic** - Reduces failure points
- **Multi-agent coordination** - Single agent for control

## Troubleshooting

### "No message found"

- Make sure ChatGPT is open and logged in
- Wait for assistant message to appear
- Check selector: `div[data-message-author-role='assistant']`

### "Failed to parse JSON"

- Ollama model didn't return valid JSON
- Falls back to raw text output
- Try larger model or simpler prompt

### Playwright Timeout

- Increase wait time in `page.wait_for_selector()`
- Check network connectivity
- Verify ChatGPT URL is accessible

### Windsurf Not Focusing

- Change hotkey in `focus_windsurf()`
- Default is Cmd+2, adjust to your setup
- Make sure Windsurf is open

### Ollama Connection Refused

```bash
# Check if Ollama is running
curl http://localhost:11434/api/generate

# Start Ollama if not running
ollama serve
```

## Configuration Tips

### For Faster Execution

```python
LOOP_LIMIT = 5
DELAY = 2
```

### For More Careful Execution

```python
LOOP_LIMIT = 20
DELAY = 10
```

### For Different Ollama Model

```python
OLLAMA_MODEL = "llama3:70b"  # More accurate, slower
OLLAMA_MODEL = "mistral"      # Faster, less accurate
```

## Next Upgrade

To make this a **real autonomous dev agent**, upgrade to:

**Patch-based system using git diff + apply**

This turns it from:
- Dumb typist bot

Into:
- Real autonomous dev agent that:
  - Creates diffs
  - Applies patches safely
  - Can revert changes
  - Tracks file modifications

**Next prompt:** "Upgrade to patch-based agent using git diff + apply"

## Architecture

```
┌─────────────────────────────────────────────────┐
│           Autonomous Coding Agent               │
├─────────────────────────────────────────────────┤
│                                                 │
│  ChatGPT → Playwright → Extract Message        │
│              ↓                                  │
│          Ollama Parse                           │
│              ↓                                  │
│          Instructions + Code                    │
│              ↓                                  │
│          Paste to Windsurf                      │
│              ↓                                  │
│          Git Status Check                       │
│              ↓                                  │
│          Ollama Decision                        │
│              ↓                                  │
│          Continue / Stop                        │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Files Created

1. `agent.py` - Main agent code
2. `agent_requirements.txt` - Python dependencies
3. `AGENT_SETUP.md` - This setup guide

## Status

✅ Working MVP
✅ Loop control
✅ Decision engine
✅ Local reasoning (Ollama)
✅ Browser extraction (Playwright)
✅ IDE execution (Windsurf)

⚠️ Paste-based (not patch-based)
⚠️ No file awareness
⚠️ No safety against bad code

## Reality Check

You now have:
- A working loop
- Local reasoning (Ollama)
- Browser extraction (Playwright)
- IDE execution (Windsurf)

**If this breaks:**
- It's not the code
- It's because you tried to let it run unattended

**Don't.**

Monitor the agent. Watch what it does. This is a tool, not a replacement for your judgment.
