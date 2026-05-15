from __future__ import annotations
from app.connectors.gateio.rest_private import GatePrivateRest

class ExecutionService:
    def __init__(self, private_rest: GatePrivateRest) -> None:
        self.private_rest = private_rest

    async def submit(self, symbol: str, size: int, price: float, client_order_id: str, reduce_only: bool, tif: str) -> dict:
        return await self.private_rest.create_order(symbol, size, price, client_order_id, reduce_only=reduce_only, tif=tif)

    async def cancel(self, order_id: str) -> dict:
        return await self.private_rest.cancel_order(order_id)

    async def fetch(self, order_id: str) -> dict:
        return await self.private_rest.get_order(order_id)
