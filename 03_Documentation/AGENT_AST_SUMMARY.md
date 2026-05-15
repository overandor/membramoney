# AST-Aware Agent - Summary

## What Was Created

### 1. AST-Aware Agent
**File:** `agent_ast.py`

The serious autonomous system upgrade:
- AST-aware patching (surgical function edits)
- Test runner (pytest validation)
- Failure loop (retries until tests pass)
- Automatic git commit on success
- Rollback on test failure

### 2. Updated Requirements
**File:** `agent_requirements.txt`

Added pytest for test runner.

### 3. Setup Guide
**File:** `AGENT_AST_SETUP.md`

Complete documentation for AST-aware agent.

## Key Upgrade

### Before (Patch Agent)
```
Parse → Apply → Validate → Decision
```

### After (AST Agent)
```
Parse → AST Patch → Apply → Test → Retry if Fail → Commit
```

## Installation

```bash
# Install dependencies
pip install playwright requests pytest
playwright install

# Install Ollama
brew install ollama
ollama run llama3

# Run agent
cd /path/to/repo
python agent_ast.py
```

## Configuration

```python
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
REPO_PATH = os.getcwd()
LOOP_LIMIT = 10
MAX_RETRIES = 3
TEST_COMMAND = "pytest -xvs"
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
      "action": "create|update|ast_patch",
      "content": "full new file content",
      "target_function": "function_name",
      "new_code": "new function code"
    }
  ]
}
```

### 3. AST-Aware Patching
For `ast_patch` actions:
- Parses file AST
- Finds target function
- Replaces function body
- Converts back to source
- Preserves file structure

### 4. Apply Changes
- Safety check (blocks dangerous operations)
- Backup existing files (.bak)
- Apply changes

### 5. Test Runner
Runs pytest to validate changes:
```python
pytest -xvs
```

### 6. Failure Loop
If tests fail:
1. Rollback changes
2. Wait 2 seconds
3. Retry (up to MAX_RETRIES)
4. If max retries reached, give up

### 7. Auto Commit
If tests pass:
```bash
git add .
git commit -m "Agent: automated changes"
```

## AST-Aware Patching

### Before (Full File Write)
```python
# Overwrites entire file
with open(file_path, "w") as f:
    f.write(new_content)
```

### After (Surgical Edit)
```python
# Parses AST, finds function, replaces body
tree = ast.parse(source)
for node in ast.walk(tree):
    if node.name == target_function:
        node.body = new_func.body
new_source = ast.unparse(tree)
```

**Benefits:**
- Surgical edits (not full file overwrites)
- Preserves file structure
- Less destructive
- More precise

## Failure Loop

```python
for retry in range(MAX_RETRIES):
    apply_changes()
    if run_tests():
        break  # Success
    else:
        rollback()  # Retry
```

**Behavior:**
- Retries up to MAX_RETRIES times
- Rolls back after each failure
- Waits 2 seconds between retries
- Gives up if max retries reached

## Safety Features

1. **Loop Limit** - Maximum 10 iterations
2. **Safety Checks** - Blocks dangerous operations
3. **Backups** - `.bak` files before modification
4. **Test Validation** - pytest must pass
5. **Failure Loop** - Retries until tests pass
6. **Rollback** - Reverts on test failure
7. **Manual Stop** - Ctrl+C interrupt

## What Works

✅ Extract structured patches
✅ AST-aware function edits
✅ Apply file changes directly
✅ Backup before modification
✅ Safety checks
✅ Test validation (pytest)
✅ Failure loop (retry until pass)
✅ Automatic git commit
✅ Rollback on failure

## What Doesn't Work Yet

❌ AST parsing limited to function-level
❌ Requires pytest tests in repo
❌ No dependency resolution
❌ No multi-step planning memory
❌ No semantic diffing

## Comparison

