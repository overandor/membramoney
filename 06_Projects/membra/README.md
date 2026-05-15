# MEMBRA CompanyOS

AI → operating roles → tasks → proof → governance → real-world execution → KPI records → company memory → better orchestration.

MEMBRA is not only a marketplace. MEMBRA is an orchestration membrane between human intent, AI agents, real-world assets, local labor, proof systems, governance, settlement rails, and company formation.

## Architecture

- **Backend**: FastAPI + SQLite + Pydantic + 10 CompanyOS service layers
- **Frontend**: React + Vite + Tailwind CSS + Recharts + 7 dashboard views
- **API Docs**: Auto-generated at `/docs` (Swagger UI)

## MEMBRA OS Layers

```
MEMBRA OS
├── IntentOS          /v1/intent — Converts human chat into structured objectives
├── OrchestrationOS   /v1/objectives, /v1/tasks — Breaks objectives into executable tasks
├── AgentOS           /v1/agents — Registry of AI agents with tools, permissions, blocked actions
├── JobOS             /v1/jobs — Turns tasks into paid jobs, bounties, and workflows
├── CompanyOS         /v1/departments, /v1/sops, /v1/operating-units
├── GovernanceOS      /v1/policies, /v1/approvals, /v1/audit-events
├── ProofBook         /v1/proof-records — SHA-256 audit ledger
├── SettlementOS      /v1/settlement-eligibility — Payout tracking, external rails only
├── WorldBridge       /v1/world-assets — Apartments, vehicles, windows, tools, wearables, people
└── KPI Dashboard     /v1/kpi/* — Real-time operational intelligence
```

## Backend

### Run

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Seed Demo Data

```bash
cd backend
python seed.py        # Core marketplace data
python seed_companyos.py  # CompanyOS demo data (agents, tasks, jobs, policies, world assets)
```

### API

Base URL: `http://localhost:8000/v1`

#### Core Marketplace Domains
- **Identity**: `/hosts`, `/guests`, `/identity/verify`, `/users`
- **Assets**: `/assets`, `/assets/nearby`, `/assets/{id}`
- **Reservations**: `/reservations`, `/reservations/{id}/risk`, `/reservations/{id}/approve`
- **Insurance**: `/insurance/quote`, `/insurance/bind`
- **Payments**: `/payments/quote`, `/payments/authorize`, `/payments/capture`, `/payouts/release`
- **Access**: `/access/{visit_id}/qr`, `/access/verify`, `/access/check-in`, `/access/check-out`
- **Incidents**: `/incidents`, `/claims`, `/disputes`
- **Ads**: `/ad-campaigns`, `/ad-placements`, `/ad-proofs`, `/ad-payouts`, `/ad-analytics/*`
- **Wear**: `/wearers`, `/wearables`, `/wear-proofs`, `/wear-analytics/*`

#### CompanyOS Domains
- **IntentOS**: `POST /v1/intent` — Parse natural language into objectives
- **OrchestrationOS**: `/v1/objectives`, `/v1/tasks` — Objective and task management
- **AgentOS**: `/v1/agents` — 9 core agents: Strategy, Product, Engineering, Ops, Sales, Finance, Legal, Governance, Proof
- **JobOS**: `/v1/jobs` — Local jobs, bounties, fulfillment tasks
- **CompanyOS**: `/v1/departments`, `/v1/sops`, `/v1/operating-units`
- **GovernanceOS**: `/v1/policies`, `/v1/approvals`, `/v1/audit-events`
- **ProofBook**: `/v1/proof-records` — Immutable SHA-256 ledger
- **SettlementOS**: `/v1/settlement-eligibility` — External rail payout tracking
- **WorldBridge**: `/v1/world-assets` — Real-world asset registry

#### KPI Analytics
- `GET /v1/kpi/summary` — Aggregated counts across all domains
- `GET /v1/kpi/timeseries?days=30` — Daily visits, payments, incidents
- `GET /v1/kpi/top-assets?limit=10` — Assets ranked by captured revenue
- `GET /v1/kpi/top-hosts?limit=10` — Hosts ranked by captured revenue

#### Production Boundaries
- `GET /v1/system/production-boundaries` — Safety doctrine and system guarantees

## Frontend

### Run

```bash
cd frontend
npm install
npm run dev
```

The dashboard will be available at `http://localhost:5173` and connects to the backend at `http://localhost:8000/v1`.

### Dashboard Views

- **Dashboard** (`/`) — KPI cards, activity chart, top assets/hosts
- **CompanyOS** (`/company`) — Agent registry, orchestration tasks, jobs, departments
- **WorldBridge** (`/worldbridge`) — Real-world asset cards: apartments, vehicles, windows, tools, wearables
- **ProofBook** (`/proofbook`) — SHA-256 audit ledger table with verification status
- **Settlement** (`/settlement`) — Payout eligibility records and external rail tracking
- **Governance** (`/governance`) — Policies, approval queue, audit events
- **Concierge** (`/concierge`) — LLM intent parser with Groq integration and deterministic fallback

## Environment Variables

Create `backend/.env`:

```env
DATABASE_URL=sqlite:///./membra.db
QR_SECRET=your-secret-key-for-qr-signing
GROQ_API_KEY=your-groq-key-for-concierge  # optional, falls back to deterministic parsing
```

## Project Structure

```
membra/
├── backend/
│   ├── main.py                 # FastAPI entry point
│   ├── requirements.txt
│   ├── seed.py                 # Core marketplace seed
│   ├── seed_companyos.py       # CompanyOS demo data
│   └── src/
│       ├── api/v1.py           # All API routes
│       ├── core/               # Config, exceptions
│       ├── db/database.py      # SQLite schema + connection
│       ├── models/             # Pydantic schemas + enums
│       └── services/           # All business logic services
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.jsx
│       ├── api/client.js
│       └── components/
│           ├── Dashboard.jsx
│           ├── CompanyOSView.jsx
│           ├── WorldBridgeView.jsx
│           ├── ProofBookView.jsx
│           ├── SettlementView.jsx
│           ├── GovernanceView.jsx
│           ├── ConciergePanel.jsx
│           └── ...
└── README.md
```

## Production Boundaries

- No fake payments
- No custody
- No guaranteed profit
- Owner confirmation before visibility
- External settlement rails only
- Proof and governance required for real-world execution
- AI recommends, humans or policy gates authorize
