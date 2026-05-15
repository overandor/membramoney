# Unified Multi-Exchange Market Maker Bundle (For Sale)

A production-style crypto trading automation bundle centered on a Gate.io market-making core, extended with unified multi-exchange balance visibility across Gate.io, Binance, OKX, Bybit, and XT.

## Deliverables
- `gate_mm_unified_onefile.py` (runnable launcher + commented full source archive)
- `gate_mm_unified_onefile_manifest.txt` (integrity manifest with per-file hashes)
- `gate_mm_unified_onefile.zip` (transfer package)
- `SALES_COPY_SHORT.txt` (short listing copy)
- `gate_mm_beast` source project (modular runtime project)

## What this includes
- `gate_mm_unified_onefile.py`: single-file consolidated bundle for reappraisal, code handoff, and portable review.
- `gate_mm_unified_onefile_manifest.txt`: integrity manifest with per-section hashes.
- `gate_mm_beast` project core with:
  - async market-making loop
  - runtime memory persistence
  - paper/live/replay modes
  - unified balance service and dashboard endpoints

## Key selling points
- Multi-exchange balance aggregation in one view.
- Gate.io-focused market-making engine with paper-trade simulation.
- Structured persistence (orders, fills, positions, snapshots).
- API + UI status surface suitable for monitoring and demos.
- Consolidated one-file artifact for simplified transfer/review.

## Quick start
1. Configure API keys in environment variables (`GATE_*`, `BINANCE_*`, `OKX_*`, `BYBIT_*`, `XT_*`).
2. Run core app from project:
   - Paper: `python /Users/alep/Downloads/gate_mm_beast/scripts/run_paper.py`
   - Live: `python /Users/alep/Downloads/gate_mm_beast/scripts/run_live.py`
3. Run consolidated launcher artifact:
   - `python /Users/alep/Downloads/gate_mm_beast/gate_mm_unified_onefile.py paper`

## Suggested listing bullets
- Multi-exchange account visibility with unified USD-style aggregation.
- Algorithmic market-making architecture with persistence and restart memory.
- Paper/live/replay execution modes for staged rollout.
- API and UI monitoring surface for operator visibility.
- Consolidated one-file handoff for buyer reappraisal and transfer.

## Support scope (recommended)
- Include one handoff session for environment setup and first paper-mode run.
- Include one bugfix window limited to packaging/runtime issues discovered immediately after delivery.
- Exclude exchange policy changes, API deprecations, and strategy PnL guarantees.

## Buyer notes
- The one-file bundle is intentionally an archive+launcher deliverable for transferability.
- Exchange APIs and policies change over time; buyer should validate credentials and endpoints before production deployment.

## Risk disclaimer
This software is for educational/research and professional evaluation purposes. Live trading involves substantial financial risk, including total loss. The buyer/operator is solely responsible for configuration, compliance, and operational safeguards.
