class HealthState:
    def __init__(self) -> None:
        self.healthy = True
        self.message = "ok"

    def fail(self, message: str) -> None:
        self.healthy = False
        self.message = message

    def ok(self) -> None:
        self.healthy = True
        self.message = "ok"
