"""
MEMBRA Operator Windsurf Workspace Monitor
Watches active workspace files and detects patterns.
"""
import os
import time
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

WATCHED_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".json", ".md", ".yml", ".yaml", ".toml", ".sql"}
IGNORED_DIRS = {"node_modules", ".git", "__pycache__", ".next", "dist", "build", ".venv", "venv", "env", ".env"}

class WindsurfMonitor:
    def __init__(self, workspace_path: str, on_change_callback: Callable | None = None):
        self.workspace = Path(workspace_path).expanduser()
        self.on_change = on_change_callback
        self._running = False
        self._snapshot: dict[str, float] = {}
        self._recent_events: list[dict] = []
        self.max_events = 200

    def _should_watch(self, path: Path) -> bool:
        parts = path.parts
        for part in parts:
            if part in IGNORED_DIRS:
                return False
        return path.suffix in WATCHED_EXTENSIONS

    def _take_snapshot(self) -> dict[str, float]:
        snap = {}
        try:
            for p in self.workspace.rglob("*"):
                if p.is_file() and self._should_watch(p):
                    snap[str(p)] = p.stat().st_mtime
        except PermissionError:
            pass
        return snap

    def poll(self) -> list[dict]:
        """Returns list of change events since last poll."""
        new_snap = self._take_snapshot()
        events = []
        old_keys = set(self._snapshot.keys())
        new_keys = set(new_snap.keys())

        for k in new_keys - old_keys:
            events.append({"type": "created", "path": k, "time": now_iso()})
        for k in old_keys - new_keys:
            events.append({"type": "deleted", "path": k, "time": now_iso()})
        for k in old_keys & new_keys:
            if abs(self._snapshot[k] - new_snap[k]) > 0.5:
                events.append({"type": "modified", "path": k, "time": now_iso()})

        self._snapshot = new_snap
        if events:
            self._recent_events.extend(events)
            self._recent_events = self._recent_events[-self.max_events:]
            if self.on_change:
                for ev in events:
                    self.on_change(ev)
        return events

    def start(self, interval_sec: float = 2.0):
        self._running = True
        self._snapshot = self._take_snapshot()
        while self._running:
            self.poll()
            time.sleep(interval_sec)

    def stop(self):
        self._running = False

    def summary(self) -> dict:
        return {
            "workspace": str(self.workspace),
            "tracked_files": len(self._snapshot),
            "recent_events": len(self._recent_events),
            "last_10_events": self._recent_events[-10:],
        }

    def get_open_files_hint(self) -> list[str]:
        """Return recently modified files as likely 'open tabs'."""
        modified = [e["path"] for e in self._recent_events if e["type"] == "modified"]
        # dedupe preserve order
        seen = set()
        out = []
        for p in reversed(modified):
            if p not in seen:
                seen.add(p)
                out.append(p)
        return out[:12]

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
