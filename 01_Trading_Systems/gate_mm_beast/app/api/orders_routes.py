def orders_payload(order_repo, symbol: str | None = None) -> list[dict]:
    return order_repo.open_orders(symbol)
