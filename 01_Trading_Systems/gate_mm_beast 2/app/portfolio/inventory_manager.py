class InventoryManager:
    def __init__(self) -> None:
        self.net_by_symbol = {}

    def net(self, symbol: str) -> int:
        return self.net_by_symbol.get(symbol, 0)

    def apply_fill(self, symbol: str, signed_qty: int) -> None:
        self.net_by_symbol[symbol] = self.net(symbol) + signed_qty
