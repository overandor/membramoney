from app.persistence.db import Database
from app.persistence.fill_repository import FillRepository
from app.persistence.order_repository import OrderRepository
from app.persistence.position_repository import PositionRepository
from app.oms.fill_processor import FillProcessor


def test_fill_processor_insert_updates_order_and_position(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    orders = OrderRepository(db)
    positions = PositionRepository(db)
    fp = FillProcessor(FillRepository(db), orders, positions)

    orders.insert("DOGE_USDT", "c1", "e1", "buy", "entry", "OPEN", 0.1, 10, {})
    fp.record_fill("DOGE_USDT", "c1", "e1", "buy", 4, 0.1, {"x": 1})

    order = orders.get_by_client_order_id("c1")
    pos = positions.get_open("DOGE_USDT")
    assert order is not None
    assert order["filled_size"] == 4
    assert order["state"] == "PARTIAL"
    assert pos is not None
    assert pos["side"] == "buy"
    assert pos["qty"] == 4


def test_fill_processor_closes_position_on_opposite_fill(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    orders = OrderRepository(db)
    positions = PositionRepository(db)
    fp = FillProcessor(FillRepository(db), orders, positions)

    positions.open_position("DOGE_USDT", "buy", 5, 0.10, {})
    orders.insert("DOGE_USDT", "c2", "e2", "sell", "exit", "OPEN", 0.11, 5, {})
    fp.record_fill("DOGE_USDT", "c2", "e2", "sell", 5, 0.11, {})

    assert positions.get_open("DOGE_USDT") is None
    order = orders.get_by_client_order_id("c2")
    assert order is not None
    assert order["state"] == "FILLED"
    assert order["filled_size"] == 5
