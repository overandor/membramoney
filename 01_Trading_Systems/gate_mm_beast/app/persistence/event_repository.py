from __future__ import annotations
import json
from app.core.clock import utc_now_iso
from app.persistence.db import Database

class EventRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def write(self, level: str, kind: str, symbol: str, payload: dict) -> None:
        with self.db.conn() as c:
            c.execute(
                "INSERT INTO events(ts,level,kind,symbol,payload_json) VALUES(?,?,?,?,?)",
                (utc_now_iso(), level, kind, symbol, json.dumps(payload)),
            )
            c.commit()

    def recent(self, limit: int = 100) -> list[dict]:
        with self.db.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)).fetchall()]
