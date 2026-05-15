# Patch-Based Agent - Summary

## What Was Created

### 1. Patch-Based Agent
**File:** `agent_patch.py`

The real upgrade from paste-based to proper autonomous dev system:
- Extracts structured patches from ChatGPT
- Applies changes directly to files
- Backups before modification
- Validates with git diff
- Safety checks for dangerous operations
- Rollback capability
- Decision engine (continue/stop/rollback)

### 2. Setup Guide
**File:** `AGENT_PATCH_SETUP.md`

Complete documentation for:
- Installation
- Configuration
- Usage
- Safety features
- Troubleshooting

## Key Upgrade

### Before (Paste Agent)
```
ChatGPT → Extract → Paste to Windsurf → Hope it works
```

### After (Patch Agent)
```
ChatGPT → Extract → Parse Patches → Safety Check → Backup → Apply → Git Validate → Decision
```

## Installation

```bash
# Install dependencies
pip install playwright requests
playwright install

# Install Ollama
brew install ollama
ollama run llama3

# Run agent
cd /path/to/repo
python agent_patch.py
```

## Configuration

```python
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
REPO_PATH = os.getcwd()
LOOP_LIMIT = 10
```

## How It Works

### 1. Extract ChatGPT Message
Playwright navigates to ChatGPT and extracts the last assistant message.

### 2. Parse into Patches
Ollama parses the message into structured file changes:

```json
{
  "changes": [
    {
      "file": "path/to/file.py",
      "action": "create|update",
      "content": "full new file content"
    }
  ]
}
```

### 3. Safety Check
Blocks dangerous operations:
- `rm -rf`
- `os.remove`
- `shutil.rmtree`

### 4. Backup Files
Creates `.bak` files before modifying existing files.

### 5. Apply Changes
Writes new content directly to files.

### 6. Git Validation
Runs `git diff` to see what changed.

### 7. Decision Engine
Ollama analyzes diff and decides:
- **continue** - Changes look good
- **stop** - Stop the agent
- **rollback** - Revert all changes

### 8. Rollback
If decision is "rollback", restores from `.bak` files.

## Safety Features

1. **Loop Limit** - Maximum 10 iterations
2. **Safety Checks** - Blocks dangerous operations
3. **Backups** - `.bak` files before modification
4. **Git Validation** - See what changed
5. **Rollback** - Revert all changes
6. **Decision Engine** - Ollama can stop/rollback
7. **Manual Stop** - Ctrl+C interrupt

## What Works

✅ Extract structured patches
✅ Apply file changes directly
✅ Backup before modification
✅ Safety checks
✅ Git validation
✅ Rollback capability
✅ Decision engine

## What Doesn't Work Yet

❌ AST-aware edits (can overwrite entire files)
❌ Test execution
❌ Dependency resolution
❌ Multi-step planning memory
❌ Semantic diffing

## Comparison

| Feature | Paste Agent | Patch Agent |
|---------|-------------|-------------|
| ChatGPT Extraction | ✅ | ✅ |
| File Awareness | ❌ | ✅ |
| Direct File Modify | ❌ | ✅ |
| Backups | ❌ | ✅ |
| Git Validation | ❌ | ✅ |
| Safety Checks | ❌ | ✅ |
| Rollback | ❌ | ✅ |
| Decision Engine | ✅ | ✅ |
| IDE Required | ✅ (Windsurf) | ❌ |

## Architecture

```
┌─────────────────────────────────────────────────┐
│         Patch-Based Autonomous Agent             │
├─────────────────────────────────────────────────┤
│                                                 │
│  ChatGPT → Playwright → Message                 │
│      ↓                                          │
│  Ollama → Parse → Patches                       │
│      ↓                                          │
│  Safety Check → Block Dangerous                 │
│      ↓                                          │
│  Backup → .bak Files                            │
│      ↓                                          │
│  Apply → Write to Files                         │
│      ↓                                          │
│  Git Diff → Validate                            │
│      ↓                                          │
│  Ollama → Decision                              │
│      ↓                                          │
│  Continue / Stop / Rollback                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Safety Check Function

```python
def is_safe(change):
    forbidden = ["rm -rf", "os.remove", "shutil.rmtree"]

    content = change.get("content", "")
    for f in forbidden:
        if f in content:
            return False

    return True
```

## Rollback Function

```python
def rollback():
    for root, _, files in os.walk(REPO_PATH):
        for f in files:
            if f.endswith(".bak"):
                original = os.path.join(root, f[:-4])
                backup = os.path.join(root, f)
                os.replace(backup, original)
                print(f"↩️ Restored {original}")
```

## Decision Engine

```python
def decide(repo_state):
    prompt = f"""
Repo state:
{repo_state}

Should the agent:
- continue
- stop
- rollback

Respond with one word.
"""

    res = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False}
    )

    decision = res.json()["response"].lower()

    if "rollback" in decision:
        return "rollback"
    if "stop" in decision:
        return "stop"
    return "continue"
```

## Troubleshooting

### "No changes found"
- ChatGPT message doesn't contain file changes
- Ollama failed to parse patches
- Check prompt format

### "Failed parsing JSON"
- Ollama didn't return valid JSON
- Try larger model (llama3:70b)
- Simplify prompt

### "Unsafe change blocked"
- Change contains forbidden operation
- Edit `is_safe()` function
- Add exceptions if needed

### Git Diff Empty
- Changes may not have been applied
- Check file paths
- Verify write permissions

### Rollback Failed
- `.bak` files missing
- Check backup creation
- Manual restore from git if needed

## Configuration Examples

### More Iterations
```python
LOOP_LIMIT = 20
```

### Different Model
```python
MODEL = "llama3:70b"  # More accurate
MODEL = "mistral"      # Faster
```

### Custom Repo Path
```python
REPO_PATH = "/path/to/repo"
```

### Additional Safety Checks
```python
def is_safe(change):
    forbidden = [
        "rm -rf",
        "os.remove",
        "shutil.rmtree",
        "subprocess.call",
        "exec(",
        "eval("
    ]
    # ... rest of function
```

## Next Level

To go from junior agent to serious autonomous system:

**Add AST-aware patching + test runner + failure loop**

This adds:
- AST parsing to modify specific code sections
- Test execution before committing
- Loop until tests pass
- Multi-step planning memory

## Files Created

1. `agent_patch.py` - Patch-based agent
2. `AGENT_PATCH_SETUP.md` - Setup guide
3. `AGENT_PATCH_SUMMARY.md` - This summary

## Status

**Current State:** ✅ Working patch-based agent
**Next Level:** AST-aware + test runner
**Production-Ready:** ⚠️ Needs AST parsing and tests

## Reality Check

You've now crossed into:
"This can actually change my entire codebase without me touching it"

**If you run this unattended:**
- Don't act surprised when it rewrites half your repo
- Then politely decides it did a great job

**Respect the loop.** Monitor the agent. Watch what it does.

## Next Prompt

To upgrade to serious autonomous system:

**"Add AST-aware patching using ast module to modify specific code sections, test runner with pytest to validate changes, and failure loop that retries until tests pass."**
