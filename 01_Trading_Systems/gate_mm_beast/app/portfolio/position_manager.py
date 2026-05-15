from __future__ import annotations
from app.persistence.position_repository import PositionRepository

class PositionManager:
    def __init__(self, repo: PositionRepository) -> None:
        self.repo = repo

    def open(self, symbol: str, side: str, qty: int, entry_vwap: float, payload: dict) -> int:
        return self.repo.open_position(symbol, side, qty, entry_vwap, payload)

    def get_open(self, symbol: str) -> dict | None:
        return self.repo.get_open(symbol)
