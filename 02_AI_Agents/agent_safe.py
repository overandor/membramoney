import os
import json
import time
import subprocess
import requests
import ast
import logging
import shutil
import tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright

# ==============================
# CONFIG
# ==============================

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
REPO_PATH = os.getcwd()
LOOP_LIMIT = 10
MAX_RETRIES = 3
TEST_COMMAND = "pytest -q"

# ==============================
# SAFETY MODES
# ==============================

DRY_RUN = False  # Set True to preview changes without applying
REQUIRE_APPROVAL = True  # Set False for full autonomy (NOT RECOMMENDED)
SANDBOX_MODE = True  # Set True to test in temp dir before real apply

# ==============================
# SAFETY CONSTRAINTS
# ==============================

# File scope guard
ALLOWED_PATHS = ["app/", "services/", "tests/", "src/"]
BLOCKED_FILES = ["config.py", ".env", "secrets.py", "settings.py", "__pycache__"]

# Operation constraints
ALLOWED_OPERATIONS = ["create", "update", "ast_patch", "function_update"]
MAX_FILES_PER_ITERATION = 5
MAX_DIFF_SIZE = 10000  # characters

# Confidence threshold
CONFIDENCE_THRESHOLD = 0.6

# ==============================
# STRUCTURED LOGGING (JSONL)
# ==============================

LOG_FILE = "agent_safe.jsonl"

def log_entry(entry):
    """Write structured log entry to JSONL file"""
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")

# Also keep text logging for console
logging.basicConfig(
    filename="agent_safe.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ==============================
# GET CHATGPT MESSAGE
# ==============================

def get_last_message():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto("https://chat.openai.com")

        page.wait_for_selector("div[data-message-author-role='assistant']")
        msgs = page.query_selector_all("div[data-message-author-role='assistant']")

        text = msgs[-1].inner_text()
        browser.close()
        return text


# ==============================
# PARSE WITH CONFIDENCE
# ==============================

def parse_with_confidence(text):
    prompt = f"""
Extract file changes from this message.

Return JSON with confidence score:
{{
  "decision": "apply|abort",
  "confidence": 0.0-1.0,
  "changes": [
    {{
      "file": "path/to/file.py",
      "operation": "create|update|ast_patch|function_update",
      "target_function": "function_name",
      "content": "full new file content",
      "new_code": "new function code"
    }}
  ]
}}

Only include "decision": "apply" if confidence > 0.6.

TEXT:
{text}
"""

    res = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False}
    )

    raw = res.json()["response"]

    try:
        return json.loads(raw)
    except:
        print("⚠️ Failed parsing JSON")
        return {"decision": "abort", "confidence": 0.0, "changes": []}


# ==============================
# PATCH SCHEMA VALIDATION
# ==============================

def validate_patch_schema(patch):
    """Strict schema validation for patch format"""
    required_fields = ["file", "operation"]
    
    for field in required_fields:
        if field not in patch:
            logger.error(f"Missing required field: {field}")
            print(f"🚫 Missing required field: {field}")
            return False
    
    # Validate operation type
    if patch["operation"] not in ALLOWED_OPERATIONS:
        logger.error(f"Invalid operation: {patch['operation']}")
        return False
    
    # Validate file path is string
    if not isinstance(patch["file"], str):
        logger.error(f"File must be string, got {type(patch['file'])}")
        return False
    
    # Validate content if present
    if "content" in patch and not isinstance(patch["content"], str):
        logger.error(f"Content must be string, got {type(patch['content'])}")
        return False
    
    return True


# ==============================
# PATCH ORDERING
# ==============================

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


# ==============================
# SANDBOX EXECUTION
# ==============================

