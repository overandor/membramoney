# ENA Hedging Bot - Daemon Mode

## Overview

The ENA Hedging Bot now supports persistent 24/7 daemon mode with automatic restart on failure, health monitoring, and graceful shutdown.

## Features

- **PID File Management**: Tracks running process to prevent duplicate instances
- **Signal Handling**: Graceful shutdown on SIGINT (Ctrl+C) and SIGTERM
- **Auto-Restart**: Automatically restarts bot on crashes (configurable max attempts)
- **Health Checks**: Periodic exchange connectivity and profit status monitoring
- **Systemd Support**: Ready for production deployment as a system service

## Configuration

Add these variables to your `.env` file:

```bash
# Daemon Configuration
DAEMON_MODE=1                    # Enable daemon mode
MAX_RESTART_ATTEMPTS=10         # Maximum restart attempts
RESTART_DELAY_SEC=5             # Delay between restarts
HEALTH_CHECK_INTERVAL_SEC=60   # Health check interval
```

## Usage

### Running as Daemon (Foreground)
```bash
DAEMON_MODE=1 PAPER_MODE=1 ARM_LIVE=NO python ena.py
```

### Running as Daemon (Background)
```bash
nohup DAEMON_MODE=1 PAPER_MODE=1 ARM_LIVE=NO python ena.py > ena_hedge.out 2>&1 &
```

### Stopping the Daemon
```bash
kill $(cat ena_hedge.pid)
```

## Systemd Service

Edit `ena-hedge.service` to set your username, then:

```bash
sudo cp ena-hedge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ena-hedge
sudo systemctl start ena-hedge
```

## Monitoring

Check PID: `cat ena_hedge.pid`
View logs: `tail -f ena_hedge.log`
Check status: `ps aux | grep ena.py`
