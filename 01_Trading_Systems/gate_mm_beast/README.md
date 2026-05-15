# gate_mm_beast

Institutional-style Gate.io market-making scaffold with:
- OpenRouter and Groq support only
- no OpenAI key dependency
- modular OMS / risk / reconcile / strategy layout
- paper, live, and replay entrypoints
- SQLite persistence
- lightweight HTTP health and dashboard API

## Project status

- Archive extracted to `gate_mm_beast/`
- Runtime memory persistence enabled via SQLite snapshots
- Ready for local run and GitHub publishing

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/run_paper.py
```

## Modes

- Paper: `python scripts/run_paper.py`
- Live: `python scripts/run_live.py`
- Replay: `python scripts/run_replay.py`

Keep `MODE=paper` while validating your setup.

## Memory and persistence

The engine stores runtime state in SQLite (`DB_PATH`):

- `snapshots` for quote and runtime memory keys
- `orders`, `fills`, `positions`, `decisions`, `events`

On startup, runtime memory is restored from snapshots, including:

- `app_state`
- `engine_state`
- `inventory`
- last known quote tops (`quote:*`)

This allows smoother restarts without losing local state context.

## Important

This is a production-oriented scaffold, not a promise of profitability.
Protective exits, fill handling, and exchange-specific logic are isolated in dedicated modules so you can harden them safely.

## GitHub publish steps

```bash
cd gate_mm_beast
git init
git add .
git commit -m "Initial gate_mm_beast scaffold"
```

Then create a GitHub repo and push:

```bash
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

## AI providers

This project intentionally does **not** use `OPENAI_API_KEY`.
Only these optional providers are wired:
- `OPENROUTER_API_KEY`
- `GROQ_API_KEY`

If you do not set either key, the engine uses local microstructure alpha only.
