import time
from datetime import datetime, timezone

def now_ts() -> float:
    return time.time()

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
