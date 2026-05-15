from __future__ import annotations
import sqlite3
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    level TEXT NOT NULL,
    kind TEXT NOT NULL,
    symbol TEXT,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    score REAL NOT NULL,
    confidence REAL NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    client_order_id TEXT,
    exchange_order_id TEXT,
    side TEXT NOT NULL,
    role TEXT NOT NULL,
    state TEXT NOT NULL,
    price REAL,
    size INTEGER NOT NULL,
    filled_size INTEGER DEFAULT 0,
    avg_fill_price REAL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS positions(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_open TEXT NOT NULL,
    ts_close TEXT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    status TEXT NOT NULL,
    qty INTEGER NOT NULL,
    entry_vwap REAL,
    exit_vwap REAL,
    realized_pnl REAL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fills(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    symbol TEXT NOT NULL,
    client_order_id TEXT,
    exchange_order_id TEXT,
    side TEXT NOT NULL,
    fill_qty INTEGER NOT NULL,
    fill_price REAL NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots(
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);
'''

class Database:
    def __init__(self, path: str) -> None:
        self.path = str(Path(path))
        self.init()

    def conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def init(self) -> None:
        with self.conn() as c:
            c.executescript(SCHEMA)
            c.commit()
