import os
import sys
import time
import json
import logging
import signal
import atexit
import requests
import hashlib
import math
import cmath
import random
from collections import deque
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import ccxt
from rich.console import Console
from rich.table import Table

# Load environment variables
load_dotenv()

# ==============================
# 📝 Logging Setup
# ==============================
BASE_DIR = Path(os.getenv("BOT_DATA_DIR", Path(__file__).resolve().parent))
BASE_DIR.mkdir(parents=True, exist_ok=True)
log_file = BASE_DIR / "ena_hedge.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ==============================
# 🎯 API Credentials (from environment)
# ==============================
API_KEY = os.getenv('GATE_API_KEY', '')
API_SECRET = os.getenv('GATE_API_SECRET', '')

if not API_KEY or not API_SECRET:
    print('FATAL: Set GATE_API_KEY and GATE_API_SECRET in .env')
    exit(1)

# Gate.io V4 API base
API_BASE = 'https://api.gateio.ws/api/v4'


# ✅ Initialize CCXT for Gate.io perpetual futures (swap) using cross margin
exchange = ccxt.gateio({
    'apiKey': API_KEY,
    'secret': API_SECRET,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'swap',
        'defaultSettle': 'usdt',
    }
})

console = Console()

# ==============================
# 🔲 Trading Configuration
# ==============================
# Runtime safety
PAPER_MODE = os.getenv("PAPER_MODE", "1") == "1"
ARM_LIVE = os.getenv("ARM_LIVE", "NO") == "YES"
PROFIT_ONLY_MODE = os.getenv("PROFIT_ONLY_MODE", "1") == "1"

# LLM Configuration
USE_OLLAMA = os.getenv("USE_OLLAMA", "1") == "1"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")

# LLM self-testing
USE_LLM_THINKER = os.getenv("USE_LLM_THINKER", "1") == "1"
ENABLE_LLM_CRITIC = os.getenv("ENABLE_LLM_CRITIC", "1") == "1"
ENABLE_LLM_POLICY_UPDATE = os.getenv("ENABLE_LLM_POLICY_UPDATE", "1") == "1"
LLM_THINK_INTERVAL_SEC = int(os.getenv("LLM_THINK_INTERVAL_SEC", "20"))
LLM_OUTCOME_HORIZON_SEC = int(os.getenv("LLM_OUTCOME_HORIZON_SEC", "60"))
LLM_CRITIC_INTERVAL_SEC = int(os.getenv("LLM_CRITIC_INTERVAL_SEC", "90"))
LLM_MAX_ERROR_CONTEXT = int(os.getenv("LLM_MAX_ERROR_CONTEXT", "20"))
LLM_MIN_CONFIDENCE_TO_OPEN = float(os.getenv("LLM_MIN_CONFIDENCE_TO_OPEN", "0.65"))

# Trading gates
MAX_SYMBOLS = int(os.getenv("MAX_SYMBOLS", "8"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "6"))
MIN_VOLUME_USD = float(os.getenv("MIN_VOLUME_USD", "100000"))
MAX_NOTIONAL_USD = float(os.getenv("MAX_NOTIONAL_USD", "10.00"))
ORDER_NOTIONAL_USD = float(os.getenv("ORDER_NOTIONAL_USD", "1.00"))
TARGET_FILL_RATE_PER_SEC = float(os.getenv("TARGET_FILL_RATE_PER_SEC", "1.0"))
MIN_NET_EDGE_USD = float(os.getenv("MIN_NET_EDGE_USD", "0.025"))
MIN_SPREAD_BPS = float(os.getenv("MIN_SPREAD_BPS", "2"))
MAX_SPREAD_BPS = float(os.getenv("MAX_SPREAD_BPS", "18"))
MAX_VOLATILITY_BPS = float(os.getenv("MAX_VOLATILITY_BPS", "250"))
MAX_FUNDING_ABS_BPS = float(os.getenv("MAX_FUNDING_ABS_BPS", "30"))
MAX_DAILY_LOSS_USD = float(os.getenv("MAX_DAILY_LOSS_USD", "3.00"))
MAX_CONSECUTIVE_ERRORS = int(os.getenv("MAX_CONSECUTIVE_ERRORS", "5"))

# Cost model
MAKER_FEE_BPS = float(os.getenv("MAKER_FEE_BPS", "2.0"))
TAKER_FEE_BPS = float(os.getenv("TAKER_FEE_BPS", "7.5"))
SLIPPAGE_MULTIPLIER = float(os.getenv("SLIPPAGE_MULTIPLIER", "0.35"))

# Legacy configuration
LEVERAGE = 3
GROSS_THRESHOLD = 0.03
INITIAL_TRADE_SIZE = 1
PRICE_OFFSET = 0.0000369
LIMIT_RETRY_DELAY = 0.5
MAX_LIMIT_RETRIES = 9
API_RETRY_DELAY = 1
LOOP_DELAY = 0.5  # Check every 0.5 seconds for faster profit capture
DCA_SIZE = 2

# ==============================
# 💰 Profit Tracking
# ==============================
start_time = time.time()
total_profit_usd = 0.0
total_operations = 0
profit_log_file = BASE_DIR / "profit_log.jsonl"

# ==============================
# 🔧 Daemon Configuration
# ==============================
PID_FILE = BASE_DIR / "ena_hedge.pid"
DAEMON_MODE = os.getenv('DAEMON_MODE', '0') == '1'
MAX_RESTART_ATTEMPTS = int(os.getenv('MAX_RESTART_ATTEMPTS', '10'))
RESTART_DELAY_SEC = int(os.getenv('RESTART_DELAY_SEC', '5'))
HEALTH_CHECK_INTERVAL_SEC = int(os.getenv('HEALTH_CHECK_INTERVAL_SEC', '60'))

# Global shutdown flag
shutdown_requested = False

# ==============================
# 🧱 Market Making Configuration
# ==============================
MARKET_MAKE_MODE = os.getenv("MARKET_MAKE_MODE", "1") == "1"
MM_MAX_SYMBOLS = int(os.getenv("MM_MAX_SYMBOLS", "6"))
MM_ORDER_NOTIONAL_USD = float(os.getenv("MM_ORDER_NOTIONAL_USD", "1.00"))
MM_REFRESH_SEC = float(os.getenv("MM_REFRESH_SEC", "0.5"))
MM_MIN_SPREAD_BPS = float(os.getenv("MM_MIN_SPREAD_BPS", "1"))
MM_MAX_SPREAD_BPS = float(os.getenv("MM_MAX_SPREAD_BPS", "20"))
MM_QUOTE_EDGE_BPS = float(os.getenv("MM_QUOTE_EDGE_BPS", "1.0"))
MM_MAX_POSITION_CONTRACTS = float(os.getenv("MM_MAX_POSITION_CONTRACTS", "10"))
MM_INVENTORY_SKEW_BPS = float(os.getenv("MM_INVENTORY_SKEW_BPS", "8"))
MM_CANCEL_REPLACE_SEC = float(os.getenv("MM_CANCEL_REPLACE_SEC", "5"))
MM_MAX_OPEN_ORDERS_PER_SYMBOL = int(os.getenv("MM_MAX_OPEN_ORDERS_PER_SYMBOL", "2"))
MM_STOP_LOSS_USD = float(os.getenv("MM_STOP_LOSS_USD", "2.00"))
MM_TAKE_PROFIT_USD = float(os.getenv("MM_TAKE_PROFIT_USD", "0.05"))
MM_REQUIRE_POST_ONLY = os.getenv("MM_REQUIRE_POST_ONLY", "0") == "1"
MM_ALLOW_SHORT = os.getenv("MM_ALLOW_SHORT", "1") == "1"
MM_ALLOW_LONG = os.getenv("MM_ALLOW_LONG", "1") == "1"
MM_MAX_SYMBOLS = int(os.getenv("MM_MAX_SYMBOLS", "20"))

# ==============================
# � Genetic Algorithm Edge Discovery
# ==============================
USE_GENETIC_ALGORITHM = os.getenv("USE_GENETIC_ALGORITHM", "0") == "1"
GA_POPULATION_SIZE = int(os.getenv("GA_POPULATION_SIZE", "20"))
GA_GENERATIONS = int(os.getenv("GA_GENERATIONS", "50"))
GA_MUTATION_RATE = float(os.getenv("GA_MUTATION_RATE", "0.15"))
GA_CROSSOVER_RATE = float(os.getenv("GA_CROSSOVER_RATE", "0.7"))
GA_ELITISM_COUNT = int(os.getenv("GA_ELITISM_COUNT", "2"))
GA_FITNESS_WINDOW = int(os.getenv("GA_FITNESS_WINDOW", "100"))
GA_GENOME_FILE = BASE_DIR / "ga_genome.json"

