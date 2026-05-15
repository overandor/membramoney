class KillSwitch:
    def __init__(self) -> None:
        self.triggered = False
        self.reason = ""

    def trigger(self, reason: str) -> None:
        self.triggered = True
        self.reason = reason
