from __future__ import annotations
from app.risk.kill_switch import KillSwitch
from app.risk.limits import RiskLimits

class RiskManager:
    def __init__(self, limits: RiskLimits, kill_switch: KillSwitch) -> None:
        self.limits = limits
        self.kill_switch = kill_switch

    def can_open(self, open_positions_count: int, symbol_position_count: int) -> bool:
        if self.kill_switch.triggered:
            return False
        if open_positions_count >= self.limits.max_positions:
            return False
        if symbol_position_count >= self.limits.max_symbol_position:
            return False
        return True
