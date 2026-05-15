# VEIS - Verified Environmental Intelligence System

A modular, scalable backend platform for municipal waste management with AI-powered detection, cleanup verification, and carbon credit generation.

## Features

- **Wallet-Based Authentication**: MetaMask integration with JWT tokens
- **Role-Based Access Control**: Admin, city_operator, reviewer, contractor, viewer roles
- **Waste Observation Ingestion**: Image uploads with GPS metadata
- **AI-Based Detection**: Automated waste type identification and mass estimation
- **Cleanup Verification**: Baseline vs follow-up image comparison
- **VCU Generation**: Verified Cleanup Units (carbon credits)
- **City Operations**: Zones, incidents, work orders management
- **NYC 311 Integration**: Mock complaint routing system
- **Async Processing**: Celery-based background jobs
- **Gradio UI**: Interactive web interface for authenticated operations
- **Production Ready**: Dockerized with PostgreSQL and Redis

## Tech Stack

- **Python 3.11**
- **FastAPI** - Web framework
- **PostgreSQL** - Database (SQLAlchemy + Alembic)
- **Redis** - Caching and message broker
- **Celery** - Background job processing
- **Pydantic** - Data validation
- **PyJWT** - JWT token handling
- **eth-account** - Ethereum wallet signature verification
- **Gradio** - Interactive web interface
- **Docker** - Containerization
- **pytest** - Testing

## Installation

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL 15+ (for local development)
- Redis 7+ (for local development)

### Quick Start with Docker

```bash
# Clone the repository
git clone https://github.com/overandor/veis.git
cd veis

# Start all services
docker-compose up -d

# Run database migrations
docker-compose exec app alembic upgrade head

# Seed initial data
docker-compose exec app python seed_data.py

# Access the API
open http://localhost:8000/docs
```

### Local Development Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env

# Edit .env with your configuration
nano .env

# Start PostgreSQL and Redis (using Docker)
docker-compose up -d db redis

# Run database migrations
alembic upgrade head

# Seed initial data
python seed_data.py

# Start the application
uvicorn app.main:app --reload

# Start Celery worker (in separate terminal)
celery -A app.workers.tasks worker --loglevel=info
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@localhost:5432/veis` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | `redis://localhost:6379/1` |
| `CELERY_RESULT_BACKEND` | Celery result backend | `redis://localhost:6379/2` |
| `SECRET_KEY` | JWT secret key | (generate your own) |
| `DEBUG` | Debug mode | `True` |
| `UPLOAD_DIR` | File upload directory | `./uploads` |
| `MAX_UPLOAD_SIZE_MB` | Max upload size | `10` |

## API Overview

### Observations

```bash
# Create observation with image upload
curl -X POST "http://localhost:8000/observations/" \
  -F "file=@waste_image.jpg" \
  -F "latitude=40.7128" \
  -F "longitude=-74.0060" \
  -F "address=123 Main St"

# Get observation
curl "http://localhost:8000/observations/1"

# List observations
curl "http://localhost:8000/observations/"
```

### Verifications

```bash
# Create verification
curl -X POST "http://localhost:8000/verifications/" \
  -H "Content-Type: application/json" \
  -d '{
    "observation_id": 1,
    "followup_image_url": "followup.jpg"
  }'

# Get verification
curl "http://localhost:8000/verifications/1"
```

### VCUs (Verified Cleanup Units)

```bash
# Get VCU
curl "http://localhost:8000/vcus/1"

# Transfer VCU
curl -X POST "http://localhost:8000/vcus/1/transfer" \
  -H "Content-Type: application/json" \
  -d '{"new_owner": "new_owner_id"}'
```

### Incidents

```bash
# Create incident
curl -X POST "http://localhost:8000/incidents/" \
  -H "Content-Type: application/json" \
  -d '{
    "zone_id": 1,
    "description": "Large waste pile on sidewalk",
    "priority": "high",
    "waste_type": "plastic"
  }'

# Auto-dispatch work order
curl -X POST "http://localhost:8000/incidents/1/dispatch"

# List incidents
curl "http://localhost:8000/incidents/"
```

### Work Orders

```bash
# Create work order
curl -X POST "http://localhost:8000/work-orders/" \
  -H "Content-Type: application/json" \
  -d '{
    "incident_id": 1,
    "zone_id": 1,
    "assigned_to": "crew_123",
    "description": "Cleanup required",
    "estimated_duration_hours": 2.0
  }'

# Complete work order
curl -X POST "http://localhost:8000/work-orders/1/complete?actual_duration_hours=1.5&verification_id=1"
```

### Zones

```bash
# Create zone
curl -X POST "http://localhost:8000/zones/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Manhattan Downtown",
    "zone_code": "MDT",
    "center_latitude": 40.7128,
    "center_longitude": -74.0060,
    "priority_level": "high"
  }'

# List zones
curl "http://localhost:8000/zones/"
```

### NYC 311 Integration

```bash
# Create NYC 311 complaint
curl -X POST "http://localhost:8000/integrations/nyc/311/complaints" \
  -H "Content-Type: application/json" \
  -d '{
    "complaint_type": "Illegal Dumping",
    "description": "Large pile of construction debris",
    "latitude": 40.7128,
    "longitude": -74.0060,
    "address": "123 Main St"
  }'

# Get complaint status
curl "http://localhost:8000/integrations/nyc/311/complaints/NYC311-ABC123"
```

### Authentication

