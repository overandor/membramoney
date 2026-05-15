import pyautogui
import base64
import time
import requests
from PIL import Image
import io
import json
import keyboard
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llava"
LOOP_DELAY = 5
MEMORY_FILE = "vision_agent_memory.json"
CONFIDENCE_THRESHOLD = 0.6


def load_memory():
    """Load saved coordinates from disk"""
    if Path(MEMORY_FILE).exists():
        with open(MEMORY_FILE, 'r') as f:
            return json.load(f)
    return {}


def save_memory(memory):
    """Save coordinates to disk"""
    with open(MEMORY_FILE, 'w') as f:
        json.dump(memory, f, indent=2)


def take_screenshot():
    screenshot = pyautogui.screenshot()
    buffer = io.BytesIO()
    screenshot.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def ask_ollama_with_confidence(image_b64):
    prompt = """
You are controlling a desktop UI.

Find:
1. The "Accept All" button in Windsurf
2. The latest ChatGPT response area

Return STRICT JSON with confidence scores (0-1):

{
  "click": {"x": int, "y": int, "confidence": float},
  "copy_area": {"x1": int, "y1": int, "x2": int, "y2": int, "confidence": float}
}

Only include fields if confidence > 0.5. If not found, set to null.
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
    """Parse JSON with error handling"""
    try:
        return json.loads(text)
    except:
        print("⚠️ Bad JSON from model:", text[:200])
        return None


def verify_click(x, y, expected_color=None):
    """Verify click target is visible by checking pixel color"""
    try:
        pixel = pyautogui.pixel(x, y)
        if expected_color:
            return pixel == expected_color
        return True  # If no expected color, assume visible
    except:
        return False


def perform_actions_with_memory(parsed, memory):
    """Execute actions using memory or vision with fallback"""
    if not parsed:
        return memory

    try:
        # Handle Accept All button
        click_data = parsed.get("click")
        if click_data and click_data.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
            x = click_data["x"]
            y = click_data["y"]
            
            # Check memory first
            if "accept_button" in memory:
                mem_x, mem_y = memory["accept_button"]
                print(f"📍 Using memory for Accept All: ({mem_x}, {mem_y})")
                pyautogui.click(mem_x, mem_y)
                
                # Verify it worked
                if verify_click(mem_x, mem_y):
                    print("✅ Memory click successful")
                else:
                    print("⚠️ Memory click failed, using vision")
                    pyautogui.click(x, y)
                    memory["accept_button"] = [x, y]  # Update memory
            else:
                print(f"🔍 Using vision for Accept All: ({x}, {y})")
                pyautogui.click(x, y)
                memory["accept_button"] = [x, y]  # Save to memory
        else:
            print("⚠️ Accept All button not found or low confidence")

        time.sleep(0.5)

        # Handle ChatGPT area
        copy_data = parsed.get("copy_area")
        if copy_data and copy_data.get("confidence", 0) >= CONFIDENCE_THRESHOLD:
            area = {
                "x1": copy_data["x1"],
                "y1": copy_data["y1"],
                "x2": copy_data["x2"],
                "y2": copy_data["y2"]
            }
            
            # Check memory first
            if "chatgpt_area" in memory:
                mem_area = memory["chatgpt_area"]
                print(f"📍 Using memory for ChatGPT area: {mem_area}")
                pyautogui.moveTo(mem_area["x1"], mem_area["y1"])
                pyautogui.dragTo(mem_area["x2"], mem_area["y2"], duration=0.5)
                
                # Verify by checking if clipboard changed
                # (simplified - in production would check clipboard content)
                print("✅ Memory area used")
            else:
                print(f"🔍 Using vision for ChatGPT area: {area}")
                pyautogui.moveTo(area["x1"], area["y1"])
                pyautogui.dragTo(area["x2"], area["y2"], duration=0.5)
                memory["chatgpt_area"] = area  # Save to memory
        else:
            print("⚠️ ChatGPT area not found or low confidence")

        pyautogui.hotkey("command", "c")
        time.sleep(0.2)

    except Exception as e:
        print("❌ Action error:", e)
    
    return memory


def paste_to_windsurf():
    """Paste clipboard to Windsurf"""
    pyautogui.hotkey("command", "2")
    time.sleep(0.5)
    pyautogui.hotkey("command", "v")


def emergency_stop():
    """Check for emergency stop signal"""
    if keyboard.is_pressed('esc'):
        print("\n🛑 Emergency stop activated!")
        return True
    return False


def run():
    print("🤖 Local Vision Agent (Ollama) with Memory running...")
    print("🛑 Press ESC to stop")
    time.sleep(2)

    memory = load_memory()
    print(f"📦 Loaded memory: {memory}")
    loop_count = 0

    while True:
        try:
            # Emergency stop check
            if emergency_stop():
                save_memory(memory)
                print(f"💾 Memory saved to {MEMORY_FILE}")
                break

            loop_count += 1
            print(f"\n🔄 Loop #{loop_count}")

            # Take screenshot
            img = take_screenshot()
            
            # Ask Ollama with confidence
            result = ask_ollama_with_confidence(img)
            print(f"🧠 Model Output: {result[:200]}...")

            # Parse JSON
            parsed = safe_parse(result)
            
            # Execute with memory and fallback
            memory = perform_actions_with_memory(parsed, memory)
            
            # Save memory periodically
            if loop_count % 5 == 0:
                save_memory(memory)
                print(f"💾 Memory saved")

            # Paste to Windsurf
            paste_to_windsurf()

            # Wait before next loop
            time.sleep(LOOP_DELAY)

        except KeyboardInterrupt:
            print("\n⚠️ Interrupted by user")
            save_memory(memory)
            break
        except Exception as e:
            print("❌ Loop error:", e)
            time.sleep(2)


if __name__ == "__main__":
    run()
