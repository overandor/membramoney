from __future__ import annotations
import json
from app.core.clock import utc_now_iso
from app.persistence.db import Database

class OrderRepository:
    def __init__(self, db: Database) -> None:
        self.db = db

    def insert(self, symbol: str, client_order_id: str, exchange_order_id: str, side: str, role: str, state: str, price: float, size: int, payload: dict) -> int:
        with self.db.conn() as c:
            cur = c.execute(
                '''INSERT INTO orders(ts,symbol,client_order_id,exchange_order_id,side,role,state,price,size,payload_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?)''',
                (utc_now_iso(), symbol, client_order_id, exchange_order_id, side, role, state, price, size, json.dumps(payload)),
            )
            c.commit()
            return int(cur.lastrowid)

    def update_state(self, client_order_id: str, state: str, filled_size: int | None = None, avg_fill_price: float | None = None) -> None:
        updates = ["state=?"]
        vals = [state]
        if filled_size is not None:
            updates.append("filled_size=?")
            vals.append(filled_size)
        if avg_fill_price is not None:
            updates.append("avg_fill_price=?")
            vals.append(avg_fill_price)
        vals.append(client_order_id)
        with self.db.conn() as c:
            c.execute(f"UPDATE orders SET {', '.join(updates)} WHERE client_order_id=?", vals)
            c.commit()

    def open_orders(self, symbol: str | None = None) -> list[dict]:
        sql = "SELECT * FROM orders WHERE state IN ('NEW','ACK','OPEN','PARTIAL')"
        params = []
        if symbol:
            sql += " AND symbol=?"
            params.append(symbol)
        with self.db.conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]