```bash
# Request nonce for wallet signature
curl -X POST "http://localhost:8000/auth/nonce" \
  -H "Content-Type: application/json" \
  -d '{"wallet_address": "0x1234..."}'

# Verify signature and get JWT token
curl -X POST "http://localhost:8000/auth/verify" \
  -H "Content-Type: application/json" \
  -d '{
    "wallet_address": "0x1234...",
    "signature": "0xabc..."
  }'

# Get current user info
curl "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Logout
curl -X POST "http://localhost:8000/auth/logout" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# List all users (admin only)
curl "http://localhost:8000/auth/admin/users" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Set user role (admin only)
curl -X POST "http://localhost:8000/auth/admin/users/0x1234.../role" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "city_operator"}'
```

### Web Interface

- **Login Page**: http://localhost:8000/auth/login - MetaMask wallet authentication
- **Gradio App**: http://localhost:8000/app - Interactive authenticated interface

## Database Schema

### Core Tables

- **observations**: Waste observations with images and GPS data
- **verifications**: Cleanup verification results
- **vcus**: Verified Cleanup Units (carbon credits)
- **incidents**: Waste management incidents
- **work_orders**: Cleanup crew assignments
- **zones**: Geographic operational zones

### Relationships

- Observation → Verifications (one-to-many)
- Verification → VCU (one-to-one)
- Incident → Work Orders (one-to-many)
- Zone → Incidents (one-to-many)
- Zone → Work Orders (one-to-many)

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_detection_service.py

# Run specific test
pytest tests/test_detection_service.py::test_detect_waste
```

## Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new feature"

# Apply migrations
alembic upgrade head

# Rollback migration
alembic downgrade -1

# View migration history
alembic history
```

## Celery Tasks

### Available Tasks

- `process_observation_task`: Process observation with AI detection
- `cleanup_old_observations`: Cleanup old completed observations

### Monitoring Celery

```bash
# View active tasks
celery -A app.workers.tasks inspect active

# View registered tasks
celery -A app.workers.tasks inspect registered

# View worker stats
celery -A app.workers.tasks inspect stats
```

## Gradio UI

### Accessing the Interface

1. Open http://localhost:8000/auth/login
2. Connect your MetaMask wallet
3. Sign the authentication message
4. Navigate to http://localhost:8000/app

### Gradio Features

- **Session Tab**: View current user info and session details
- **Admin Tab**: List users and manage roles (admin only)
- **Info Tab**: Usage instructions and role information

### Admin Operations

- List all registered users
- Promote users to different roles
- View user organization assignments
- Monitor user status

## Architecture

### Service Layer Pattern

- **API Layer**: FastAPI routes (app/api/)
- **Service Layer**: Business logic (app/services/)
- **Model Layer**: Database models (app/models/)
- **Schema Layer**: Pydantic schemas (app/schemas/)

### Authentication Architecture

- **Wallet-Based**: MetaMask integration with signature verification
- **JWT Tokens**: Stateless authentication with configurable expiration
- **Role-Based Access Control**: 5 roles with different permissions
- **Session Management**: In-memory session tracking with revocation
- **Gradio Integration**: Authenticated web interface

### User Roles

1. **admin** - Full system access, user management
2. **city_operator** - Manage incidents, work orders, zones
3. **reviewer** - Review verifications, approve VCUs
4. **contractor** - Complete assigned work orders
5. **viewer** - Read-only access to observations and data

### Async Processing

- **Celery**: Background job processing
- **Redis**: Message broker and result backend
- **Retry Logic**: Automatic retry with exponential backoff

## Monitoring & Logging

### Structured Logging

Logs are structured in JSON format for easy parsing:

```json
{
  "event": "Observation created",
  "observation_id": 1,
  "level": "info",
  "timestamp": "2026-04-18T12:00:00Z"
}
```

### Health Checks

```bash
# Health check endpoint
curl http://localhost:8000/health

# Response
{
  "status": "healthy",
  "app": "veis",
  "version": "1.0.0"
}
```

## Production Deployment

### Docker Compose (Production)

```bash
# Use production configuration
docker-compose -f docker-compose.prod.yml up -d
```

### Environment Setup

1. Set strong `SECRET_KEY`
2. Configure production database
3. Set up Redis cluster
4. Configure CDN for file uploads
5. Enable SSL/TLS
6. Set up monitoring (Prometheus, Grafana)

### Scaling

- **Horizontal Scaling**: Run multiple app instances behind load balancer
- **Celery Scaling**: Add more workers for high-volume processing
- **Database Scaling**: Use read replicas for queries
- **Redis Scaling**: Use Redis Cluster for high availability

## Security Considerations

- **API Keys**: Implement API key authentication
- **Rate Limiting**: Add rate limiting to prevent abuse
- **Input Validation**: All inputs validated via Pydantic
- **SQL Injection**: Protected via SQLAlchemy ORM
- **File Upload**: Validate file types and sizes
- **CORS**: Configure allowed origins in production

## Future Enhancements

- [ ] Authentication & RBAC
- [ ] Rate limiting & API keys
- [ ] Audit logs
- [ ] IPFS hash storage for images
- [ ] Real WebSocket updates
- [ ] Mobile app integration
- [ ] Real AI model integration
- [ ] Blockchain VCU minting
- [ ] Analytics dashboard
- [ ] Multi-tenant support

## License

MIT License

## Support

For issues and questions:
- GitHub Issues: https://github.com/overandor/veis/issues
- Documentation: https://docs.veis.example.com

---

**VEIS** - Verified Environmental Intelligence System
*Making cities cleaner, one observation at a time*
