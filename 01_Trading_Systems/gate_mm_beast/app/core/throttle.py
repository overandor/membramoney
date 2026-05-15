import time

class Throttle:
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self._last = 0.0

    def ready(self) -> bool:
        now = time.time()
        if now - self._last >= self.seconds:
            self._last = now
            return True
        return False
