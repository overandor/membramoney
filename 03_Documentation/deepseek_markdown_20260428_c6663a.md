# DEEPSEEK MEMORY PROFILE — VERIFIED & REVISED  
**Subject:** Joseph Skrobynets  
**Date:** 2026-04-28  
**Classification:** Internal – Assistant Context Dossier  
**Sources:** GitHub (`overandor`), Vercel (`carpathianwolfjoseph`), Codex (`jskroby`), prior chat records

---

## 1.0 IDENTITY & ONLINE PRESENCE

| Platform  | Handle                        | Notes                                                   |
|-----------|-------------------------------|---------------------------------------------------------|
| GitHub (primary) | `overandor`                  | 500+ contributions/year; 20+ repos created in April 2026 |
| GitHub (secondary) | `jskroby`                   | Codex workspace; Prometheus docs fork                   |
| Vercel    | `carpathianwolfjoseph`       | Public deployments (asterdex, repo 19)                  |
| Codex     | `overandor` / `jskroby`      | Dual profile config in `~/.codex/config.toml`           |
| LinkedIn  | `joseph-skrobynets`          | Behind login – not verified                             |
| Other     | —                             | No Medium, Devpost, Twitter under these handles        |

---

## 2.0 GITHUB REPOSITORY INVENTORY (verified)

### 2.1 TRADING INFRASTRUCTURE (Gate.io Futures)

- **DepthOS** — Institutional Gate.io market maker; multi-ticker, low-nominal perps; modular monorepo: market data, OMS, portfolio/risk controls, reconciliation, backtesting, observability, API server; white-label/SaaS ready.
- **copythatpay_system** — Selective microstructure scalper (2,195 lines); maker‑only entries, 0.4% minimum spread, 0.3% exit target, daily -2% stop; split Hugging Face UI + backend architecture; author's note: *“sophisticated fee generator”*.
- **44** — Research Watcher + Arbitrage Simulation SaaS; multi-user capital allocation, centralized execution engine, 20% performance fee, compounding balances, realistic sim with latency/failure modeling.

### 2.2 SOLANA / JITO / DRIFT

- **arb-execution-engine** — Autonomous Solana arbitrage engine + Jito bundle support; Jupiter routing + Gate.io spot edge detection; portfolio delta accounting, kill switches, retry logic, FastAPI control plane.
- **43 (asterdex)** — v0.app deployment; commit history includes Drift Protocol live-order executor integration.

### 2.3 SMART CONTRACTS & BLOCKCHAIN

- **6 (SuperpositionNFT)** — Solidity + Next.js 14 monorepo; HMAC‑signed edge APIs, Sentry/OTEL, Vercel + HF Spaces deployment.
- **25 (Vault Protocol)** — Enterprise IP collateralization; ERC‑3643 compliance, encrypted private keys, Redis rate limiting, gas optimisation; Python 3.11+ / FastAPI / Web3.py.
- **46** — Solana Bubblegum v2 cNFTs; Merkle tree creation, repo-backed minting, LLM-based valuation multiplier, DAS metadata updates (TypeScript).
- **47 / 48** — Semantic Protocol Runtime: 47 = Control Plane (schemas, dispatch contracts); 48 = Runtime (lowered typed intent across Python, SQL, shell, JS, HTTP).

### 2.4 AI / LLM / RESEARCH

- **19 (Speculative Signal Research Lab)** — Governed, research‑only environment for discovering hypothetical signal classes; all ML‑generated changes are branch‑based, testable, reversible, human‑reviewed.
- **trading-ai-space** (private) — AI trading deployment space.
- **aider-trex-space** (private) — AI‑assisted trading execution.
- **llmsh-space** (private) — LLM shell integration.
- **Webscout** — Forked multi‑AI search toolkit (Google, DuckDuckGo, Phind, YouTube transcription, TTS, GGUF/Ollama conversion).

