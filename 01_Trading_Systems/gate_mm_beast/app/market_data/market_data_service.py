from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
from app.types import BookTop
from app.market_data.book_builder import BookBuilder

@dataclass
class SymbolRuntime:
    symbol: str
    tick: float
    multiplier: float
    book: BookTop = field(default_factory=BookTop)
    candles = None
    recent_mid: deque = field(default_factory=lambda: deque(maxlen=120))

class MarketDataService:
    def __init__(self) -> None:
        self.runtimes: dict[str, SymbolRuntime] = {}
        self.builder = BookBuilder()

    def set_symbols(self, runtimes: dict[str, SymbolRuntime]) -> None:
        self.runtimes = runtimes

    async def on_book_ticker(self, item: dict) -> None:
        symbol = str(item.get("s") or item.get("contract") or "")
        rt = self.runtimes.get(symbol)
        if not rt:
            return
        self.builder.apply_book_ticker(rt.book, item)
        if rt.book.mid > 0:
            rt.recent_mid.append(rt.book.mid)

    def get(self, symbol: str) -> SymbolRuntime | None:
        return self.runtimes.get(symbol)

    def symbols(self) -> list[str]:
        return list(self.runtimes.keys())
