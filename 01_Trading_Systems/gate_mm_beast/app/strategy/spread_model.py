def target_half_spread_ticks(volatility_score: float) -> int:
    if volatility_score > 0.8:
        return 4
    if volatility_score > 0.4:
        return 3
    return 2
