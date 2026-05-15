"""
MEMBRA Operator Memory Store
Persistent conversation + workspace memory (SQLite).
"""
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path.home() / ".membra_operator" / "memory.db"

class MemoryStore:
    def __init__(self):
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            tool_calls TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id);

        CREATE TABLE IF NOT EXISTS workspace_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            note TEXT NOT NULL,
            tag TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_notes_path ON workspace_notes(file_path);

        CREATE TABLE IF NOT EXISTS production_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            checkpoint TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            verified_at TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS user_facts (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """)
        self.conn.commit()

    # ─── Conversation ──────────────────────────────────────────
    def add_message(self, session_id: str, role: str, content: str, tool_calls: dict | None = None):
        self.conn.execute(
            "INSERT INTO conversations (session_id, role, content, tool_calls, created_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, role, content, json.dumps(tool_calls) if tool_calls else None, now_iso()),
        )
        self.conn.commit()

    def get_session_messages(self, session_id: str, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content, tool_calls FROM conversations WHERE session_id = ? ORDER BY id LIMIT ?",
            (session_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            m = {"role": r["role"], "content": r["content"]}
            if r["tool_calls"]:
                m["tool_calls"] = json.loads(r["tool_calls"])
            out.append(m)
        return out

    def get_recent_context(self, session_id: str, n: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT role, content FROM conversations WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, n),
        ).fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    # ─── Workspace Notes ─────────────────────────────────────
    def add_note(self, file_path: str, note: str, tag: str | None = None):
        self.conn.execute(
            "INSERT INTO workspace_notes (file_path, note, tag, created_at) VALUES (?, ?, ?, ?)",
            (file_path, note, tag, now_iso()),
        )
        self.conn.commit()

    def get_notes_for_file(self, file_path: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT note, tag, created_at FROM workspace_notes WHERE file_path = ? ORDER BY id DESC",
            (file_path,),
        ).fetchall()
        return [{"note": r["note"], "tag": r["tag"], "created_at": r["created_at"]} for r in rows]

    # ─── Production Checklist ────────────────────────────────
    def ensure_checkpoints(self, checkpoints: list[str]):
        for cp in checkpoints:
            self.conn.execute(
                "INSERT OR IGNORE INTO production_checklist (checkpoint, status) VALUES (?, 'pending')",
                (cp,),
            )
        self.conn.commit()

    def mark_checkpoint(self, checkpoint: str, status: str, notes: str = ""):
        self.conn.execute(
            "UPDATE production_checklist SET status = ?, verified_at = ?, notes = ? WHERE checkpoint = ?",
            (status, now_iso(), notes, checkpoint),
        )
        self.conn.commit()

    def get_checklist(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT checkpoint, status, verified_at, notes FROM production_checklist ORDER BY checkpoint"
        ).fetchall()
        return [{"checkpoint": r["checkpoint"], "status": r["status"], "verified_at": r["verified_at"], "notes": r["notes"]} for r in rows]

    def readiness_score(self) -> tuple[int, int]:
        total = self.conn.execute("SELECT COUNT(*) FROM production_checklist").fetchone()[0]
        done = self.conn.execute("SELECT COUNT(*) FROM production_checklist WHERE status = 'passed'").fetchone()[0]
        return done, total

    # ─── User Facts ──────────────────────────────────────────
    def remember(self, key: str, value: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO user_facts (key, value, updated_at) VALUES (?, ?, ?)",
            (key, value, now_iso()),
        )
        self.conn.commit()

    def recall(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM user_facts WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
