from app.persistence.db import Database
from app.persistence.fill_repository import FillRepository
from app.persistence.order_repository import OrderRepository
from app.persistence.position_repository import PositionRepository
from app.oms.fill_processor import FillProcessor

def test_fill_processor_insert(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    fp = FillProcessor(FillRepository(db), OrderRepository(db), PositionRepository(db))
    fp.record_fill("DOGE_USDT", "c1", "e1", "buy", 10, 0.1, {"x":1})
