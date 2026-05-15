#!/usr/bin/env python3
"""
GATE MICROCAP HEDGE ENGINE WITH LLM REASONING
================================================
Continuous LLM-powered decision assistant for Gate.io futures market making.

Features:
- Historical market feature builder
- LLM symbol selector with Groq
- Continuous LLM thinking loop
- Outcome testing loop
- LLM critic loop for policy updates
- Execution gate with LLM approval
- Dashboard with LLM insights
- Safety-first defaults (paper mode)

Usage:
  1. Copy .env.example -> .env and fill in API keys
  2. Set GROQ_API_KEY in .env
  3. Run: GATE_PAPER=1 USE_LLM_THINKER=1 ENABLE_LLM_CRITIC=1 python gate_microcap_hedge_engine_fixed.py
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dotenv import load_dotenv
import aiohttp
import logging

# Load environment variables
load_dotenv()

# ══════════════════════════════════════════════════════════════
# API Keys — from .env ONLY (NEVER HARDCODED)
# ══════════════════════════════════════════════════════════════
API_KEY = os.getenv('GATE_API_KEY', '')
API_SECRET = os.getenv('GATE_API_SECRET', '')
GROQ_API_KEY = os.getenv('GROQ_API_KEY', '')

if not API_KEY or not API_SECRET:
    print('FATAL: Set GATE_API_KEY and GATE_API_SECRET in .env')
    exit(1)

if not GROQ_API_KEY:
    print('WARNING: GROQ_API_KEY not set. LLM features will be disabled.')

# ══════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════
USE_LLM_THINKER = os.getenv('USE_LLM_THINKER', '0') == '1'
ENABLE_LLM_CRITIC = os.getenv('ENABLE_LLM_CRITIC', '0') == '1'
ENABLE_LLM_POLICY_UPDATE = os.getenv('ENABLE_LLM_POLICY_UPDATE', '0') == '1'
GROQ_MODEL = os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')
LLM_THINK_INTERVAL_SEC = int(os.getenv('LLM_THINK_INTERVAL_SEC', '20'))
LLM_OUTCOME_HORIZON_SEC = int(os.getenv('LLM_OUTCOME_HORIZON_SEC', '60'))
LLM_CRITIC_INTERVAL_SEC = int(os.getenv('LLM_CRITIC_INTERVAL_SEC', '90'))
LLM_MAX_ERROR_CONTEXT = int(os.getenv('LLM_MAX_ERROR_CONTEXT', '20'))
LLM_MIN_CONFIDENCE_TO_OPEN = float(os.getenv('LLM_MIN_CONFIDENCE_TO_OPEN', '0.65'))

# Safety defaults
GATE_PAPER = os.getenv('GATE_PAPER', '1') == '1'
ARM_LIVE = os.getenv('ARM_LIVE', 'NO') == 'YES'
LIVE_ONE_SHOT = os.getenv('LIVE_ONE_SHOT', '1') == '1'
ORDER_NOTIONAL_USD = float(os.getenv('ORDER_NOTIONAL_USD', '10'))
MAX_TOTAL_EXPOSURE_USD = float(os.getenv('MAX_TOTAL_EXPOSURE_USD', '100'))

# Risk parameters
MAX_NOTIONAL = 0.10  # only symbols where 1 contract < $0.10
DEFAULT_LEVERAGE = 3
MAX_EQUITY_PER_POS = 0.02
MAX_TOTAL_EXPOSURE = 0.30
FEE_RATE = 0.00075
MARGIN_MODE = 'cross'

# ══════════════════════════════════════════════════════════════
# Memory Files
# ══════════════════════════════════════════════════════════════
LLM_TRADE_MEMORY_FILE = 'llm_trade_memory.jsonl'
LLM_ERROR_MEMORY_FILE = 'llm_error_memory.jsonl'
LLM_POLICY_FILE = 'llm_policy.json'

# ══════════════════════════════════════════════════════════════
# Logging
# ══════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('GateMicrocapHedgeEngine')

# ══════════════════════════════════════════════════════════════
# Data Classes
# ══════════════════════════════════════════════════════════════
@dataclass
class MarketFeatures:
    """Historical market features for a symbol."""
    symbol: str
    last_price: float
    volume_24h_usd: float
    daily_change_pct: float
    volume_change_pct: float
    spread_bps: float
    volatility_pct: float
    momentum_4h_pct: float
    liquidity_score: float
    opportunity_score: float
    timestamp: str

@dataclass
class LLMAction:
    """LLM-recommended action for a symbol."""
    symbol: str
    action: str  # WATCH | OPEN | SKIP | HALT
    confidence: float
    reason: str
    timestamp: str

@dataclass
class LLMPolicy:
    """Learned policy from LLM critic."""
    version: int
    avoid_conditions: List[str]
    prefer_conditions: List[str]
    confidence_adjustments: Dict[str, float]
    notes: str
    min_confidence_to_open: float

@dataclass
class TradeDecision:
    """Trade decision for outcome testing."""
    symbol: str
    action: str
    confidence: float
    reason: str
    start_price: float
    start_spread_bps: float
    start_time: str
    thesis: str
    risk_notes: str

@dataclass
class LLMDecisionTest:
    """Registered LLM decision for continuous outcome testing."""
    decision_id: str
    created_at: float
    symbol: str
    features: dict
    action: str
    confidence: float
    reason: str
    thesis: str
    start_bid: float
    start_ask: float
    start_mid: float
    evaluated: bool = False

# ══════════════════════════════════════════════════════════════
# Gate.io Public Client
# ══════════════════════════════════════════════════════════════
class GatePublicClient:
    """Gate.io public API client for market data."""
    
    BASE_URL = 'https://api.gateio.ws/api/v4'
    
    def __init__(self):
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()
    
    async def get_tickers(self) -> List[Dict]:
        """Get all futures tickers."""
        async with self.session.get(f'{self.BASE_URL}/futures/usdt/contract_tickers') as resp:
            data = await resp.json()
            return data.get('data', [])
    
    async def get_candlesticks(self, contract: str, interval: str = '1h', limit: int = 100) -> List[List]:
        """Get candlestick data for a contract."""
        params = {
            'contract': contract,
            'interval': interval,
            'limit': limit,
            'from': int(time.time()) - (limit * 3600)  # last N hours
        }
        async with self.session.get(f'{self.BASE_URL}/futures/usdt/candlesticks', params=params) as resp:
            data = await resp.json()
            return data.get('data', [])
    
    async def get_order_book(self, contract: str, limit: int = 20) -> Dict:
        """Get order book for a contract."""
        params = {'contract': contract, 'limit': limit}
        async with self.session.get(f'{self.BASE_URL}/futures/usdt/order_book', params=params) as resp:
            data = await resp.json()
            return data.get('data', {})

# ══════════════════════════════════════════════════════════════
# Historical Market Feature Builder
# ══════════════════════════════════════════════════════════════
class MarketFeatureBuilder:
    """Builds historical market features for symbols."""
    
    def __init__(self, client: GatePublicClient):
        self.client = client
    
    async def build_features(self, symbol: str) -> Optional[MarketFeatures]:
        """Build market features for a symbol."""
        try:
            # Get ticker data
            tickers = await self.client.get_tickers()
            ticker_data = next((t for t in tickers if t.get('contract') == symbol), None)
            
            if not ticker_data:
                logger.warning(f"No ticker data for {symbol}")
                return None
            
            # Get candlestick data for momentum
            candles = await self.client.get_candlesticks(symbol, interval='1h', limit=4)
            
            # Get order book for spread
            order_book = await self.client.get_order_book(symbol)
            
            # Calculate features
            last_price = float(ticker_data.get('last_price', 0))
            volume_24h_usd = float(ticker_data.get('volume_24h', 0)) * last_price
            daily_change_pct = float(ticker_data.get('change_percentage', 0))
            
            # Volume change (24h vs previous 24h from candles)
            volume_change_pct = 0.0
            if len(candles) >= 24:
                recent_vol = sum(float(c[5]) for c in candles[-24:])
                prev_vol = sum(float(c[5]) for c in candles[-48:-24]) if len(candles) >= 48 else recent_vol
                volume_change_pct = ((recent_vol - prev_vol) / prev_vol * 100) if prev_vol > 0 else 0.0
            
            # Spread from order book
            asks = order_book.get('asks', [])
            bids = order_book.get('bids', [])
            spread_bps = 0.0
            if asks and bids:
                best_ask = float(asks[0][0]) if asks else 0
                best_bid = float(bids[0][0]) if bids else 0
                if best_ask > 0 and best_bid > 0:
                    spread_bps = ((best_ask - best_bid) / best_ask) * 10000
            
            # Volatility (std dev of returns)
            volatility_pct = 0.0
            if len(candles) >= 24:
                returns = []
                for i in range(1, len(candles)):
                    prev_close = float(candles[i-1][2])
                    curr_close = float(candles[i][2])
                    if prev_close > 0:
                        returns.append((curr_close - prev_close) / prev_close)
                if returns:
                    import statistics
                    volatility_pct = statistics.stdev(returns) * 100 if len(returns) > 1 else 0.0
            
            # 4h momentum
            momentum_4h_pct = 0.0
            if len(candles) >= 4:
                price_4h_ago = float(candles[-4][2])
                if price_4h_ago > 0:
                    momentum_4h_pct = ((last_price - price_4h_ago) / price_4h_ago) * 100
            
            # Liquidity score (volume / volatility)
            liquidity_score = min(100, (volume_24h_usd / 1000000) / (max(0.01, volatility_pct) / 100))
            
            # Opportunity score (momentum - spread - volatility)
            opportunity_score = max(0, momentum_4h_pct - (spread_bps / 100) - (volatility_pct / 10))
            
            return MarketFeatures(
                symbol=symbol,
                last_price=last_price,
                volume_24h_usd=volume_24h_usd,
                daily_change_pct=daily_change_pct,
                volume_change_pct=volume_change_pct,
                spread_bps=spread_bps,
                volatility_pct=volatility_pct,
                momentum_4h_pct=momentum_4h_pct,
                liquidity_score=liquidity_score,
                opportunity_score=opportunity_score,
                timestamp=datetime.now().isoformat()
            )
            
        except Exception as e:
            logger.error(f"Error building features for {symbol}: {e}")
            return None

# ══════════════════════════════════════════════════════════════
# LLM Symbol Selector
# ══════════════════════════════════════════════════════════════
class LLMSymbolSelector:
    """Uses LLM to select symbols and recommend actions."""
    
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.base_url = 'https://api.groq.com/openai/v1'
    
    async def select_symbols(
        self,
        features: List[MarketFeatures],
        policy: LLMPolicy,
        recent_errors: List[Dict]
    ) -> Dict:
        """Use LLM to select symbols and recommend actions."""
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY not set, returning empty selection")
            return self._default_selection(features)
        
        # Build prompt
        prompt = self._build_prompt(features, policy, recent_errors)
        
        try:
            async with aiohttp.ClientSession() as session:
                headers = {
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json'
                }
                
                payload = {
                    'model': self.model,
                    'messages': [
                        {
                            'role': 'system',
                            'content': 'You are a trading decision assistant. Return ONLY valid JSON with the specified structure.'
                        },
                        {
                            'role': 'user',
                            'content': prompt
                        }
                    ],
                    'temperature': 0.3,
                    'response_format': {'type': 'json_object'}
                }
                
                async with session.post(f'{self.base_url}/chat/completions', headers=headers, json=payload) as resp:
                    data = await resp.json()
                    
                    if 'choices' not in data or not data['choices']:
                        logger.error("Invalid LLM response")
                        return self._default_selection(features)
                    
                    content = data['choices'][0]['message']['content']
                    result = json.loads(content)
                    
                    # Validate structure
                    if not self._validate_result(result):
                        logger.warning("Invalid LLM result structure, using default")
                        return self._default_selection(features)
                    
                    return result
                    
        except Exception as e:
            logger.error(f"Error calling LLM: {e}")
            return self._default_selection(features)
    
    def _build_prompt(self, features: List[MarketFeatures], policy: LLMPolicy, recent_errors: List[Dict]) -> str:
        """Build prompt for LLM."""
        
        features_text = "\n".join([
            f"- {f.symbol}: price={f.last_price}, spread={f.spread_bps}bps, "
            f"volatility={f.volatility_pct:.2f}%, momentum={f.momentum_4h_pct:.2f}%, "
            f"liquidity={f.liquidity_score:.1f}, opportunity={f.opportunity_score:.2f}"
            for f in features
        ])
        
        policy_text = json.dumps(asdict(policy), indent=2)
        
        errors_text = "\n".join([
            f"- {e.get('symbol', 'N/A')}: {e.get('reason', 'N/A')}"
            for e in recent_errors[:5]
        ])
        
        return f"""
