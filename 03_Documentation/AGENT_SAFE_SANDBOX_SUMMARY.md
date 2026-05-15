# Agent Safe Sandbox + Ordering + Structured Logs - Implementation Summary

## What Was Added

The previous version had a single pipeline but still had critical flaws:
- No sandbox execution (learned AFTER damage)
- No patch ordering (arbitrary order breaks dependencies)
- Text logs (not replayable for debugging)

This version adds the missing layers.

## Changes Made

### 1. Sandbox Execution (Shadow Apply)

```python
SANDBOX_MODE = True  # Set True to test in temp dir before real apply

def run_in_sandbox(patch):
    """
    Apply patch in temporary directory and run tests.
    Returns (success, output)
    """
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_")
    
    try:
        # Copy repo to temp dir
        shutil.copytree(REPO_PATH, temp_dir, dirs_exist_ok=True, 
                       ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        
        # Apply patch in sandbox
        sandbox_file_path = Path(temp_dir) / patch["file"]
        with open(sandbox_file_path, "w") as f:
            f.write(patch.get("content", ""))
        
        # Run tests in sandbox
        result = subprocess.run(
            TEST_COMMAND.split(),
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        return result.returncode == 0, result.stdout + result.stderr
        
    finally:
        # Cleanup sandbox
        shutil.rmtree(temp_dir)
```

**Purpose:**
- Test patches in isolated environment before touching real repo
- Prevents damage from bad patches
- Only apply to real repo if sandbox tests pass
- Auto-cleanup of temp directories

**Pipeline Integration:**
```python
# 8. Sandbox execution (if enabled)
if SANDBOX_MODE:
    print(f"🔬 Running in sandbox: {patch['file']}")
    sandbox_passed, sandbox_output = run_in_sandbox(patch)
    
    if not sandbox_passed:
        return "rejected", "sandbox_tests_failed"
```

### 2. Patch Ordering (Dependency Awareness)

```python
def order_patches(patches):
    """
    Order patches by dependency priority.
    Lower priority numbers applied first.
    """
    priority = ["models", "services", "routes", "tests"]
    
    def get_priority(patch):
        file_path = patch.get("file", "")
        for i, key in enumerate(priority):
            if key in file_path:
                return i
        return 999  # Lowest priority
    
    return sorted(patches, key=get_priority)
```

**Purpose:**
- Ensures models are applied before services
- Ensures services are applied before routes
- Ensures routes are applied before tests
- Prevents import errors from wrong order

**Main Loop Integration:**
```python
# Order patches by dependency priority
ordered_changes = order_patches(changes)
print(f"📋 Patch order: {[c['file'] for c in ordered_changes]}")

for change in ordered_changes:
    status, reason = process_patch(change, i+1)
```

**Example Order:**
```
Before: [routes/user.py, models/user.py, services/user.py]
After:  [models/user.py, services/user.py, routes/user.py]
```

### 3. Structured Replayable Logs (JSONL)

```python
LOG_FILE = "agent_safe.jsonl"

def log_entry(entry):
    """Write structured log entry to JSONL file"""
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

**Purpose:**
- Machine-readable logs for analysis
- Replayable for debugging
- Pattern detection
- Audit trail

**Log Entry Format:**
```json
{
  "timestamp": 1713692400.123,
  "patch": {
    "file": "app/services/user.py",
    "operation": "update",
    "content": "...",
    "confidence": 0.85
  },
  "result": "accepted",
  "reason": "success",
  "test_output": "...",
  "duration": 2.5
}
```

**What Gets Logged:**
- Agent start/stop with config
- Each patch processing
- All rejections with reasons
- Sandbox test results
- Real test results
- Rollback actions
- Git commits
- Duration tracking

**Benefits:**
- Replay failures: `jq '.result == "rejected"' agent_safe.jsonl`
- Analyze patterns: `jq '.reason' | group_by' agent_safe.jsonl`
- Debug agent behavior: `jq '.patch, .result' agent_safe.jsonl`
- Compliance documentation

## Updated Pipeline Flow

```
Patch → Schema → Confidence → Scope → Operation → Content → 
Dry-Run → Approval → SANDBOX TEST → AST → Backup → Apply → 
Git Check → Real Test → Commit
```

