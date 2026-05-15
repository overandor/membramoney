from app.types import BookTop
from app.connectors.gateio.mapper import map_book_ticker

class BookBuilder:
    def apply_book_ticker(self, current: BookTop, item: dict) -> BookTop:
        m = map_book_ticker(item)
        current.bid = m["bid"]
        current.ask = m["ask"]
        current.bid_size = m["bid_size"]
        current.ask_size = m["ask_size"]
        return current
