# Production Dockerfile for Solana Trading System
# Multi-stage build for optimal size and security

# Stage 1: Builder
FROM python:3.11-slim as builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    SOLANA_RPC_URL="https://api.mainnet-beta.solana.com" \
    LOG_LEVEL="INFO"

# Install runtime system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    dnsutils \
    jq \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash solana

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create application directory
WORKDIR /app

# Copy application files
COPY --chown=solana:solana . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/config && \
    chown -R solana:solana /app

# Switch to non-root user
USER solana

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8083/api/rotator_status || exit 1

# Expose ports
EXPOSE 8080 8081 8082 8083

# Default command
CMD ["python", "solana_rpc_rotator.py"]

# Labels for metadata
LABEL maintainer="Solana Trading Team" \
      version="1.0.0" \
      description="Production Solana Trading System with RPC Rotator" \
      org.opencontainers.image.title="Solana Trading System" \
      org.opencontainers.image.description="Production-ready Solana trading with RPC rotation" \
      org.opencontainers.image.vendor="Solana Trading" \
      org.opencontainers.image.licenses="MIT"
