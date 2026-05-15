from __future__ import annotations
import numpy as np
import pandas as pd
from app.connectors.gateio.rest_public import GatePublicRest

def add_features(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x["ret1"] = x["close"].pct_change(1)
    x["ema8"] = x["close"].ewm(span=8, adjust=False).mean()
    x["ema21"] = x["close"].ewm(span=21, adjust=False).mean()
    x["ema55"] = x["close"].ewm(span=55, adjust=False).mean()
    x["atr14"] = (pd.concat([
        (x["high"] - x["low"]),
        (x["high"] - x["close"].shift()).abs(),
        (x["low"] - x["close"].shift()).abs(),
    ], axis=1).max(axis=1)).rolling(14).mean()
    x["z20"] = (x["close"] - x["close"].rolling(20).mean()) / x["close"].rolling(20).std()
    x["volz"] = (x["volume"] - x["volume"].rolling(20).mean()) / x["volume"].rolling(20).std()
    return x

class CandlesService:
    def __init__(self, rest: GatePublicRest) -> None:
        self.rest = rest

    async def load(self, symbol: str, interval: str, limit: int) -> pd.DataFrame:
        df = await self.rest.candles(symbol, interval, limit)
        if df.empty:
            return df
        return add_features(df).dropna().reset_index(drop=True)
