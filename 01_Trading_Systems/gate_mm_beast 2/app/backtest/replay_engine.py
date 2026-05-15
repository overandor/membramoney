from __future__ import annotations
from dataclasses import dataclass
import math
import numpy as np

@dataclass
class ReplayResult:
    trades: int
    win_rate: float
    avg_pnl_usd: float
    pnl_usd: float
    max_drawdown_usd: float
    sharpe_like: float
    allowed: bool

class ReplayEngine:
    def __init__(self, take_atr_mult: float = 1.0, stop_atr_mult: float = 1.6):
        self.take_atr_mult = take_atr_mult
        self.stop_atr_mult = stop_atr_mult

    def run(self, df, multiplier: float, size: int) -> ReplayResult:
        if df is None or len(df) < 100:
            return ReplayResult(0,0.0,0.0,0.0,0.0,-99.0,False)
        pnls = []
        equity = peak = max_dd = 0.0
        for i in range(60, len(df) - 8):
            row = df.iloc[i]
            score = ((row["ema8"] - row["ema21"]) / max(row["close"], 1e-9)) * 2000.0
            if abs(score) < 0.2:
                continue
            side = "buy" if score > 0 else "sell"
            entry = float(row["close"])
            atr = max(float(row["atr14"]), entry * 0.002)
            take = entry + atr * self.take_atr_mult if side == "buy" else entry - atr * self.take_atr_mult
            stop = entry - atr * self.stop_atr_mult if side == "buy" else entry + atr * self.stop_atr_mult
            exit_px = float(df.iloc[min(i+7, len(df)-1)]["close"])
            for j in range(i+1, min(i+8, len(df))):
                hi = float(df.iloc[j]["high"])
                lo = float(df.iloc[j]["low"])
                if side == "buy":
                    if lo <= stop:
                        exit_px = stop
                        break
                    if hi >= take:
                        exit_px = take
                        break
                else:
                    if hi >= stop:
                        exit_px = stop
                        break
                    if lo <= take:
                        exit_px = take
                        break
            pnl = ((exit_px - entry) if side == "buy" else (entry - exit_px)) * size * multiplier
            pnls.append(pnl)
            equity += pnl
            peak = max(peak, equity)
            max_dd = max(max_dd, peak - equity)
        if not pnls:
            return ReplayResult(0,0.0,0.0,0.0,0.0,-99.0,False)
        return ReplayResult(
            trades=len(pnls),
            win_rate=float(np.mean([1.0 if p > 0 else 0.0 for p in pnls])),
            avg_pnl_usd=float(np.mean(pnls)),
            pnl_usd=float(np.sum(pnls)),
            max_drawdown_usd=float(max_dd),
            sharpe_like=float(np.mean(pnls)/(np.std(pnls)+1e-9) * math.sqrt(max(len(pnls),1))),
            allowed=len(pnls) >= 10 and float(np.mean(pnls)) > 0,
        )
