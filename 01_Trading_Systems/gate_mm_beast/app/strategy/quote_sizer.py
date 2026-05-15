def quote_size(base_size: int, alpha_score: float, inventory_skew: float) -> tuple[int, int]:
    bias = max(-0.5, min(0.5, alpha_score * 0.5 - inventory_skew * 0.5))
    bid = max(1, int(base_size * (1.0 + bias)))
    ask = max(1, int(base_size * (1.0 - bias)))
    return bid, ask