def run_in_sandbox(patch):
    """
    Apply patch in temporary directory and run tests.
    Returns (success, output)
    """
    temp_dir = tempfile.mkdtemp(prefix="agent_sandbox_")
    
    try:
        # Copy repo to temp dir
        shutil.copytree(REPO_PATH, temp_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        
        logger.info(f"Sandbox created: {temp_dir}")
        
        # Apply patch in sandbox
        sandbox_file_path = Path(temp_dir) / patch["file"]
        sandbox_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Backup in sandbox
        if sandbox_file_path.exists():
            backup_path = str(sandbox_file_path) + ".bak"
            with open(sandbox_file_path, "r") as f:
                existing = f.read()
            with open(backup_path, "w") as f:
                f.write(existing)
        
        # Apply in sandbox
        with open(sandbox_file_path, "w") as f:
            f.write(patch.get("content", ""))
        
        logger.info(f"Patch applied in sandbox: {patch['file']}")
        
        # Run tests in sandbox
        result = subprocess.run(
            TEST_COMMAND.split(),
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=60  # 60 second timeout
        )
        
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        logger.info(f"Sandbox tests: {'PASSED' if success else 'FAILED'}")
        
        return success, output
        
    except subprocess.TimeoutExpired:
        logger.error("Sandbox test execution timed out")
        return False, "Test execution timed out"
    except Exception as e:
        logger.error(f"Sandbox execution failed: {e}")
        return False, str(e)
    finally:
        # Cleanup sandbox
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Sandbox cleaned up: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup sandbox: {e}")


# ==============================
# BUNDLE SANDBOX EXECUTION
# ==============================

def run_bundle_in_sandbox(patches):
    """
    Apply multiple patches in sandbox as a bundle and run tests.
    Returns (success, output)
    """
    temp_dir = tempfile.mkdtemp(prefix="agent_bundle_sandbox_")
    
    try:
        # Copy repo to temp dir
        shutil.copytree(REPO_PATH, temp_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        
        logger.info(f"Bundle sandbox created: {temp_dir}")
        
        # Apply all patches in sandbox (in order)
        for patch in patches:
            sandbox_file_path = Path(temp_dir) / patch["file"]
            sandbox_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Backup in sandbox
            if sandbox_file_path.exists():
                backup_path = str(sandbox_file_path) + ".bak"
                with open(sandbox_file_path, "r") as f:
                    existing = f.read()
                with open(backup_path, "w") as f:
                    f.write(existing)
            
            # Apply in sandbox
            with open(sandbox_file_path, "w") as f:
                f.write(patch.get("content", ""))
            
            logger.info(f"Bundle patch applied in sandbox: {patch['file']}")
        
        # Run tests in sandbox
        result = subprocess.run(
            TEST_COMMAND.split(),
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        output = result.stdout + result.stderr
        success = result.returncode == 0
        
        logger.info(f"Bundle sandbox tests: {'PASSED' if success else 'FAILED'}")
        
        return success, output
        
    except subprocess.TimeoutExpired:
        logger.error("Bundle sandbox test execution timed out")
        return False, "Test execution timed out"
    except Exception as e:
        logger.error(f"Bundle sandbox execution failed: {e}")
        return False, str(e)
    finally:
        # Cleanup sandbox
        try:
            shutil.rmtree(temp_dir)
            logger.info(f"Bundle sandbox cleaned up: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup bundle sandbox: {e}")


# ==============================
# BUNDLE EXECUTION
# ==============================

def process_bundle(bundle, iteration):
    """
    Process a bundle of patches as an atomic unit.
    All patches in bundle succeed together or rollback together.
    """
    bundle_start_time = time.time()
    bundle_id = bundle.get("bundle_id", f"bundle_{iteration}_{int(time.time())}")
    patches = bundle.get("changes", [])
    
    logger.info(f"Processing bundle: {bundle_id} with {len(patches)} patches")
    
    # Order patches by dependency
    ordered_patches = order_patches(patches)
    print(f"📦 Bundle order: {[p['file'] for p in ordered_patches]}")
    
    # Schema validation for all patches
    for patch in ordered_patches:
        if not validate_patch_schema(patch):
            logger.warning(f"Bundle {bundle_id} rejected: schema validation failed for {patch['file']}")
            log_entry({
                "timestamp": bundle_start_time,
                "bundle_id": bundle_id,
                "result": "rejected",
                "reason": "schema_validation_failed",
                "failed_patch": patch["file"],
                "patch_count": len(patches),
                "duration": time.time() - bundle_start_time
            })
            return False, "schema_validation_failed"
    
    # Sandbox execution for entire bundle
    if SANDBOX_MODE:
        print(f"🔬 Running bundle in sandbox: {bundle_id}")
        sandbox_passed, sandbox_output = run_bundle_in_sandbox(ordered_patches)
        
        if not sandbox_passed:
            logger.warning(f"Bundle {bundle_id} rejected: sandbox tests failed")
            log_entry({
                "timestamp": bundle_start_time,
                "bundle_id": bundle_id,
                "result": "rejected",
                "reason": "sandbox_tests_failed",
                "test_output": sandbox_output[:500],
                "patch_count": len(patches),
                "duration": time.time() - bundle_start_time
            })
            return False, "sandbox_tests_failed"
        
        print(f"✅ Bundle sandbox tests passed")
    
    # Dry-run mode
    if DRY_RUN:
        print("\n" + "="*60)
        print(f"🔍 DRY RUN MODE - BUNDLE PREVIEW: {bundle_id}")
        print("="*60)
        for patch in ordered_patches:
            print(f"  - {patch['file']} ({patch.get('operation', 'update')})")
        print("="*60 + "\n")
        log_entry({
            "timestamp": bundle_start_time,
            "bundle_id": bundle_id,
            "result": "previewed",
            "reason": "dry_run",
            "patch_count": len(patches),
            "duration": time.time() - bundle_start_time
        })
        return True, "dry_run"
    
    # Human approval
    if REQUIRE_APPROVAL:
        print("\n" + "="*60)
        print(f"🔍 BUNDLE REVIEW: {bundle_id}")
        print(f"Patches: {len(ordered_patches)}")
        for patch in ordered_patches:
            print(f"  - {patch['file']}")
        print("="*60)
        print("Press Enter to apply bundle, Ctrl+C to abort...")
        try:
            input()
        except KeyboardInterrupt:
            logger.warning(f"Bundle {bundle_id} rejected: user aborted")
            print("\n🛑 User aborted bundle")
            log_entry({
                "timestamp": bundle_start_time,
                "bundle_id": bundle_id,
                "result": "rejected",
                "reason": "user_aborted",
                "patch_count": len(patches),
                "duration": time.time() - bundle_start_time
            })
            return False, "user_aborted"
    
    # Apply all patches to real repo (atomic)
    applied_patches = []
    try:
        for patch in ordered_patches:
            file_path = Path(REPO_PATH) / patch["file"]
            
            # Backup
            file_path.parent.mkdir(parents=True, exist_ok=True)
            if file_path.exists():
                backup_path = str(file_path) + ".bak"
                with open(file_path, "r") as f:
                    existing = f.read()
                with open(backup_path, "w") as f:
                    f.write(existing)
            
            # Apply
            with open(file_path, "w") as f:
                f.write(patch.get("content", ""))
            
            applied_patches.append(patch["file"])
            logger.info(f"Bundle patch applied: {patch['file']}")
            print(f"✅ Applied: {patch['file']}")
        
        # Git diff constraint check
        if not check_diff_constraints():
            logger.warning(f"Bundle {bundle_id} reverted: diff constraints violated")
            rollback()
            log_entry({
                "timestamp": bundle_start_time,
                "bundle_id": bundle_id,
                "result": "reverted",
                "reason": "diff_constraints_violated",
                "patch_count": len(patches),
                "duration": time.time() - bundle_start_time
            })
            return False, "diff_constraints_violated"
        
        # Run tests
        tests_passed, test_output = run_tests()
        
        if not tests_passed:
            logger.warning(f"Bundle {bundle_id} reverted: tests failed")
            rollback()
            log_entry({
                "timestamp": bundle_start_time,
                "bundle_id": bundle_id,
                "result": "reverted",
                "reason": "tests_failed",
                "test_output": test_output[:500],
                "patch_count": len(patches),
                "duration": time.time() - bundle_start_time
            })
            return False, "tests_failed"
        
        # Success
        logger.info(f"Bundle {bundle_id} applied successfully")
        log_entry({
            "timestamp": bundle_start_time,
            "bundle_id": bundle_id,
            "result": "applied",
            "reason": "success",
            "patch_count": len(patches),
            "sandbox_passed": SANDBOX_MODE,
            "test_output": test_output[:500] if tests_passed else None,
            "duration": time.time() - bundle_start_time
        })
        return True, "success"
        
    except Exception as e:
        logger.error(f"Bundle {bundle_id} failed with exception: {e}")
        rollback()
        log_entry({
            "timestamp": bundle_start_time,
            "bundle_id": bundle_id,
            "result": "reverted",
            "reason": f"exception: {str(e)}",
            "patch_count": len(patches),
            "duration": time.time() - bundle_start_time
        })
        return False, f"exception: {str(e)}"


# ==============================
# FILE SCOPE GUARD
# ==============================

def is_safe_path(file_path):
    """Check if file path is within allowed scope"""
    # Check if file is blocked
    if any(file in file_path for file in BLOCKED_FILES):
        logger.warning(f"Blocked file: {file_path}")
        print(f"🚫 Blocked file: {file_path}")
        return False
    
    # Check if file is in allowed paths
    if any(file_path.startswith(path) for path in ALLOWED_PATHS):
        return True
    
    logger.warning(f"Path not in allowed scope: {file_path}")
    print(f"🚫 Path not in allowed scope: {file_path}")
    return False


# ==============================
# OPERATION TYPE ENFORCEMENT
# ==============================

def is_valid_operation(operation):
    """Check if operation type is allowed"""
    if operation in ALLOWED_OPERATIONS:
        return True
    print(f"🚫 Blocked operation: {operation}")
    return False


# ==============================
# CONTENT SAFETY CHECK
# ==============================

def is_safe_content(content):
    """Check content for dangerous operations"""
    forbidden = ["rm -rf", "os.remove", "shutil.rmtree", "exec(", "eval("]
    
    for f in forbidden:
        if f in content:
            print(f"🚫 Dangerous content blocked: {f}")
            return False
    
    return True


# ==============================
# AST SAFETY VALIDATION
# ==============================

def validate_ast(source):
    """Validate that source is valid Python"""
    try:
        ast.parse(source)
        return True
    except SyntaxError as e:
        print(f"❌ AST validation failed: {e}")
        return False


def validate_ast_after_patch(file_path, target_function):
    """Validate AST after patching"""
    try:
        with open(file_path, "r") as f:
            source = f.read()
        
        tree = ast.parse(source)
        
        # Check if target function still exists
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == target_function:
                return True
        
        print(f"⚠️ Target function {target_function} not found after patch")
        return False
    except Exception as e:
        print(f"❌ Post-patch validation failed: {e}")
        return False


# ==============================
# GIT DIFF CONSTRAINT CHECK
# ==============================

def check_diff_constraints():
    """Check git diff for constraint violations"""
    result = subprocess.run(
        ["git", "diff", "--stat"],
        capture_output=True,
        text=True
    )
    
    # Count changed files
    changed_files = len([line for line in result.stdout.split('\n') if line.strip()])
    
    if changed_files > MAX_FILES_PER_ITERATION:
        print(f"🚫 Too many files changed: {changed_files} > {MAX_FILES_PER_ITERATION}")
        return False
    
    # Check diff size
    diff_result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True
    )
    
    if len(diff_result.stdout) > MAX_DIFF_SIZE:
        print(f"🚫 Diff too large: {len(diff_result.stdout)} > {MAX_DIFF_SIZE}")
        return False
    
    return True


# ==============================
# AST-AWARE PATCHING
# ==============================

def apply_ast_patch(file_path, target_function, new_code):
    """Apply surgical edit using AST parsing"""
    try:
        with open(file_path, "r") as f:
            source = f.read()

        # Validate before patching
        if not validate_ast(source):
            return False

        tree = ast.parse(source)

        # Find target function
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == target_function:
                # Parse new code
                new_func = ast.parse(new_code).body[0]
                
                # Replace function in tree
                node.body = new_func.body
                node.args = new_func.args
                node.returns = new_func.returns
                
                # Convert back to source
                new_source = ast.unparse(tree)
                
                # Validate after patching
                if not validate_ast(new_source):
                    print("❌ Generated invalid AST")
                    return False
                
                # Backup
                backup_path = str(file_path) + ".bak"
                with open(backup_path, "w") as f:
                    f.write(source)
                
                # Write new source
                with open(file_path, "w") as f:
                    f.write(new_source)
                
                # Validate target function still exists
                if not validate_ast_after_patch(file_path, target_function):
                    # Rollback
                    os.replace(backup_path, file_path)
                    return False
                
                print(f"✅ AST patch applied: {target_function} in {file_path}")
                return True

        print(f"⚠️ Function {target_function} not found in {file_path}")
        return False

    except Exception as e:
        print(f"❌ AST patch failed: {e}")
        return False


# ==============================
# SINGLE PATCH PIPELINE
# ==============================

def process_patch(patch, iteration):
    """
    SINGLE pipeline function that ALL patches must go through.
    This enforces all safety checks in a deterministic order.
    """
    patch_start_time = time.time()
    
    logger.info(f"Iteration {iteration}: Processing patch for {patch.get('file', 'unknown')}")
    
    # 1. Schema validation (first gate)
    if not validate_patch_schema(patch):
        logger.warning(f"Patch rejected: schema validation failed")
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "rejected",
            "reason": "schema_validation_failed",
            "duration": time.time() - patch_start_time
        })
        return "rejected", "schema_validation_failed"
    
    # 2. Confidence check
    confidence = patch.get("confidence", 0.0)
    if confidence < CONFIDENCE_THRESHOLD:
        logger.warning(f"Patch rejected: confidence {confidence} < {CONFIDENCE_THRESHOLD}")
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "rejected",
            "reason": "low_confidence",
            "confidence": confidence,
            "duration": time.time() - patch_start_time
        })
        return "rejected", "low_confidence"
    
    # 3. File scope guard
    file_path = Path(REPO_PATH) / patch["file"]
    if not is_safe_path(str(file_path)):
        logger.warning(f"Patch rejected: unsafe path {patch['file']}")
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "rejected",
            "reason": "unsafe_path",
            "duration": time.time() - patch_start_time
        })
        return "rejected", "unsafe_path"
    
    # 4. Operation type enforcement
    operation = patch.get("operation", "update")
    if not is_valid_operation(operation):
        logger.warning(f"Patch rejected: invalid operation {operation}")
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "rejected",
            "reason": "invalid_operation",
            "duration": time.time() - patch_start_time
        })
        return "rejected", "invalid_operation"
    
    # 5. Content safety check
    content = patch.get("content", "")
    if content and not is_safe_content(content):
        logger.warning(f"Patch rejected: dangerous content")
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "rejected",
            "reason": "dangerous_content",
            "duration": time.time() - patch_start_time
        })
        return "rejected", "dangerous_content"
    
    # 6. Dry-run mode (if enabled)
    if DRY_RUN:
        print("\n" + "="*60)
        print("🔍 DRY RUN MODE - PATCH PREVIEW")
        print("="*60)
        print(f"File: {patch['file']}")
        print(f"Operation: {operation}")
        print(f"Content length: {len(content)} chars")
        print(f"Confidence: {confidence}")
        print("="*60 + "\n")
        logger.info(f"Patch previewed (dry-run mode): {patch['file']}")
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "previewed",
            "reason": "dry_run",
            "duration": time.time() - patch_start_time
        })
        return "previewed", "dry_run"
    
    # 7. Human approval (if required)
    if REQUIRE_APPROVAL:
        print("\n" + "="*60)
        print(f"🔍 PATCH REVIEW: {patch['file']}")
        print(f"Operation: {operation}")
        print(f"Confidence: {confidence}")
        print("="*60)
        print("Press Enter to apply, Ctrl+C to abort...")
        try:
            input()
        except KeyboardInterrupt:
            logger.warning(f"Patch rejected: user aborted")
            print("\n🛑 User aborted")
            log_entry({
                "timestamp": patch_start_time,
                "patch": patch,
                "result": "rejected",
                "reason": "user_aborted",
                "duration": time.time() - patch_start_time
            })
            return "rejected", "user_aborted"
    
    # 8. Sandbox execution (if enabled)
    if SANDBOX_MODE:
        print(f"🔬 Running in sandbox: {patch['file']}")
        sandbox_passed, sandbox_output = run_in_sandbox(patch)
        
        if not sandbox_passed:
            logger.warning(f"Patch rejected: sandbox tests failed")
            log_entry({
                "timestamp": patch_start_time,
                "patch": patch,
                "result": "rejected",
                "reason": "sandbox_tests_failed",
                "test_output": sandbox_output[:500],
                "duration": time.time() - patch_start_time
            })
            return "rejected", "sandbox_tests_failed"
        
        print(f"✅ Sandbox tests passed")
    
    # 9. AST validation before patch
    if content and not validate_ast(content):
        logger.warning(f"Patch rejected: AST validation failed")
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "rejected",
            "reason": "ast_validation_failed",
            "duration": time.time() - patch_start_time
        })
        return "rejected", "ast_validation_failed"
    
    # 10. Backup file
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.exists():
        backup_path = str(file_path) + ".bak"
        with open(file_path, "r") as f:
            existing = f.read()
        with open(backup_path, "w") as f:
            f.write(existing)
        logger.info(f"Backup created: {backup_path}")
    
    # 11. Apply patch
    try:
        if operation in ["ast_patch", "function_update"]:
            target_func = patch.get("target_function")
            new_code = patch.get("new_code")
            success = apply_ast_patch(file_path, target_func, new_code)
        else:
            with open(file_path, "w") as f:
                f.write(content)
            logger.info(f"Patch applied: {patch['file']}")
            print(f"✅ Applied: {patch['file']}")
            success = True
        
        if not success:
            logger.warning(f"Patch rejected: application failed")
            log_entry({
                "timestamp": patch_start_time,
                "patch": patch,
                "result": "rejected",
                "reason": "application_failed",
                "duration": time.time() - patch_start_time
            })
            return "rejected", "application_failed"
    except Exception as e:
        logger.error(f"Patch failed with exception: {e}")
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "rejected",
            "reason": f"exception: {str(e)}",
            "duration": time.time() - patch_start_time
        })
        return "rejected", f"exception: {str(e)}"
    
    # 12. Git diff constraint check
    if not check_diff_constraints():
        logger.warning(f"Patch rejected: diff constraints violated")
        rollback()
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "reverted",
            "reason": "diff_constraints_violated",
            "duration": time.time() - patch_start_time
        })
        return "reverted", "diff_constraints_violated"
    
    # 13. Run tests
    tests_passed, test_output = run_tests()
    
    if not tests_passed:
        logger.warning(f"Patch rejected: tests failed")
        logger.warning(f"Test output: {test_output[-500:]}")
        rollback()
        log_entry({
            "timestamp": patch_start_time,
            "patch": patch,
            "result": "reverted",
            "reason": "tests_failed",
            "test_output": test_output[:500],
            "duration": time.time() - patch_start_time
        })
        return "reverted", "tests_failed"
    
    logger.info(f"Patch accepted and committed: {patch['file']}")
    log_entry({
        "timestamp": patch_start_time,
        "patch": patch,
        "result": "accepted",
        "reason": "success",
        "test_output": test_output[:500] if tests_passed else None,
        "duration": time.time() - patch_start_time
    })
    return "accepted", "success"


