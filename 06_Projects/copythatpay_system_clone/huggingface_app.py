"""
CopyThatPay - Hugging Face Gradio Interface
UI + API Client (No direct exchange access)
Execution Research Engine for Microstructure Strategies

⚠️ This app does NOT connect to exchanges directly.
It calls a backend API with static IP (whitelisted).
"""

import gradio as gr
import os
import requests
from typing import Dict, List, Optional
from datetime import datetime

# Backend API URL (set via environment variable or use localhost for dev)
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

def api_call(method: str, endpoint: str, data: dict = None):
    """Make API call to backend."""
    url = f"{BACKEND_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, timeout=5)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=5)
        else:
            return {"error": f"Unknown method: {method}"}
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API error: {response.status_code}", "detail": response.text}
    except Exception as e:
        return {"error": f"Connection failed: {str(e)}"}

def start_engine(mode: str, max_daily_loss: float, max_position_size: float, allowed_symbols: str):
    """Start the trading engine via backend API."""
    config = {
        "mode": mode,
        "max_daily_loss": max_daily_loss,
        "max_position_size": max_position_size,
        "allowed_symbols": [s.strip() for s in allowed_symbols.split(",")]
    }
    result = api_call("POST", "/bot/start", config)
    status = get_status_display()
    return str(result), status

def stop_engine():
    """Stop the trading engine via backend API."""
    result = api_call("POST", "/bot/stop")
    status = get_status_display()
    return str(result), status

def get_status_display():
    """Get current engine status from backend."""
    status = api_call("GET", "/bot/status")
    if "error" in status:
        return f"**Error:** {status['error']}"
    
    status_text = f"""
    **Status:** {'🟢 Running' if status['running'] else '🔴 Stopped'}
    **Mode:** {status['mode']}
    **Uptime:** {status['uptime']}
    """
    return status_text

def get_metrics_display():
    """Get current metrics from backend."""
    metrics = api_call("GET", "/metrics")
    if "error" in metrics:
        return f"**Error:** {metrics['error']}"
    
    metrics_text = f"""
    **Equity:** ${metrics['equity']:.2f}
    **Realized PnL:** ${metrics['realized_pnl']:.4f}
    **Unrealized PnL:** ${metrics['unrealized_pnl']:.4f}
    **Edge Ratio:** {metrics['edge_ratio']:.3f}
    **Win Rate:** {metrics['win_rate']:.1%}
    **Avg Win:** {metrics['avg_win']:.4f}
    **Avg Loss:** {metrics['avg_loss']:.4f}
    **Avg Slippage:** {metrics['avg_slippage']:.4f}
    **Time to Exit:** {metrics['time_to_exit_sec']}s
    """
    return metrics_text

def get_symbol_performance_display():
    """Get symbol performance from backend."""
    perf = api_call("GET", "/symbols/performance")
    if "error" in perf:
        return f"**Error:** {perf['error']}"
    
    lines = []
    for symbol, data in perf.items():
        lines.append(f"**{symbol}**")
        lines.append(f"  Trades: {data['trades']}")
        lines.append(f"  PnL: ${data['pnl']:.4f}")
        lines.append(f"  Edge Ratio: {data['edge_ratio']:.3f}")
        lines.append(f"  Win Rate: {data['win_rate']:.1%}")
        lines.append(f"  Score: {data['score']:.3f}")
        lines.append("")
    return "\n".join(lines)

def auto_prune_symbols():
    """Auto-prune worst performing symbols via backend API."""
    result = api_call("POST", "/symbols/auto_prune")
    if "error" in result:
        return f"Error: {result['error']}"
    
    if result['pruned']:
        return f"Pruned symbols: {', '.join(result['pruned'])}"
    else:
        return "No symbols pruned (insufficient data or all performing well)"

def check_backend_connection():
    """Check if backend is reachable."""
    result = api_call("GET", "/health")
    if "error" in result:
        return f"🔴 Backend unreachable: {result['error']}"
    return f"🟢 Backend connected (IP whitelisted)"

