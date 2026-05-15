from __future__ import annotations
import json
from app.core.clock import utc_now_iso
from app.persistence.db import Database

class PositionRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def open_position(self, symbol: str, side: str, qty: int, entry_vwap: float, payload: dict) -> int:
        with self.db.conn() as c:
            cur = c.execute(
                '''INSERT INTO positions(ts_open,symbol,side,status,qty,entry_vwap,payload_json)
                   VALUES(?,?,?,?,?,?,?)''',
                (utc_now_iso(), symbol, side, "open", qty, entry_vwap, json.dumps(payload)),
            )
            c.commit()
            return int(cur.lastrowid)

    def close_position(self, symbol: str, exit_vwap: float, realized_pnl: float) -> None:
        with self.db.conn() as c:
            c.execute(
                "UPDATE positions SET ts_close=?, status='closed', exit_vwap=?, realized_pnl=? WHERE symbol=? AND status='open'",
                (utc_now_iso(), exit_vwap, realized_pnl, symbol),
            )
            c.commit()

    def get_open(self, symbol: str) -> dict | None:
        with self.db.conn() as c:
            row = c.execute("SELECT * FROM positions WHERE symbol=? AND status='open' ORDER BY id DESC LIMIT 1", (symbol,)).fetchone()
            return dict(row) if row else None
