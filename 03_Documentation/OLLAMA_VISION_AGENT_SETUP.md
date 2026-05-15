# Ollama Vision Agent - Local UI Automation

## Overview

Fully local vision-based UI automation agent using Ollama for computer vision and PyAutoGUI for desktop control. No API costs, works offline.

## Architecture

```
Screenshot → Local Vision Model (Ollama/LLaVA) → JSON Actions → Execute
```

- **Ollama** = Brain (local inference)
- **PyAutoGUI** = Hands (UI control)
- **Screenshot** = Eyes (visual input)

## Installation

### 1. Install Ollama

```bash
brew install ollama
```

### 2. Start Ollama Server

```bash
ollama serve
```

### 3. Pull Vision-Capable Model

**Critical:** Must use a vision model. Text-only models (like llama3) will NOT work.

```bash
ollama pull llava
```

Alternative vision models:
- `llava` (default, good balance)
- `llava:13b` (more accurate, slower)
- `bakllava` (smaller, faster)

### 4. Install Python Dependencies

```bash
pip install -r ollama_vision_requirements.txt
```

Or manually:
```bash
pip install pyautogui pillow requests
```

## Usage

### Basic Run

```bash
python ollama_vision_agent.py
```

### What It Does

The agent loops continuously:

1. **Takes screenshot** of entire desktop
2. **Sends to Ollama** with vision prompt
3. **Parses JSON response** for coordinates
4. **Clicks "Accept All"** button in Windsurf
5. **Selects and copies** ChatGPT response area
6. **Pastes** to Windsurf (Cmd+2, Cmd+V)
7. **Waits 5 seconds** and repeats

## Configuration

Edit these in `ollama_vision_agent.py`:

```python
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llava"  # Change to llava:13b for better accuracy
LOOP_DELAY = 5   # Seconds between loops
```

## Current Prompt

The agent looks for:
1. "Accept All" button in Windsurf
2. Latest ChatGPT response area

Returns JSON:
```json
{
  "click": {"x": 1234, "y": 567},
  "copy_area": {"x1": 100, "y1": 200, "x2": 500, "y2": 600}
}
```

## Limitations

### 1. LLaVA Precision

LLaVA is not pixel-perfect:
- May miss buttons
- Gives rough coordinates
- Sometimes hallucinates UI elements

**Mitigation:** Use larger model (`llava:13b`) for better accuracy.

### 2. No Bounding Box Grounding

Unlike advanced vision APIs:
- Ollama models don't return structured detections
- They "guess" coordinates based on visual understanding
- No confidence scores or alternative suggestions

### 3. Performance

Each loop includes:
- Screenshot capture
- Base64 encoding
- HTTP request to Ollama
- Local inference

**Performance depends on:**
- CPU/GPU hardware
- Model size (llava vs llava:13b)
- Screen resolution

## Next Steps: Memory + Fallback

To make this production-ready, implement:

### 1. Memory System

Save discovered coordinates:
```python
memory = {
    "accept_button": [x, y],
    "chatgpt_area": [x1, y1, x2, y2]
}
```

### 2. Fallback Logic

```python
def click_with_fallback(target):
    # Try memory first
    if target in memory:
        pyautogui.click(memory[target])
    else:
        # Use vision
        coords = ask_ollama(screenshot())
        memory[target] = coords
        pyautogui.click(coords)
```

### 3. Confidence Scoring

Add confidence to JSON response:
```json
{
  "click": {"x": 1234, "y": 567, "confidence": 0.8},
  "copy_area": {...}
}
```

Only execute if confidence > threshold.

## Troubleshooting

### "Bad JSON from model"

The model didn't return valid JSON. Try:
- Using larger model (`llava:13b`)
- Simplifying the prompt
- Adding "Return ONLY JSON" emphasis

### "Action error: key not found"

JSON structure mismatch. Check:
- Model output format
- Prompt instructions
- JSON parsing logic

### Ollama connection refused

Make sure Ollama is running:
```bash
ollama serve
```

Check if port 11434 is accessible:
```bash
curl http://localhost:11434/api/generate
```

### Clicks are inaccurate

Try:
- Larger model (`llava:13b`)
- Smaller screen region (crop to Windsurf window)
- Multiple coordinate samples and average

## Advanced: Custom Prompts

Modify the prompt for different tasks:

### Example: Find Any Button

```python
prompt = """
Find any clickable button in the UI.

Return JSON:
{
  "button": {"x": int, "y": int, "label": str}
}
"""
```

### Example: Read Text

```python
prompt = """
Read all visible text in the UI.

Return JSON:
{
  "text": [
    {"content": str, "x": int, "y": int}
  ]
}
"""
```

## Safety

### Fail-Safe

Add emergency stop:
```python
import keyboard

def emergency_stop():
    if keyboard.is_pressed('esc'):
        print("🛑 Emergency stop!")
        exit()

# In loop:
emergency_stop()
```

### Screen Bounds

Limit actions to specific window:
```python
def crop_to_window(screenshot, window_bounds):
    x, y, w, h = window_bounds
    return screenshot.crop((x, y, x+w, y+h))
```

## Performance Tips

1. **Use smaller model** for speed: `llava`
2. **Crop screenshot** to relevant area only
3. **Increase LOOP_DELAY** if CPU is slow
4. **Use GPU acceleration** if available (Ollama auto-detects)

## Alternative Vision Models

Try different models:

```bash
ollama pull bakllava    # Smaller, faster
ollama pull llava:13b   # More accurate, slower
ollama pull llava:34b   # Best accuracy, very slow
```

## Next Prompt

To add memory + fallback + confidence scoring:

**"Add memory system to save discovered coordinates, fallback logic to reuse memory before vision, and confidence scoring for JSON responses to only execute high-confidence actions."**

This will transform it from a simple loop into a stable, learning agent.
