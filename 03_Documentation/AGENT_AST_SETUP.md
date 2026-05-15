# AST-Aware Agent with Test Runner - Setup Guide

## Overview

This is the **serious autonomous system** upgrade from the patch-based agent.

**What's New:**
- AST-aware patching (surgical edits, not full file overwrites)
- Test runner (pytest validation)
- Failure loop (retries until tests pass)
- Automatic git commits on success

## Build Status

✅ Extract structured patches from ChatGPT
✅ AST-aware patching (surgical function edits)
✅ Apply changes directly to files
✅ Backup files before modifying
✅ Run pytest to validate changes
✅ Failure loop (retry until tests pass)
✅ Automatic git commit on success
✅ Rollback on test failure
⚠️ Requires pytest tests in repo
⚠️ AST parsing limited to function-level edits

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
# Install Python dependencies
pip install playwright requests pytest
playwright install

# Install Ollama
brew install ollama
ollama run llama3

# Make sure Ollama is running
ollama serve
```

## Configuration

Edit in `agent_ast.py`:

```python
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
REPO_PATH = os.getcwd()
LOOP_LIMIT = 10
MAX_RETRIES = 3
TEST_COMMAND = "pytest -xvs"
```

## Usage

### Before Running

1. Open ChatGPT in browser (logged in)
2. Navigate to your repo directory
3. Make sure git is initialized
4. **IMPORTANT:** Have pytest tests in your repo

### Run Agent

```bash
cd /path/to/your/repo
python agent_ast.py
```

## How It Works

### Loop Flow

```
1. Extract ChatGPT message (Playwright)
   ↓
2. Parse into patches (Ollama)
   ↓
3. For each change:
   - Safety check
   - AST-aware patch OR full file write
   - Backup
   ↓
4. Run pytest
   ↓
5. If tests pass:
   - Commit changes
   - Continue
   ↓
6. If tests fail:
   - Rollback
   - Retry (up to MAX_RETRIES)
   ↓
7. If max retries reached:
   - Give up
   - Move to next iteration
```

### Patch Format

Ollama extracts changes in this format:

```json
{
  "changes": [
    {
      "file": "path/to/file.py",
      "action": "create|update|ast_patch",
      "content": "full new file content",
      "target_function": "function_name",  // for ast_patch only
      "new_code": "new function code"      // for ast_patch only
    }
  ]
}
```

### AST-Aware Patching

Instead of overwriting entire files, the agent can surgically edit specific functions:

```python
def apply_ast_patch(file_path, target_function, new_code):
    # Parse file AST
    tree = ast.parse(source)
    
    # Find target function
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == target_function:
            # Replace function body
            node.body = new_func.body
            
    # Convert back to source
    new_source = ast.unparse(tree)
```

**Benefits:**
- Surgical edits (not full file overwrites)
- Preserves file structure
- Less destructive
- More precise

### Test Runner

Uses pytest to validate changes:

```python
def run_tests():
    result = subprocess.run(
        "pytest -xvs".split(),
        capture_output=True,
        cwd=REPO_PATH
    )
    return result.returncode == 0
```

**Flags:**
- `-x` - Stop on first failure
- `-v` - Verbose output
- `-s` - Show print statements

### Failure Loop

If tests fail, the agent:
1. Rolls back changes (restores .bak files)
2. Waits 2 seconds
3. Retries (up to MAX_RETRIES)
4. If max retries reached, gives up

```python
for retry in range(MAX_RETRIES):
    apply_changes()
    if run_tests():
        break  # Success
    else:
        rollback()  # Retry
```

### Automatic Git Commit

If tests pass, the agent automatically commits:

```bash
git add .
git commit -m "Agent: automated changes"
```

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

❌ AST parsing limited to function-level (can't edit classes/modules)
❌ Requires pytest tests in repo
❌ No dependency resolution
❌ No multi-step planning memory
❌ No semantic diffing

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

## Example Scenarios

### Scenario 1: Function Edit

**ChatGPT says:**
"Change the `calculate_total` function to include tax"

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
4. Runs tests
5. If tests pass, commits

### Scenario 2: Test Failure

**Agent applies changes → Tests fail**

**Agent:**
1. Rolls back (restores .bak files)
2. Waits 2 seconds
3. Retries (up to 3 times)
4. If still failing, gives up

## Troubleshooting

### "No changes found"
- ChatGPT message doesn't contain file changes
- Ollama failed to parse patches
- Check prompt format

### "AST patch failed"
- Function not found in file
- AST parsing error
- Try full file write instead

### "Tests failed, max retries reached"
- Changes break tests
- Ollama generated bad code
- Review changes manually
- Adjust prompt or retry manually

### "pytest not found"
- Install pytest: `pip install pytest`
- Add tests to your repo
- Update TEST_COMMAND if needed

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
TEST_COMMAND = "pytest"
TEST_COMMAND = "python -m pytest"
TEST_COMMAND = "pytest tests/ -v"
```

### Skip Auto Commit
```python
# Comment out commit section in run()
```

### Different Model
```python
MODEL = "llama3:70b"  # More accurate
MODEL = "mistral"      # Faster
```

## Prerequisites

### Required in Repo
1. **Git initialized**
   ```bash
   git init
   ```

2. **Pytest tests**
   ```bash
   # Create tests/ directory
   mkdir tests
   
   # Create test file
   touch tests/test_example.py
   
   # Add tests
   # def test_something():
   #     assert True
   ```

3. **Working environment**
   - Ollama running
   - ChatGPT open in browser
   - Repo has tests to validate

## Files Created

1. `agent_ast.py` - AST-aware agent with test runner
2. `AGENT_AST_SETUP.md` - This setup guide

## Status

**Current State:** ✅ Working AST-aware agent
**Next Level:** Multi-step planning memory
**Production-Ready:** ⚠️ Needs more test coverage and error handling

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
- No dependency resolution

**Monitor the agent.** Watch what it does. This is powerful but not infallible.

## Next Level

To make this a full autonomous engineer:

**Add multi-step planning memory and dependency resolution**

This adds:
- Task planning across multiple files
- Dependency analysis
- State tracking
- Complex multi-step execution