Analyze these market features and recommend actions:

MARKET FEATURES:
{features_text}

CURRENT POLICY:
{policy_text}

RECENT ERRORS:
{errors_text}

Return JSON with this exact structure:
{{
  "selected_symbols": ["SYMBOL_USDT"],
  "market_thesis": "short thesis",
  "actions": [
    {{
      "symbol": "SYMBOL_USDT",
      "action": "WATCH|OPEN|SKIP|HALT",
      "confidence": 0.0,
      "reason": "short reason"
    }}
  ],
  "risk_notes": "short risk note"
}}

Rules:
- Only select symbols with opportunity_score > 0.5
- OPEN only if confidence >= {policy.min_confidence_to_open}
- HALT if spread > 100bps or volatility > 10%
- WATCH if momentum > 2% but spread > 50bps
- SKIP if liquidity < 10 or opportunity < 0.3
- confidence must be between 0.0 and 1.0
"""
    
    def _validate_result(self, result: Dict) -> bool:
        """Validate LLM result structure."""
        required_keys = ['selected_symbols', 'market_thesis', 'actions', 'risk_notes']
        if not all(key in result for key in required_keys):
            return False
        
        if not isinstance(result['actions'], list):
            return False
        
        for action in result['actions']:
            if not all(key in action for key in ['symbol', 'action', 'confidence', 'reason']):
                return False
            
            if action['action'] not in ['WATCH', 'OPEN', 'SKIP', 'HALT']:
                return False
            
            if not 0.0 <= action['confidence'] <= 1.0:
                return False
        
        return True
    
    def _default_selection(self, features: List[MarketFeatures]) -> Dict:
        """Return default selection when LLM fails."""
        # Select top 3 by opportunity score
        sorted_features = sorted(features, key=lambda f: f.opportunity_score, reverse=True)[:3]
        
        actions = []
        for f in sorted_features:
            if f.opportunity_score > 0.5:
                action = 'OPEN' if f.spread_bps < 50 and f.volatility_pct < 5 else 'WATCH'
            else:
                action = 'SKIP'
            
            actions.append({
                'symbol': f.symbol,
                'action': action,
                'confidence': 0.5,
                'reason': f'Default selection based on opportunity score'
            })
        
        return {
            'selected_symbols': [f.symbol for f in sorted_features],
            'market_thesis': 'Default thesis (LLM unavailable)',
            'actions': actions,
            'risk_notes': 'Using default selection due to LLM unavailability'
        }

# ══════════════════════════════════════════════════════════════
# Hedge Engine with LLM Integration
# ══════════════════════════════════════════════════════════════
class GateMicrocapHedgeEngine:
    """Main hedge engine with LLM reasoning layer."""
    
    def __init__(self):
        self.client = GatePublicClient()
        self.feature_builder = MarketFeatureBuilder(self.client)
        
        # LLM components
        self.llm_selector = LLMSymbolSelector(GROQ_API_KEY, GROQ_MODEL) if USE_LLM_THINKER else None
        self.llm_policy = self._load_policy()
        self.llm_actions: Dict[str, LLMAction] = {}
        self.llm_thesis = ""
        self.llm_risk_notes = ""
        
        # Memory
        self.trade_decisions: List[TradeDecision] = []
        self.llm_tests: Dict[str, LLMDecisionTest] = {}
        self.recent_errors: List[Dict] = []
        
        # State
        self.global_halt = False
        self.last_critic_at = 0.0
        self.global_halt_reason = ""
        self.active_symbols: List[str] = []
        self.market_features: Dict[str, MarketFeatures] = {}
        
        # Stats
        self.open_tests = 0
        self.llm_calls = 0
    
    def _load_policy(self) -> LLMPolicy:
        """Load LLM policy from file."""
        try:
            if os.path.exists(LLM_POLICY_FILE):
                with open(LLM_POLICY_FILE, 'r') as f:
                    data = json.load(f)
                    return LLMPolicy(**data)
        except Exception as e:
            logger.warning(f"Error loading policy: {e}")
        
        # Default policy
        return LLMPolicy(
            version=1,
            avoid_conditions=[],
            prefer_conditions=[],
            confidence_adjustments={},
            notes="Default policy",
            min_confidence_to_open=LLM_MIN_CONFIDENCE_TO_OPEN
        )
    
    def _save_policy(self):
        """Save LLM policy to file."""
        try:
            with open(LLM_POLICY_FILE, 'w') as f:
                json.dump(asdict(self.llm_policy), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving policy: {e}")
    
    def _log_trade_memory(self, decision: TradeDecision, outcome: str, reason: str):
        """Log trade decision to memory."""
        try:
            entry = {
                **asdict(decision),
                'outcome': outcome,
                'outcome_reason': reason,
                'evaluated_at': datetime.now().isoformat()
            }
            
            with open(LLM_TRADE_MEMORY_FILE, 'a') as f:
                f.write(json.dumps(entry) + '\n')
                
        except Exception as e:
            logger.error(f"Error logging trade memory: {e}")
    
    def _log_error_memory(self, decision: TradeDecision, reason: str):
        """Log error to memory."""
        try:
            entry = {
                **asdict(decision),
                'error_reason': reason,
                'logged_at': datetime.now().isoformat()
            }
            
            with open(LLM_ERROR_MEMORY_FILE, 'a') as f:
                f.write(json.dumps(entry) + '\n')
                
            # Add to recent errors
            self.recent_errors.append(entry)
            if len(self.recent_errors) > LLM_MAX_ERROR_CONTEXT:
                self.recent_errors.pop(0)
                
        except Exception as e:
            logger.error(f"Error logging error memory: {e}")

    def register_llm_decision_test(self, symbol: str, action: dict, book: dict) -> None:
        """Register every LLM action as a test for later outcome evaluation."""
        feature = self.market_features.get(symbol)
        decision_id = f"{symbol}-{int(time.time() * 1000)}"
        test = LLMDecisionTest(
            decision_id=decision_id,
            created_at=time.time(),
            symbol=symbol,
            features=asdict(feature) if feature else {},
            action=str(action.get("action", "WATCH")).upper(),
            confidence=action.get("confidence", 0.0),
            reason=str(action.get("reason", ""))[:500],
            thesis=self.llm_thesis[:800],
            start_bid=book.get("bid", 0.0),
            start_ask=book.get("ask", 0.0),
            start_mid=book.get("mid", 0.0),
        )
        self.llm_tests[decision_id] = test
        entry = {
            "event": "llm_decision_registered",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "decision_id": decision_id,
            "symbol": symbol,
            "action": test.action,
            "confidence": test.confidence,
            "reason": test.reason,
            "features": test.features,
            "start_bid": test.start_bid,
            "start_ask": test.start_ask,
            "start_mid": test.start_mid,
        }
        try:
            with open(LLM_TRADE_MEMORY_FILE, 'a') as f:
                f.write(json.dumps(entry, separators=(',', ':')) + '\n')
        except Exception as e:
            logger.error(f"Error registering LLM decision: {e}")

    def append_jsonl(self, path: str, row: dict) -> None:
        try:
            with open(path, 'a') as f:
                f.write(json.dumps(row, separators=(',', ':')) + '\n')
        except Exception as e:
            logger.error(f"Error writing JSONL: {e}")

    def read_recent_jsonl(self, path: str, limit: int) -> List[dict]:
        if not os.path.exists(path):
            return []
        try:
            with open(path, 'r') as f:
                lines = f.readlines()
            rows = []
            for line in lines[-limit:]:
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
            return rows
        except Exception:
            return []

    def load_llm_policy(self) -> dict:
        default_policy = {
            "version": 1,
            "avoid_conditions": [],
            "prefer_conditions": [],
            "confidence_adjustments": {},
            "notes": "Initial policy. Updated by LLM critic from historical errors.",
            "min_confidence_to_open": LLM_MIN_CONFIDENCE_TO_OPEN,
        }
        if not os.path.exists(LLM_POLICY_FILE):
            return default_policy
        try:
            with open(LLM_POLICY_FILE, 'r') as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                return {**default_policy, **loaded}
        except Exception:
            pass
        return default_policy

    def save_llm_policy(self) -> None:
        if not ENABLE_LLM_POLICY_UPDATE:
            return
        try:
            policy_dict = asdict(self.llm_policy) if isinstance(self.llm_policy, LLMPolicy) else self.llm_policy
            with open(LLM_POLICY_FILE, 'w') as f:
                json.dump(policy_dict, f, indent=2, sort_keys=True)
        except Exception as e:
            logger.error(f"Error saving policy: {e}")

    async def polling_loop(self, client: GatePublicClient):
        """Main polling loop for market data."""
        logger.info("Starting polling loop")
        
        while not self.global_halt:
            try:
                # Get tickers
                tickers = await client.get_tickers()
                
                # Filter for microcap futures (notional < $0.10)
                microcap_symbols = []
                for ticker in tickers:
                    contract = ticker.get('contract', '')
                    last_price = float(ticker.get('last_price', 0))
                    contract_size = float(ticker.get('contract_size', 1))
                    notional = last_price * contract_size
                    
                    if notional < MAX_NOTIONAL and contract.endswith('USDT'):
                        microcap_symbols.append(contract)
                
                self.active_symbols = microcap_symbols[:50]  # Limit to top 50
                logger.info(f"Found {len(self.active_symbols)} microcap symbols")
                
                # Build features for active symbols
                for symbol in self.active_symbols[:10]:  # Limit to 10 for feature building
                    features = await self.feature_builder.build_features(symbol)
                    if features:
                        self.market_features[symbol] = features
                
                await asyncio.sleep(5)  # Poll every 5 seconds
                
            except Exception as e:
                logger.error(f"Error in polling loop: {e}")
                await asyncio.sleep(10)
    
    async def llm_thinking_loop(self, client: GatePublicClient):
        """Continuous LLM thinking loop."""
        logger.info("Starting LLM thinking loop")
        
        while not self.global_halt:
            try:
                if not USE_LLM_THINKER or not self.llm_selector:
                    await asyncio.sleep(LLM_THINK_INTERVAL_SEC)
                    continue
                
                # Get features for top symbols
                features = list(self.market_features.values())
                if not features:
                    await asyncio.sleep(LLM_THINK_INTERVAL_SEC)
                    continue
                
                # Call LLM
                self.llm_calls += 1
                result = await self.llm_selector.select_symbols(features, self.llm_policy, self.recent_errors)
                
                # Update state
                self.llm_thesis = result.get('market_thesis', '')
                self.llm_risk_notes = result.get('risk_notes', '')
                
                # Update actions and register tests
                self.llm_actions = {}
                for action_data in result.get('actions', []):
                    symbol = action_data['symbol']
                    self.llm_actions[symbol] = LLMAction(
                        symbol=symbol,
                        action=action_data['action'],
                        confidence=action_data['confidence'],
                        reason=action_data['reason'],
                        timestamp=datetime.now().isoformat()
                    )
                    
                    # Register decision test once per fresh action
                    if USE_LLM_THINKER and not action_data.get('_registered'):
                        feature = self.market_features.get(symbol)
                        if feature:
                            mid = feature.last_price
                            spread = mid * (feature.spread_bps / 10000.0)
                            book = {
                                'bid': mid - spread / 2.0,
                                'ask': mid + spread / 2.0,
                                'mid': mid,
                            }
                            self.register_llm_decision_test(symbol, action_data, book)
                            action_data['_registered'] = True
                    
                    # Check for HALT
                    if action_data['action'] == 'HALT':
                        self.global_halt = True
                        self.global_halt_reason = action_data['reason']
                        logger.warning(f"Global halt triggered by LLM: {action_data['reason']}")
                
                logger.info(f"LLM thinking complete. Actions: {len(self.llm_actions)}")
                
                await asyncio.sleep(LLM_THINK_INTERVAL_SEC)
                
            except Exception as e:
                logger.error(f"Error in LLM thinking loop: {e}")
                await asyncio.sleep(LLM_THINK_INTERVAL_SEC)
    
    async def llm_outcome_testing_loop(self):
        """Continuously evaluates old LLM decisions against later market outcomes."""
        logger.info("Starting outcome testing loop")
        while not self.global_halt:
            try:
                now = time.time()
                for decision_id, test in list(self.llm_tests.items()):
                    if test.evaluated:
                        continue
                    age = now - test.created_at
                    if age < LLM_OUTCOME_HORIZON_SEC:
                        continue
                    current_features = await self.feature_builder.build_features(test.symbol)
                    if not current_features:
                        continue
                    end_mid = current_features.last_price
                    mid_change_bps = ((end_mid - test.start_mid) / test.start_mid) * 10_000 if test.start_mid > 0 else 0.0
                    spread_then = test.start_ask - test.start_bid
                    spread_now = (current_features.last_price * (current_features.spread_bps / 10000.0))
                    spread_change_bps = 0.0
                    if spread_then > 0:
                        spread_change_bps = ((spread_now - spread_then) / spread_then) * 10_000
                    was_correct = False
                    error_type = None
                    if test.action == "OPEN":
                        if spread_change_bps > -3000 and abs(mid_change_bps) < 250:
                            was_correct = True
                        else:
                            error_type = "bad_open_spread_or_volatility"
                    elif test.action == "WATCH":
                        if abs(mid_change_bps) < 150:
                            was_correct = True
                        else:
                            error_type = "missed_large_move"
                    elif test.action == "SKIP":
                        if abs(mid_change_bps) < 200:
                            was_correct = True
                        else:
                            error_type = "skipped_active_symbol"
                    elif test.action == "HALT":
                        was_correct = self.global_halt
                        if not was_correct:
                            error_type = "unnecessary_halt"
                    result = {
                        "event": "llm_decision_evaluated",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "decision_id": decision_id,
                        "symbol": test.symbol,
                        "action": test.action,
                        "confidence": test.confidence,
                        "reason": test.reason,
                        "features": test.features,
                        "start_mid": test.start_mid,
                        "end_mid": end_mid,
                        "mid_change_bps": mid_change_bps,
                        "spread_change_bps": spread_change_bps,
                        "was_correct": was_correct,
                        "error_type": error_type,
                        "horizon_sec": LLM_OUTCOME_HORIZON_SEC,
                    }
                    self.append_jsonl(LLM_TRADE_MEMORY_FILE, result)
                    if not was_correct:
                        self.append_jsonl(LLM_ERROR_MEMORY_FILE, result)
                        self.recent_errors.append(result)
                        if len(self.recent_errors) > LLM_MAX_ERROR_CONTEXT:
                            self.recent_errors.pop(0)
                        self.open_tests += 1
                        logger.warning(f"LLM ERROR {test.symbol}: action={test.action} error={error_type} mid_change={mid_change_bps:.2f}bps")
                    else:
                        logger.info(f"LLM TEST PASS {test.symbol}: action={test.action} mid_change={mid_change_bps:.2f}bps")
                    test.evaluated = True
            except Exception as e:
                logger.error(f"LLM outcome tester error: {e}")
            await asyncio.sleep(5)
    
    async def llm_policy_critic_loop(self, client: GatePublicClient):
        """Periodically asks the LLM to review historical errors and update policy."""
        if not ENABLE_LLM_CRITIC:
            logger.info("LLM critic disabled")
            return
        if not GROQ_API_KEY:
            logger.info("LLM critic disabled: missing GROQ_API_KEY")
            return
        logger.info("Starting LLM policy critic loop")
        while not self.global_halt:
            try:
                recent_errors = self.read_recent_jsonl(LLM_ERROR_MEMORY_FILE, LLM_MAX_ERROR_CONTEXT)
                if not recent_errors:
                    await asyncio.sleep(LLM_CRITIC_INTERVAL_SEC)
                    continue
                current_policy = self.llm_policy if isinstance(self.llm_policy, dict) else asdict(self.llm_policy)
                prompt = f"""You are the critic for a tiny-balance market-making / hedge scanner.