# ==============================
# APPLY CHANGE WITH SAFETY
# ==============================

def apply_change(change):
    file_path = Path(REPO_PATH) / change["file"]
    
    # File scope guard
    if not is_safe_path(str(file_path)):
        return False
    
    # Operation type enforcement
    operation = change.get("operation", "update")
    if not is_valid_operation(operation):
        return False
    
    # Content safety check
    content = change.get("content", "")
    if content and not is_safe_content(content):
        return False
    
    # Create dirs if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    if operation in ["ast_patch", "function_update"]:
        target_func = change.get("target_function")
        new_code = change.get("new_code")
        return apply_ast_patch(file_path, target_func, new_code)

    # Regular file write
    if file_path.exists():
        # Validate existing file
        with open(file_path, "r") as f:
            existing = f.read()
        if not validate_ast(existing):
            print(f"⚠️ Existing file has invalid AST: {file_path}")
            return False
        
        # Backup
        backup_path = str(file_path) + ".bak"
        with open(backup_path, "w") as f:
            f.write(existing)
    
    # Validate new content
    if content and not validate_ast(content):
        print(f"⚠️ New content has invalid AST: {file_path}")
        return False
    
    with open(file_path, "w") as f:
        f.write(content)

    print(f"✅ Applied: {change['file']}")
    return True


