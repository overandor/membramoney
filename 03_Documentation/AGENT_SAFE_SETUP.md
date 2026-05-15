# Safe AST-Aware Agent - Setup Guide

## Overview

This is the **production-safe** upgrade to the AST agent. It adds the critical safety layer that separates "cool demo" from "doesn't nuke your repo at 3am."

## What Was Added

### Safety Layer (The Missing Piece)

1. **Single Pipeline Function**
   - ALL patches must go through `process_patch()`
   - Deterministic order of safety checks
   - No way to bypass any check
   - Clear rejection reasons

2. **Patch Schema Validation**
   - Strict schema enforcement
   - Required fields: file, operation
   - Type checking
   - Rejects malformed patches

3. **Safety Mode Toggles**
   - DRY_RUN mode - Preview changes without applying
   - REQUIRE_APPROVAL - Human confirmation before applying
   - Configurable safety levels

4. **Structured Logging**
   - Real logging to `agent_safe.log`
   - Timestamps and levels
   - Audit trail of all actions
   - Not just print statements

5. **File Scope Guard**
   - ALLOWED_PATHS - Only modify files in these directories
   - BLOCKED_FILES - Never modify these files
   - Enforced before any change

6. **Operation Type Enforcement**
   - Must declare operation type (create, update, ast_patch, function_update)
   - Rejects unknown operation types
   - Prevents accidental full file overwrites

7. **AST Safety Validation**
   - Validate AST before patching
   - Validate AST after patching
   - Ensure target function still exists
   - Rejects invalid Python

8. **Smarter Test Loop**
   - Captures test output
   - Feeds failure back to Ollama
   - Gets fix suggestions
   - Can abort based on feedback

9. **Git Diff Constraint Check**
   - Max files per iteration (5)
   - Max diff size (10,000 chars)
   - Rejects large changes

10. **Confidence Kill Switch**
    - Ollama must provide confidence score
    - Reject if confidence < 0.6
    - Prevents low-confidence changes

## Build Status

✅ Single pipeline function (all patches go through)
✅ Patch schema validation (strict format enforcement)
✅ Safety mode toggles (dry-run, approval)
✅ Structured logging (agent_safe.log)
✅ Extract structured patches from ChatGPT
✅ Confidence scoring with kill switch
✅ File scope guard (allowed/blocked paths)
✅ Operation type enforcement
✅ AST safety validation (before/after)
✅ Apply changes with safety checks
✅ Backup files before modifying
✅ Smarter test runner with feedback loop
✅ Git diff constraint check
✅ Failure loop with Ollama feedback
✅ Automatic git commit on success
✅ Rollback on constraint violation
⚠️ Still no dependency resolution
⚠️ No environment awareness
⚠️ No long-term memory

## Configuration

