from __future__ import annotations
import json
from app.persistence.db import Database

class SnapshotRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def set(self, k: str, v: dict) -> None:
        with self.db.conn() as c:
            c.execute("INSERT INTO snapshots(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, json.dumps(v)))
            c.commit()

    def get(self, k: str, default: dict | None = None) -> dict:
        with self.db.conn() as c:
            row = c.execute("SELECT v FROM snapshots WHERE k=?", (k,)).fetchone()
            if not row:
                return default or {}
            try:
                return json.loads(row[0])
            except Exception:
                return default or {}

    def delete(self, k: str) -> None:
        with self.db.conn() as c:
            c.execute("DELETE FROM snapshots WHERE k=?", (k,))
            c.commit()

    def get_prefix(self, prefix: str) -> dict[str, dict]:
        out: dict[str, dict] = {}
        with self.db.conn() as c:
            rows = c.execute("SELECT k,v FROM snapshots WHERE k LIKE ?", (f"{prefix}%",)).fetchall()
            for row in rows:
                key = str(row[0])
                try:
                    out[key] = json.loads(row[1])
                except Exception:
                    out[key] = {}
        return out