# Create Gradio interface
with gr.Blocks(title="CopyThatPay - Execution Research Engine", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# CopyThatPay")
    gr.Markdown("## Execution Research Engine for Microstructure Strategies")
    gr.Markdown("*UI + API Client (Backend has static IP, whitelisted in Gate.io)*")
    
    # Backend connection status
    backend_status = gr.Markdown(check_backend_connection())
    refresh_connection = gr.Button("Check Connection", size="sm")
    refresh_connection.click(
        lambda: check_backend_connection(),
        outputs=backend_status
    )
    
    with gr.Tabs():
        # Status Tab
        with gr.Tab("Status"):
            status_display = gr.Markdown(get_status_display())
            with gr.Row():
                start_btn = gr.Button("Start Engine", variant="primary")
                stop_btn = gr.Button("Stop Engine", variant="stop")
            
            with gr.Row():
                mode = gr.Radio(["paper", "live"], value="paper", label="Mode")
                max_daily_loss = gr.Slider(0.01, 0.10, value=0.02, step=0.01, label="Max Daily Loss (%)")
                max_position_size = gr.Slider(0.1, 5.0, value=0.45, step=0.05, label="Max Position Size ($)")
                allowed_symbols = gr.Textbox(value="DOGS/USDT,SUN/USDT,TLM/USDT,ZK/USDT", label="Allowed Symbols (comma-separated)")
            
            start_btn.click(
                start_engine,
                inputs=[mode, max_daily_loss, max_position_size, allowed_symbols],
                outputs=[gr.Textbox(label="Result"), status_display]
            )
            stop_btn.click(
                stop_engine,
                outputs=[gr.Textbox(label="Result"), status_display]
            )
        
        # Metrics Tab
        with gr.Tab("Metrics"):
            metrics_display = gr.Markdown(get_metrics_display())
            refresh_metrics = gr.Button("Refresh Metrics")
            refresh_metrics.click(
                lambda: get_metrics_display(),
                outputs=metrics_display
            )
        
        # Symbol Performance Tab
        with gr.Tab("Symbol Performance"):
            symbol_display = gr.Markdown(get_symbol_performance_display())
            prune_btn = gr.Button("Auto-Prune Worst Symbols")
            prune_result = gr.Textbox(label="Prune Result")
            prune_btn.click(
                auto_prune_symbols,
                outputs=prune_result
            )
            refresh_symbols = gr.Button("Refresh")
            refresh_symbols.click(
                lambda: get_symbol_performance_display(),
                outputs=symbol_display
            )
        
        # Configuration Tab
        with gr.Tab("Configuration"):
            gr.Markdown("### Risk Controls")
            gr.Markdown("- **Max Daily Loss:** Engine stops when daily loss exceeds this threshold")
            gr.Markdown("- **Max Position Size:** Maximum position size per trade")
            gr.Markdown("- **Allowed Symbols:** Only trade these symbols")
            gr.Markdown("- **Mode:** Paper trading (simulation) or Live trading")
            
            gr.Markdown("### Strategy Parameters")
            gr.Markdown("- **MIN_REAL_SPREAD:** 0.4% minimum spread to trade")
            gr.Markdown("- **SPREAD_TARGET_PCT:** 0.3% target per leg")
            gr.Markdown("- **MAX_ADVERSE_MOVE:** 0.2% hard adverse selection exit")
            gr.Markdown("- **DAILY_STOP:** -2% daily stop loss")
            
            gr.Markdown("### Edge Filters")
            gr.Markdown("- **No Trade Zone:** Skip dead markets (momentum < 0.05%) and too volatile (momentum > 1%)")
            gr.Markdown("- **One-Side Trading:** Trade only the side with edge (bullish = long, bearish = short)")
            gr.Markdown("- **Adverse Selection Exit:** Force market close on 0.2% adverse move")
        
        # Info Tab
        with gr.Tab("Info"):
            gr.Markdown("### ⚠️ Architecture")
            gr.Markdown("**This app does NOT connect to exchanges directly.**")
            gr.Markdown("")
            gr.Markdown("It calls a backend API with:")
            gr.Markdown("- Static IP (whitelisted in Gate.io)")
            gr.Markdown("- CCXT + execution engine")
            gr.Markdown("- Risk controls and state management")
            gr.Markdown("")
            gr.Markdown("**Hugging Face = UI layer only**")
            gr.Markdown("**Backend = Execution layer**")
            gr.Markdown("")
            gr.Markdown("### What This System Does")
            gr.Markdown("CopyThatPay is a selective microstructure scalper with real edge filters.")
            gr.Markdown("")
            gr.Markdown("**Core Strategy:**")
            gr.Markdown("- Trade ONLY when real spread exists (0.4% minimum)")
            gr.Markdown("- One-side trading based on edge (bullish = long only, bearish = short only)")
            gr.Markdown("- Maker entries only - no taker fallback (no forced losses)")
            gr.Markdown("- Small achievable exits (0.3% target)")
            gr.Markdown("- Hard adverse selection exits (0.2% max adverse move)")
            gr.Markdown("- Skip dead markets (momentum < 0.05%) and too volatile (momentum > 1%)")
            gr.Markdown("- Daily stop loss (-2%) to prevent death spirals")
            gr.Markdown("")
            gr.Markdown("**Risk Controls:**")
            gr.Markdown("- Max 2% equity drawdown per symbol, 10% global — hard enforced")
            gr.Markdown("- Time-based exits flatten stale positions automatically")
            gr.Markdown("- Volatility kill-switch pauses trading in abnormal conditions")
            gr.Markdown("- Inventory control (max 10 contracts net exposure per symbol)")
            gr.Markdown("- Edge ratio kill switch (pause if realized/expected < 80%)")
            gr.Markdown("")
            gr.Markdown("### Important Disclaimer")
            gr.Markdown("*This is an execution research engine, not a guaranteed profit tool. Trading involves significant risk of loss. Past performance does not guarantee future results. Use at your own risk.*")

if __name__ == "__main__":
    demo.launch()
