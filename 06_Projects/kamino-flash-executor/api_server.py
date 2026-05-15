#!/usr/bin/env python3
"""
Simple API server for Kamino Flash Arb Dashboard
Exposes scanner metrics and logs via HTTP
"""

from aiohttp import web
import json
import asyncio
import subprocess
import re
from datetime import datetime
from collections import deque
import os

# Store recent logs and metrics
logs = deque(maxlen=100)
metrics = {
    "status": "running",
    "candidates": 0,
    "profitable": 0,
    "best_profit_usdc": 0.0,
    "total_scans": 0,
    "start_time": datetime.utcnow().isoformat(),
    "last_scan_time": None
}

# Pattern to match JSON log lines
json_pattern = re.compile(r'^\{.*\}$')

async def handle_metrics(request):
    """Get current scanner metrics"""
    return web.json_response(metrics)

async def handle_logs(request):
    """Get recent logs"""
    return web.json_response({"logs": list(logs)})

async def handle_index(request):
    """Serve the dashboard HTML"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "dashboard.html")
    with open(dashboard_path, 'r') as f:
        return web.Response(text=f.read(), content_type='text/html')

async def handle_config(request):
    """Get current configuration"""
    config = {
        "scan_interval_ms": 10000,
        "max_concurrency": 1,
        "target_mint": "WSOL",
        "borrow_size_usdc": 100,
        "min_profit_threshold_usdc": 0.10,
        "executor_enabled": False
    }
    return web.json_response(config)

async def handle_dex_comparison(request):
    """Get latest DEX comparison data"""
    # Extract DEX comparison logs
    dex_logs = []
    for log in reversed(logs):
        if log.get('message') == 'dex_comparison':
            dex_logs.append(log)
            if len(dex_logs) >= 20:  # Keep last 20 comparisons
                break
    return web.json_response({"dex_comparisons": dex_logs})

async def log_tailer():
    """Tail the scanner logs and parse them"""
    log_file = "/tmp/kamino_scanner.log"
    
    # Create log file if it doesn't exist
    if not os.path.exists(log_file):
        with open(log_file, 'w') as f:
            f.write('')
    
    # Tail the log file
    with open(log_file, 'r') as f:
        # Move to end of file
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if line:
                line = line.strip()
                if json_pattern.match(line):
                    try:
                        log_data = json.loads(line)
                        logs.append(log_data)
                        
                        # Update metrics from scan_cycle_complete logs
                        if log_data.get('message') == 'scan_cycle_complete':
                            metrics['candidates'] = log_data.get('candidates', 0)
                            metrics['profitable'] = log_data.get('profitable', 0)
                            metrics['best_profit_usdc'] = float(log_data.get('bestNetProfitUsdc', '0'))
                            metrics['total_scans'] += 1
                            metrics['last_scan_time'] = log_data.get('ts', datetime.utcnow().isoformat())
                            
                            # Update status
                            metrics['status'] = 'running'
                    except json.JSONDecodeError:
                        pass
            else:
                await asyncio.sleep(0.1)

async def start_background_tasks(app):
    """Start background tasks"""
    asyncio.create_task(log_tailer())

def create_app():
    app = web.Application()
    app.router.add_get('/api/metrics', handle_metrics)
    app.router.add_get('/api/logs', handle_logs)
    app.router.add_get('/api/config', handle_config)
    app.router.add_get('/api/dex-comparison', handle_dex_comparison)
    app.router.add_get('/', handle_index)
    app.on_startup.append(start_background_tasks)
    return app

if __name__ == '__main__':
    app = create_app()
    web.run_app(app, host='127.0.0.1', port=8765)
    print("API Server running on http://127.0.0.1:8765")