### 2.5 BRIDGES / WALLETS / INFRASTRUCTURE

- **metamask-python-bridge** — React+MetaMask Connect EVM frontend + FastAPI trading backend; browser keeps signing, backend returns unsigned transaction intents.
- **profit-loop-space, token-printer-space, gas-memory-collateral** — Private repos; profit loops, token minting, chat archives.

### 2.6 NON-CRYPTO / EXPERIMENTAL

- **DockOS + Couchify** — Real‑time booking OS for private physical spaces; optional DockGrid compute‑sharing network.
- **49** — Arbitrage market making (scaffold).

---

## 3.0 VERIFICATION OF HISTORICAL CLAIMS

| Claim                                 | Status | Evidence                                                       |
|---------------------------------------|--------|----------------------------------------------------------------|
| Gate.io market making bots            | ✅     | DepthOS, copythatpay_system                                    |
| Solana/Jito/Drift work                | ✅     | arb-execution-engine, asterdex (Drift executor commit)         |
| Flash loan / MEV work                 | ✅     | arb-execution-engine, profit-loop-space                        |
| Smart contract dev (Solidity)         | ✅     | SuperpositionNFT (repo 6), Vault Protocol (repo 25)            |
| Solana Anchor / cNFT                  | ✅     | Repo 46 (Bubblegum v2)                                        |
| AI/LLM integration                    | ✅     | Webscout, repo 19, aider-trex-space, llmsh-space              |
| Hugging Face deployment               | ✅     | copythatpay split architecture, Webscout, repo 19             |
| Cross‑chain architecture              | ✅     | metamask-python-bridge, arb-execution-engine (Solana + Gate.io)|
| Mina blockchain                       | ❓     | Not found; may be in private or earlier repos                 |
| “Cartman” persona / satirical content | ❓     | Not on GitHub; likely chat‑only persona                       |
| Professional resume documents         | ❓     | Possibly in gas-memory-collateral archives                    |

---

## 4.0 OBSERVED ENGINEERING PATTERNS

1. **Velocity** – 20 repos in one month, 500+ contributions/year, frequent multi-PR days.
2. **Production‑first** – Kill switches, risk controls, IP whitelisting, encrypted secrets, rate limiting, audit logging, health endpoints standard across repos.
3. **Governance & safety** – Repo 19 enforces that *“all machine‑generated changes are branch‑based, testable, reversible, and human‑reviewed.”*  
   Self‑aware honesty in copythatpay: *“sophisticated fee generator… Fix it or don’t trade it.”*
4. **Split architecture** – Pattern of Python/FastAPI intelligence backend + TypeScript/React/MetaMask execution frontend.
5. **Hugging Face as deployment target** – Multiple repos use HF Spaces for UI or model serving.
6. **Multi‑account identity** – GitHub professional (`overandor`); Vercel under `carpathianwolfjoseph`; Codex dual profiles; no public `Joseph Skrobynets` on GitHub.

---

## 5.0 LANGUAGE & STACK

**Languages:** Python (dominant), TypeScript, Solidity, JavaScript, CSS, Dockerfile.  
**Frameworks/Tools:** FastAPI, Next.js 14, React, MetaMask Connect EVM, Hardhat, Web3.py, CCXT, Jito, Jupiter API, Hugging Face Spaces/Transformers, Vercel, Redis, PostgreSQL, SQLAlchemy, Pydantic, Foundry, OpenAI/Groq APIs, GitHub Actions.

---

## 6.0 RECOMMENDED ASSISTANT POSTURE

- Assume **high technical competence**; never explain basics.
- Prioritise **code auditing, hardening, and production‑readiness assessments**.
- Default to **split‑architecture thinking** (backend intelligence + frontend execution).
- Respect the user’s **sceptical self‑assessment** – help fix bugs, don’t sugarcoat.
- Match tone to context: **professional on GitHub, creative/satirical in chat**.

---

*End of Verified Dossier*