from app.risk.risk_manager import RiskManager
from app.risk.limits import RiskLimits
from app.risk.kill_switch import KillSwitch

def test_risk_manager():
    rm = RiskManager(RiskLimits(max_positions=1, max_symbol_position=1), KillSwitch())
    assert rm.can_open(0, 0)
    assert not rm.can_open(1, 0)