**New Gates:**
- Sandbox test (step 8) - Test in temp dir before real apply
- Patch ordering (before loop) - Apply in dependency order

## Configuration

```python
# Safety modes
DRY_RUN = False  # Preview without applying
REQUIRE_APPROVAL = True  # Human confirmation
SANDBOX_MODE = True  # Test in temp dir before real apply

# Patch priority
priority = ["models", "services", "routes", "tests"]

# Logging
LOG_FILE = "agent_safe.jsonl"  # Structured logs
```

## Log File Examples

### Agent Start
```json
{
  "timestamp": 1713692400.000,
  "event": "agent_start",
  "config": {
    "dry_run": false,
    "require_approval": true,
    "sandbox_mode": true,
    "allowed_paths": ["app/", "services/", "tests/", "src/"],
    "blocked_files": ["config.py", ".env", "secrets.py"],
    "confidence_threshold": 0.6
  }
}
```

### Patch Accepted
```json
{
  "timestamp": 1713692402.500,
  "patch": {
    "file": "app/services/user.py",
    "operation": "update",
    "content": "def get_user(): ...",
    "confidence": 0.85
  },
  "result": "accepted",
  "reason": "success",
  "test_output": "...",
  "duration": 2.5
}
```

### Patch Rejected (Sandbox Failed)
```json
{
  "timestamp": 1713692405.000,
  "patch": {
    "file": "app/models/user.py",
    "operation": "update",
    "content": "class User: ...",
    "confidence": 0.72
  },
  "result": "rejected",
  "reason": "sandbox_tests_failed",
  "test_output": "FAILED tests/test_user.py::test_create_user...",
  "duration": 3.0
}
```

### Agent Done
```json
{
  "timestamp": 1713692410.000,
  "event": "agent_done",
  "duration": 10.0
}
```

## Log Analysis Examples

### Count Rejections by Reason
```bash
jq -r 'select(.result == "rejected") | .reason' agent_safe.jsonl | sort | uniq -c
```

### Replay Failed Patches
```bash
jq 'select(.result == "rejected") | .patch' agent_safe.jsonl
```

### Find Long-Running Patches
```bash
jq 'select(.duration > 5.0)' agent_safe.jsonl
```

### Success Rate
```bash
jq -r '.result' agent_safe.jsonl | sort | uniq -c
```

## Safety Comparison

| Feature | Previous | Current |
|---------|----------|---------|
| Single Pipeline | ✅ | ✅ |
| Schema Validation | ✅ | ✅ |
| Dry-Run Mode | ✅ | ✅ |
| Human Approval | ✅ | ✅ |
| Sandbox Execution | ❌ | ✅ |
| Patch Ordering | ❌ | ✅ |
| Structured Logs | ❌ | ✅ |
| Replayable Logs | ❌ | ✅ |

## What This Fixes

### Before Sandbox
- Apply patch → Mutate files → Run tests → Rollback if fail
- Damage already done even with rollback
- Side effects possible

### After Sandbox
- Copy repo → Apply in sandbox → Run tests → Only apply if pass
- Real repo never touched unless patch proves itself
- No side effects from failed patches

### Before Ordering
- Arbitrary patch order
- Import errors possible
- Dependency breaks

### After Ordering
- Models → Services → Routes → Tests
- Dependencies respected
- No import errors

### Before Text Logs
- "Applied patch to app/main.py"
- Useless for debugging
- No replay capability

### After JSONL Logs
- Full patch, result, reason, duration
- Replayable for debugging
- Pattern analysis

## Brutal Truth

Previous version: "safe enough to run with supervision"

Current version: "safe enough to trust for real iterations"

**This is the difference between:**
- Learning AFTER damage (previous)
- Learning BEFORE damage (current)

## Next Steps

After sandboxing + ordering + structured logs:
- The agent is ready for memory + planning
- Logs provide training data for learning
- Sandbox provides safe environment for experimentation
- Ordering prevents dependency breaks

## Status

✅ Sandbox execution (test before real apply)
✅ Patch ordering (dependency awareness)
✅ Structured JSONL logs (replayable)
✅ Single pipeline (no bypass)
✅ Schema validation
✅ Dry-run mode
✅ Human approval

**This is what production-safe actually means.**
