def skew_from_inventory(net_qty: int, max_abs_qty: int) -> float:
    if max_abs_qty <= 0:
        return 0.0
    return max(-1.0, min(1.0, net_qty / max_abs_qty))
