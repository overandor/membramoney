import pyautogui
import base64
import time
import requests
from PIL import Image
import io
import json

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llava"
LOOP_DELAY = 5


def take_screenshot():
    screenshot = pyautogui.screenshot()
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def ask_ollama(image_b64):
    prompt = """
You are controlling a desktop UI.

Find:
1. The "Accept All" button in Windsurf
2. The latest ChatGPT response area

Return STRICT JSON only:

{
  "click": {"x": int, "y": int},
  "copy_area": {"x1": int, "y1": int, "x2": int, "y2": int}
}
"""

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
    )

    data = response.json()
    return data["response"]


def safe_parse(text):
    try:
        return json.loads(text)
    except:
        print("⚠️ Bad JSON from model:", text)
        return None


def perform_actions(parsed):
    if not parsed:
        return

    try:
        # Click Accept All
        x = parsed["click"]["x"]
        y = parsed["click"]["y"]
        pyautogui.click(x, y)

        time.sleep(0.5)

        # Copy ChatGPT area
        area = parsed["copy_area"]
        pyautogui.moveTo(area["x1"], area["y1"])
        pyautogui.dragTo(area["x2"], area["y2"], duration=0.5)
        pyautogui.hotkey("command", "c")

    except Exception as e:
        print("❌ Action error:", e)


def paste_to_windsurf():
    pyautogui.hotkey("command", "2")
    time.sleep(0.5)
    pyautogui.hotkey("command", "v")


def run():
    print("🤖 Local Vision Agent (Ollama) running...")
    time.sleep(2)

    while True:
        try:
            img = take_screenshot()
            result = ask_ollama(img)

            print("\n🧠 Model Output:", result)

            parsed = safe_parse(result)
            perform_actions(parsed)
            paste_to_windsurf()

            time.sleep(LOOP_DELAY)

        except Exception as e:
            print("❌ Loop error:", e)
            time.sleep(2)


if __name__ == "__main__":
    run()
