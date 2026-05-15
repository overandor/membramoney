# 🐳 Docker Deployment Guide
## Production Solana Trading System with RPC Rotator

### 🚀 Quick Start

#### Prerequisites
- Docker Desktop (Mac/Windows) or Docker Engine (Linux)
- Docker Compose
- Git
- 4GB+ RAM recommended

#### One-Command Deployment
```bash
# Clone the repository
git clone <repository-url>
cd decentralized-trader

# Deploy with default settings
./deploy.sh deploy

# Or deploy with custom settings
./deploy.sh deploy latest production 8080
```

### 📋 System Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Nginx Proxy   │────│  Solana Trader   │────│  RPC Rotator    │
│   (Port 80/443) │    │  (Port 8080)     │    │  (Port 8083)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                │
                       ┌──────────────────┐
                       │      Redis       │
                       │    (Port 6379)   │
                       └──────────────────┘
                                │
                       ┌──────────────────┐
                       │   Grafana        │
                       │   (Port 3000)    │
                       └──────────────────┘
```

### 🔧 Installation

#### 1. Install Docker

**Mac (Intel):**
```bash
# Download and install Docker Desktop
curl -O https://desktop.docker.com/mac/main/amd64/Docker.dmg
open Docker.dmg
```

**Mac (Apple Silicon):**
```bash
# Download and install Docker Desktop
curl -O https://desktop.docker.com/mac/main/arm64/Docker.dmg
open Docker.dmg
```

**Linux (Ubuntu/Debian):**
```bash
# Update package index
sudo apt-get update

# Install Docker
sudo apt-get install -y docker.io docker-compose-plugin

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Linux (CentOS/RHEL):**
```bash
# Install Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start and enable Docker
sudo systemctl start docker
sudo systemctl enable docker

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

#### 2. Verify Installation
```bash
docker --version
docker compose version
```

#### 3. Clone and Deploy
```bash
# Clone repository
git clone <repository-url>
cd decentralized-trader

# Make deploy script executable
chmod +x deploy.sh

# Deploy the system
./deploy.sh deploy
```

### 🌐 Access Points

After deployment, access the system at:

| Service | URL | Credentials |
|---------|-----|-------------|
| Main Application | http://localhost:8080 | None |
| API Documentation | http://localhost:8081 | None |
| Trading Interface | http://localhost:8082 | None |
| RPC Rotator Status | http://localhost:8083/api/rotator_status | None |
| Grafana Dashboard | http://localhost:3000 | admin/admin123 |
| Prometheus | http://localhost:9090 | None |
| Redis | localhost:6379 | None |

### 📊 Monitoring

#### Grafana Dashboard
1. Access Grafana at http://localhost:3000
2. Login with admin/admin123
3. View pre-configured dashboards:
   - System Performance
   - RPC Endpoint Health
   - Trading Statistics
   - Error Rates

#### Prometheus Metrics
Access Prometheus at http://localhost:9090 for raw metrics.

#### Health Checks
```bash
# Check all services
./deploy.sh status

# Check specific service health
curl http://localhost:8083/api/rotator_status
curl http://localhost:8080/api/system_status
```

### 🔧 Configuration

#### Environment Variables
Edit `.env` file to customize:

```bash
# Application Settings
PROJECT_NAME=solana-trading
ENVIRONMENT=production
LOG_LEVEL=INFO

# Network Ports
RPC_ROTATOR_PORT=8083
MAIN_APP_PORT=8080
NGINX_HTTP_PORT=80

# Solana Configuration
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
LOAD_BALANCING_STRATEGY=health_based
HEALTH_CHECK_INTERVAL=30

# Security
JWT_SECRET=your-secret-key
API_RATE_LIMIT=100
```

#### Custom RPC Endpoints
Add custom RPC endpoints in `solana_rpc_rotator.py`:

```python
RPC_ENDPOINTS = [
    "https://your-custom-rpc-1.com",
    "https://your-custom-rpc-2.com",
    # ... more endpoints
]
```

### 🚀 Deployment Commands

#### Basic Commands
```bash
# Deploy with latest version
./deploy.sh deploy

# Deploy with specific version
./deploy.sh deploy v1.0.0

# Deploy to staging environment
./deploy.sh deploy latest staging 8080

# Stop all services
./deploy.sh stop

# Restart all services
./deploy.sh restart

# View logs
./deploy.sh logs

