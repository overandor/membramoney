class Metrics:
    def __init__(self) -> None:
        self.values = {
            "orders_submitted": 0,
            "fills": 0,
            "rejects": 0,
            "quotes_live": 0,
        }

    def inc(self, name: str, value: int = 1) -> None:
        self.values[name] = self.values.get(name, 0) + value
