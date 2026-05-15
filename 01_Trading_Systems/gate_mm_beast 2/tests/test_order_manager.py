import pytest

from app.oms.order_manager import OrderManager
from app.persistence.db import Database
from app.persistence.order_repository import OrderRepository


class DummyExecution:
    def __init__(self):
        self.calls = []

    async def submit(self, symbol, size, price, client_order_id, reduce_only, tif):
        self.calls.append({
            "symbol": symbol,
            "size": size,
            "price": price,
            "client_order_id": client_order_id,
            "reduce_only": reduce_only,
            "tif": tif,
        })
        return {"id": "abc123"}

    async def cancel(self, order_id):
        return {"id": order_id}


@pytest.mark.asyncio
async def test_submit_limit_signs_sell_orders_negative(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    repo = OrderRepository(db)
    execution = DummyExecution()
    om = OrderManager(repo, execution)

    await om.submit_limit("DOGE_USDT", "sell", "entry", 0.1, 7)

    assert execution.calls[0]["size"] == -7
