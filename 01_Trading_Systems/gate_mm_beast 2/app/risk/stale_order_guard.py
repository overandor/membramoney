class StaleOrderGuard:
    def should_cancel(self, age_seconds: float, ttl_seconds: float) -> bool:
        return age_seconds > ttl_seconds
