from dataclasses import dataclass

@dataclass
class RiskLimits:
    max_positions: int = 10
    max_symbol_position: int = 1
    max_daily_loss_usd: float = 250.0
