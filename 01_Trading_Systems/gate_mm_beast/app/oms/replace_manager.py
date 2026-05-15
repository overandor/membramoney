class ReplaceManager:
    def should_replace(self, current_price: float, desired_price: float, tick: float) -> bool:
        return abs(current_price - desired_price) >= max(tick, 1e-8)
