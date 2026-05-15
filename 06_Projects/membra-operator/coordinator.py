"""
MEMBRA Operator Coordinator
Brings together voice, monitor, LLM, memory, and tools.
"""
import os
import uuid
import threading
import time
from datetime import datetime, timezone

from voice_interface import VoiceInterface
from windsurf_monitor import WindsurfMonitor
from llm_bridge import LLMBridge
from memory_store import MemoryStore
from tools import TOOL_REGISTRY

DEFAULT_WORKSPACE = os.environ.get("MEMBRA_WORKSPACE", str(os.path.expanduser("~/Downloads")))

class MembraOperator:
    def __init__(self, workspace: str = DEFAULT_WORKSPACE):
        self.session_id = uuid.uuid4().hex[:12]
        self.workspace = workspace
        self.voice = VoiceInterface(on_speech_callback=self._on_speech)
        self.monitor = WindsurfMonitor(workspace, on_change_callback=self._on_file_change)
        self.llm = LLMBridge()
        self.memory = MemoryStore()
        self._init_checklist()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self.status = "idle"
        self.last_thought = ""
        self.last_user_message = ""

    def _init_checklist(self):
        self.memory.ensure_checkpoints([
            "backend_starts_cleanly",
            "frontend_builds_cleanly",
            "all_env_vars_set",
            "database_migrations_ok",
            "cors_configured",
            "health_check_passes",
            "no_broken_imports",
            "no_leaked_secrets_in_code",
            "tests_pass_or_smoke_test_exists",
            "README_accurate",
            "deployment_config_valid",
            "production_boundaries_documented",
        ])

    # ─── Voice callbacks ─────────────────────────────────────
    def _on_speech(self, text: str):
        self.last_user_message = text
        self.memory.add_message(self.session_id, "user", f"[voice] {text}")
        self.process_user_input(text)

    def speak(self, text: str):
        self.last_thought = text
        self.voice.speak(text, block=False)
        self.memory.add_message(self.session_id, "assistant", f"[voice] {text}")

    # ─── File monitor callback ──────────────────────────────
    def _on_file_change(self, event: dict):
        # Auto-observe for 3 min pattern detection
        recent = self.monitor.get_open_files_hint()
        if len(recent) >= 3:
            self.last_thought = f"Detected activity on {len(recent)} files"

    # ─── Core loop ─────────────────────────────────────────
    def process_user_input(self, text: str):
        self.status = "thinking"
        # Build context
        context = self._build_context()
        prompt = f"User said: {text}\n\nWorkspace context:\n{context}\n\nRespond briefly (1-2 sentences). If a tool is needed, use JSON tool call."
        response = self.llm.tool_call(prompt, TOOL_REGISTRY, self.memory.get_recent_context(self.session_id, n=10))
        self.status = "idle"
        if response.startswith("[ASK_USER]"):
            # UI layer will show modal
            self.speak("I need to ask you something. Check the window.")
        elif response.startswith("[SPEAK]"):
            self.speak(response.replace("[SPEAK] ", ""))
        else:
            self.speak(response)

    def _build_context(self) -> str:
        lines = []
        lines.append(f"Workspace: {self.workspace}")
        lines.append(f"Tracked files: {self.monitor.summary()['tracked_files']}")
        recent = self.monitor.get_open_files_hint()
        if recent:
            lines.append("Recent files:")
            for p in recent[:6]:
                lines.append(f"  - {os.path.relpath(p, self.workspace)}")
        done, total = self.memory.readiness_score()
        lines.append(f"Production readiness: {done}/{total}")
        return "\n".join(lines)

    # ─── Autonomous watch mode ──────────────────────────────
    def start_watch_mode(self, duration_sec: int = 180):
        """Watch workspace for N seconds, then suggest continuation."""
        self.speak(f"Watching workspace for {duration_sec} seconds.")
        self.status = "watching"
        self._running = True
        self._monitor_thread = threading.Thread(target=self._watch_loop, args=(duration_sec,), daemon=True)
        self._monitor_thread.start()

    def _watch_loop(self, duration_sec: int):
        start = time.time()
        while self._running and (time.time() - start) < duration_sec:
            self.monitor.poll()
            time.sleep(2)
        if self._running:
            self.status = "thinking"
            self._autonomous_continue()

    def _autonomous_continue(self):
        context = self._build_context()
        prompt = (
            "You just observed the workspace for 3 minutes. "
            "Based on recent file changes and the production checklist, "
            "what is the single most obvious next safe step? "
            "Respond in 1 sentence and suggest a tool if applicable."
        )
        response = self.llm.tool_call(
            f"{prompt}\n\n{context}", TOOL_REGISTRY, self.memory.get_recent_context(self.session_id, n=10)
        )
        self.speak(response)
        self.status = "idle"

    # ─── Interview mode ────────────────────────────────────
    def start_interview(self):
        """Ask clarifying questions until intent is clear."""
        questions = [
            "What are you building right now?",
            "Which folder is the active project?",
            "Are you fixing bugs, adding features, or polishing UI?",
            "What is the deployment target? Vercel, Render, or local?",
        ]
        for q in questions:
            self.speak(q)
            # In background mode, we can't block; UI will capture response.
            self.memory.add_message(self.session_id, "assistant", q)
            break  # ask one at a time; UI re-triggers

    # ─── Lifecycle ───────────────────────────────────────────
    def start(self):
        self._running = True
        self.monitor._snapshot = self.monitor._take_snapshot()

    def stop(self):
        self._running = False
        self.voice.stop_background_listener()

    def stats(self) -> dict:
        return {
            "session": self.session_id,
            "status": self.status,
            "workspace": self.workspace,
            "last_thought": self.last_thought,
            "last_user_message": self.last_user_message,
            "readiness": self.memory.readiness_score(),
        }
