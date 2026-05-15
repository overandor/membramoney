#!/bin/bash
# Production Deployment Script for Solana Trading System
# This script deploys the system to any environment with Docker

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="solana-trading"
DOCKER_REGISTRY="ghcr.io"
REPO_NAME="${DOCKER_REGISTRY}/$(git config remote.origin.url | sed 's|.*/||')"
VERSION=${1:-"latest"}
ENVIRONMENT=${2:-"production"}
PORT=${3:-8080}

echo -e "${BLUE}🚀 Solana Trading System Deployment${NC}"
echo -e "${BLUE}=====================================${NC}"
echo "Project: $PROJECT_NAME"
echo "Version: $VERSION"
echo "Environment: $ENVIRONMENT"
echo "Port: $PORT"
echo ""

# Function to check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}❌ Docker is not installed. Please install Docker first.${NC}"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        echo -e "${RED}❌ Docker Compose is not installed. Please install Docker Compose first.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Docker and Docker Compose are installed${NC}"
}

# Function to check if Docker daemon is running
check_docker_daemon() {
    if ! docker info &> /dev/null; then
        echo -e "${RED}❌ Docker daemon is not running. Please start Docker.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Docker daemon is running${NC}"
}

# Function to create necessary directories
create_directories() {
    echo -e "${BLUE}📁 Creating necessary directories...${NC}"
    
    mkdir -p logs
    mkdir -p data
    mkdir -p config
    mkdir -p ssl
    mkdir -p grafana/dashboards
    mkdir -p grafana/datasources
    
    echo -e "${GREEN}✅ Directories created${NC}"
}

# Function to generate environment file
generate_env_file() {
    echo -e "${BLUE}🔧 Generating environment file...${NC}"
    
    cat > .env << EOF
# Solana Trading System Environment Configuration
# Generated on $(date)

# Application Configuration
PROJECT_NAME=$PROJECT_NAME
ENVIRONMENT=$ENVIRONMENT
VERSION=$VERSION
LOG_LEVEL=INFO

# Network Configuration
RPC_ROTATOR_PORT=8083
MAIN_APP_PORT=8080
API_PORT=8081
TRADER_PORT=8082
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443

# Database Configuration
DATABASE_URL=sqlite:///app/data/trading.db
REDIS_URL=redis://redis:6379

# Solana Configuration
SOLANA_RPC_URL=https://api.mainnet-beta.solana.com
SOLANA_WS_URL=wss://api.mainnet-beta.solana.com
DRIFT_PROGRAM_ID=DRiFT5tHvhm9jYwUnE5wv1vqB1FvGdeh7eE2K3yWqgzZ

# Security Configuration
JWT_SECRET=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 32)
API_RATE_LIMIT=100
CORS_ORIGIN=*

# Monitoring Configuration
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
GRAFANA_ADMIN_PASSWORD=$(openssl rand -base64 12)

# Load Balancing Configuration
LOAD_BALANCING_STRATEGY=health_based
HEALTH_CHECK_INTERVAL=30
FAILURE_THRESHOLD=3
MAX_LATENCY_MS=1000

# Docker Configuration
COMPOSE_PROJECT_NAME=$PROJECT_NAME
COMPOSE_FILE=docker-compose.yml
EOF

    echo -e "${GREEN}✅ Environment file generated${NC}"
}

# Function to build Docker images
build_images() {
    echo -e "${BLUE}🔨 Building Docker images...${NC}"
    
    # Build the main application image
    docker build -t $REPO_NAME:$VERSION .
    docker tag $REPO_NAME:$VERSION $REPO_NAME:latest
    
    echo -e "${GREEN}✅ Docker images built${NC}"
}

# Function to deploy the application
deploy_app() {
    echo -e "${BLUE}🚀 Deploying application...${NC}"
    
    # Stop existing services
    docker-compose down
    
    # Pull latest images (if using registry)
    if [ "$VERSION" != "local" ]; then
        docker-compose pull
    fi
    
    # Start services
    docker-compose up -d
    
    # Wait for services to be ready
    echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
    sleep 30
    
    # Check service health
    check_health
    
    echo -e "${GREEN}✅ Application deployed successfully${NC}"
}

