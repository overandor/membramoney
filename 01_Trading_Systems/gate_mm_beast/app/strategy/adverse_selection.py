def should_quote(book_spread: float, tick: float) -> bool:
    return book_spread >= tick
