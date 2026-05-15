from __future__ import annotations
import json
from app.core.clock import utc_now_iso
from app.persistence.db import Database

class FillRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, symbol: str, client_order_id: str, exchange_order_id: str, side: str, fill_qty: int, fill_price: float, payload: dict) -> int:
        with self.db.conn() as c:
            cur = c.execute(
                '''INSERT INTO fills(ts,symbol,client_order_id,exchange_order_id,side,fill_qty,fill_price,payload_json)
                   VALUES(?,?,?,?,?,?,?,?)''',
                (utc_now_iso(), symbol, client_order_id, exchange_order_id, side, fill_qty, fill_price, json.dumps(payload)),
            )
            c.commit()
            return int(cur.lastrowid)