# View logs for specific service
./deploy.sh logs solana-trader

# Check system status
./deploy.sh status

# Cleanup unused resources
./deploy.sh cleanup
```

#### Advanced Commands
```bash
# Build Docker images only
./deploy.sh build

# Scale services
docker-compose up -d --scale solana-trader=3

# Update specific service
docker-compose up -d solana-trader

# View resource usage
docker stats

# Enter container shell
docker-compose exec solana-trader bash
```

### 🔄 CI/CD Integration

#### GitHub Actions
The system includes automatic CI/CD with GitHub Actions:

1. **Automatic Testing**: Runs on every push/PR
2. **Security Scanning**: Trivy vulnerability scanning
3. **Docker Build**: Multi-platform image building
4. **Automatic Deployment**: Staging on develop, Production on releases

#### Manual Deployment from GitHub
```bash
# Pull latest image
docker pull ghcr.io/your-org/solana-trading:latest

# Deploy with GitHub image
./deploy.sh deploy latest
```

### 🐛 Troubleshooting

#### Common Issues

**Docker not running:**
```bash
# Start Docker daemon
sudo systemctl start docker

# On Mac/Windows, start Docker Desktop
```

**Port conflicts:**
```bash
# Check what's using the port
lsof -i :8080

# Kill the process
kill -9 <PID>

# Or change port in .env file
```

**Permission denied:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**Service not starting:**
```bash
# Check logs
./deploy.sh logs

# Check container status
docker-compose ps

# Restart specific service
docker-compose restart solana-trader
```

**Memory issues:**
```bash
# Check memory usage
docker stats

# Increase Docker memory limit in Docker Desktop settings
```

#### Debug Mode
Enable debug logging:
```bash
# Set log level to debug
export LOG_LEVEL=DEBUG

# Or edit .env file
echo "LOG_LEVEL=DEBUG" >> .env

# Restart services
./deploy.sh restart
```

### 📈 Performance Tuning

#### Docker Optimization
```bash
# Optimize Docker for production
echo '{"default-runtime": "runc"}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
```

#### Resource Limits
Edit `docker-compose.yml` to add resource limits:

```yaml
services:
  solana-trader:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 2G
        reservations:
          cpus: '1.0'
          memory: 1G
```

#### Load Balancing
Configure load balancing strategy in `.env`:

```bash
LOAD_BALANCING_STRATEGY=weighted  # Options: round_robin, weighted, health_based
HEALTH_CHECK_INTERVAL=30
FAILURE_THRESHOLD=3
MAX_LATENCY_MS=1000
```

### 🔒 Security

#### SSL/TLS Setup
```bash
# Generate SSL certificates
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl/private.key \
  -out ssl/certificate.crt

# Update nginx.conf to use SSL
# The system will automatically use SSL certificates
```

#### API Security
```bash
# Generate secure API keys
python -c "
import secrets
print('JWT_SECRET=' + secrets.token_hex(32))
print('ENCRYPTION_KEY=' + secrets.token_hex(32))
"
```

#### Firewall Rules
```bash
# Allow only necessary ports
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

### 📱 Mobile Access

The system is fully responsive and works on mobile devices. Access via browser on any device connected to the same network.

### 🌍 Global Deployment

#### Cloud Deployment
Deploy to any cloud provider with Docker support:

**AWS:**
```bash
# Install Docker on EC2 instance
# Deploy using same commands
./deploy.sh deploy
```

**Google Cloud:**
```bash
# Use Cloud Run or GKE with Docker image
gcloud run deploy solana-trading --image ghcr.io/your-org/solana-trading
```

**Azure:**
```bash
# Use Azure Container Instances
az container create --resource-group solana-trading --image ghcr.io/your-org/solana-trading
```

#### Domain Setup
1. Configure DNS to point to your server
2. Update nginx.conf with your domain
3. Obtain SSL certificate (Let's Encrypt recommended)
4. Restart services

### 📞 Support

#### Getting Help
- Check logs: `./deploy.sh logs`
- Check status: `./deploy.sh status`
- Review this README
- Check GitHub Issues

#### Reporting Issues
1. Collect logs: `./deploy.sh logs > issue.log`
2. Get system info: `docker-compose ps > system.log`
3. Create GitHub Issue with logs and description

---

**🎉 Congratulations! Your Solana Trading System is now running with Docker!**

For additional help, check the logs or run `./deploy.sh help` for all available commands.
