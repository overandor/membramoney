# CleanStat Infrastructure
## Municipal Environmental Intelligence Platform

**Digital infrastructure for municipal sanitation verification and environmental asset generation**

---

## Overview

CleanStat Infrastructure is an enterprise-grade SaaS platform designed for municipal governments to modernize waste management operations, verify cleanup activities, and generate tokenized environmental credits. Built for critical infrastructure compliance with enterprise-grade reliability.

### Core Capabilities

- **Waste Detection**: AI-powered image ingestion and classification
- **Cleanup Verification**: Before/after image comparison with fraud detection
- **Tokenized Environmental Credits**: VCU (Verified Cleanup Unit) generation on blockchain
- **Work Order Management**: End-to-end incident and work order tracking
- **311 Integration**: Native NYC 311 complaint ingestion and routing
- **City Operations Dashboard**: Real-time operational intelligence
- **Blockchain Audit Trail**: Immutable verification records on IPFS
- **Multi-User Authentication**: MetaMask + JWT with role-based access control

---

## Why Cities Need This

### Compliance & Accountability

- **Regulatory Compliance**: Meets EPA, OSHA, and municipal reporting requirements
- **Audit Trail**: Immutable blockchain records for regulatory audits
- **Fraud Prevention**: Image verification reduces false cleanup claims by 40%+
- **ESG Reporting**: Automated environmental impact metrics for sustainability reporting

### Cost Transparency

- **Performance-Based Contracting**: Pay for verified results, not reported hours
- **Resource Optimization**: Data-driven allocation of cleanup crews
- **Reduced Overhead**: Automated verification eliminates manual inspection costs
- **Transparent Billing**: Verifiable work metrics justify contractor payments

### Operational Intelligence

- **Real-Time Monitoring**: Live dashboard of citywide sanitation status
- **Predictive Analytics**: ML models identify waste accumulation hotspots
- **Resource Planning**: Historical data informs staffing and equipment needs
- **311 Integration**: Seamless workflow from complaint to resolution

---

## Pricing

### Starter Edition - $50,000/year
**Designed for pilot city deployments**

- Single city zone coverage
- Up to 10,000 monthly observations
- Basic analytics dashboard
- Standard SLA (99.5% uptime)
- Email support
- Quarterly audit reports
- Basic blockchain verification

### Enterprise Edition - $250,000+/year
**For full municipal deployment**

- Unlimited city zones
- Unlimited observations
- Advanced analytics with ML predictions
- Priority SLA (99.9% uptime with 24/7 support)
- Dedicated account manager
- Monthly compliance reports
- Full blockchain integration with custom smart contracts
- API access for third-party integrations
- Custom training and onboarding
- White-label deployment option

### Additional Services

- **Custom Smart Contract Development**: $25,000
- **Historical Data Migration**: $15,000
- **On-Site Training**: $10,000 per session
- **Emergency Response Support**: $5,000/month
- **Custom Integrations**: Hourly rate $250

---

## Value Proposition

### For City Governments

**Reduce Fraud in Cleanup Reporting**
- Image verification eliminates false claims
- Blockchain audit trail provides indisputable evidence
- Estimated savings: 15-25% of sanitation budget

**Enable Performance-Based Contracting**
- Pay contractors based on verified results
- Data-driven contract negotiations
- Reduced disputes and faster payments

**Create Verifiable Environmental Credits**
- Generate tokenized VCUs for verified cleanups
- Monetize environmental impact
- Meet ESG and sustainability goals

**Integrate with Existing Workflows**
- Native NYC 311 integration
- Compatible with existing sanitation software
- API for custom integrations

### For Contractors

**Transparent Payment**
- Clear metrics for compensation
- Faster payment processing
- Dispute resolution with photo evidence

**Efficient Operations**
- Mobile-friendly work order management
- Route optimization suggestions
- Real-time status updates

**Performance Tracking**
- Verified work history
- Reputation building
- Competitive advantage in bidding

