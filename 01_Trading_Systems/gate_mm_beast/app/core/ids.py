import hashlib
import time

def client_order_id(prefix: str, symbol: str) -> str:
    raw = f"{prefix}|{symbol}|{time.time_ns()}".encode()
    return f"{prefix}-{hashlib.sha1(raw).hexdigest()[:20]}"