# ==============================
# SMARTER TEST RUNNER
# ==============================

def run_tests():
    """Run pytest and return success/failure with output"""
    try:
        result = subprocess.run(
            TEST_COMMAND.split(),
            capture_output=True,
            text=True,
            cwd=REPO_PATH
        )
        
        success = result.returncode == 0
        output = result.stdout + result.stderr
        
        return success, output
    except Exception as e:
        print(f"❌ Test runner error: {e}")
        return False, str(e)


# ==============================
# FEEDBACK LOOP WITH OLLAMA
# ==============================

def fix_with_feedback(test_output, last_patch):
    """Ask Ollama to fix based on test failure"""
    prompt = f"""
Tests failed. Fix the issue.

ERROR:
{test_output}

PREVIOUS PATCH:
{last_patch}

Return JSON:
{{
  "decision": "retry|abort",
  "fix": "improved patch or explanation"
}}
"""

    res = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "prompt": prompt, "stream": False}
    )

    raw = res.json()["response"]
    
    try:
        return json.loads(raw)
    except:
        return {"decision": "abort", "fix": raw}


# ==============================
# ROLLBACK
# ==============================

def rollback():
    logger.info("Starting rollback")
    restored_count = 0
    for root, _, files in os.walk(REPO_PATH):
        for f in files:
            if f.endswith(".bak"):
                original = os.path.join(root, f[:-4])
                backup = os.path.join(root, f)
                os.replace(backup, original)
                logger.info(f"Restored {original}")
                print(f"↩️ Restored {original}")
                restored_count += 1
    logger.info(f"Rollback complete: {restored_count} files restored")


