class MarketRegimeGuard:
    def allow_quotes(self, spread_bps: float) -> bool:
        return spread_bps < 100.0