# ==============================
# �� Stoikov + Ricci Market Geometry
# ==============================
USE_STOIKOV_QUOTES = os.getenv("USE_STOIKOV_QUOTES", "1") == "1"
USE_RICCI_CURVATURE = os.getenv("USE_RICCI_CURVATURE", "1") == "1"
# Avellaneda–Stoikov parameters
STOIKOV_GAMMA = float(os.getenv("STOIKOV_GAMMA", "0.12"))          # risk aversion
STOIKOV_KAPPA = float(os.getenv("STOIKOV_KAPPA", "1.5"))          # order arrival liquidity slope
STOIKOV_HORIZON_SEC = float(os.getenv("STOIKOV_HORIZON_SEC", "60"))
STOIKOV_MIN_HALF_SPREAD_BPS = float(os.getenv("STOIKOV_MIN_HALF_SPREAD_BPS", "2.5"))
STOIKOV_MAX_HALF_SPREAD_BPS = float(os.getenv("STOIKOV_MAX_HALF_SPREAD_BPS", "35"))
# Volatility estimator
VOL_LOOKBACK_CANDLES = int(os.getenv("VOL_LOOKBACK_CANDLES", "20"))
VOL_TIMEFRAME = os.getenv("VOL_TIMEFRAME", "1m")
# Ricci-style curvature parameters
RICCI_DEPTH_LEVELS = int(os.getenv("RICCI_DEPTH_LEVELS", "10"))
RICCI_STRESS_MULTIPLIER = float(os.getenv("RICCI_STRESS_MULTIPLIER", "1.25"))
RICCI_MIN_STRESS = float(os.getenv("RICCI_MIN_STRESS", "0.0"))
RICCI_MAX_STRESS = float(os.getenv("RICCI_MAX_STRESS", "3.0"))
# Quote safety
MM_MIN_QUOTE_DISTANCE_BPS = float(os.getenv("MM_MIN_QUOTE_DISTANCE_BPS", "1.0"))

# ==============================
# ζ Zeta Zero Source
# ==============================
USE_DYNAMIC_ZETA_ZEROS = os.getenv("USE_DYNAMIC_ZETA_ZEROS", "1") == "1"
ZETA_ZERO_COUNT = int(os.getenv("ZETA_ZERO_COUNT", "32"))
ZETA_ZERO_CACHE_FILE = BASE_DIR / "zeta_zero_ordinates.json"
FALLBACK_ZETA_ZERO_ORDINATES = [
    14.134725141,
    21.022039639,
    25.010857580,
    30.424876126,
    32.935061588,
    37.586178159,
    40.918719012,
    43.327073281,
    48.005150881,
    49.773832478,
]

# ==============================
# ζ Riemann Zeta Critical-Line Signal
# ==============================
USE_ZETA_ZERO_FILTER = os.getenv("USE_ZETA_ZERO_FILTER", "1") == "1"
ZETA_LOOKBACK_TICKS = int(os.getenv("ZETA_LOOKBACK_TICKS", "128"))
ZETA_RESONANCE_MULTIPLIER = float(os.getenv("ZETA_RESONANCE_MULTIPLIER", "0.35"))
ZETA_STRESS_THRESHOLD = float(os.getenv("ZETA_STRESS_THRESHOLD", "0.62"))
ZETA_MAX_STRESS = float(os.getenv("ZETA_MAX_STRESS", "2.0"))
# Runtime price memory
PRICE_TAPE = {}

# ==============================
# 🔧 Signal Handlers & Daemon Management
# ==============================
def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_requested
    logger.info(f"[DAEMON] Received signal {signum}, initiating graceful shutdown...")
    shutdown_requested = True

def write_pid_file():
    """Write current process PID to file"""
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"[DAEMON] PID file written: {PID_FILE} (PID: {os.getpid()})")
    except Exception as e:
        logger.error(f"[DAEMON] Failed to write PID file: {e}")

def remove_pid_file():
    """Remove PID file on shutdown"""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
            logger.info(f"[DAEMON] PID file removed: {PID_FILE}")
    except Exception as e:
        logger.error(f"[DAEMON] Failed to remove PID file: {e}")

def check_existing_daemon():
    """Check if daemon is already running"""
    if not PID_FILE.exists():
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process is running
        try:
            os.kill(pid, 0)  # Signal 0 checks if process exists
            logger.warning(f"[DAEMON] Daemon already running with PID {pid}")
            return True
        except OSError:
            # Process not running, stale PID file
            logger.info(f"[DAEMON] Stale PID file found (PID {pid} not running), removing...")
            PID_FILE.unlink()
            return False
    except Exception as e:
        logger.error(f"[DAEMON] Error checking existing daemon: {e}")
        return False

def health_check():
    """Perform health check and log status"""
    try:
        # Check if we can connect to exchange
        ticker = exchange.fetch_ticker('BTC/USDT:USDT')
        logger.info(f"[HEALTH] Exchange connection OK | BTC price: ${ticker['last']}")
        
        # Log profit stats
        elapsed_seconds = time.time() - start_time
        profit_per_second = total_profit_usd / elapsed_seconds if elapsed_seconds > 0 else 0
        cents_per_second = profit_per_second * 100
        logger.info(f"[HEALTH] Total Profit: ${total_profit_usd:.4f} | Rate: {cents_per_second:.2f}¢/sec | Ops: {total_operations}")
        
        return True
    except Exception as e:
        logger.error(f"[HEALTH] Health check failed: {e}")
        return False

def generate_zeta_zero_ordinates(count=32):
    """
    Deterministically generates the first N imaginary ordinates of
    the non-trivial Riemann zeta zeros on the critical line.
    Uses mpmath when available.
    Does NOT ask the LLM to invent constants.
    """
    try:
        import mpmath as mp
        zeros = []
        for n in range(1, count + 1):
            z = mp.zetazero(n)
            zeros.append(float(mp.im(z)))
        return zeros
    except Exception as e:
        logger.warning(f"[ZETA] Could not generate zeros with mpmath: {e}")
        return FALLBACK_ZETA_ZERO_ORDINATES[:count]

def load_or_generate_zeta_zeros():
    """
    Loads cached zeta zero ordinates if available.
    Otherwise generates and caches them.
    """
    if not USE_DYNAMIC_ZETA_ZEROS:
        return FALLBACK_ZETA_ZERO_ORDINATES
    try:
        if ZETA_ZERO_CACHE_FILE.exists():
            with open(ZETA_ZERO_CACHE_FILE, "r") as f:
                data = json.load(f)
            zeros = data.get("zeros", [])
            if len(zeros) >= ZETA_ZERO_COUNT:
                logger.info(f"[ZETA] Loaded {len(zeros)} cached zeta zeros")
                return zeros[:ZETA_ZERO_COUNT]
    except Exception as e:
        logger.warning(f"[ZETA] Failed loading cached zeta zeros: {e}")
    zeros = generate_zeta_zero_ordinates(ZETA_ZERO_COUNT)
    try:
        payload = {
            "generated_at": datetime.now().isoformat(),
            "count": len(zeros),
            "source": "mpmath.zetazero",
            "zeros": zeros,
        }
        with open(ZETA_ZERO_CACHE_FILE, "w") as f:
            json.dump(payload, f, indent=2)
        logger.info(f"[ZETA] Generated and cached {len(zeros)} zeta zeros")
    except Exception as e:
        logger.warning(f"[ZETA] Failed saving zeta zero cache: {e}")
    return zeros

# Initialize zeta zeros
ZETA_ZERO_ORDINATES = load_or_generate_zeta_zeros()

# ==============================
# 🤖 Local Ollama Decision Engine
# ==============================
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1')
USE_OLLAMA = os.getenv('USE_OLLAMA', '1') == '1'

