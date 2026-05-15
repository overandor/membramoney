from app.core.decimal_utils import safe_float

def map_book_ticker(item: dict) -> dict:
    return {
        "symbol": str(item.get("s") or item.get("contract") or ""),
        "bid": safe_float(item.get("b") or item.get("bid_price")),
        "ask": safe_float(item.get("a") or item.get("ask_price")),
        "bid_size": safe_float(item.get("B") or item.get("bid_size") or item.get("bid_amount")),
        "ask_size": safe_float(item.get("A") or item.get("ask_size") or item.get("ask_amount")),
    }
