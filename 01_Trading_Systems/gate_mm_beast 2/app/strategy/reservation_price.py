def reservation_price(fair_value: float, alpha_score: float, inventory_skew: float, half_spread: float) -> float:
    return fair_value + alpha_score * half_spread - inventory_skew * half_spread
