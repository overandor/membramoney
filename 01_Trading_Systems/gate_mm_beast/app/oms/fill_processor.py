from __future__ import annotations
from app.persistence.fill_repository import FillRepository
from app.persistence.order_repository import OrderRepository
from app.persistence.position_repository import PositionRepository

class FillProcessor:
    def __init__(self, fills: FillRepository, orders: OrderRepository, positions: PositionRepository) -> None:
        self.fills = fills
        self.orders = orders
        self.positions = positions

    def record_fill(self, symbol: str, client_order_id: str, exchange_order_id: str, side: str, fill_qty: int, fill_price: float, payload: dict) -> None:
        self.fills.insert(symbol, client_order_id, exchange_order_id, side, fill_qty, fill_price, payload)