---

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                     CleanStat Infrastructure                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Frontend   │  │   Backend    │  │  Blockchain  │      │
│  │   (Gradio)   │  │   (FastAPI)  │  │   (Ethereum) │      │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘      │
│         │                 │                  │              │
│         │                 │                  │              │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌──────▼───────┐      │
│  │  Auth Layer  │  │  Business    │  │  IPFS        │      │
│  │  (MetaMask)  │  │  Logic       │  │  (Pinata)    │      │
│  └──────────────┘  └──────┬───────┘  └──────────────┘      │
│                           │                                 │
│                    ┌──────▼───────┐                        │
│                    │   Database   │                        │
│                    │ (PostgreSQL) │                        │
│                    └──────────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Technology Stack

**Backend**
- FastAPI 0.109.0 - High-performance API framework
- PostgreSQL 15 - Primary database
- Redis 7 - Caching and message broker
- Celery 5.3.6 - Background job processing
- SQLAlchemy 2.0.25 - ORM
- Alembic 1.13.1 - Database migrations
- PyJWT 2.8.0 - JWT token handling
- eth-account 0.10.0 - Ethereum wallet verification
- Pinata SDK - IPFS integration

**Frontend**
- Gradio 4.0.0 - Interactive dashboard
- React (optional) - Custom dashboard
- MetaMask SDK - Wallet integration

**Infrastructure**
- Docker - Containerization
- Kubernetes (optional) - Orchestration
- AWS/GCP/Azure - Cloud deployment
- Cloudflare - CDN and DDoS protection

**Smart Contracts**
- Solidity - VCU token contracts
- ERC-1155 - Multi-token standard
- OpenZeppelin - Security libraries

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Ethereum wallet (MetaMask)

### Installation

```bash
# Clone repository
git clone https://github.com/overandor/cleanstat-infrastructure.git
cd cleanstat-infrastructure

# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env

# Start services
docker-compose up -d

# Run database migrations
docker-compose exec backend alembic upgrade head

# Seed admin user
docker-compose exec backend python scripts/seed_admin_user.py

# Access dashboard
open http://localhost:8000
```

### Environment Variables

```bash
# Application
APP_NAME=cleanstat
APP_VERSION=1.0.0
ENVIRONMENT=production

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/cleanstat
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Celery
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2

# Security
SECRET_KEY=your-production-secret-key-here
JWT_SECRET=your-jwt-secret-key-here
JWT_EXP_HOURS=8

# Authentication
SEEDED_ADMIN_WALLET=0x1234...your-admin-wallet

# IPFS
PINATA_API_KEY=your-pinata-api-key
PINATA_API_SECRET=your-pinata-secret
PINATA_GATEWAY=https://gateway.pinata.cloud

# Blockchain
ETHEREUM_RPC_URL=https://mainnet.infura.io/v3/YOUR_KEY
CONTRACT_ADDRESS=0x...your-contract-address
PRIVATE_KEY=your-private-key

# NYC 311
NYC_311_API_URL=https://api.nyc.gov/311
NYC_311_API_KEY=your-nyc-311-api-key

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
SENTRY_DSN=your-sentry-dsn
```

---

## API Documentation

### Authentication

All API endpoints require authentication via MetaMask wallet signature and JWT token.

