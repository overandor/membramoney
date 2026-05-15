class CircuitBreaker:
    def __init__(self, threshold: int = 5) -> None:
        self.threshold = threshold
        self.failures = 0
        self.open = False

    def record_success(self) -> None:
        self.failures = 0
        self.open = False

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.open = True
