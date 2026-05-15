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
