import asyncio
from app.risk.protective_exit import ProtectiveExit

def test_protective_exit():
    cmd = asyncio.run(ProtectiveExit().build("DOGE_USDT", "sell", 10, 0.09, 0.089))
    assert cmd.symbol == "DOGE_USDT"
