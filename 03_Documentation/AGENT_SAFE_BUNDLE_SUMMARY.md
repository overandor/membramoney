# Agent Safe Bundle Execution - Implementation Summary

## What Was Added

The previous version had sandbox execution and patch ordering, but still treated patches as independent operations. This version adds bundle execution for atomic multi-file changes.

## Problem Solved

### Previous Issue
Patches were treated as independent operations:
```python
[
  {"file": "models/user.py"},
  {"file": "services/user.py"},
  {"file": "routes/user.py"}
]
```

If one failed, the others might have already been applied, leaving the repo in a broken state.

### Solution
Treat related patches as atomic bundles:
```python
{
  "bundle_id": "user_feature_update",
  "changes": [
    {"file": "models/user.py"},
    {"file": "services/user.py"},
    {"file": "routes/user.py"}
  ]
}
```

**All patches succeed together or rollback together.**

## Changes Made

### 1. Bundle Sandbox Execution

```python
def run_bundle_in_sandbox(patches):
    """
    Apply multiple patches in sandbox as a bundle and run tests.
    """
    temp_dir = tempfile.mkdtemp(prefix="agent_bundle_sandbox_")
    
    # Copy repo to temp dir
    # Apply ALL patches in sandbox (in order)
    # Run tests
    # Cleanup
    return success, output
```

**Purpose:** Test entire bundle in sandbox before real apply. Ensures all patches work together.

### 2. Bundle Execution Function

```python
def process_bundle(bundle, iteration):
    """
    Process a bundle of patches as an atomic unit.
    All patches in bundle succeed together or rollback together.
    """
    bundle_id = bundle.get("bundle_id", f"bundle_{iteration}_{int(time.time())}")
    patches = bundle.get("changes", [])
    
    # Order patches by dependency
    ordered_patches = order_patches(patches)
    
    # Schema validation for ALL patches
    for patch in ordered_patches:
        if not validate_patch_schema(patch):
            return False, "schema_validation_failed"
    
    # Sandbox execution for ENTIRE bundle
    if SANDBOX_MODE:
        sandbox_passed, sandbox_output = run_bundle_in_sandbox(ordered_patches)
        if not sandbox_passed:
            return False, "sandbox_tests_failed"
    
    # Dry-run mode
    if DRY_RUN:
        return True, "dry_run"
    
    # Human approval
    if REQUIRE_APPROVAL:
        input("Press Enter to apply bundle...")
    
    # Apply ALL patches to real repo (atomic)
    for patch in ordered_patches:
        backup_file(patch)
        apply_patch(patch)
    
    # Git diff check
    if not check_diff_constraints():
        rollback()
        return False, "diff_constraints_violated"
    
    # Run tests
    if not tests_passed:
        rollback()
        return False, "tests_failed"
    
    return True, "success"
```

**Purpose:** Atomic execution of multi-file changes. One decision, one outcome.

### 3. Bundle-Level Logging

```python
log_entry({
    "timestamp": bundle_start_time,
    "bundle_id": bundle_id,
    "result": "applied",
    "reason": "success",
    "patch_count": len(patches),
    "sandbox_passed": SANDBOX_MODE,
    "test_output": test_output[:500],
    "duration": time.time() - bundle_start_time
})
```

**Purpose:** Log at bundle level, not just patch level. Debug scenes, not frames.

### 4. Main Loop Bundle Support

```python
# Group changes into bundles
if "bundles" in parsed:
    bundles = parsed["bundles"]
else:
    # Create single bundle from all changes
    bundles = [{
        "bundle_id": f"bundle_{i}_{int(time.time())}",
        "changes": changes
    }]

# Process each bundle
for bundle in bundles:
    success, reason = process_bundle(bundle, i+1)
    if not success:
        break
```

**Purpose:** Support explicit bundles from LLM, or auto-group changes.

## Bundle Format

### Explicit Bundles (from LLM)
```json
{
  "decision": "apply",
  "confidence": 0.85,
  "bundles": [
    {
      "bundle_id": "add_user_auth_feature",
      "changes": [
        {"file": "app/models/user.py", "operation": "update", "content": "..."},
        {"file": "app/services/auth.py", "operation": "update", "content": "..."},
        {"file": "app/routes/auth.py", "operation": "create", "content": "..."}
      ]
    }
  ]
}
```

### Auto-Grouped (fallback)
```json
{
  "decision": "apply",
  "confidence": 0.85,
  "changes": [
    {"file": "app/models/user.py", "operation": "update", "content": "..."},
    {"file": "app/services/auth.py", "operation": "update", "content": "..."}
  ]
}
```

