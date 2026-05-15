"""
CopyThatPay Backend API
FastAPI server for execution engine with static IP (whitelisted)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict
import os
from dotenv import load_dotenv
import asyncio
from datetime import datetime

# Load environment variables
load_dotenv()

app = FastAPI(title="CopyThatPay Backend API")

# CORS for Hugging Face app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class BotConfig(BaseModel):
    mode: str = "paper"  # "paper" or "live"
    max_daily_loss: float = 0.02
    max_position_size: float = 0.45
    allowed_symbols: List[str] = ["DOGS/USDT", "SUN/USDT", "TLM/USDT", "ZK/USDT"]
    leverage_cap: int = 5

class MetricsResponse(BaseModel):
    timestamp: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    edge_ratio: float
    win_rate: float
    avg_win: float
    avg_loss: float
    avg_slippage: float
    time_to_exit_sec: float

class SymbolPerformance(BaseModel):
    symbol: str
    trades: int
    pnl: float
    edge_ratio: float
    win_rate: float
    score: float

# Mock engine state (replace with real engine integration)
class EngineState:
    def __init__(self):
        self.running = False
        self.mode = "paper"
        self.config = None
        self.metrics = MetricsResponse(
            timestamp=0,
            equity=5.87,
            realized_pnl=0.00,
            unrealized_pnl=0.00,
            edge_ratio=0.00,
            win_rate=0.00,
            avg_win=0.00,
            avg_loss=0.00,
            avg_slippage=0.00,
            time_to_exit_sec=0
        )
        self.symbol_performance = {
            "DOGS/USDT": SymbolPerformance(symbol="DOGS/USDT", trades=0, pnl=0.00, edge_ratio=0.00, win_rate=0.00, score=0.00),
            "SUN/USDT": SymbolPerformance(symbol="SUN/USDT", trades=0, pnl=0.00, edge_ratio=0.00, win_rate=0.00, score=0.00),
            "TLM/USDT": SymbolPerformance(symbol="TLM/USDT", trades=0, pnl=0.00, edge_ratio=0.00, win_rate=0.00, score=0.00),
            "ZK/USDT": SymbolPerformance(symbol="ZK/USDT", trades=0, pnl=0.00, edge_ratio=0.00, win_rate=0.00, score=0.00),
        }

engine = EngineState()

# Endpoints
@app.get("/")
async def root():
    return {
        "service": "CopyThatPay Backend API",
        "status": "running",
        "ip_whitelisted": True,
        "note": "This server must have static IP whitelisted in Gate.io"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "engine_running": engine.running,
        "mode": engine.mode
    }

@app.post("/bot/start")
async def start_bot(config: BotConfig):
    """Start the trading engine with configuration."""
    if engine.running:
        raise HTTPException(status_code=400, detail="Engine already running")
    
    # Validate config
    if config.max_daily_loss > 0.10:
        raise HTTPException(status_code=400, detail="max_daily_loss cannot exceed 10%")
    
    if config.mode == "live" and not os.getenv("GATE_API_KEY"):
        raise HTTPException(status_code=400, detail="GATE_API_KEY not set for live mode")
    
    engine.config = config
    engine.mode = config.mode
    engine.running = True
    
    # In real implementation, start the actual engine here
    # asyncio.create_task(run_copythatpay_engine(config))
    
    return {
        "status": "started",
        "mode": config.mode,
        "config": config.dict()
    }

@app.post("/bot/stop")
async def stop_bot():
    """Stop the trading engine."""
    if not engine.running:
        raise HTTPException(status_code=400, detail="Engine not running")
    
    engine.running = False
    
    # In real implementation, stop the actual engine here
    
    return {
        "status": "stopped"
    }

@app.get("/bot/status")
async def get_status():
    """Get current engine status."""
    return {
        "running": engine.running,
        "mode": engine.mode,
        "config": engine.config.dict() if engine.config else None,
        "uptime": "0s"  # Would be real uptime in production
    }

@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """Get current performance metrics."""
    engine.metrics.timestamp = datetime.now().timestamp()
    return engine.metrics

@app.get("/symbols/performance")
async def get_symbol_performance():
    """Get per-symbol performance data."""
    return engine.symbol_performance

@app.post("/symbols/auto_prune")
async def auto_prune_symbols():
    """Auto-prune worst performing symbols."""
    pruned = []
    threshold = 0.5  # Score threshold for pruning
    
    for symbol, perf in engine.symbol_performance.items():
        if perf.trades >= 20:
            if perf.score < threshold:
                pruned.append(symbol)
    
    if pruned:
        # In real implementation, disable these symbols
        pass
    
    return {
        "pruned": pruned,
        "count": len(pruned)
    }

@app.get("/config")
async def get_config():
    """Get current configuration."""
    return engine.config.dict() if engine.config else None

@app.post("/config")
async def update_config(config: BotConfig):
    """Update engine configuration."""
    if engine.running:
        raise HTTPException(status_code=400, detail="Cannot update config while engine running")
    
    engine.config = config
    return {"status": "updated", "config": config.dict()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
