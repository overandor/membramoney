from __future__ import annotations
from app.types import ProtectiveExitCommand

class ProtectiveExit:
    async def build(self, symbol: str, side: str, size: int, stop_price: float, marketable_limit_price: float) -> ProtectiveExitCommand:
        return ProtectiveExitCommand(
            symbol=symbol,
            side=side,
            size=size,
            reason="stop_cross",
            stop_price=stop_price,
            marketable_limit_price=marketable_limit_price,
        )