```python
# Safety modes
DRY_RUN = False  # Set True to preview changes without applying
REQUIRE_APPROVAL = True  # Set False for full autonomy (NOT RECOMMENDED)
SANDBOX_MODE = True  # Set True to test in temp dir before real apply

# Safety constraints
ALLOWED_PATHS = ["app/", "services/", "tests/", "src/"]
BLOCKED_FILES = ["config.py", ".env", "secrets.py", "settings.py"]
ALLOWED_OPERATIONS = ["create", "update", "ast_patch", "function_update"]
MAX_FILES_PER_ITERATION = 5
MAX_DIFF_SIZE = 10000
CONFIDENCE_THRESHOLD = 0.6

# Agent config
LOOP_LIMIT = 10
MAX_RETRIES = 3
TEST_COMMAND = "pytest -q"

# Logging
LOG_FILE = "agent_safe.jsonl"  # Structured replayable logs
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
python agent_safe.py
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│              Safety Layer                        │
├─────────────────────────────────────────────────┤
│                                                 │
│  SINGLE PIPELINE (process_patch function)       │
│                                                 │
│  1. Schema Validation                            │
│     - Required fields: file, operation          │
│     - Type checking                              │
│     - Reject malformed patches                  │
│                                                 │
│  2. Confidence Check                             │
│     - Must be > 0.6                             │
│     - Otherwise abort                            │
│                                                 │
│  3. File Scope Guard                            │
│     - Only allowed paths                         │
│     - Blocked files rejected                     │
│                                                 │
│  4. Operation Enforcement                        │
│     - Must be valid operation type               │
│     - Unknown types rejected                     │
│                                                 │
│  5. Content Safety                              │
│     - No dangerous operations                    │
│     - No rm -rf, exec, eval                     │
│                                                 │
│  6. Dry-Run Mode (if enabled)                   │
│     - Preview changes only                      │
│     - No modifications                           │
│                                                 │
│  7. Human Approval (if required)                │
│     - Press Enter to apply                       │
│     - Ctrl+C to abort                            │
│                                                 │
│  8. Sandbox Execution (if enabled)              │
│     - Copy repo to temp dir                     │
│     - Apply patch in sandbox                     │
│     - Run tests in sandbox                      │
│     - Only apply to real if pass                 │
│                                                 │
│  9. AST Validation                              │
│     - Validate before patching                   │
│     - Validate after patching                    │
│     - Target must still exist                    │
│                                                 │
│  10. Backup                                     │
│     - Create .bak file                          │
│     - Before modification                        │
│                                                 │
│  11. Apply Patch                                │
│     - Write changes to file                     │
│                                                 │
│  12. Git Constraints                            │
│     - Max files per iteration                   │
│     - Max diff size                              │
│     - Reject if exceeded                        │
│                                                 │
│  13. Test Run                                   │
│     - Run pytest                                │
│     - Validate code works                       │
│                                                 │
│  14. Commit or Rollback                         │
│     - If tests pass → commit                    │
│     - If tests fail → rollback                   │
│                                                 │
└─────────────────────────────────────────────────┘

PATCH ORDERING (before pipeline):
  models → services → routes → tests
```

## Safety Modes

### Dry-Run Mode
```python
DRY_RUN = True
```
- Previews changes without applying
- Shows file, operation, content length, confidence
- Safe for testing and review
- No modifications to files

### Human Approval Mode
```python
REQUIRE_APPROVAL = True
```
- Requires manual confirmation before applying
- Shows patch details
- Press Enter to apply, Ctrl+C to abort
- Default and recommended setting

### Autonomous Mode (NOT RECOMMENDED)
```python
DRY_RUN = False
REQUIRE_APPROVAL = False
```
- No human intervention
- Fully automated
- High risk
- Only use after extensive testing

### Sandbox Mode
```python
SANDBOX_MODE = True
```
- Tests patches in temporary directory before real apply
- Prevents damage from bad patches
- Only applies to real repo if sandbox tests pass
- Auto-cleanup of temp directories
- Recommended for all production use

## Log File

All agent actions are logged to two files:

### Text Log (`agent_safe.log`)
```
2026-04-21 11:50:00 - INFO - Agent started
2026-04-21 11:50:05 - INFO - Iteration 1: Processing patch for app/services/user.py
2026-04-21 11:50:06 - INFO - Backup created: app/services/user.py.bak
2026-04-21 11:50:07 - INFO - Patch applied: app/services/user.py
2026-04-21 11:50:10 - INFO - Patch accepted and committed: app/services/user.py
2026-04-21 11:50:11 - INFO - Changes committed successfully
2026-04-21 11:50:12 - INFO - Agent finished
```

### Structured JSONL Log (`agent_safe.jsonl`)
```json
{"timestamp": 1713692400.000, "event": "agent_start", "config": {...}}
{"timestamp": 1713692402.500, "patch": {...}, "result": "accepted", "reason": "success", "duration": 2.5}
{"timestamp": 1713692405.000, "patch": {...}, "result": "rejected", "reason": "sandbox_tests_failed", "duration": 3.0}
{"timestamp": 1713692410.000, "event": "agent_done", "duration": 10.0}
```