# Function to check service health
check_health() {
    echo -e "${BLUE}🏥 Checking service health...${NC}"
    
    # Check RPC Rotator
    if curl -f http://localhost:8083/api/rotator_status &> /dev/null; then
        echo -e "${GREEN}✅ RPC Rotator is healthy${NC}"
    else
        echo -e "${RED}❌ RPC Rotator is not responding${NC}"
    fi
    
    # Check Main Application
    if curl -f http://localhost:8080/api/system_status &> /dev/null; then
        echo -e "${GREEN}✅ Main Application is healthy${NC}"
    else
        echo -e "${RED}❌ Main Application is not responding${NC}"
    fi
    
    # Check Redis
    if docker exec solana_redis redis-cli ping &> /dev/null; then
        echo -e "${GREEN}✅ Redis is healthy${NC}"
    else
        echo -e "${RED}❌ Redis is not responding${NC}"
    fi
}

# Function to show deployment status
show_status() {
    echo -e "${BLUE}📊 Deployment Status${NC}"
    echo "=================="
    
    docker-compose ps
    
    echo ""
    echo -e "${BLUE}🌐 Service URLs${NC}"
    echo "=================="
    echo "Main Application: http://localhost:$PORT"
    echo "RPC Rotator: http://localhost:8083"
    echo "API Documentation: http://localhost:8081"
    echo "Grafana Dashboard: http://localhost:3000 (admin/admin123)"
    echo "Prometheus: http://localhost:9090"
    echo ""
    
    echo -e "${BLUE}📝 Logs${NC}"
    echo "========"
    echo "View logs with: docker-compose logs -f [service_name]"
    echo "Available services: solana-rpc-rotator, solana-trader, redis, nginx, prometheus, grafana"
}

# Function to cleanup
cleanup() {
    echo -e "${BLUE}🧹 Cleaning up...${NC}"
    
    # Remove stopped containers
    docker container prune -f
    
    # Remove unused images
    docker image prune -f
    
    # Remove unused networks
    docker network prune -f
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Main deployment function
main() {
    echo -e "${BLUE}🎯 Starting deployment process...${NC}"
    
    # Pre-deployment checks
    check_docker
    check_docker_daemon
    
    # Setup
    create_directories
    generate_env_file
    
    # Build and deploy
    if [ "$VERSION" == "local" ]; then
        build_images
    fi
    
    deploy_app
    
    # Show status
    show_status
    
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "1. Test the application: curl http://localhost:$PORT/api/system_status"
    echo "2. View logs: docker-compose logs -f"
    echo "3. Monitor performance: http://localhost:3000"
    echo "4. Stop the application: docker-compose down"
    echo ""
    echo -e "${BLUE}For support, check the logs or run: docker-compose logs${NC}"
}

# Handle script arguments
case "${1:-}" in
    "build")
        check_docker
        check_docker_daemon
        build_images
        ;;
    "deploy")
        main
        ;;
    "stop")
        echo -e "${BLUE}🛑 Stopping application...${NC}"
        docker-compose down
        echo -e "${GREEN}✅ Application stopped${NC}"
        ;;
    "restart")
        echo -e "${BLUE}🔄 Restarting application...${NC}"
        docker-compose restart
        check_health
        ;;
    "logs")
        docker-compose logs -f "${2:-}"
        ;;
    "status")
        check_health
        show_status
        ;;
    "cleanup")
        cleanup
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [COMMAND] [VERSION] [ENVIRONMENT] [PORT]"
        echo ""
        echo "Commands:"
        echo "  build              Build Docker images"
        echo "  deploy [VERSION]   Deploy application (default: latest)"
        echo "  stop               Stop application"
        echo "  restart            Restart application"
        echo "  logs [SERVICE]     Show logs for service"
        echo "  status             Show application status"
        echo "  cleanup            Cleanup unused Docker resources"
        echo "  help               Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 deploy latest production 8080"
        echo "  $0 deploy v1.0.0 staging 8080"
        echo "  $0 logs solana-trader"
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $1${NC}"
        echo "Run '$0 help' for usage information"
        exit 1
        ;;
esac
