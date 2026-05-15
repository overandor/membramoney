from app.oms.order_state import can_transition

def test_state_transitions():
    assert can_transition("NEW", "ACK")
    assert not can_transition("FILLED", "OPEN")