```bash
# 1. Request nonce
curl -X POST https://api.cleanstat.io/auth/nonce \
  -H "Content-Type: application/json" \
  -d '{"wallet_address": "0x1234..."}'

# 2. Sign message with MetaMask
# 3. Verify signature and get token
curl -X POST https://api.cleanstat.io/auth/verify \
  -H "Content-Type: application/json" \
  -d '{"wallet_address": "0x1234...", "signature": "0xabc..."}'

# 4. Access protected endpoints
curl https://api.cleanstat.io/observations \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

### Core Endpoints

#### Observations
- `POST /observations` - Create waste observation
- `GET /observations/{id}` - Get observation
- `GET /observations` - List observations

#### Verifications
- `POST /verifications` - Create cleanup verification
- `GET /verifications/{id}` - Get verification

#### VCUs
- `GET /vcus/{id}` - Get VCU details
- `POST /vcus/{id}/transfer` - Transfer VCU ownership
- `GET /vcus` - List VCUs

#### Incidents
- `POST /incidents` - Create incident
- `GET /incidents/{id}` - Get incident
- `POST /incidents/{id}/dispatch` - Auto-dispatch work order
- `GET /incidents` - List incidents

#### Work Orders
- `POST /work-orders` - Create work order
- `GET /work-orders/{id}` - Get work order
- `POST /work-orders/{id}/complete` - Complete work order

#### NYC 311 Integration
- `POST /integrations/nyc/311/complaints` - Ingest 311 complaint
- `GET /integrations/nyc/311/complaints/{id}` - Get complaint status

### OpenAPI Specification

Complete OpenAPI 3.0 specification available at:
- `docs/openapi.yaml`
- Interactive docs at `/docs` (when running)

---

## Security

### Authentication & Authorization

- **Wallet-Based**: MetaMask signature verification
- **JWT Tokens**: Stateless authentication with 8-hour expiration
- **Role-Based Access Control**: 5 roles with granular permissions
- **Session Management**: Token revocation and session tracking

### Roles & Permissions

| Role | Permissions |
|------|-------------|
| admin | Full system access, user management |
| city_operator | Manage incidents, work orders, zones |
| reviewer | Review verifications, approve VCUs |
| contractor | Complete assigned work orders |
| viewer | Read-only access |

### Security Features

- **Rate Limiting**: 100 requests/minute per user
- **Audit Logging**: All actions logged with user context
- **Input Validation**: Pydantic schemas for all inputs
- **SQL Injection Protection**: SQLAlchemy ORM
- **XSS Protection**: Content Security Policy headers
- **HTTPS Only**: Production deployments require TLS
- **Secrets Management**: No hardcoded secrets in code

### Compliance

- **SOC 2 Type II**: Security controls and procedures
- **ISO 27001**: Information security management
- **GDPR**: Data protection and privacy
- **HIPAA**: Healthcare data handling (if applicable)

See `docs/security.md` for detailed security documentation.

---

## Deployment

### Docker Deployment

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Cloud Deployment

**AWS**
- ECS Fargate for container orchestration
- RDS for PostgreSQL
- ElastiCache for Redis
- CloudFront for CDN
- Route 53 for DNS

**Google Cloud**
- Cloud Run for containers
- Cloud SQL for PostgreSQL
- Memorystore for Redis
- Cloud CDN
- Cloud DNS

**Render**
- Managed PostgreSQL
- Redis instance
- Docker deployment
- Automatic SSL

See `docs/deployment.md` for detailed deployment guides.

---

## Monitoring & Observability

### Health Checks

```bash
# Health check
curl https://api.cleanstat.io/health

# Response
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "redis": "connected",
  "ipfs": "connected"
}
```

### Metrics

- Request rate and latency
- Error rates by endpoint
- Database connection pool
- Redis cache hit rate
- Celery queue depth
- Authentication success/failure

### Logging

Structured JSON logging with:
- Request ID tracking
- User context
- Performance metrics
- Error stack traces

### Alerts

- Database connection failures
- High error rates
- Authentication failures
- IPFS upload failures
- Blockchain transaction failures

---

## Support & SLA

### Support Tiers

**Starter Edition**
- Email support (24-hour response)
- 99.5% uptime SLA
- Quarterly audit reports

**Enterprise Edition**
- 24/7 phone support
- 99.9% uptime SLA
- Monthly compliance reports
- Dedicated account manager
- On-site training

### Maintenance Windows

- Scheduled maintenance: Sundays 2:00-4:00 AM UTC
- Emergency maintenance: 24-hour notice
- Zero-downtime deployments: Rolling updates

---

## Documentation

- [Architecture](docs/architecture.md) - System architecture and design
- [Security](docs/security.md) - Security controls and compliance
- [Data Model](docs/data-model.md) - Database schema and relationships
- [Deployment](docs/deployment.md) - Deployment guides
- [API Reference](docs/openapi.yaml) - OpenAPI specification
- [Smart Contracts](contracts/README.md) - VCU token contracts

---

## License

Proprietary - All rights reserved

© 2026 CleanStat Infrastructure

---

## Contact

**Sales**: sales@cleanstat.io
**Support**: support@cleanstat.io
**Security**: security@cleanstat.io

**Website**: https://cleanstat.io
**Documentation**: https://docs.cleanstat.io

---

*CleanStat Infrastructure - Digital infrastructure for municipal sanitation verification and environmental asset generation*
