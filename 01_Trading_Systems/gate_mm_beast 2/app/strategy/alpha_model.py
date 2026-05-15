from __future__ import annotations
import numpy as np

def estimate_alpha(rt) -> dict:
    df = rt.candles
    if df is None or len(df) < 80:
        return {"score": 0.0, "confidence": 0.0}
    row = df.iloc[-1]
    mid = rt.book.mid or float(row["close"])
    tick = max(rt.tick, 1e-8)
    trend = np.clip((float(row["ema8"]) - float(row["ema21"])) / max(mid, 1e-9) * 2000.0, -1.0, 1.0)
    reversion = np.clip(-float(row["z20"]) / 2.5, -1.0, 1.0)
    flow = np.clip((rt.book.bid_size - rt.book.ask_size) / max(rt.book.bid_size + rt.book.ask_size, 1e-9), -1.0, 1.0)
    spread_score = np.clip((rt.book.spread / tick - 1.0) / 5.0, -1.0, 1.0)
    score = 0.35 * trend + 0.30 * reversion + 0.25 * flow + 0.10 * spread_score
    return {"score": float(score), "confidence": float(min(abs(score), 0.95))}
