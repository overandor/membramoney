# Agent Migration Guide - Stop Using Old Scripts

## The Problem

You're getting:
```
ModuleNotFoundError: No module named 'keyboard'
```

**Why:** You're running an outdated script that still imports `keyboard`.

## The Reality

Your old script (`winserv_automation_agent.py`) is obsolete.

**Old Architecture (Broken):**
- GUI automation
- Pixel-based clicking
- Keyboard hooks (break on macOS)
- Fragile, resolution-dependent
- No validation
- No rollback

**New Architecture (Working):**
- Patch-based file modification
- AST-aware surgical edits
- Playwright for ChatGPT extraction
- Ollama for parsing
- Test runner (pytest)
- Failure loop
- Git validation
- Rollback capability
- No UI dependency

## What to Do

### Option 1: Delete Old Script (Recommended)

```bash
rm /Users/alep/Downloads/winserv_chatgpt_automation/winserv_automation_agent.py
```

### Option 2: Ignore It

Just stop running it. Use the new agent instead.

## What to Run Instead

```bash
# NOT this:
python winserv_automation_agent.py

# Use this (recommended for production):
python agent_safe.py

# Or this (good, but no safety layer):
python agent_ast.py

# Or this (simpler, no tests):
python agent_patch.py
```

## Architecture Evolution

### Phase 1 (Obsolete - Delete)
```
GUI automation → Click → Paste → Hope
```
- ❌ Fragile
- ❌ macOS keyboard issues
- ❌ Resolution dependent
- ❌ No validation

### Phase 2 (Patch Agent - Alternative)
```
ChatGPT → Parse → Patch → Write Files → Git Validate
```
- ✅ File-specific
- ✅ Safety checks
- ✅ Backups
- ✅ Validation
- ✅ Rollback

### Phase 3 (AST Agent - Good)
```
ChatGPT → AST Parse → Test → Loop Until Pass → Commit
```
- ✅ Surgical edits
- ✅ Test validation
- ✅ Self-correcting
- ✅ Real autonomy
- ✅ Auto commit
- ❌ No safety constraints

### Phase 4 (Safe Agent - Recommended for Production)
```
ChatGPT → Confidence Check → Scope Guard → Operation Check → AST Validate → Test → Feedback → Commit
```
- ✅ Surgical edits
- ✅ Test validation
- ✅ Self-correcting
- ✅ Real autonomy
- ✅ Auto commit
- ✅ Confidence kill switch
- ✅ File scope guard
- ✅ Operation enforcement
- ✅ AST validation
- ✅ Git constraints
- ✅ Smart feedback loop

## File Inventory

### Keep These (Recommended)
- `agent_safe.py` - Safe AST-aware agent with safety layer (BEST FOR PRODUCTION)
- `agent_ast.py` - AST-aware agent with test runner (GOOD, but no safety layer)
- `agent_patch.py` - Patch-based agent (SIMPLER, no tests)
- `agent.py` - Paste-based agent (for review workflow)
- `ollama_vision_agent.py` - Vision-based UI control (if needed)
- `ollama_vision_agent_with_memory.py` - Vision with memory (if needed)

### Delete/Ignore These
- `winserv_automation_agent.py` - Obsolete GUI automation
- Any scripts importing `keyboard` - macOS incompatible

## Why the Old Script Failed

1. **Keyboard Hooks on macOS**
   - macOS security blocks keyboard hooks
   - Requires accessibility permissions
   - Still fragile even with permissions

2. **Pixel-Based Clicking**
   - Breaks on resolution changes
   - Breaks on window movement
   - Breaks on scaling changes
   - No reliability

3. **No Validation**
   - No way to verify changes
   - No rollback
   - No safety checks

## Why the New Scripts Work

### Patch Agent (agent_patch.py)
1. **File-Based**
   - No UI dependency
   - No clicking
   - No guessing coordinates

2. **Validated**
   - Git diff shows changes
   - Safety checks block dangerous ops
   - Decision engine can stop/rollback

3. **Safe**
   - Backups before modification
   - Rollback capability
   - Controlled execution

### AST Agent (agent_ast.py) - RECOMMENDED
All of the above PLUS:
1. **AST-Aware**
   - Surgical function edits
   - Not full file overwrites
   - Preserves file structure

2. **Test Validation**
   - Pytest must pass
   - Code actually works
   - No broken commits

3. **Failure Loop**
   - Retries until tests pass
   - Self-correcting
   - Gives up after max retries

4. **Auto Commit**
   - Commits working code
   - Automated workflow
   - Git history tracking

## If You Really Need UI Control

Use the vision agents properly:

```bash
# Vision with memory (better than old script)
python ollama_vision_agent_with_memory.py
```

But don't build your system around UI automation. Use it as a fallback only.

## Migration Steps

1. **Stop running old script**
   ```bash
   # Don't do this:
   python winserv_automation_agent.py
   ```

2. **Start using safe agent (recommended for production)**
   ```bash
   cd /path/to/repo
   python agent_safe.py
   ```

3. **Or use AST agent (good, but no safety layer)**
   ```bash
   cd /path/to/repo
   python agent_ast.py
   ```

4. **Or use patch agent (simpler)**
   ```bash
   cd /path/to/repo
   python agent_patch.py
   ```

5. **Delete obsolete files**
   ```bash
   rm winserv_automation_agent.py
   ```

6. **Move forward**
   - Focus on AST-based architecture
   - Add pytest tests to your repo
   - Monitor agent execution

## Next Upgrade

The safe agent is the current state of the art. To make it even better:

**"Add multi-step planning memory and dependency resolution for complex multi-file tasks"**

This gives you:
- Task planning across multiple files
- Dependency analysis
- State tracking
- Complex multi-step execution

## Summary

**Don't fix the old script.** It's obsolete.

**Use the safe agent** (agent_safe.py) for production-ready autonomous coding with safety layer.

**Use the AST agent** (agent_ast.py) for AST edits without safety constraints.

**Use the patch agent** (agent_patch.py) for simpler workflows without tests.

**Move forward.** You've evolved from broken hammer to nail gun to surgical robot with guardrails.

## Which Agent to Use?

| Need | Use Agent |
|------|-----------|
| Production-ready autonomous coding (safest) | agent_safe.py |
| AST edits with tests (no safety layer) | agent_ast.py |
| Simple file changes, no tests | agent_patch.py |
| Review workflow, manual control | agent.py |
| UI automation (fallback only) | ollama_vision_agent_with_memory.py |

**Recommendation:** Use `agent_safe.py` for any autonomous execution. The safety layer is critical.
