from dataclasses import dataclass

@dataclass
class OrderRecord:
    symbol: str
    client_order_id: str
    side: str
    role: str
    state: str
    price: float
    size: int