| Feature | Patch Agent | AST Agent |
|---------|-------------|-----------|
| ChatGPT Extraction | ✅ | ✅ |
| File Awareness | ✅ | ✅ |
| Direct File Modify | ✅ | ✅ |
| Backups | ✅ | ✅ |
| Safety Checks | ✅ | ✅ |
| Git Validation | ✅ | ✅ |
| Rollback | ✅ | ✅ |
| AST-Aware Edits | ❌ | ✅ |
| Test Runner | ❌ | ✅ |
| Failure Loop | ❌ | ✅ |
| Auto Commit | ❌ | ✅ |

## Architecture

```
┌─────────────────────────────────────────────────┐
│      AST-Aware Agent with Test Runner             │
├─────────────────────────────────────────────────┤
│                                                 │
│  ChatGPT → Playwright → Message                 │
│      ↓                                          │
│  Ollama → Parse → Patches                       │
│      ↓                                          │
│  Safety Check → Block Dangerous                 │
│      ↓                                          │
│  AST Patch OR Full Write                         │
│      ↓                                          │
│  Backup → .bak Files                            │
│      ↓                                          │
│  Apply → Write to Files                         │
│      ↓                                          │
│  Test Runner → pytest                           │
│      ↓                                          │
│  Pass?                                         │
│    ↓ Yes         ↓ No                            │
│  Commit         Rollback                         │
│    ↓              ↓                              │
│  Continue       Retry (MAX_RETRIES)              │
│                  ↓                               │
│              Give Up                             │
│                                                 │
└─────────────────────────────────────────────────┘
```

## Example Scenario

### Task: "Fix the bug in calculate_total function"

**Ollama extracts:**
```json
{
  "file": "src/calculator.py",
  "action": "ast_patch",
  "target_function": "calculate_total",
  "new_code": "def calculate_total(amount):\n    return amount * 1.1"
}
```

**Agent:**
1. Parses calculator.py AST
2. Finds `calculate_total` function
3. Replaces function body
4. Runs pytest
5. If tests pass → commit
6. If tests fail → rollback → retry

## Troubleshooting

### "AST patch failed"
- Function not found in file
- AST parsing error
- Try full file write instead

### "Tests failed, max retries reached"
- Changes break tests
- Ollama generated bad code
- Review changes manually

### "pytest not found"
- Install pytest: `pip install pytest`
- Add tests to your repo

### "Git commit failed"
- Git not initialized
- No changes to commit
- Git configuration issue

## Configuration Examples

### More Retries
```python
MAX_RETRIES = 5
```

### Different Test Command
```python
TEST_COMMAND = "pytest tests/ -v"
```

### Skip Auto Commit
```python
# Comment out commit section in run()
```

## Prerequisites

### Required in Repo
1. **Git initialized**
   ```bash
   git init
   ```

2. **Pytest tests**
   ```bash
   mkdir tests
   touch tests/test_example.py
   ```

3. **Working environment**
   - Ollama running
   - ChatGPT open in browser
   - Repo has tests

## Files Created

1. `agent_ast.py` - AST-aware agent with test runner
2. `AGENT_AST_SETUP.md` - Setup guide
3. `AGENT_AST_SUMMARY.md` - This summary

## Status

**Current State:** ✅ Working AST-aware agent
**Next Level:** Multi-step planning memory
**Production-Ready:** ⚠️ Needs more test coverage

## Evolution Summary

### Phase 1: Paste Agent (Obsolete)
- Copy → paste to IDE
- No file awareness
- No validation

### Phase 2: Patch Agent (Current Alternative)
- File-specific changes
- Safety checks
- Rollback capability

### Phase 3: AST Agent (Current Recommended)
- Surgical function edits
- Test validation
- Failure loop
- Auto commit

### Phase 4: Next Level (Future)
- Multi-step planning
- Dependency resolution
- State tracking

## Reality Check

This agent can:
- Surgically edit specific functions
- Validate changes with tests
- Retry until tests pass
- Automatically commit working code

**But it still:**
- Limited to function-level AST edits
- Requires existing tests
- Can't plan multi-step tasks

**Monitor the agent.** Watch what it does.

## Next Level

To make this a full autonomous engineer:

**"Add multi-step planning memory and dependency resolution for complex multi-file tasks"**