**What gets logged:**
- Agent start/stop with config
- Each patch processing
- All rejections with reasons
- Sandbox test results
- Real test results
- Rollback actions
- Git commits
- Duration tracking

**Benefits:**
- Audit trail of all actions
- Replayable for debugging
- Pattern analysis
- Compliance documentation
- Incident investigation

**Log Analysis Examples:**
```bash
# Count rejections by reason
jq -r 'select(.result == "rejected") | .reason' agent_safe.jsonl | sort | uniq -c

# Replay failed patches
jq 'select(.result == "rejected") | .patch' agent_safe.jsonl

# Find long-running patches
jq 'select(.duration > 5.0)' agent_safe.jsonl

# Success rate
jq -r '.result' agent_safe.jsonl | sort | uniq -c
```

## How It Works

### 1. Confidence Kill Switch

Ollama must provide confidence score:

```json
{
  "decision": "apply",
  "confidence": 0.72
}
```

If confidence < 0.6 → abort

### 2. File Scope Guard

```python
ALLOWED_PATHS = ["app/", "services/", "tests/"]
BLOCKED_FILES = ["config.py", ".env", "secrets.py"]

def is_safe_path(file_path):
    # Must be in allowed paths
    # Must not be blocked file
    return any(path.startswith(p) for p in ALLOWED_PATHS)
```

### 3. Operation Type Enforcement

Must declare operation type:

```json
{
  "operation": "ast_patch",
  "target_function": "process_order"
}
```

Allowed: create, update, ast_patch, function_update

### 4. AST Safety Validation

**Before patching:**
```python
def validate_ast(source):
    ast.parse(source)  # Will raise if invalid
```

**After patching:**
```python
def validate_ast_after_patch(file_path, target):
    # Parse patched file
    # Check target function still exists
```

### 5. Smarter Test Loop

```python
# Run tests
success, output = run_tests()

if not success:
    # Feed failure to Ollama
    fix = fix_with_feedback(output, last_patch)
    
    if fix["decision"] == "abort":
        break
```

### 6. Git Diff Constraints

```python
# Check file count
if changed_files > 5:
    rollback()

# Check diff size
if len(diff) > 10000:
    rollback()
```

## Comparison

| Feature | AST Agent | Safe Agent |
|---------|-----------|------------|
| Single Pipeline | ❌ | ✅ |
| Schema Validation | ❌ | ✅ |
| Dry-Run Mode | ❌ | ✅ |
| Human Approval | ❌ | ✅ |
| Sandbox Execution | ❌ | ✅ |
| Patch Ordering | ❌ | ✅ |
| Bundle Execution | ❌ | ✅ |
| Atomic Rollback | ❌ | ✅ |
| Bundle-Level Logs | ❌ | ✅ |
| Structured JSONL Logs | ❌ | ✅ |
| Confidence Scoring | ❌ | ✅ |
| File Scope Guard | ❌ | ✅ |
| Operation Enforcement | ❌ | ✅ |
| AST Validation | ❌ | ✅ |
| Content Safety | ✅ | ✅ |
| Git Constraints | ❌ | ✅ |
| Test Feedback | ❌ | ✅ |
| Smart Retry | ❌ | ✅ |

## What It Prevents

### Before (AST Agent)
- Could modify any file
- Could rewrite entire files
- No confidence threshold
- Blind retries on test failure
- No git diff limits

### After (Safe Agent)
- Only modifies allowed paths
- Blocks config/secrets files
- Requires confidence > 0.6
- Gets fix suggestions from Ollama
- Limits files per iteration
- Limits diff size
- Validates AST before/after

## Example Scenarios

### Scenario 1: Blocked File

**Ollama tries:**
```json
{
  "file": "config.py",
  "operation": "update",
  "content": "..."
}
```

**Agent:**
```
🚫 Blocked file: config.py
Rejected
```

### Scenario 2: Low Confidence

**Ollama returns:**
```json
{
  "decision": "apply",
  "confidence": 0.4
}
```

