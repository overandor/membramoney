import time
import json
import subprocess
import pyautogui
import pyperclip
import requests
from playwright.sync_api import sync_playwright

# ==============================
# CONFIG
# ==============================

CHATGPT_URL = "https://chat.openai.com"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3"

LOOP_LIMIT = 10
DELAY = 5

# ==============================
# PLAYWRIGHT: GET LAST MESSAGE
# ==============================

def get_last_chatgpt_message():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        page.goto(CHATGPT_URL)

        print("➡️ Waiting for ChatGPT UI...")
        page.wait_for_selector("div[data-message-author-role='assistant']")

        messages = page.query_selector_all(
            "div[data-message-author-role='assistant']"
        )

        if not messages:
            return None

        last = messages[-1].inner_text()
        browser.close()
        return last


# ==============================
# OLLAMA: PARSE MESSAGE
# ==============================

def ollama_parse(text):
    prompt = f"""
You are an AI coding agent.

Extract:
- task
- instructions
- code_blocks (if any)

Return JSON only:
{{
  "task": "...",
  "instructions": "...",
  "code_blocks": ["..."]
}}

TEXT:
{text}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
    )

    data = response.json()
    try:
        return json.loads(data["response"])
    except:
        print("⚠️ Failed to parse JSON, raw output used")
        return {"instructions": data["response"], "code_blocks": []}


# ==============================
# WINDSURF CONTROL
# ==============================

def focus_windsurf():
    pyautogui.hotkey("command", "2")  # adjust if needed
    time.sleep(1)


def paste_to_windsurf(text):
    pyperclip.copy(text)
    focus_windsurf()
    pyautogui.hotkey("command", "v")


# ==============================
# REPO CHECK
# ==============================

def get_repo_status():
    result = subprocess.run(
        ["git", "status"],
        capture_output=True,
        text=True
    )
    return result.stdout


# ==============================
# DECISION ENGINE (OLLAMA)
# ==============================

def decide_next(repo_status):
    prompt = f"""
You are controlling an autonomous coding agent.

Repo state:
{repo_status}

Decide next step:
- continue
- stop

Respond ONLY with one word.
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
    )

    decision = response.json()["response"].strip().lower()

    if "stop" in decision:
        return "stop"
    return "continue"


# ==============================
# MAIN LOOP
# ==============================

def run_agent():
    print("🚀 Starting agent...")

    for i in range(LOOP_LIMIT):
        print(f"\n🔁 Loop {i+1}")

        try:
            # 1. Get ChatGPT output
            msg = get_last_chatgpt_message()
            if not msg:
                print("❌ No message found")
                break

            print("📥 Pulled message")

            # 2. Parse with Ollama
            parsed = ollama_parse(msg)

            instructions = parsed.get("instructions", "")
            code_blocks = parsed.get("code_blocks", [])

            full_text = instructions + "\n\n" + "\n\n".join(code_blocks)

            # 3. Paste into Windsurf
            paste_to_windsurf(full_text)
            print("📤 Sent to Windsurf")

            time.sleep(DELAY)

            # 4. Check repo
            repo = get_repo_status()
            print("📊 Repo checked")

            # 5. Decide next
            decision = decide_next(repo)
            print(f"🧠 Decision: {decision}")

            if decision == "stop":
                print("🛑 Agent stopped by decision engine")
                break

        except Exception as e:
            print(f"🔥 Error: {e}")
            break

    print("✅ Agent finished")


# ==============================
# ENTRY
# ==============================

if __name__ == "__main__":
    run_agent()
