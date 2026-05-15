# gate_mm_beast

Institutional-style Gate.io market-making scaffold with:
- OpenRouter and Groq support only
- no OpenAI key dependency
- modular OMS / risk / reconcile / strategy layout
- paper, live, and replay entrypoints
- SQLite persistence
- lightweight HTTP health and dashboard API

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/run_paper.py
```

## Important

This is a production-oriented scaffold, not a promise of profitability.
Protective exits, fill handling, and exchange-specific logic are isolated in dedicated modules so you can harden them safely.

## AI providers

This project intentionally does **not** use `OPENAI_API_KEY`.
Only these optional providers are wired:
- `OPENROUTER_API_KEY`
- `GROQ_API_KEY`

If you do not set either key, the engine uses local microstructure alpha only.


## Live layer 1
This build adds:
- live quote placement/cancel-replace loop
- startup sync of open orders and positions
- REST order book fallback when WS book becomes stale
- per-symbol max position cap and global open-order cap
- `LIVE_ENABLE_TRADING=false` by default for safe startup

To enable real trading, set:
```bash
MODE=live
LIVE_ENABLE_TRADING=true
GATE_API_KEY=...
GATE_API_SECRET=...
```
