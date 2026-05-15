from __future__ import annotations

from app.constants import ORDER_STATE_FILLED, ORDER_STATE_OPEN, ORDER_STATE_PARTIAL
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
        self._update_order(symbol, client_order_id, fill_qty, fill_price)
        self._apply_to_position(symbol, side, fill_qty, fill_price)

    def _update_order(self, symbol: str, client_order_id: str, fill_qty: int, fill_price: float) -> None:
        order = self.orders.get_by_client_order_id(client_order_id)
        if not order:
            # Keep the fill even if the order row is missing.
            return
        current_filled = int(order.get("filled_size") or 0)
        order_size = abs(int(order.get("size") or 0))
        new_filled = min(current_filled + abs(fill_qty), order_size) if order_size > 0 else current_filled + abs(fill_qty)
        current_avg = float(order.get("avg_fill_price") or 0.0)
        if current_filled > 0 and current_avg > 0:
            avg_fill_price = ((current_avg * current_filled) + (fill_price * abs(fill_qty))) / max(new_filled, 1)
        else:
            avg_fill_price = fill_price
        state = ORDER_STATE_FILLED if order_size and new_filled >= order_size else ORDER_STATE_PARTIAL
        if state == ORDER_STATE_PARTIAL and new_filled == 0:
            state = ORDER_STATE_OPEN
        self.orders.update_state(client_order_id, state, filled_size=new_filled, avg_fill_price=avg_fill_price)

    def _apply_to_position(self, symbol: str, side: str, fill_qty: int, fill_price: float) -> None:
        fill_qty = abs(int(fill_qty))
        if fill_qty <= 0:
            return
        pos = self.positions.get_open(symbol)
        if not pos:
            self.positions.open_position(symbol, side, fill_qty, fill_price, {"source": "fill_processor"})
            return

        pos_side = str(pos.get("side") or "")
        pos_qty = int(pos.get("qty") or 0)
        entry_vwap = float(pos.get("entry_vwap") or 0.0)

        if pos_side == side:
            new_qty = pos_qty + fill_qty
            new_vwap = ((entry_vwap * pos_qty) + (fill_price * fill_qty)) / max(new_qty, 1)
            self.positions.update_open_position(symbol, side, new_qty, new_vwap, {"source": "fill_processor", "mode": "scale_in"})
            return

        closing_qty = min(pos_qty, fill_qty)
        realized = self._realized_pnl(pos_side, closing_qty, entry_vwap, fill_price)

        if fill_qty < pos_qty:
            remaining = pos_qty - fill_qty
            self.positions.update_open_position(symbol, pos_side, remaining, entry_vwap, {"source": "fill_processor", "mode": "partial_close", "realized_pnl": realized})
            return

        self.positions.close_position(symbol, fill_price, realized)
        if fill_qty > pos_qty:
            reverse_qty = fill_qty - pos_qty
            self.positions.open_position(symbol, side, reverse_qty, fill_price, {"source": "fill_processor", "mode": "reverse_after_close"})

    @staticmethod
    def _realized_pnl(open_side: str, qty: int, entry_vwap: float, exit_vwap: float) -> float:
        if open_side == "buy":
            return (exit_vwap - entry_vwap) * qty
        return (entry_vwap - exit_vwap) * qty
