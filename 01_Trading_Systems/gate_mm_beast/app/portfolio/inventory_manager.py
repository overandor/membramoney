class InventoryManager:
    def __init__(self) -> None:
        self.net_by_symbol = {}

    def net(self, symbol: str) -> int:
        return self.net_by_symbol.get(symbol, 0)

    def apply_fill(self, symbol: str, signed_qty: int) -> None:
        self.net_by_symbol[symbol] = self.net(symbol) + signed_qty

    def export_state(self) -> dict[str, int]:
        return {str(k): int(v) for k, v in self.net_by_symbol.items()}

    def import_state(self, state: dict[str, int]) -> None:
        self.net_by_symbol = {str(k): int(v) for k, v in (state or {}).items()}
