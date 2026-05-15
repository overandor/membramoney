class PnLManager:
    def realized(self, entry: float, exit_: float, qty: int, multiplier: float, side: str) -> float:
        if side == "buy":
            return (exit_ - entry) * qty * multiplier
        return (entry - exit_) * qty * multiplier