# ==============================
# MAIN LOOP WITH BUNDLE EXECUTION
# ==============================

def run():
    agent_start_time = time.time()
    
    log_entry({
        "timestamp": agent_start_time,
        "event": "agent_start",
        "config": {
            "dry_run": DRY_RUN,
            "require_approval": REQUIRE_APPROVAL,
            "sandbox_mode": SANDBOX_MODE,
            "allowed_paths": ALLOWED_PATHS,
            "blocked_files": BLOCKED_FILES,
            "confidence_threshold": CONFIDENCE_THRESHOLD
        }
    })
    
    logger.info("Agent started")
    print("🚀 Safe AST-aware agent started (bundle-aware)")
    print(f"🛡️ Allowed paths: {ALLOWED_PATHS}")
    print(f"🛡️ Blocked files: {BLOCKED_FILES}")
    print(f"🛡️ Confidence threshold: {CONFIDENCE_THRESHOLD}")
    print(f"🔍 Dry-run mode: {DRY_RUN}")
    print(f"👤 Require approval: {REQUIRE_APPROVAL}")
    print(f"🔬 Sandbox mode: {SANDBOX_MODE}")

    for i in range(LOOP_LIMIT):
        print(f"\n🔁 Iteration {i+1}")
        logger.info(f"Starting iteration {i+1}")

        msg = get_last_message()
        parsed = parse_with_confidence(msg)

        # Confidence kill switch
        decision = parsed.get("decision", "abort")
        confidence = parsed.get("confidence", 0.0)
        
        print(f"🧠 Decision: {decision}, Confidence: {confidence}")
        logger.info(f"Decision: {decision}, Confidence: {confidence}")
        
        if decision == "abort" or confidence < CONFIDENCE_THRESHOLD:
            print("🛑 Agent aborted (low confidence or abort decision)")
            logger.info("Agent aborted: low confidence or abort decision")
            log_entry({
                "timestamp": time.time(),
                "event": "agent_aborted",
                "reason": "low_confidence_or_abort",
                "iteration": i+1
            })
            break

        changes = parsed.get("changes", [])

        if not changes:
            print("❌ No changes found")
            logger.warning("No changes found")
            log_entry({
                "timestamp": time.time(),
                "event": "no_changes",
                "iteration": i+1
            })
            break

        # File count constraint
        if len(changes) > MAX_FILES_PER_ITERATION:
            print(f"🚫 Too many changes: {len(changes)} > {MAX_FILES_PER_ITERATION}")
            logger.warning(f"Too many changes: {len(changes)}")
            log_entry({
                "timestamp": time.time(),
                "event": "too_many_changes",
                "count": len(changes),
                "iteration": i+1
            })
            break

        # Group changes into bundles
        # If parsed has explicit bundles, use them
        # Otherwise, treat all changes as a single bundle
        if "bundles" in parsed:
            bundles = parsed["bundles"]
        else:
            # Create single bundle from all changes
            bundles = [{
                "bundle_id": f"bundle_{i}_{int(time.time())}",
                "changes": changes
            }]
        
        print(f"� Processing {len(bundles)} bundle(s)")
        
        # Process each bundle
        applied_count = 0
        for bundle in bundles:
            bundle_id = bundle.get("bundle_id", "unknown")
            
            # Process bundle
            success, reason = process_bundle(bundle, i+1)
            
            if success:
                applied_count += len(bundle["changes"])
                print(f"✅ Bundle {bundle_id} applied")
            else:
                logger.warning(f"Bundle {bundle_id} failed: {reason}")
                print(f"⚠️ Bundle {bundle_id} failed: {reason}")
                break

        if applied_count > 0:
            # Commit if all bundles applied
            try:
                subprocess.run(
                    ["git", "add", "."],
                    capture_output=True,
                    cwd=REPO_PATH
                )
                subprocess.run(
                    ["git", "commit", "-m", "Agent: automated changes"],
                    capture_output=True,
                    cwd=REPO_PATH
                )
                print("✅ Changes committed")
                logger.info("Changes committed successfully")
                log_entry({
                    "timestamp": time.time(),
                    "event": "changes_committed",
                    "count": applied_count,
                    "iteration": i+1
                })
            except Exception as e:
                print(f"⚠️ Git commit failed: {e}")
                logger.error(f"Git commit failed: {e}")

        time.sleep(3)

    print("✅ Agent done")
    logger.info("Agent finished")
    log_entry({
        "timestamp": time.time(),
        "event": "agent_done",
        "duration": time.time() - agent_start_time
    })


if __name__ == "__main__":
    run()
