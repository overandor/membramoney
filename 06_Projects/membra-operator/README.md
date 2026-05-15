# MEMBRA Operator

Persistent AI pair-programmer macOS app for Windsurf / MEMBRA workspaces.

## Features

- **Voice Interaction** — TTS via macOS `say`, STT via speech_recognition (microphone optional)
- **Local LLM** — Ollama integration (`qwen2.5:0.5b` / `llama3.2:1b` fallback)
- **Memory** — SQLite persistent conversation + workspace notes + user facts
- **Tools** — `read_file`, `edit_file`, `list_dir`, `run_command`, `ask_user`, `mark_ready`, `speak`
- **Windsurf Monitor** — File-system watcher that detects workspace patterns
- **Interview Mode** — Asks clarifying questions when intent is unclear
- **Watch Mode** — Observes workspace for 3 minutes, then suggests next step
- **Production Readiness Tracker** — 12-point checklist with scoring

## Quick Start

```bash
cd membra-operator
pip install -r requirements.txt
python main.py
```

## Build DMG

```bash
./build_dmg.sh
```

Output: `dist/MEMBRA-Operator-0.1.0.dmg` (~64 MB)

## Voice Commands

- Click **Listen** to enable background STT
- Speak naturally: "Continue", "Build the project", "What's broken", "Mark backend starts cleanly as passed"

## Keyboard

- Type commands in the chat input
- Quick buttons: **Continue**, **Build**, **Test**, **Deploy**

## Ollama

Requires Ollama running locally:
```bash
ollama pull qwen2.5:0.5b
ollama serve
```

## Files

- `main.py` — Tkinter UI entry point
- `coordinator.py` — Core operator logic
- `voice_interface.py` — TTS/STT
- `windsurf_monitor.py` — Workspace watcher
- `llm_bridge.py` — Ollama client with tool support
- `memory_store.py` — SQLite persistence
- `tools.py` — Tool registry

## Production Boundaries

- No fake payments
- No custody
- No guaranteed profit
- Owner confirmation before visibility
- External settlement rails only
