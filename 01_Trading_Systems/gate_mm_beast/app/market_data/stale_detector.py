import time

def is_stale(ts: float, max_age: float = 10.0) -> bool:
    return time.time() - ts > max_age
