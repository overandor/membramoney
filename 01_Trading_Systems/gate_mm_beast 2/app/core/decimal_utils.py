def safe_float(x, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default

def round_to_tick(price: float, tick: float) -> float:
    if tick <= 0:
        return price
    return round(round(price / tick) * tick, 10)
