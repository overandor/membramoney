
from __future__ import annotations
from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    gate_api_key: str = os.getenv("GATE_API_KEY", "")
    gate_api_secret: str = os.getenv("GATE_API_SECRET", "")
    gate_base_url: str = os.getenv("GATE_BASE_URL", "https://fx-api.gateio.ws/api/v4").rstrip("/")
    gate_ws_url: str = os.getenv("GATE_WS_URL", "wss://fx-ws.gateio.ws/v4/ws/usdt")
    gate_settle: str = os.getenv("GATE_SETTLE", "usdt").lower()

    mode: str = os.getenv("MODE", "paper").lower()
    symbols_raw: str = os.getenv("SYMBOLS", "DOGE_USDT,XRP_USDT,TRX_USDT")
    db_path: str = os.getenv("DB_PATH", "gate_mm_beast.db")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_model: str = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-70b-instruct")
    openrouter_base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1/chat/completions")

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    groq_base_url: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions")

    risk_usd: float = float(os.getenv("RISK_USD", "15"))
    leverage: int = int(os.getenv("LEVERAGE", "2"))
    bar_interval: str = os.getenv("BAR_INTERVAL", "1m")
    bar_limit: int = int(os.getenv("BAR_LIMIT", "400"))
    loop_seconds: float = float(os.getenv("LOOP_SECONDS", "2"))
    entry_edge_bps: float = float(os.getenv("ENTRY_EDGE_BPS", "5"))
    take_atr_mult: float = float(os.getenv("TAKE_ATR_MULT", "1.0"))
    stop_atr_mult: float = float(os.getenv("STOP_ATR_MULT", "1.6"))

    enable_api: bool = os.getenv("ENABLE_API", "true").lower() == "true"
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8788"))

    request_timeout: int = int(os.getenv("REQUEST_TIMEOUT", "15"))

    # Live execution hardening knobs
    max_abs_position_per_symbol: int = int(os.getenv("MAX_ABS_POSITION_PER_SYMBOL", "100"))
    max_total_open_orders: int = int(os.getenv("MAX_TOTAL_OPEN_ORDERS", "30"))
    replace_threshold_ticks: int = int(os.getenv("REPLACE_THRESHOLD_TICKS", "1"))
    book_stale_seconds: float = float(os.getenv("BOOK_STALE_SECONDS", "3.0"))
    rest_book_refresh_seconds: float = float(os.getenv("REST_BOOK_REFRESH_SECONDS", "2.0"))
    startup_sync: bool = os.getenv("STARTUP_SYNC", "true").lower() == "true"
    cancel_all_on_start: bool = os.getenv("CANCEL_ALL_ON_START", "false").lower() == "true"
    live_enable_trading: bool = os.getenv("LIVE_ENABLE_TRADING", "false").lower() == "true"
    quote_tif: str = os.getenv("QUOTE_TIF", "gtc").lower()
    post_only_mode: bool = os.getenv("POST_ONLY_MODE", "false").lower() == "true"

    @property
    def symbols(self) -> list[str]:
        return [s.strip().upper() for s in self.symbols_raw.split(",") if s.strip()]