**Agent:**
```
🧠 Decision: apply, Confidence: 0.4
🛑 Agent aborted (low confidence)
```

### Scenario 3: Too Many Files

**Ollama tries to modify 10 files**

**Agent:**
```
🚫 Too many changes: 10 > 5
Rejected
```

### Scenario 4: Test Failure with Feedback

**Tests fail → Agent:**
1. Rolls back
2. Feeds test output to Ollama
3. Gets fix suggestion
4. Retries with fix
5. If Ollama says abort → stops

## Configuration Examples

### Stricter Scope
```python
ALLOWED_PATHS = ["app/services/"]
BLOCKED_FILES = ["config.py", "settings.py", "main.py"]
```

### Higher Confidence
```python
CONFIDENCE_THRESHOLD = 0.8
```

### More Permissive
```python
MAX_FILES_PER_ITERATION = 10
MAX_DIFF_SIZE = 50000
```

### Different Test Command
```python
TEST_COMMAND = "pytest -xvs"
```

## Troubleshooting

### "Agent aborted (low confidence)"
- Ollama confidence < 0.6
- Try lowering threshold if needed
- Review why confidence is low

### "Blocked file"
- File in BLOCKED_FILES list
- Remove from list if safe
- Or move file to allowed path

### "Path not in allowed scope"
- File not in ALLOWED_PATHS
- Add path to allowed list
- Or change file location

### "Invalid AST"
- Generated code is invalid Python
- Ollama generated bad code
- Agent rejects and rolls back

### "Too many files changed"
- More than 5 files in one iteration
- Increase MAX_FILES_PER_ITERATION
- Or split into smaller changes

## What Still Doesn't Work

❌ No dependency resolution
- Imports may break
- Missing packages

❌ No environment awareness
- Config assumptions
- Secrets
- Runtime differences

❌ No long-term memory
- It forgets previous mistakes
- No learning from failures

## Files Created

1. `agent_safe.py` - Safe AST-aware agent with safety layer
2. `AGENT_SAFE_SETUP.md` - This setup guide

## Status

**Current State:** ✅ Bundle-aware agent with atomic multi-file execution
**Next Level:** Task memory + multi-step planning (ready to implement)
**Production-Ready:** ✅ Safe for real iterations with bundles + sandbox + ordering + logs

## Brutal Truth

The previous "safe agent" had scattered safety checks that could be bypassed.

This version has:
- A SINGLE pipeline function that ALL patches must go through
- NO way to bypass any safety check
- Deterministic order of operations
- Real logging for audit trail
- Dry-run mode for safe testing
- Human approval by default
- Sandbox execution to prevent damage
- Patch ordering to respect dependencies
- Structured JSONL logs for replay/debug

**This is what "safe" actually means.**

## Reality Check

This agent:
- ✅ Has confidence threshold
- ✅ Guards file scope
- ✅ Enforces operation types
- ✅ Validates AST
- ✅ Limits changes
- ✅ Gets feedback on failures
- ✅ Rollbacks on failure
- ✅ Tests in sandbox before real apply
- ✅ Orders patches by dependency
- ✅ Logs structured replayable data

But:
- ⚠️ Still no dependency resolution
- ⚠️ No environment awareness
- ⚠️ No long-term memory (ready to add)

**Monitor the agent.** The safety layer reduces risk but doesn't eliminate it.

## Next Level

To make this a full autonomous engineer:

**"Add task memory + multi-step planning with checkpointing"**

This adds:
- Task planning across multiple files
- Dependency analysis
- State tracking
- Complex multi-step execution
- Checkpoint/restore capability

## Which Agent to Use?

| Need | Use Agent |
|------|-----------|
| Maximum safety, production | agent_safe.py |
| AST edits with tests | agent_ast.py |
| Simple file changes | agent_patch.py |
| Review workflow | agent.py |

**Recommendation:** Use `agent_safe.py` for any autonomous execution. The safety layer is critical.
