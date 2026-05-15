from dataclasses import dataclass

@dataclass
class OrderIntent:
    symbol: str
    side: str
    role: str
    price: float
    size: int
    reduce_only: bool = False
    tif: str = "poc"
