import os
import json
import time
import subprocess
import requests
from pathlib import Path
from playwright.sync_api import sync_playwright

# ==============================
# CONFIG
# ==============================

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3"
REPO_PATH = os.getcwd()
LOOP_LIMIT = 10


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
      "action": "create|update",
      "content": "full new file content"
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
# APPLY PATCH
# ==============================

def apply_change(change):
    file_path = Path(REPO_PATH) / change["file"]

    # create dirs if needed
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # backup
    if file_path.exists():
        backup_path = str(file_path) + ".bak"
        with open(file_path, "r") as f:
            old = f.read()
        with open(backup_path, "w") as f:
            f.write(old)

    # write new content
    with open(file_path, "w") as f:
        f.write(change["content"])

    print(f"✅ Applied: {change['file']}")


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
# DECISION ENGINE
# ==============================

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
# MAIN LOOP
# ==============================

def run():
    print("🚀 Patch-based agent started")

    for i in range(LOOP_LIMIT):
        print(f"\n🔁 Iteration {i+1}")

        msg = get_last_message()
        parsed = parse_patch(msg)

        changes = parsed.get("changes", [])

        if not changes:
            print("❌ No changes found")
            break

        # Apply changes safely
        for change in changes:
            if not is_safe(change):
                print(f"🚫 Unsafe change blocked: {change['file']}")
                continue

            apply_change(change)

        # Validate
        diff = git_diff()
        print("📊 Git diff:\n", diff[:500])

        decision = decide(diff)
        print(f"🧠 Decision: {decision}")

        if decision == "rollback":
            rollback()
            break

        if decision == "stop":
            break

        time.sleep(3)

    print("✅ Agent done")


if __name__ == "__main__":
    run()
