from app.strategy.quote_engine import QuoteEngine

def test_quote_engine():
    q = QuoteEngine().build("DOGE_USDT", 0.1, 0.099, 0.101, 0.001, 100, 0.3, 0.2, 0, 10)
    assert q.bid_px < q.ask_px