Your job:
- Review historical LLM decision errors.
- Improve the future decision policy.
- Do NOT suggest increasing risk aggressively.
- Prefer conservative rules for a tiny account.
- Return ONLY JSON.
Current policy:
{json.dumps(current_policy, separators=(",", ":"))}
Recent errors:
{json.dumps(recent_errors, separators=(",", ":"))}
Return updated policy JSON with this exact structure:
{{
  "version": 1,
  "avoid_conditions": [
    "condition text"
  ],
  "prefer_conditions": [
    "condition text"
  ],
  "confidence_adjustments": {{
    "rule_name": "adjustment text"
  }},
  "notes": "short explanation",
  "min_confidence_to_open": 0.65
}}"""
                payload = {
                    "model": self.llm_selector.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a JSON-only trading policy critic. Return only JSON.",
                        },
                        {
                            "role": "user",
                            "content": prompt,
                        },
                    ],
                    "temperature": 0.1,
                    "max_tokens": 900,
                    "response_format": {"type": "json_object"},
                }
                headers = {
                    "Authorization": f"Bearer {self.llm_selector.api_key}",
                    "Content-Type": "application/json",
                }
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            f"{self.llm_selector.base_url}/chat/completions",
                            headers=headers,
                            json=payload,
                            timeout=20,
                        ) as r:
                            text = await r.text()
                            if r.status >= 400:
                                raise RuntimeError(f"Groq critic error {r.status}: {text[:600]}")
                            data = json.loads(text)
                            content = data["choices"][0]["message"]["content"]
                            updated = json.loads(content)
                except Exception as e:
                    logger.error(f"Error in policy critic API call: {e}")
                    await asyncio.sleep(LLM_CRITIC_INTERVAL_SEC)
                    continue
                # Validate and clamp
                if not isinstance(updated, dict):
                    logger.error("Critic returned non-dict policy")
                    await asyncio.sleep(LLM_CRITIC_INTERVAL_SEC)
                    continue
                min_conf = updated.get("min_confidence_to_open", LLM_MIN_CONFIDENCE_TO_OPEN)
                updated["min_confidence_to_open"] = max(0.55, min(0.95, float(min_conf)))
                updated["version"] = int(updated.get("version", 1))
                # Update policy in-place to preserve reference
                if ENABLE_LLM_POLICY_UPDATE:
                    if isinstance(self.llm_policy, dict):
                        self.llm_policy = updated
                    else:
                        self.llm_policy = LLMPolicy(**updated)
                    self._save_policy()
                    self.save_llm_policy()
                    logger.info(
                        f"LLM POLICY UPDATED: min_conf={self.llm_policy.get('min_confidence_to_open') if isinstance(self.llm_policy, dict) else self.llm_policy.min_confidence_to_open} "
                        f"notes={updated.get('notes', '')}"
                    )
                self.last_critic_at = time.time()
            except Exception as e:
                logger.error(f"LLM policy critic error: {e}")
            await asyncio.sleep(LLM_CRITIC_INTERVAL_SEC)
    
    def should_open(self, symbol: str, spread: float, balance: float, exposure: float) -> Tuple[bool, str]:
        """Check if should open position with LLM gate."""
        
        # Deterministic checks first
        if spread > 0.01:  # 1% spread too wide
            return False, "Spread too wide"
        
        if exposure > MAX_TOTAL_EXPOSURE * balance:
            return False, "Max exposure reached"
        
        if balance * MAX_EQUITY_PER_POS < ORDER_NOTIONAL_USD:
            return False, "Insufficient balance"
        
        # LLM gate
        if not USE_LLM_THINKER:
            return True, "LLM disabled, proceeding with deterministic checks"
        
        llm_action = self.llm_actions.get(symbol)
        
        if not llm_action:
            return False, "No LLM action for symbol"
        
        if llm_action.action != "OPEN":
            return False, f"LLM action is {llm_action.action}: {llm_action.reason}"
        
        min_conf = self.llm_policy.get("min_confidence_to_open", LLM_MIN_CONFIDENCE_TO_OPEN) if isinstance(self.llm_policy, dict) else self.llm_policy.min_confidence_to_open
        if llm_action.confidence < min_conf:
            return False, f"LLM confidence {llm_action.confidence} below threshold {min_conf}"
        
        return True, f"LLM approved: {llm_action.reason}"
    
    def get_dashboard_state(self) -> Dict:
        """Get state for dashboard."""
        return {
            "llm": {
                "enabled": USE_LLM_THINKER,
                "model": GROQ_MODEL if USE_LLM_THINKER else "disabled",
                "thesis": self.llm_thesis,
                "risk_notes": self.llm_risk_notes,
                "actions": {k: asdict(v) for k, v in self.llm_actions.items()},
                "features": {k: asdict(v) for k, v in self.market_features.items()}
            },
            "llm_learning": {
                "policy": asdict(self.llm_policy),
                "open_tests": self.open_tests,
                "recent_errors": self.recent_errors[-5:],
                "llm_calls": self.llm_calls
            },
            "system": {
                "global_halt": self.global_halt,
                "global_halt_reason": self.global_halt_reason,
                "active_symbols": self.active_symbols,
                "paper_mode": GATE_PAPER
            }
        }

# ══════════════════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════════════════
async def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("GATE MICROCAP HEDGE ENGINE WITH LLM REASONING")
    logger.info("=" * 60)
    logger.info(f"Paper Mode: {GATE_PAPER}")
    logger.info(f"LLM Thinker: {USE_LLM_THINKER}")
    logger.info(f"LLM Critic: {ENABLE_LLM_CRITIC}")
    logger.info(f"LLM Policy Update: {ENABLE_LLM_POLICY_UPDATE}")
    logger.info(f"Groq Model: {GROQ_MODEL}")
    logger.info("=" * 60)
    
    if not GATE_PAPER and not ARM_LIVE:
        logger.error("LIVE trading requires ARM_LIVE=YES")
        return
    
    engine = GateMicrocapHedgeEngine()
    
    async with engine.client:
        # Run all loops together
        await asyncio.gather(
            engine.polling_loop(engine.client),
            engine.llm_thinking_loop(engine.client),
            engine.llm_outcome_testing_loop(),
            engine.llm_policy_critic_loop(engine.client)
        )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")
