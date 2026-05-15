from __future__ import annotations
from app.core.decimal_utils import round_to_tick
from app.strategy.fair_value import fair_value
from app.strategy.inventory_skew import skew_from_inventory
from app.strategy.quote_sizer import quote_size
from app.strategy.reservation_price import reservation_price
from app.strategy.spread_model import target_half_spread_ticks
from app.types import QuoteDecision

class QuoteEngine:
    def build(self, symbol: str, mid: float, bid: float, ask: float, tick: float, base_size: int, alpha_score: float, volatility_score: float, net_qty: int, max_abs_qty: int = 10) -> QuoteDecision:
        fv = fair_value(mid)
        inv_skew = skew_from_inventory(net_qty, max_abs_qty)
        half_ticks = target_half_spread_ticks(volatility_score)
        half_spread = half_ticks * tick
        rp = reservation_price(fv, alpha_score, inv_skew, half_spread)
        bid_px = round_to_tick(min(rp - half_spread, ask - tick), tick)
        ask_px = round_to_tick(max(rp + half_spread, bid + tick), tick)
        bid_sz, ask_sz = quote_size(base_size, alpha_score, inv_skew)
        return QuoteDecision(
            symbol=symbol,
            bid_px=bid_px,
            ask_px=ask_px,
            bid_size=bid_sz,
            ask_size=ask_sz,
            alpha_score=alpha_score,
            fair_value=fv,
            meta={"inventory_skew": inv_skew, "reservation_price": rp},
        )
