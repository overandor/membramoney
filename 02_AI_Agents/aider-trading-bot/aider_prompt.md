Build a Python paper-trading crypto bot project.

Requirements:
- Python 3.11+
- paper trading only by default
- one symbol initially (BTC/USDT)
- modular structure
- config loading from .env
- structured logging
- public market data polling
- simple EMA + ATR strategy
- position sizing with max risk per trade
- max daily loss lockout
- state persistence
- CSV trade journal
- graceful shutdown
- backtest script using CSV candles
- README with exact setup instructions

Create:
- bot.py
- strategy.py
- risk.py
- state.py
- backtest.py
- requirements.txt
- README.md

Constraints:
- do not promise profitability
- validate config at startup
- catch runtime exceptions in the main loop
- keep the code executable and well-commented
