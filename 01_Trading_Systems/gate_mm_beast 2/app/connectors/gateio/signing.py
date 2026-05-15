import hashlib
import hmac
import time

def build_headers(api_key: str, api_secret: str, method: str, path: str, query_string: str = "", body: str = "") -> dict:
    ts = str(int(time.time()))
    body_hash = hashlib.sha512(body.encode("utf-8")).hexdigest()
    sign_str = f"{method.upper()}\n/api/v4{path}\n{query_string}\n{body_hash}\n{ts}"
    sign = hmac.new(api_secret.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
    return {
        "KEY": api_key,
        "Timestamp": ts,
        "SIGN": sign,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