Agent auto-groups into single bundle if no explicit bundles provided.

## Bundle Execution Flow

```
Bundle → Order Patches → Schema Validate All → 
Sandbox Test Bundle → Dry-Run (if enabled) → 
Human Approval (if required) → Apply All → 
Git Check → Test → Commit or Rollback All
```

**Atomic guarantee:** All patches apply together or rollback together.

## Bundle-Level Log Examples

### Bundle Applied
```json
{
  "timestamp": 1713692400.000,
  "bundle_id": "add_user_auth_feature",
  "result": "applied",
  "reason": "success",
  "patch_count": 3,
  "sandbox_passed": true,
  "test_output": "...",
  "duration": 3.2
}
```

### Bundle Rejected (Sandbox Failed)
```json
{
  "timestamp": 1713692405.000,
  "bundle_id": "add_user_auth_feature",
  "result": "rejected",
  "reason": "sandbox_tests_failed",
  "test_output": "FAILED tests/test_auth.py...",
  "patch_count": 3,
  "duration": 5.0
}
```

### Bundle Reverted (Tests Failed)
```json
{
  "timestamp": 1713692410.000,
  "bundle_id": "add_user_auth_feature",
  "result": "reverted",
  "reason": "tests_failed",
  "test_output": "FAILED tests/test_user.py...",
  "patch_count": 3,
  "duration": 5.5
}
```

## Log Analysis Examples

### Bundle Success Rate
```bash
jq -r 'select(.bundle_id) | .result' agent_safe.jsonl | sort | uniq -c
```

### Failed Bundles
```bash
jq 'select(.result == "rejected" or .result == "reverted") | {bundle_id, reason}' agent_safe.jsonl
```

### Bundle Duration Analysis
```bash
jq 'select(.bundle_id) | {bundle_id, duration}' agent_safe.jsonl
```

### Sandbox vs Real Test Comparison
```bash
jq 'select(.bundle_id) | {bundle_id, sandbox_passed, result}' agent_safe.jsonl
```

## Safety Comparison

| Feature | Previous | Current |
|---------|----------|---------|
| Single Pipeline | ✅ | ✅ |
| Schema Validation | ✅ | ✅ |
| Sandbox Execution | ✅ (per patch) | ✅ (per bundle) |
| Patch Ordering | ✅ | ✅ |
| Bundle Execution | ❌ | ✅ |
| Atomic Rollback | ❌ | ✅ |
| Bundle-Level Logs | ❌ | ✅ |
| Structured JSONL Logs | ✅ | ✅ |

## What This Fixes

### Before Bundle Execution
- Patches applied independently
- If one fails, others might be applied
- Repo in broken state
- Rollback partial

### After Bundle Execution
- Patches applied as atomic unit
- If one fails, all rollback
- Repo always consistent
- No half-applied garbage

## Example Scenario

### Feature Update Across 3 Files
```python
bundle = {
    "bundle_id": "add_user_email_field",
    "changes": [
        {"file": "app/models/user.py", "content": "class User: email = ..."},
        {"file": "app/services/user.py", "content": "def update_email..."},
        {"file": "app/routes/user.py", "content": "@router.put('/email')"}
    ]
}
```

**Without bundles:**
- Apply models/user.py ✅
- Apply services/user.py ✅
- Apply routes/user.py ❌ (test fails)
- Repo broken (models and services updated, routes not)

**With bundles:**
- Sandbox test all 3 together ✅
- Apply all 3 to real repo ✅
- Test all 3 ✅
- Commit all 3 ✅

**If sandbox fails:**
- Rejected before real apply
- Real repo untouched
- No damage

## Brutal Truth

Previous version: "safe enough for single-file changes"

Current version: "safe enough for multi-file atomic changes"

**This is the difference between:**
- Script thinking (independent operations)
- System thinking (atomic units)

## Next Steps

After bundle execution:
- Agent can plan multi-step changes
- Group related changes into bundles
- Simulate bundles safely
- Apply bundles atomically

**Ready for memory + planning.**

## Status

✅ Bundle execution (atomic multi-file changes)
✅ Bundle sandbox testing (test together)
✅ Bundle-level logging (scene-level debug)
✅ Atomic rollback (all or nothing)
✅ Single pipeline (no bypass)
✅ Schema validation
✅ Patch ordering
✅ Sandbox execution
✅ Structured JSONL logs

**This is what system-level safety actually means.**
