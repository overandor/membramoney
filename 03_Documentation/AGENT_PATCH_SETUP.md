# Patch-Based Autonomous Coding Agent - Setup Guide

## Overview

This is the **real upgrade** from paste-based automation to a proper autonomous dev system.

**Before:** Copy → paste → pray
**After:** Structured patches → safe apply → git validate → rollback capable

## Build Status

✅ Extract structured patches from ChatGPT
✅ Apply changes directly to files
✅ Backup files before modifying
✅ Validate with git diff
✅ Reject dangerous operations
✅ No more blind pasting
✅ Rollback capability
⚠️ Still no full AST parsing (text-based patching)
⚠️ Assumes repo is clean-ish

## Key Difference

### Paste-Based Agent (Old)
- Pastes blobs into Windsurf
- No file awareness
- No validation
- No rollback
- Hope it works

### Patch-Based Agent (New)
- Extracts file-specific patches
- Applies changes directly to files
- Validates with git diff
- Backups before modification
- Rollback capability
- Safety checks

## Installation

```bash
# Install Python dependencies
pip install playwright requests
playwright install

# Install Ollama
brew install ollama
ollama run llama3

# Make sure Ollama is running
ollama serve
```

## Configuration

Edit in `agent_patch.py`:

```python
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
REPO_PATH = os.getcwd()  # Current directory
LOOP_LIMIT = 10
```

## Usage

### Before Running

1. Open ChatGPT in browser (logged in)
2. Navigate to your repo directory
3. Make sure git is initialized

### Run Agent

```bash
cd /path/to/your/repo
python agent_patch.py
```

## How It Works

### Loop Flow

```
1. Extract ChatGPT message (Playwright)
   ↓
2. Parse into structured patches (Ollama)
   ↓
3. Safety check (block dangerous operations)
   ↓
4. Backup existing files
   ↓
5. Apply changes to files
   ↓
6. Validate with git diff
   ↓
7. Decision engine (continue/stop/rollback)
   ↓
8. If rollback → restore backups
   ↓
9. Repeat until limit or stop
```

### Patch Format

Ollama extracts changes in this format:

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

### Safety Checks

Blocked operations:
- `rm -rf`
- `os.remove`
- `shutil.rmtree`

Add more in `is_safe()` function.

### Backup System

- Creates `.bak` files before modifying
- Rollback restores from `.bak` files
- Automatic cleanup on successful apply

### Git Validation

After applying changes:
- Runs `git diff` to see what changed
- Shows diff preview (first 500 chars)
- Decision engine analyzes diff

### Decision Engine

Ollama analyzes git diff and decides:
- **continue** - Changes look good, proceed
- **stop** - Stop the agent
- **rollback** - Revert all changes

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

## Architecture

```
┌─────────────────────────────────────────────────┐
│         Patch-Based Autonomous Agent             │
├─────────────────────────────────────────────────┤
│                                                 │
│  ChatGPT (Browser)                               │
│      ↓                                          │
│  Playwright (Extract Message)                    │
│      ↓                                          │
│  Ollama (Parse to Patches)                       │
│      ↓                                          │
│  Safety Check (Block Dangerous)                  │
│      ↓                                          │
│  Backup Files (.bak)                             │
│      ↓                                          │
│  Apply Changes to Files                         │
│      ↓                                          │
│  Git Diff (Validate)                             │
│      ↓                                          │
│  Ollama (Decision)                               │
│      ↓                                          │
│  Continue / Stop / Rollback                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

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
| AST-Aware | ❌ | ❌ |

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

**Next prompt:** "Add AST-aware patching using ast module, test runner with pytest, and failure loop that retries until tests pass"

## Files Created

1. `agent_patch.py` - Patch-based agent
2. `AGENT_PATCH_SETUP.md` - This setup guide

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
