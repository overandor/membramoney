import os
import json
import time
import subprocess
import requests
import ast
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
TEST_COMMAND = "pytest -xvs"

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
# PARSE INTO PATCHES
# ==============================

def parse_patch(text):
    prompt = f"""
Extract file changes from this message.

Return JSON:
{{
  "changes": [
    {{
      "file": "path/to/file.py",
      "action": "create|update|ast_patch",
      "content": "full new file content",
      "target_function": "function_name",  // for ast_patch only
      "new_code": "new function code"      // for ast_patch only
    }}
  ]
}}

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
        return {"changes": []}


# ==============================
# SAFETY CHECK
# ==============================

def is_safe(change):
    forbidden = ["rm -rf", "os.remove", "shutil.rmtree"]

    content = change.get("content", "")
    for f in forbidden:
        if f in content:
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
                
                # Backup
                backup_path = str(file_path) + ".bak"
                with open(backup_path, "w") as f:
                    f.write(source)
                
                # Write new source
                with open(file_path, "w") as f:
                    f.write(new_source)
                
                print(f"✅ AST patch applied: {target_function} in {file_path}")
                return True

        print(f"⚠️ Function {target_function} not found in {file_path}")
        return False

    except Exception as e:
        print(f"❌ AST patch failed: {e}")
        return False


# ==============================
# APPLY CHANGE
# ==============================

def apply_change(change):
    file_path = Path(REPO_PATH) / change["file"]

    # create dirs if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    action = change.get("action", "update")

    if action == "ast_patch":
        target_func = change.get("target_function")
        new_code = change.get("new_code")
        return apply_ast_patch(file_path, target_func, new_code)

    # Regular file write
    if file_path.exists():
        backup_path = str(file_path) + ".bak"
        with open(file_path, "r") as f:
            old = f.read()
        with open(backup_path, "w") as f:
            f.write(old)

    with open(file_path, "w") as f:
        f.write(change["content"])

    print(f"✅ Applied: {change['file']}")
    return True


# ==============================
# TEST RUNNER
# ==============================

def run_tests():
    """Run pytest and return success/failure"""
    try:
        result = subprocess.run(
            TEST_COMMAND.split(),
            capture_output=True,
            text=True,
            cwd=REPO_PATH
        )
        
        print("🧪 Test output:")
        print(result.stdout[-500:])  # Last 500 chars
        
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Test runner error: {e}")
        return False


# ==============================
# GIT VALIDATION
# ==============================

def git_diff():
    result = subprocess.run(
        ["git", "diff"],
        capture_output=True,
        text=True
    )
    return result.stdout


def git_status():
    result = subprocess.run(
        ["git", "status"],
        capture_output=True,
        text=True
    )
    return result.stdout


# ==============================
# ROLLBACK
# ==============================

def rollback():
    for root, _, files in os.walk(REPO_PATH):
        for f in files:
            if f.endswith(".bak"):
                original = os.path.join(root, f[:-4])
                backup = os.path.join(root, f)
                os.replace(backup, original)
                print(f"↩️ Restored {original}")


# ==============================
# MAIN LOOP WITH FAILURE LOOP
# ==============================

def run():
    print("🚀 AST-aware agent with test runner started")

    for i in range(LOOP_LIMIT):
        print(f"\n🔁 Iteration {i+1}")

        msg = get_last_message()
        parsed = parse_patch(msg)

        changes = parsed.get("changes", [])

        if not changes:
            print("❌ No changes found")
            break

        # Failure loop: retry until tests pass
        for retry in range(MAX_RETRIES):
            print(f"\n🔄 Attempt {retry + 1}/{MAX_RETRIES}")

            # Apply changes safely
            for change in changes:
                if not is_safe(change):
                    print(f"🚫 Unsafe change blocked: {change['file']}")
                    continue

                success = apply_change(change)
                if not success:
                    print(f"⚠️ Failed to apply: {change['file']}")
                    rollback()
                    break

            # Run tests
            tests_passed = run_tests()

            if tests_passed:
                print("✅ Tests passed!")
                break
            else:
                print("❌ Tests failed, rolling back...")
                rollback()
                
                if retry < MAX_RETRIES - 1:
                    print("🔄 Retrying...")
                    time.sleep(2)
                else:
                    print("⚠️ Max retries reached, giving up")
                    break

        # Validate
        diff = git_diff()
        print("📊 Git diff:\n", diff[:500])

        # Commit if tests passed
        if tests_passed:
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
            except Exception as e:
                print(f"⚠️ Git commit failed: {e}")

        time.sleep(3)

    print("✅ Agent done")


if __name__ == "__main__":
    run()
