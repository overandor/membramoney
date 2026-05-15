from __future__ import annotations
import json
from app.core.clock import utc_now_iso
from app.persistence.db import Database

class DecisionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, symbol: str, score: float, confidence: float, payload: dict) -> int:
        with self.db.conn() as c:
            cur = c.execute(
                "INSERT INTO decisions(ts,symbol,score,confidence,payload_json) VALUES(?,?,?,?,?)",
                (utc_now_iso(), symbol, score, confidence, json.dumps(payload)),
            )
            c.commit()
            return int(cur.lastrowid)