def query_ollama(prompt: str) -> str:
    """Query local Ollama API for decision"""
    if not USE_OLLAMA:
        return None
    
    try:
        response = requests.post(
            f'{OLLAMA_BASE_URL}/api/generate',
            json={
                'model': OLLAMA_MODEL,
                'prompt': prompt,
                'stream': False,
                'options': {
                    'temperature': 0.3,
                    'num_predict': 200
                }
            },
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get('response', '').strip()
        else:
            logger.error(f"[OLLAMA] API error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"[OLLAMA] Query error: {e}")
        return None

def ollama_trading_decision(pair, position_type, entry_price, current_price, unrealized_pnl, size, market_context):
    """
    Ask Ollama for trading decision on a position.
    Returns decision dict with action and reason.
    """
    if not USE_OLLAMA:
        return {'action': 'HOLD', 'reason': 'Ollama disabled', 'confidence': 0.5}
    
    prompt = f"""You are a trading decision engine. Analyze this position and recommend an action.

Position Details:
- Pair: {pair}
- Type: {position_type}
- Entry Price: {entry_price:.6f}
- Current Price: {current_price:.6f}
- Unrealized PnL: ${unrealized_pnl:.4f}
- Size: {size:.2f}
- Market Context: {market_context}

Available Actions:
1. CLOSE - Close position now (take profit or cut loss)
2. HOLD - Keep position open
3. REOPEN - Reopen position after closing (for hedging)

Respond in this exact JSON format:
{{"action": "CLOSE|HOLD|REOPEN", "confidence": 0.0-1.0, "reason": "short reason"}}

Consider:
- If unrealized profit is positive and strong momentum, recommend CLOSE
- If unrealized loss is growing, recommend CLOSE to stop bleeding
- If market is stable and profit is moderate, recommend HOLD
- If position closed and opportunity exists, recommend REOPEN"""

    response = query_ollama(prompt)
    
    if response:
        try:
            # Try to extract JSON from response
            import re
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                decision = json.loads(json_match.group())
                logger.info(f"[OLLAMA] {pair} {position_type}: {decision['action']} (conf: {decision.get('confidence', 0):.2f}) - {decision.get('reason', '')}")
                return decision
        except Exception as e:
            logger.warning(f"[OLLAMA] Failed to parse response: {e}")
    
    # Fallback
    return {'action': 'HOLD', 'reason': 'LLM decision unavailable', 'confidence': 0.3}

# ==============================
# 📊 Market Data & Indicators
# ==============================
def fetch_all_futures_contracts():
    """Fetch all available USDT futures contracts from Gate.io"""
    try:
        # Use fetch_markets to get all futures
        markets = exchange.fetch_markets()
        usdt_futures = []
        
        for market in markets:
            if market.get('type') == 'swap' and market.get('settle') == 'usdt':
                contract_size = market.get('contractSize', 1)
                symbol = market.get('symbol', '')
                
                usdt_futures.append({
                    'symbol': symbol,
                    'contract': market.get('contract', symbol),
                    'active': market.get('active', True),
                    'contract_size': contract_size,
                    'info': market.get('info', {})
                })
        
        logger.info(f"[MARKET] Found {len(usdt_futures)} USDT futures contracts")
        return usdt_futures
    except Exception as e:
        logger.error(f"[MARKET] Error fetching contracts: {e}")
        return []

def calculate_indicators(symbol, contract_size=1):
    """Calculate technical indicators for a symbol"""
    try:
        # Fetch ticker
        ticker = exchange.fetch_ticker(symbol, params={'type': 'swap'})
        
        # Fetch recent candles (1h timeframe)
        candles = exchange.fetch_ohlcv(symbol, timeframe='1h', limit=24, params={'type': 'swap'})
        
        if not candles or len(candles) < 5:
            return None
        
        # Calculate basic indicators
        closes = [c[4] for c in candles]
        volumes = [c[5] for c in candles]
        
        last_price = float(ticker['last'])
        volume_24h = float(ticker.get('quoteVolume', 0))
        change_24h = float(ticker.get('percentage', 0))
        
        # Calculate notional value (contract_size * price)
        notional_value = contract_size * last_price
        
        # Simple moving averages
        sma_5 = sum(closes[-5:]) / 5
        sma_24 = sum(closes[-24:]) / 24 if len(closes) >= 24 else sma_5
        
        # Price momentum
        momentum = (closes[-1] - closes[-5]) / closes[-5] if len(candles) >= 5 else 0
        
        # Volume trend
        avg_volume = sum(volumes[-5:]) / 5 if len(volumes) >= 5 else volumes[-1]
        volume_ratio = volumes[-1] / avg_volume if avg_volume > 0 else 1
        
        # Volatility (std dev of last 5 closes)
        if len(candles) >= 5:
            mean_price = sum(closes[-5:]) / 5
            variance = sum((p - mean_price) ** 2 for p in closes[-5:]) / 5
            volatility = variance ** 0.5
        else:
            volatility = 0
        
        return {
            'symbol': symbol,
            'last_price': last_price,
            'volume_24h': volume_24h,
            'change_24h': change_24h,
            'sma_5': sma_5,
            'sma_24': sma_24,
            'momentum': momentum,
            'volume_ratio': volume_ratio,
            'volatility': volatility,
            'trend': 'BULLISH' if last_price > sma_5 else 'BEARISH',
            'contract_size': contract_size,
            'notional_value': notional_value
        }
    except Exception as e:
        logger.warning(f"[INDICATORS] Error calculating for {symbol}: {e}")
        return None

def ollama_symbol_selection(indicators_list):
    """Ask Ollama to select best symbols to trade based on indicators"""
    if not USE_OLLAMA or not indicators_list:
        return [i['symbol'] for i in indicators_list[:MAX_SYMBOLS]]
    
    # Format indicators for prompt
    indicators_text = "\n".join([
        f"- {i['symbol']}: Price=${i['last_price']:.6f}, Vol=${i['volume_24h']:,.0f}, "
        f"Change={i['change_24h']:+.2f}%, Trend={i['trend']}, "
        f"Momentum={i['momentum']:+.3f}, VolRatio={i['volume_ratio']:.2f}"
        for i in indicators_list
    ])
    
    prompt = f"""You are a symbol selection engine for a hedging trading bot. Analyze these indicators and select the best {MAX_SYMBOLS} symbols to trade.

Available Symbols filtered by volume ${MIN_VOLUME_USD:,}+ and notional <= ${MAX_NOTIONAL_USD}:
{indicators_text}

Selection Criteria:
- Prefer symbols with strong momentum (positive or negative)
- Prefer symbols with high volume ratio (increasing activity)
- Prefer symbols with moderate volatility (good for hedging)
- Avoid symbols with extremely low price or zero volume
- Select a mix of bullish and bearish trends for hedging

Respond in this exact JSON format:
{{"selected_symbols": ["SYMBOL1", "SYMBOL2", ...], "reason": "brief explanation"}}"""

    response = query_ollama(prompt)
    
    if response:
        try:
            import re
            json_match = re.search(r'\{[^}]+\}', response)
            if json_match:
                decision = json.loads(json_match.group())
                selected = decision.get('selected_symbols', [])
                logger.info(f"[OLLAMA] Selected {len(selected)} symbols: {selected}")
                logger.info(f"[OLLAMA] Reason: {decision.get('reason', '')}")
                return selected[:MAX_SYMBOLS]
        except Exception as e:
            logger.warning(f"[OLLAMA] Failed to parse symbol selection: {e}")
    
    # Fallback: top by volume
    sorted_by_volume = sorted(indicators_list, key=lambda x: x['volume_24h'], reverse=True)
    return [i['symbol'] for i in sorted_by_volume[:MAX_SYMBOLS]]

def get_llm_selected_symbols():
    """Fetch market data, calculate indicators, and let LLM select symbols"""
    logger.info("=" * 60)
    logger.info("[SYMBOL SELECTION] Fetching market data...")
    
    # Fetch all contracts
    contracts = fetch_all_futures_contracts()
    
    # Calculate indicators for each (check up to 600 tickers)
    indicators = []
    for contract in contracts[:600]:
        symbol = contract['symbol']
        contract_size = contract.get('contract_size', 1)
        
        if not contract.get('active', True):
            continue
            
        ind = calculate_indicators(symbol, contract_size)
        if ind:
            # Filter by criteria: notional <= 1 cent and minimum volume
            if ind['notional_value'] <= MAX_NOTIONAL_USD and ind['volume_24h'] >= MIN_VOLUME_USD:
                indicators.append(ind)
                logger.info(f"[SYMBOL] {symbol}: Notional=${ind['notional_value']:.6f}, Price=${ind['last_price']:.6f}, Vol=${ind['volume_24h']:,.0f}")
    
    logger.info(f"[SYMBOL SELECTION] Found {len(indicators)} symbols with notional <= ${MAX_NOTIONAL_USD} out of {len(contracts)} checked")
    
    if not indicators:
        logger.warning("[SYMBOL SELECTION] No symbols match criteria, returning empty list")
        return []
    
    # Let Ollama select
    selected = ollama_symbol_selection(indicators)
    logger.info(f"[SYMBOL SELECTION] Final selection: {selected}")
    return selected

# Global variable for dynamic symbols
CURRENT_PAIRS = []

def log_profit_event(event_type, pair, side, profit_usd, details=""):
    """Log profit event to file and update totals."""
    global total_profit_usd, total_operations
    if event_type in ['CLOSE', 'PROFIT']:
        total_profit_usd += profit_usd
        total_operations += 1
    timestamp = datetime.now().isoformat()
    elapsed_seconds = time.time() - start_time
    profit_per_second = total_profit_usd / elapsed_seconds if elapsed_seconds > 0 else 0
    cents_per_second = profit_per_second * 100
    event = {
        'timestamp': timestamp,
        'event_type': event_type,
        'pair': pair,
        'side': side,
        'profit_usd': profit_usd,
        'total_profit_usd': total_profit_usd,
        'elapsed_seconds': elapsed_seconds,
        'profit_per_second': profit_per_second,
        'cents_per_second': cents_per_second,
        'details': details
    }
    with open(profit_log_file, 'a') as f:
        f.write(json.dumps(event) + '\n')
    logger.info(
        f"[PROFIT] {event_type} {pair} {side}: +${profit_usd:.4f} | "
        f"Total: ${total_profit_usd:.4f} | Rate: {cents_per_second:.2f}¢/sec"
    )
    return event

# ==============================
# 🔒 Safety: Paper/Live Order Gate
# ==============================
def live_orders_allowed():
    return ARM_LIVE and not PAPER_MODE

def safe_create_limit_order(symbol, side, amount, price, params=None):
    params = params or {}
    if not live_orders_allowed():
        logger.info(
            f"[PAPER_ORDER] {symbol} {side.upper()} amount={amount} price={price} params={params}"
        )
        console.print(
            f"[PAPER] Would place {side.upper()} {symbol} amount={amount} @ {price}",
            style="bold yellow"
        )
        return {
            "id": f"paper-{int(time.time() * 1000)}",
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "status": "paper"
        }
    return exchange.create_limit_order(
        symbol=symbol,
        side=side,
        amount=amount,
        price=price,
        params=params
    )

def safe_cancel_order(order_id, symbol):
    if not live_orders_allowed():
        logger.info(f"[PAPER_CANCEL] Would cancel {order_id} on {symbol}")
        return True
    return exchange.cancel_order(
        order_id,
        symbol,
        params={'marginMode': 'cross', 'type': 'swap'}
    )

def bps(a, b):
    if b == 0:
        return 0
    return ((a - b) / b) * 10000

def now_ms():
    return int(time.time() * 1000)

def round_price(symbol, price):
    try:
        return float(exchange.price_to_precision(symbol, price))
    except Exception:
        return float(price)

def round_amount(symbol, amount):
    try:
        return float(exchange.amount_to_precision(symbol, amount))
    except Exception:
        return float(amount)

def estimate_short_volatility(symbol):
    """
    Estimates short-horizon volatility from recent candles.
    Returns volatility as decimal price-return std dev.
    Example: 0.002 = 20 bps.
    """
    try:
        candles = exchange.fetch_ohlcv(
            symbol,
            timeframe=VOL_TIMEFRAME,
            limit=VOL_LOOKBACK_CANDLES,
            params={'type': 'swap'}
        )
        if not candles or len(candles) < 5:
            return 0.001
        closes = [float(c[4]) for c in candles if float(c[4]) > 0]
        if len(closes) < 5:
            return 0.001
        returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            if prev > 0:
                returns.append((curr - prev) / prev)
        if not returns:
            return 0.001
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / max(len(returns) - 1, 1)
        vol = variance ** 0.5
        return max(vol, 1e-6)
    except Exception as e:
        logger.warning(f"[VOL] Failed volatility estimate for {symbol}: {e}")
        return 0.001

def compute_book_ricci_curvature(orderbook, levels=10):
    """
    Ricci-style order-book curvature / stress proxy.
    This is not pure differential geometry Ricci curvature.
    It is a market-geometry approximation:
    - Smooth, balanced depth = positive / stable curvature.
    - Thin, jagged, one-sided depth = negative / stressed curvature.
    - Higher stress widens quotes and reduces aggressiveness.
    Returns:
        curvature: higher is healthier
        stress: higher means widen quotes
        details: diagnostics
    """
    try:
        bids = orderbook.get("bids", [])[:levels]
        asks = orderbook.get("asks", [])[:levels]
        if len(bids) < 3 or len(asks) < 3:
            return 0.0, 2.0, {"reason": "insufficient_depth"}
        bid_prices = [float(x[0]) for x in bids]
        ask_prices = [float(x[0]) for x in asks]
        bid_sizes = [float(x[1]) for x in bids]
        ask_sizes = [float(x[1]) for x in asks]
        best_bid = bid_prices[0]
        best_ask = ask_prices[0]
        mid = (best_bid + best_ask) / 2
        if mid <= 0:
            return 0.0, 2.0, {"reason": "bad_mid"}
        bid_depth = sum(bid_sizes)
        ask_depth = sum(ask_sizes)
        total_depth = max(bid_depth + ask_depth, 1e-9)
        imbalance = (bid_depth - ask_depth) / total_depth
        # Local liquidity slope: how quickly depth decays away from touch.
        bid_weighted_distance = 0.0
        ask_weighted_distance = 0.0
        for price, size in zip(bid_prices, bid_sizes):
            dist_bps = abs((mid - price) / mid) * 10000
            bid_weighted_distance += dist_bps * size
        for price, size in zip(ask_prices, ask_sizes):
            dist_bps = abs((price - mid) / mid) * 10000
            ask_weighted_distance += dist_bps * size
        bid_avg_distance = bid_weighted_distance / max(bid_depth, 1e-9)
        ask_avg_distance = ask_weighted_distance / max(ask_depth, 1e-9)
        # Jaggedness: uneven liquidity distribution across depth levels.
        def normalized_jaggedness(sizes):
            if not sizes or sum(sizes) <= 0:
                return 1.0
            total = sum(sizes)
            probs = [s / total for s in sizes]
            uniform = 1.0 / len(probs)
            return sum(abs(p - uniform) for p in probs)
        bid_jag = normalized_jaggedness(bid_sizes)
        ask_jag = normalized_jaggedness(ask_sizes)
        jaggedness = (bid_jag + ask_jag) / 2
        # Curvature proxy:
        # balanced depth and smooth distribution = healthier positive curvature.
        balance_score = 1.0 - min(abs(imbalance), 1.0)
        smooth_score = 1.0 - min(jaggedness, 1.0)
        # Compact depth near touch is good, but too compact with one-sided imbalance can be toxic.
        avg_distance = (bid_avg_distance + ask_avg_distance) / 2
        depth_compactness = 1.0 / (1.0 + avg_distance / 25.0)
        curvature = (
            0.45 * balance_score
            + 0.35 * smooth_score
            + 0.20 * depth_compactness
        )
        # Stress is inverse curvature plus toxicity from imbalance/jaggedness.
        stress = (
            (1.0 - curvature)
            + 0.75 * abs(imbalance)
            + 0.50 * jaggedness
        ) * RICCI_STRESS_MULTIPLIER
        stress = max(RICCI_MIN_STRESS, min(RICCI_MAX_STRESS, stress))
        details = {
            "bid_depth": bid_depth,
            "ask_depth": ask_depth,
            "imbalance": imbalance,
            "bid_avg_distance_bps": bid_avg_distance,
            "ask_avg_distance_bps": ask_avg_distance,
            "jaggedness": jaggedness,
            "balance_score": balance_score,
            "smooth_score": smooth_score,
            "depth_compactness": depth_compactness,
            "curvature": curvature,
            "stress": stress,
        }
        return curvature, stress, details
    except Exception as e:
        logger.warning(f"[RICCI] curvature calculation failed: {e}")
        return 0.0, 2.0, {"reason": str(e)}

def fetch_orderbook_features(symbol):
    """
    Returns normalized market-making features from top-of-book,
    now with Ricci-style curvature and short volatility.
    """
    ob = exchange.fetch_order_book(symbol, limit=max(20, RICCI_DEPTH_LEVELS), params={'type': 'swap'})
    if not ob.get("bids") or not ob.get("asks"):
        return None
    best_bid = float(ob["bids"][0][0])
    best_ask = float(ob["asks"][0][0])
    bid_size = float(ob["bids"][0][1])
    ask_size = float(ob["asks"][0][1])
    if best_bid <= 0 or best_ask <= 0 or best_ask <= best_bid:
        return None
    mid = (best_bid + best_ask) / 2
    spread_bps = bps(best_ask, best_bid)
    bid_depth = sum(float(x[1]) for x in ob["bids"][:10])
    ask_depth = sum(float(x[1]) for x in ob["asks"][:10])
    imbalance = (bid_depth - ask_depth) / max(bid_depth + ask_depth, 1e-9)
    vol = estimate_short_volatility(symbol)
    update_price_tape(symbol, mid)
    zeta_resonance, zeta_stress, zeta_details = compute_zeta_resonance(symbol)
    if USE_RICCI_CURVATURE:
        ricci_curvature, ricci_stress, ricci_details = compute_book_ricci_curvature(
            ob,
            levels=RICCI_DEPTH_LEVELS
        )
    else:
        ricci_curvature, ricci_stress, ricci_details = 1.0, 0.0, {}
    return {
        "symbol": symbol,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
        "spread_bps": spread_bps,
        "bid_size": bid_size,
        "ask_size": ask_size,
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "imbalance": imbalance,
        "volatility": vol,
        "ricci_curvature": ricci_curvature,
        "ricci_stress": ricci_stress,
        "ricci_details": ricci_details,
        "zeta_resonance": zeta_resonance,
        "zeta_stress": zeta_stress,
        "zeta_details": zeta_details,
        "orderbook": ob,
    }

def fetch_position_for_symbol(symbol):
    """
    Returns long/short contracts and unrealized PnL for one futures symbol.
    """
    long_size = 0.0
    short_size = 0.0
    long_pnl = 0.0
    short_pnl = 0.0
    try:
        positions = exchange.fetch_positions([symbol], params={'type': 'swap'})
    except Exception as e:
        logger.warning(f"[POSITION] Could not fetch {symbol}: {e}")
        return {
            "long_size": 0.0,
            "short_size": 0.0,
            "net": 0.0,
            "unrealized": 0.0,
        }
    for p in positions:
        side = p.get("side")
        contracts = float(p.get("contracts", 0) or 0)
        pnl = float(p.get("unrealizedPnl", 0) or 0)
        if side == "long":
            long_size += contracts
            long_pnl += pnl
        elif side == "short":
            short_size += contracts
            short_pnl += pnl
    return {
        "long_size": long_size,
        "short_size": short_size,
        "net": long_size - short_size,
        "unrealized": long_pnl + short_pnl,
    }

def cancel_symbol_orders(symbol):
    """
    Cancels existing open orders for this symbol before replacing quotes.
    """
    try:
        open_orders = exchange.fetch_open_orders(
            symbol,
            params={'marginMode': 'cross', 'type': 'swap'}
        )
        for order in open_orders:
            order_id = order.get("id")
            if not order_id:
                continue
            try:
                safe_cancel_order(order_id, symbol)
                logger.info(f"[MM_CANCEL] {symbol} cancelled order {order_id}")
                time.sleep(0.1)
            except Exception as e:
                logger.warning(f"[MM_CANCEL_FAIL] {symbol} {order_id}: {e}")
        return True
    except Exception as e:
        logger.warning(f"[MM_CANCEL] Could not cancel orders for {symbol}: {e}")
        return False

def calc_contract_amount(symbol, mid_price, contract_size=1):
    """
    Converts desired USD notional into futures contract amount.
    """
    if mid_price <= 0:
        return 0
    raw_amount = MM_ORDER_NOTIONAL_USD / max(mid_price * contract_size, 1e-12)
    return max(round_amount(symbol, raw_amount), 1.0)

def should_quote_symbol(features, position):
    """
    Deterministic market-making risk gate.
    """
    spread = features["spread_bps"]
    if spread < MM_MIN_SPREAD_BPS:
        return False, f"spread too tight {spread:.2f}bps"
    if spread > MM_MAX_SPREAD_BPS:
        return False, f"spread too wide {spread:.2f}bps"
    if abs(position["net"]) >= MM_MAX_POSITION_CONTRACTS:
        return False, f"inventory limit reached net={position['net']}"
    if position["unrealized"] <= -abs(MM_STOP_LOSS_USD):
        return False, f"stop loss hit unrealized={position['unrealized']:.4f}"
    return True, "ok"

def build_market_maker_quotes(symbol, features, position):
    """
    Builds maker quotes.
    If USE_STOIKOV_QUOTES=1:
        Uses Avellaneda–Stoikov style reservation price and optimal spread.
    Reservation price:
        r = mid - q * gamma * sigma^2 * T
    Approximate optimal half-spread:
        half_spread = gamma * sigma^2 * T / 2 + (1 / gamma) * ln(1 + gamma / kappa)
    Then Ricci stress widens the half-spread when book geometry is unstable.
    """
    mid = features["mid"]
    best_bid = features["best_bid"]
    best_ask = features["best_ask"]
    net_inventory = position["net"]
    inventory_ratio = net_inventory / max(MM_MAX_POSITION_CONTRACTS, 1)
    ricci_stress = features.get("ricci_stress", 0.0)
    ricci_curvature = features.get("ricci_curvature", 1.0)
    zeta_resonance = features.get("zeta_resonance", 0.0)
    zeta_stress = features.get("zeta_stress", 0.0)
    geometry_stress = ricci_stress + zeta_stress
    sigma = max(features.get("volatility", 0.001), 1e-6)
    if USE_STOIKOV_QUOTES:
        gamma = max(STOIKOV_GAMMA, 1e-6)
        kappa = max(STOIKOV_KAPPA, 1e-6)
        horizon = max(STOIKOV_HORIZON_SEC, 1.0)
        # Convert horizon into rough candle-time scale.
        # For 1m volatility, 60 sec ≈ 1 unit.
        time_scale = horizon / 60.0
        inventory_penalty = net_inventory * gamma * (sigma ** 2) * time_scale
        reservation_price = mid * (1 - inventory_penalty)
        optimal_half_spread_decimal = (
            (gamma * (sigma ** 2) * time_scale / 2.0)
            + ((1.0 / gamma) * math.log(1.0 + gamma / kappa)) / 10000.0
        )
        half_spread_bps = optimal_half_spread_decimal * 10000
        # Ricci stress widens spread under bad book geometry.
        half_spread_bps *= (1.0 + geometry_stress)
        # Also widen if inventory is large.
        half_spread_bps *= (1.0 + 0.5 * abs(inventory_ratio))
        half_spread_bps = max(STOIKOV_MIN_HALF_SPREAD_BPS, half_spread_bps)
        half_spread_bps = min(STOIKOV_MAX_HALF_SPREAD_BPS, half_spread_bps)
        bid_price = reservation_price * (1 - half_spread_bps / 10000)
        ask_price = reservation_price * (1 + half_spread_bps / 10000)
    else:
        base_edge = MM_QUOTE_EDGE_BPS / 10000
        inventory_skew = (MM_INVENTORY_SKEW_BPS / 10000) * inventory_ratio
        bid_edge = base_edge + max(inventory_skew, 0)
        ask_edge = base_edge - min(inventory_skew, 0)
        # Ricci stress widens both sides.
        bid_edge *= (1.0 + ricci_stress)
        ask_edge *= (1.0 + ricci_stress)
        bid_price = mid * (1 - bid_edge)
        ask_price = mid * (1 + ask_edge)
    # Never cross the book. Stay maker-side.
    min_quote_distance = MM_MIN_QUOTE_DISTANCE_BPS / 10000
    bid_price = min(bid_price, best_bid * (1 - min_quote_distance))
    ask_price = max(ask_price, best_ask * (1 + min_quote_distance))
    bid_price = round_price(symbol, bid_price)
    ask_price = round_price(symbol, ask_price)
    logger.info(
        f"[QUOTE_MODEL] {symbol} "
        f"stoikov={USE_STOIKOV_QUOTES} "
        f"mid={mid:.10f} "
        f"sigma={sigma:.6f} "
        f"net={net_inventory:.4f} "
        f"ricci_curvature={ricci_curvature:.4f} "
        f"ricci_stress={ricci_stress:.4f} "
        f"bid={bid_price} ask={ask_price}"
    )
    return bid_price, ask_price

def place_market_maker_quotes(symbol, features, position, contract_size=1):
    """
    Cancel/replace two-sided maker quotes with inventory controls.
    """
    allowed, reason = should_quote_symbol(features, position)
    if not allowed:
        logger.info(f"[MM_SKIP] {symbol}: {reason}")
        console.print(f"[{symbol}] MM skip: {reason}", style="yellow")
        return False
    amount = calc_contract_amount(symbol, features["mid"], contract_size)
    if amount <= 0:
        logger.info(f"[MM_SKIP] {symbol}: amount <= 0")
        return False
    bid_price, ask_price = build_market_maker_quotes(symbol, features, position)
    cancel_symbol_orders(symbol)
    params = {
        'marginMode': 'cross',
        'type': 'swap',
    }
    if MM_REQUIRE_POST_ONLY:
        params['postOnly'] = True
    placed = []
    if MM_ALLOW_LONG and position["net"] < MM_MAX_POSITION_CONTRACTS:
        bid_order = safe_create_limit_order(
            symbol=symbol,
            side="buy",
            amount=amount,
            price=bid_price,
            params=params
        )
        placed.append(("buy", bid_price, bid_order.get("id")))
    if MM_ALLOW_SHORT and position["net"] > -MM_MAX_POSITION_CONTRACTS:
        ask_order = safe_create_limit_order(
            symbol=symbol,
            side="sell",
            amount=amount,
            price=ask_price,
            params=params
        )
        placed.append(("sell", ask_price, ask_order.get("id")))
    for side, price, oid in placed:
        logger.info(
            f"[MM_QUOTE] {symbol} {side.upper()} amount={amount} price={price} "
            f"mid={features['mid']:.8f} spread={features['spread_bps']:.2f}bps "
            f"net={position['net']} id={oid}"
        )
    return True

def update_price_tape(symbol, mid_price):
    """
    Maintains rolling mid-price tape for zeta-line resonance detection.
    """
    if symbol not in PRICE_TAPE:
        PRICE_TAPE[symbol] = deque(maxlen=ZETA_LOOKBACK_TICKS)
    if mid_price and mid_price > 0:
        PRICE_TAPE[symbol].append(float(mid_price))

def compute_log_returns(prices):
    """
    Converts price tape into log returns.
    """
    if len(prices) < 8:
        return []
    returns = []
    for i in range(1, len(prices)):
        prev = prices[i - 1]
        curr = prices[i]
        if prev > 0 and curr > 0:
            returns.append(math.log(curr / prev))
    return returns

def zeta_critical_line_kernel(t, zeros=None):
    """
    Truncated critical-line zeta-zero oscillation kernel.
    Uses the imaginary ordinates of non-trivial zeta zeros:
        rho_n = 1/2 + i * gamma_n
    This is NOT computing ζ(s) directly.
    It uses the zero ordinates as harmonic probes against market return rhythm.
    """
    zeros = zeros or ZETA_ZERO_ORDINATES
    value = 0j
    for gamma in zeros:
        # Weight lower zeros more heavily.
        weight = 1.0 / math.sqrt(gamma)
        # Critical-line oscillation component.
        value += weight * cmath.exp(1j * gamma * t)
    return value

def compute_zeta_resonance(symbol):
    """
    Computes a normalized zeta-zero resonance score from recent log returns.
    Interpretation:
        low score  = market rhythm is not matching zeta-zero harmonics
        high score = clustered oscillation / unstable resonance
    Returns:
        resonance_score: 0..1+
        zeta_stress: 0..ZETA_MAX_STRESS
        details: diagnostics
    """
    if not USE_ZETA_ZERO_FILTER:
        return 0.0, 0.0, {"enabled": False}
    prices = list(PRICE_TAPE.get(symbol, []))
    returns = compute_log_returns(prices)
    if len(returns) < 16:
        return 0.0, 0.0, {
            "enabled": True,
            "reason": "insufficient_history",
            "samples": len(returns),
        }
    n = len(returns)
    # Normalize returns to avoid scale domination.
    mean_r = sum(returns) / n
    centered = [r - mean_r for r in returns]
    variance = sum(r * r for r in centered) / max(n - 1, 1)
    std = math.sqrt(max(variance, 1e-18))
    normalized = [r / std for r in centered]
    # Project market returns onto zeta-zero harmonic kernel.
    projection = 0j
    energy = 0.0
    for idx, r in enumerate(normalized):
        # t runs from 0..1 over the lookback window.
        t = idx / max(n - 1, 1)
        # Scale t so low zeta zeros complete visible phase cycles.
        phase_t = 2 * math.pi * t
        kernel = zeta_critical_line_kernel(phase_t)
        projection += r * kernel
        energy += abs(kernel) ** 2
    raw_resonance = abs(projection) / max(math.sqrt(energy) * n, 1e-9)
    # Squash into usable trading signal.
    resonance_score = max(0.0, min(1.5, raw_resonance))
    if resonance_score < ZETA_STRESS_THRESHOLD:
        zeta_stress = 0.0
    else:
        zeta_stress = (resonance_score - ZETA_STRESS_THRESHOLD) * ZETA_RESONANCE_MULTIPLIER
    zeta_stress = max(0.0, min(ZETA_MAX_STRESS, zeta_stress))
    details = {
        "enabled": True,
        "samples": n,
        "mean_return": mean_r,
        "return_std": std,
        "raw_resonance": raw_resonance,
        "resonance_score": resonance_score,
        "zeta_stress": zeta_stress,
        "threshold": ZETA_STRESS_THRESHOLD,
        "zeros_used": len(ZETA_ZERO_ORDINATES),
    }
    return resonance_score, zeta_stress, details

# ==============================
# 1) Utility: Wait for Order Fill
# ==============================
def wait_for_fill(symbol, side, expected_size, timeout=10):
    """
    Polls the exchange for up to timeout seconds to verify that the position has been filled.
    Returns True if the position is filled (contracts >= expected_size), False otherwise.
    """
    start = time.time()
    while time.time() - start < timeout:
        positions = exchange.fetch_positions([symbol], params={'type': 'swap'})
        pos = next((p for p in positions if p.get('side') == ('long' if side=="buy" else 'short')), None)
        if pos and float(pos.get('contracts', 0)) >= expected_size:
            return True
        time.sleep(1)
    return False

# ==============================
# 2) Open Position Function (using CCXT)
# ==============================
def open_position(symbol, side, size):
    """
    Opens a position on the given side (buy for LONG, sell for SHORT) using a CCXT limit order.
    Returns the approximate entry (limit) price used.
    """
    try:
        exchange.set_leverage(LEVERAGE, symbol, params={'type': 'swap'})
        ticker = exchange.fetch_ticker(symbol, params={'type': 'swap'})
        market_price = float(ticker['last'])
        if side == "buy":
            limit_price = market_price * (1 - PRICE_OFFSET)
        else:
            limit_price = market_price * (1 + PRICE_OFFSET)
        
        logger.info(f"[OPEN] {symbol} {side.upper()} {size} @ {limit_price:.6f} (MP={market_price:.6f})")
        console.print(f"📌 Opening {side.upper()} position of {size} @ ~{limit_price:.6f} (MP={market_price:.6f})", style="bold cyan")
        
        placed_order = None
        for attempt in range(1, MAX_LIMIT_RETRIES + 1):
            try:
                placed_order = safe_create_limit_order(
                    symbol=symbol,
                    side=side,
                    amount=size,
                    price=limit_price,
                    params={'marginMode': 'cross', 'type': 'swap'}
                )
                console.print(f"✅ [{attempt}/{MAX_LIMIT_RETRIES}] {side.upper()} order placed @ {limit_price:.6f}", style="bold green")
                logger.info(f"[ORDER] {symbol} {side.upper()} placed @ {limit_price:.6f} | ID: {placed_order.get('id', 'N/A')}")
                break
            except Exception as e:
                console.print(f"⚠️ Attempt {attempt}/{MAX_LIMIT_RETRIES} failed: {e}", style="bold yellow")
                logger.warning(f"[RETRY] {symbol} {side.upper()} attempt {attempt} failed: {e}")
                time.sleep(LIMIT_RETRY_DELAY)
                if side == "buy":
                    limit_price *= (1 - PRICE_OFFSET)
                else:
                    limit_price *= (1 + PRICE_OFFSET)
        if placed_order is None:
            console.print(f"🚨 Could not open {side.upper()} position after max retries.", style="bold red")
            logger.error(f"[FAIL] {symbol} {side.upper()} could not open after max retries")
            return None
        # Wait for the order to fill (optional)
        if wait_for_fill(symbol, side, size, timeout=10):
            console.print(f"✅ {side.upper()} order filled.", style="bold green")
            logger.info(f"[FILLED] {symbol} {side.upper()} order filled")
            log_profit_event('OPEN', symbol, side, 0, f"Entry: {limit_price:.6f}, Size: {size}")
        else:
            console.print(f"⚠️ {side.upper()} order not fully filled within timeout.", style="bold yellow")
            logger.warning(f"[TIMEOUT] {symbol} {side.upper()} order fill timeout")
        return limit_price
    except Exception as e:
        console.print(f"⚠️ open_position error: {e}", style="bold red")
        logger.error(f"[ERROR] open_position {symbol} {side}: {e}")
        return None

def cancel_pending_reduce_orders(symbol):
    """Cancel ALL pending orders for a symbol, not just reduce-only"""
    try:
        open_orders = exchange.fetch_open_orders(symbol, params={'marginMode': 'cross', 'type': 'swap'})
        logger.info(f"[CANCEL] Found {len(open_orders)} pending orders for {symbol}")
        
        for order in open_orders:
            try:
                exchange.cancel_order(order['id'], symbol, params={'marginMode': 'cross', 'type': 'swap'})
                logger.info(f"[CANCEL] Cancelled order {order['id']} for {symbol}")
                console.print(f"Cancelled pending order {order['id']}", style="bold magenta")
                time.sleep(0.2)  # Small delay between cancels
            except Exception as e:
                logger.warning(f"[CANCEL] Failed to cancel order {order['id']}: {e}")
        
        # Verify all orders cancelled
        remaining = exchange.fetch_open_orders(symbol, params={'marginMode': 'cross', 'type': 'swap'})
        if remaining:
            logger.warning(f"[CANCEL] {len(remaining)} orders still pending after cancellation attempt")
        
    except Exception as e:
        logger.error(f"[CANCEL] Error cancelling orders for {symbol}: {e}")
        console.print(f"⚠️ Error cancelling pending orders: {e}", style="bold red")

# ==============================
# 3) Close Position at Target Function
# ==============================
def close_position_at_target(symbol, side, target_price, size):
    """
    Closes an existing position on the specified side using a limit order at the target price.
    For LONG positions (side 'buy'), we send a SELL order.
    For SHORT positions (side 'sell'), we send a BUY order.
    Returns True if successful, False otherwise.
    """
    try:
        if side == "buy":
            close_side = "sell"
        else:
            close_side = "buy"
        
        # Before attempting a new close order, cancel any pending reduce-only orders.
        cancel_pending_reduce_orders(symbol)
        
        console.print(f"📌 Attempting to close {side.upper()} position of size {size} @ target ~{target_price:.6f}", style="bold cyan")
        close_order = None
        # Use exponential backoff for retry attempts
        delay = LIMIT_RETRY_DELAY
        for attempt in range(1, MAX_LIMIT_RETRIES + 1):
            try:
                close_order = safe_create_limit_order(
                    symbol=symbol,
                    side=close_side,
                    amount=size,
                    price=target_price,
                    params={'marginMode': 'cross', 'reduceOnly': True, 'type': 'swap'}
                )
                console.print(f"✅ [{attempt}/{MAX_LIMIT_RETRIES}] Close order placed @ {target_price:.6f}", style="bold green")
                break  # order placed successfully
            except Exception as e:
                console.print(f"⚠️ Close attempt {attempt}/{MAX_LIMIT_RETRIES} failed: {e}", style="bold yellow")
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                # Optionally try cancelling pending orders again
                cancel_pending_reduce_orders(symbol)
        if close_order is None:
            console.print(f"🚨 Could not close {side.upper()} position after max retries.", style="bold red")
            return False
        return True
    except Exception as e:
        console.print(f"⚠️ close_position_at_target error: {e}", style="bold red")
        return False# ==============================
# 4) Profit Check & Closure Function
# ==============================
def check_profit_and_close():
    """
    Checks each open position's unrealized profit for CURRENT_PAIRS.
    Legacy helper. Main profit_only_close_loop() already scans all account positions.
    """
    active_pairs = CURRENT_PAIRS or []
    closed_positions = {pair: {'long': False, 'short': False} for pair in active_pairs}
    base_profit_per_contract = 0.01
    fee_cost_per_contract = 0.002
    for pair in active_pairs:
        try:
            positions = exchange.fetch_positions([pair], params={'type': 'swap'})
            
            # Process LONG positions
            long_pos = next((p for p in positions if p.get('side') == 'long'), None)
            if long_pos:
                size = float(long_pos.get('contracts', 0))
                entry_price = float(long_pos.get('entryPrice', 0))
                unrealized = float(long_pos.get('unrealizedPnl', 0))
                if size > 0:
                    effective_threshold = (base_profit_per_contract + fee_cost_per_contract) * size
                    target_exit = entry_price + (effective_threshold / size)
                    console.print(f"[{pair} LONG] Entry: {entry_price:.6f}, Size: {size:.6f}, Unrealized PnL: ${unrealized:.6f}, Effective TP: ${effective_threshold:.6f}, Target Exit: {target_exit:.6f}", style="bold blue")
                    if unrealized >= effective_threshold:
                        console.print(f"✅ [{pair}] LONG profit threshold reached (Unrealized: ${unrealized:.6f} >= ${effective_threshold:.6f})", style="bold green")
                        if close_position_at_target(pair, "buy", target_exit, size):
                            closed_positions[pair]['long'] = True

            # Process SHORT positions
            short_pos = next((p for p in positions if p.get('side') == 'short'), None)
            if short_pos:
                size = float(short_pos.get('contracts', 0))
                entry_price = float(short_pos.get('entryPrice', 0))
                unrealized = float(short_pos.get('unrealizedPnl', 0))
                if size > 0:
                    effective_threshold = (base_profit_per_contract + fee_cost_per_contract) * size
                    target_exit = entry_price - (effective_threshold / size)
                    console.print(f"[{pair} SHORT] Entry: {entry_price:.6f}, Size: {size:.6f}, Unrealized PnL: ${unrealized:.6f}, Effective TP: ${effective_threshold:.6f}, Target Exit: {target_exit:.6f}", style="bold blue")
                    if unrealized >= effective_threshold:
                        console.print(f"✅ [{pair}] SHORT profit threshold reached (Unrealized: ${unrealized:.6f} >= ${effective_threshold:.6f})", style="bold green")
                        if close_position_at_target(pair, "sell", target_exit, size):
                            closed_positions[pair]['short'] = True
        except Exception as e:
            console.print(f"⚠️ Error checking {pair}: {e}", style="bold red")
    
    return closed_positions

# ==============================
# 5) Profit-Only Close Loop (No New Opens)
# ==============================
def profit_only_close_loop():
    """
    Only closes positions when profit threshold is reached.
    Does NOT open new positions or DCA.
    Cancels all orders on startup.
    Uses LLM-selected symbols.
    """
    global CURRENT_PAIRS
    
    console.print("=" * 60, style="bold yellow")
    console.print("PROFIT-ONLY CLOSE MODE", style="bold yellow")
    console.print("Closing profitable positions only. No new opens.", style="bold yellow")
    console.print("=" * 60, style="bold yellow")
    
    # Initialize symbols with LLM selection
    CURRENT_PAIRS = get_llm_selected_symbols()
    if not CURRENT_PAIRS:
        logger.warning("No symbols selected. Continuing with account-wide position scan only.")
        CURRENT_PAIRS = []
    
    # Cancel all orders on startup
    console.print("Cancelling all orders...", style="bold cyan")
    for pair in CURRENT_PAIRS:
        try:
            cancel_pending_reduce_orders(pair)
            console.print(f"[{pair}] Orders cancelled", style="bold green")
        except Exception as e:
            console.print(f"[{pair}] Error cancelling orders: {e}", style="bold red")
    
    last_health_check = time.time()
    
    while not shutdown_requested:
        try:
            console.print("-" * 60, style="bold blue")
            console.print(f"Checking positions at {datetime.now().strftime('%H:%M:%S')}", style="bold blue")
            
            # Periodic health check
            if time.time() - last_health_check > HEALTH_CHECK_INTERVAL_SEC:
                health_check()
                last_health_check = time.time()
            
            # Show profit rate
            elapsed = time.time() - start_time
            profit_rate = total_profit_usd / elapsed if elapsed > 0 else 0
            cents_per_sec = profit_rate * 100
            console.print(f"💰 Total Profit: ${total_profit_usd:.4f} | Rate: {cents_per_sec:.2f}¢/sec | Ops: {total_operations}", style="bold green")
            
            # Fetch ALL open positions from account (not just selected symbols)
            try:
                all_positions = exchange.fetch_positions(params={'type': 'swap'})
                open_positions = [p for p in all_positions if float(p.get('contracts', 0)) != 0]
                
                logger.info(f"[POSITIONS] Found {len(open_positions)} open positions in account")
                
                if not open_positions:
                    console.print("No open positions in account", style="dim")
                else:
                    for pos in open_positions:
                        symbol = pos.get('symbol', 'UNKNOWN')
                        side = pos.get('side', 'unknown')
                        size = float(pos.get('contracts', 0))
                        entry_price = float(pos.get('entryPrice', 0))
                        unrealized = float(pos.get('unrealizedPnl', 0))
                        
                        console.print(f"[{symbol}] {side.upper()}: Size={size:.2f}, Entry=${entry_price:.6f}, Unrealized=${unrealized:.4f}", style="bold blue")
                        
                        # Check if profitable and should close
                        base_profit = 0.01
                        fee_cost = 0.002
                        effective_threshold = (base_profit + fee_cost) * size
                        
                        if unrealized >= effective_threshold:
                            console.print(f"[{symbol}] ✅ Profit reached! Closing {side.upper()}...", style="bold green")
                            
                            # Calculate target exit
                            if side == 'long':
                                target_exit = entry_price + (effective_threshold / size)
                                close_side = "buy"
                            else:
                                target_exit = entry_price - (effective_threshold / size)
                                close_side = "sell"
                            
                            if PAPER_MODE:
                                log_profit_event('PAPER_CLOSE', symbol, side, unrealized, "paper close only")
                            else:
                                if close_position_at_target(symbol, close_side, target_exit, size):
                                    log_profit_event('CLOSE', symbol, side, unrealized, f"Entry: {entry_price:.6f}, Exit: {target_exit:.6f}")
            
            except Exception as e:
                logger.error(f"[POSITIONS] Error fetching positions: {e}")
                console.print(f"⚠️ Error fetching positions: {e}", style="bold red")
            
            time.sleep(LOOP_DELAY)
            
        except KeyboardInterrupt:
            logger.info("[DAEMON] KeyboardInterrupt received")
            break
        except Exception as e:
            logger.error(f"[DAEMON] Loop error: {e}")
            console.print(f"⚠️ Loop error: {e}", style="bold red")
            if not shutdown_requested:
                time.sleep(API_RETRY_DELAY)
    
    logger.info("[DAEMON] Profit-only close loop stopped")

def market_making_loop():
    """
    Market-making mode:
    - Selects symbols using indicators / Ollama selector.
    - Pulls live order books.
    - Places post-only bid/ask quotes.
    - Skews quotes based on current inventory.
    - Cancels/replaces quotes every MM_REFRESH_SEC.
    - Paper mode by default.
    """
    global CURRENT_PAIRS
    console.print("=" * 70, style="bold cyan")
    console.print("GATE FUTURES MARKET MAKER MODE", style="bold cyan")
    console.print("Two-sided maker quoting with inventory skew + deterministic risk gates.", style="bold cyan")
    console.print(f"Paper Mode: {PAPER_MODE} | ARM Live: {ARM_LIVE}", style="bold yellow")
    console.print("=" * 70, style="bold cyan")
    try:
        exchange.load_markets()
    except Exception as e:
        logger.warning(f"[MM] load_markets failed: {e}")
    CURRENT_PAIRS = get_llm_selected_symbols()
    if not CURRENT_PAIRS:
        logger.warning("[MM] No LLM-selected symbols. Falling back to high-volume micro futures scan.")
        contracts = fetch_all_futures_contracts()
        candidates = []
        for c in contracts[:600]:
            symbol = c.get("symbol")
            contract_size = c.get("contract_size", 1)
            if not symbol or not c.get("active", True):
                continue
            ind = calculate_indicators(symbol, contract_size)
            if not ind:
                continue
            if ind["volume_24h"] >= MIN_VOLUME_USD:
                candidates.append(ind)
        candidates = sorted(candidates, key=lambda x: x["volume_24h"], reverse=True)
        CURRENT_PAIRS = [x["symbol"] for x in candidates[:MM_MAX_SYMBOLS]]
    CURRENT_PAIRS = CURRENT_PAIRS[:MM_MAX_SYMBOLS]
    if not CURRENT_PAIRS:
        logger.error("[MM] No symbols available. Exiting market maker.")
        return
    logger.info(f"[MM] Selected symbols: {CURRENT_PAIRS}")
    console.print(f"Selected symbols: {CURRENT_PAIRS}", style="bold green")
    # Set leverage once.
    for symbol in CURRENT_PAIRS:
        try:
            exchange.set_leverage(LEVERAGE, symbol, params={'type': 'swap'})
            logger.info(f"[MM] Set leverage {LEVERAGE}x for {symbol}")
        except Exception as e:
            logger.warning(f"[MM] Could not set leverage for {symbol}: {e}")
    last_health_check = time.time()
    last_quote_at = {symbol: 0 for symbol in CURRENT_PAIRS}
    while not shutdown_requested:
        try:
            if time.time() - last_health_check > HEALTH_CHECK_INTERVAL_SEC:
                health_check()
                last_health_check = time.time()
            table = Table(title="Gate Futures Market Maker")
            table.add_column("Symbol")
            table.add_column("Bid")
            table.add_column("Ask")
            table.add_column("Spread bps")
            table.add_column("Net Pos")
            table.add_column("Unrealized")
            table.add_column("Action")
            for symbol in CURRENT_PAIRS:
                try:
                    if time.time() - last_quote_at[symbol] < MM_REFRESH_SEC:
                        continue
                    features = fetch_orderbook_features(symbol)
                    if not features:
                        table.add_row(symbol, "-", "-", "-", "-", "-", "no book")
                        continue
                    position = fetch_position_for_symbol(symbol)
                    # Contract size from market metadata.
                    market = exchange.market(symbol)
                    contract_size = float(market.get("contractSize", 1) or 1)
                    # If position is nicely profitable, optionally place reduce-only closer.
                    if position["unrealized"] >= MM_TAKE_PROFIT_USD:
                        logger.info(
                            f"[MM_TP] {symbol} unrealized={position['unrealized']:.4f} "
                            f"take-profit threshold={MM_TAKE_PROFIT_USD:.4f}"
                        )
                    ok = place_market_maker_quotes(
                        symbol=symbol,
                        features=features,
                        position=position,
                        contract_size=contract_size
                    )
                    last_quote_at[symbol] = time.time()
                    action = "quoted" if ok else "skipped"
                    table.add_row(
                        symbol,
                        f"{features['best_bid']:.8f}",
                        f"{features['best_ask']:.8f}",
                        f"{features['spread_bps']:.2f}",
                        f"{position['net']:.2f}",
                        f"${position['unrealized']:.4f}",
                        action
                    )
                except Exception as e:
                    logger.error(f"[MM_SYMBOL_ERROR] {symbol}: {e}")
                    table.add_row(symbol, "-", "-", "-", "-", "-", f"error: {str(e)[:25]}")
            console.print(table)
            time.sleep(LOOP_DELAY)
        except KeyboardInterrupt:
            logger.info("[MM] KeyboardInterrupt received")
            break
        except Exception as e:
            logger.error(f"[MM_LOOP_ERROR] {e}")
            if not shutdown_requested:
                time.sleep(API_RETRY_DELAY)
    logger.info("[MM] Market-making loop stopped")

# ==============================
# 🚀 Daemon Wrapper with Auto-Restart
# ==============================
def daemon_wrapper():
    """Main daemon wrapper with auto-restart capability"""
    global shutdown_requested
    restart_attempts = 0
    
    logger.info("[DAEMON] Starting daemon wrapper...")
    logger.info(f"[DAEMON] Daemon Mode: {DAEMON_MODE}")
    logger.info(f"[DAEMON] Max Restart Attempts: {MAX_RESTART_ATTEMPTS}")
    logger.info(f"[DAEMON] Restart Delay: {RESTART_DELAY_SEC}s")
    logger.info(f"[DAEMON] Health Check Interval: {HEALTH_CHECK_INTERVAL_SEC}s")
    
    while not shutdown_requested and restart_attempts < MAX_RESTART_ATTEMPTS:
        try:
            logger.info(f"[DAEMON] Starting bot instance (attempt {restart_attempts + 1}/{MAX_RESTART_ATTEMPTS})")
            
            # Run the main trading loop
            profit_only_close_loop()
            
            # If we get here, the loop stopped normally
            if shutdown_requested:
                logger.info("[DAEMON] Shutdown requested, exiting...")
                break
            else:
                logger.warning(f"[DAEMON] Bot stopped unexpectedly, restarting in {RESTART_DELAY_SEC}s...")
                restart_attempts += 1
                time.sleep(RESTART_DELAY_SEC)
                
        except Exception as e:
            logger.error(f"[DAEMON] Fatal error in bot instance: {e}")
            restart_attempts += 1
            
            if restart_attempts < MAX_RESTART_ATTEMPTS and not shutdown_requested:
                logger.info(f"[DAEMON] Restarting in {RESTART_DELAY_SEC}s (attempt {restart_attempts}/{MAX_RESTART_ATTEMPTS})...")
                time.sleep(RESTART_DELAY_SEC)
            else:
                logger.error(f"[DAEMON] Max restart attempts reached or shutdown requested, giving up")
                break
    
    logger.info(f"[DAEMON] Daemon wrapper stopped. Total restarts: {restart_attempts}")

def main():
    """Main entry point with daemon support"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    atexit.register(remove_pid_file)
    if check_existing_daemon():
        logger.error("[DAEMON] Another instance is already running. Exiting.")
        sys.exit(1)
    write_pid_file()
    logger.info("=" * 60)
    logger.info("GATE BOT - STARTING")
    logger.info(f"Paper Mode: {PAPER_MODE}")
    logger.info(f"ARM Live: {ARM_LIVE}")
    logger.info(f"Market Make Mode: {MARKET_MAKE_MODE}")
    logger.info(f"Profit Only Mode: {PROFIT_ONLY_MODE}")
    logger.info("=" * 60)
    if MARKET_MAKE_MODE:
        market_making_loop()
    elif PROFIT_ONLY_MODE:
        profit_only_close_loop()
    else:
        logger.error("No mode enabled. Set MARKET_MAKE_MODE=1 or PROFIT_ONLY_MODE=1.")
    logger.info("[DAEMON] Bot shutdown complete")

if __name__ == '__main__':
    main()
