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
                """INSERT INTO orders(ts,symbol,client_order_id,exchange_order_id,side,role,state,price,size,payload_json)
                   VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (utc_now_iso(), symbol, client_order_id, exchange_order_id, side, role, state, price, size, json.dumps(payload)),
            )
            c.commit()
            return int(cur.lastrowid)

    def get_by_client_order_id(self, client_order_id: str) -> dict | None:
        with self.db.conn() as c:
            row = c.execute("SELECT * FROM orders WHERE client_order_id=? ORDER BY id DESC LIMIT 1", (client_order_id,)).fetchone()
            return dict(row) if row else None

    def update_state(self, client_order_id: str, state: str, filled_size: int | None = None, avg_fill_price: float | None = None) -> None:
        updates = ["state=?"]
        vals: list[object] = [state]
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

    def update_exchange_order_id(self, client_order_id: str, exchange_order_id: str) -> None:
        with self.db.conn() as c:
            c.execute("UPDATE orders SET exchange_order_id=? WHERE client_order_id=?", (exchange_order_id, client_order_id))
            c.commit()

    def open_orders(self, symbol: str | None = None) -> list[dict]:
        sql = "SELECT * FROM orders WHERE state IN ('NEW','ACK','OPEN','PARTIAL')"
        params: list[object] = []
        if symbol:
            sql += " AND symbol=?"
            params.append(symbol)
        with self.db.conn() as c:
            return [dict(r) for r in c.execute(sql, params).fetchall()]

    def count_open_orders(self) -> int:
        with self.db.conn() as c:
            row = c.execute("SELECT COUNT(*) AS n FROM orders WHERE state IN ('NEW','ACK','OPEN','PARTIAL')").fetchone()
            return int(row["n"]) if row else 0
