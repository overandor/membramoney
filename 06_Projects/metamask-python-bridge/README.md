# MetaMask Python Bridge

**MetaMask-powered execution frontend with Python intelligence backend**

A production-grade application that bridges Python quantitative trading logic with MetaMask wallet execution, following secure architecture patterns where signing stays in the frontend and intelligence stays in the backend.

## Architecture

### Frontend (React + TypeScript + MetaMask Connect EVM)
- **MetaMask Connect EVM**: EIP-1193 provider compatible with viem, ethers, web3.js
- **User Actions**: Connect wallet, sign transactions, approve deployments
- **Display**: Portfolio dashboards, strategy suggestions, execution UI

### Backend (FastAPI + Python)
- **Strategy Engine**: Compute trading signals and deployment parameters
- **Analytics**: Portfolio analysis, risk metrics, market data aggregation
- **Preparation**: Generate unsigned transaction intents, deployment parameters
- **Storage**: Database for strategy settings, historical data, task queues

### Shared Boundary
```
Frontend → Backend: Request deployment params, trade suggestions, unsigned intents
Backend → Frontend: Return prepared data, human-readable rationale
Frontend → MetaMask: User signs and broadcasts transactions
```

## What This Does Well

✅ Deploy smart contracts with MetaMask confirmation  
✅ Manage strategy settings from Python  
✅ Run bots or analytics in Python  
✅ Push deploy/trade intents to frontend  
✅ Display portfolio/risk dashboards  
✅ Bridge Python quant logic into browser wallet UX

## What This Does NOT Do

❌ Hold user's MetaMask private key in Python  
❌ "Connect MetaMask directly to Python" as if Python becomes the wallet  
❌ Silently deploy on behalf of user wallet without frontend approval

## MVP Flows

### 1. Wallet Connect
Frontend uses MetaMask Connect EVM to establish secure wallet connection.

### 2. Contract Deploy Assistant
**Python Backend Prepares:**
- ABI
- Bytecode
- Constructor args
- Network config

**Frontend Submits:** Deploy transaction through MetaMask with user approval.

### 3. Python Strategy → User Execution
**Python Backend Returns:**
- Recommended action
- Target contract/method
- Calldata params
- Human-readable rationale

**Frontend Shows:** "Approve in MetaMask" for user to sign and execute.

## Repository Structure

```
metamask-python-bridge/
├── frontend/
│   ├── src/
│   │   ├── metamask.ts          # MetaMask Connect EVM integration
│   │   ├── app.tsx              # Main React application
│   │   ├── contracts.ts        # Contract interaction logic
│   │   └── components/          # UI components
│   ├── package.json
│   └── tsconfig.json
├── backend/
│   ├── app.py                   # FastAPI application
│   ├── strategies/              # Trading strategies
│   ├── services/                # Business logic services
│   ├── db/                      # Database models
│   └── requirements.txt
├── shared/
│   └── schemas.json             # Shared data schemas
├── contracts/
│   ├── src/                     # Solidity contracts
│   └── script/                  # Deployment scripts
├── README.md
└── docker-compose.yml
```

## Tech Stack

### Frontend
- **React**: UI framework
- **TypeScript**: Type safety
- **@metamask/connect-evm**: MetaMask integration
- **viem**: Ethereum library

### Backend
- **FastAPI**: High-performance API framework
- **SQLAlchemy**: ORM (or sqlite for simplicity)
- **Pydantic**: Data validation

### Optional
- **Foundry**: Contract deployment artifacts
- **Redis**: Task queues
- **Docker**: Containerization

## Installation

### Backend
```bash
cd backend
pip install -r requirements.txt
python app.py
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Docker
```bash
docker-compose up
```

## API Endpoints

### Wallet
- `GET /api/wallet/challenge` - Request signing challenge
- `POST /api/wallet/verify` - Verify signature and issue session token

### Strategy
- `GET /api/strategy/signals` - Get trading signals from Python backend
- `POST /api/strategy/configure` - Configure strategy parameters

### Deployment
- `GET /api/deploy/params` - Get deployment parameters
- `POST /api/deploy/prepare` - Prepare unsigned transaction

### Portfolio
- `GET /api/portfolio/summary` - Get portfolio summary
- `GET /api/portfolio/analytics` - Get analytics data

## Security

- **Private Keys**: Never stored in backend
- **Signing**: Always happens in frontend via MetaMask
- **Session**: JWT tokens for authenticated sessions
- **Rate Limiting**: Prevent abuse
- **Input Validation**: All inputs validated with Pydantic

## Development

### Running Locally
```bash
# Terminal 1: Backend
cd backend
python app.py

# Terminal 2: Frontend
cd frontend
npm run dev
```

### Environment Variables
```bash
# Backend
DATABASE_URL=sqlite:///./app.db
JWT_SECRET=your-secret-key
ETH_RPC_URL=https://eth-mainnet.g.alchemy.com/v2/YOUR_KEY

# Frontend
VITE_API_URL=http://localhost:8000
VITE_CHAIN_ID=1
```

## Product Ideas

This repo can become:
- **Contract Deployment Console**: Python prepares deployments, MetaMask signs
- **AI-Assisted DeFi Terminal**: Python computes actions, frontend executes with MetaMask
- **Portfolio + Strategy Dashboard**: Python analytics, JS wallet control
- **Market Maker Control Panel**: Python bot backend, MetaMask admin actions

## Why This Architecture

**Better than current bridge script:**
- Clearly split client/server roles
- MetaMask-compatible by design
- Deployable
- Easier to sell
- Safer (no private keys in backend)

**Message**: "MetaMask-powered execution frontend with Python intelligence backend"

## License

MIT License - See LICENSE file for details

## Status

🚧 **In Development** - MVP scaffold being built
