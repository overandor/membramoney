from __future__ import annotations
from app.constants import *
from app.core.ids import client_order_id
from app.oms.order_state import can_transition
from app.persistence.order_repository import OrderRepository
from app.oms.execution_service import ExecutionService

class OrderManager:
    def __init__(self, repo: OrderRepository, execution: ExecutionService) -> None:
        self.repo = repo
        self.execution = execution

    async def submit_limit(self, symbol: str, side: str, role: str, price: float, size: int, reduce_only: bool = False, tif: str = "poc") -> str:
        coid = client_order_id(role, symbol)
        self.repo.insert(symbol, coid, "", side, role, ORDER_STATE_NEW, price, size, {"reduce_only": reduce_only, "tif": tif})
        resp = await self.execution.submit(symbol, size, price, coid, reduce_only, tif)
        self.repo.update_state(coid, ORDER_STATE_ACK)
        return coid

    def transition(self, client_order_id: str, old: str, new: str) -> bool:
        if not can_transition(old, new):
            return False
        self.repo.update_state(client_order_id, new)
        return True
