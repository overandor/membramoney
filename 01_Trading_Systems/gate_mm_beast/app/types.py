from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import time

@dataclass
class BookTop:
    bid: float = 0.0
    ask: float = 0.0
    bid_size: float = 0.0
    ask_size: float = 0.0
    ts: float = field(default_factory=time.time)

    @property
    def mid(self) -> float:
        if self.bid > 0 and self.ask > 0:
            return (self.bid + self.ask) / 2.0
        return 0.0

    @property
    def spread(self) -> float:
        if self.bid > 0 and self.ask >= self.bid:
            return self.ask - self.bid
        return 0.0

@dataclass
class QuoteDecision:
    symbol: str
    bid_px: float
    ask_px: float
    bid_size: int
    ask_size: int
    alpha_score: float
    fair_value: float
    meta: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EngineStatus:
    mode: str
    started_at: float
    symbols: list[str]
    healthy: bool = True
    message: str = "ok"

@dataclass
class ProtectiveExitCommand:
    symbol: str
    side: str
    size: int
    reason: str
    stop_price: Optional[float] = None
    marketable_limit_price: Optional[float] = None
