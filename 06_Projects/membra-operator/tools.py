"""
MEMBRA Operator Tool Registry
Functions the LLM can invoke.
"""
import os
import subprocess
from pathlib import Path

def read_file(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"[error] File not found: {path}"
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:8000]
    except Exception as e:
        return f"[error] {e}"

def edit_file(path: str, old: str, new: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"[error] File not found: {path}"
    try:
        text = p.read_text(encoding="utf-8")
        if old not in text:
            return f"[error] old_string not found in {path}"
        text = text.replace(old, new, 1)
        p.write_text(text, encoding="utf-8")
        return f"[ok] Edited {path}"
    except Exception as e:
        return f"[error] {e}"

def list_dir(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists():
        return f"[error] Path not found: {path}"
    try:
        items = []
        for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            typ = "dir" if child.is_dir() else "file"
            size = child.stat().st_size if child.is_file() else 0
            items.append(f"{typ:4} {size:>10}  {child.name}")
        return "\n".join(items[:200])
    except Exception as e:
        return f"[error] {e}"

def run_command(cmd: str) -> str:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
        out = result.stdout[:4000]
        err = result.stderr[:2000]
        status = "ok" if result.returncode == 0 else f"exit {result.returncode}"
        lines = [f"[{status}]"]
        if out:
            lines.append(out)
        if err:
            lines.append("[stderr] " + err)
        return "\n".join(lines)
    except subprocess.TimeoutExpired:
        return "[error] Command timed out after 60s"
    except Exception as e:
        return f"[error] {e}"

def ask_user(question: str) -> str:
    # Handled by UI layer; this stub returns the question so the caller knows to prompt.
    return f"[ASK_USER] {question}"

def mark_ready(checkpoint: str) -> str:
    from memory_store import MemoryStore
    mem = MemoryStore()
    mem.mark_checkpoint(checkpoint, "passed", "Auto-verified by operator")
    done, total = mem.readiness_score()
    return f"[ok] Checkpoint '{checkpoint}' marked passed. Score: {done}/{total}"

def speak(text: str) -> str:
    # Handled by voice layer
    return f"[SPEAK] {text}"

TOOL_REGISTRY = {
    "read_file": read_file,
    "edit_file": edit_file,
    "list_dir": list_dir,
    "run_command": run_command,
    "ask_user": ask_user,
    "mark_ready": mark_ready,
    "speak": speak,
}
