#!/usr/bin/env python3
"""
AutoGen + Ollama Gate.io Market Maker
=====================================
AI-powered market making bot with $3 balance protection
Uses AutoGen for multi-agent coordination and Ollama for local LLM inference
"""

import os
import asyncio
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

import aiohttp
import ccxt.async_support as ccxt

# AutoGen imports
try:
    import autogen
    from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager
except ImportError:
    print("Installing AutoGen...")
    os.system("pip install pyautogen")
    import autogen
    from autogen import AssistantAgent, UserProxyAgent, GroupChat, GroupChatManager

# Load environment variables
load_dotenv()

GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# Configuration
MIN_BALANCE = 3.0  # Minimum balance protection
TARGET_BALANCE = 3.0  # Target balance for trading
MAX_POSITION_SIZE = 1.0  # Maximum position size
SPREAD_THRESHOLD = 0.001  # 0.1% spread minimum
RISK_PER_TRADE = 0.10  # 10% of balance per trade

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/Users/alep/Downloads/autogen_ollama_gate_mm.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class MarketState:
    symbol: str
    bid: float
    ask: float
    spread: float
    spread_pct: float
    volume_24h: float
    timestamp: float


@dataclass
class TradingSignal:
    action: str  # 'buy', 'sell', 'hold', 'close'
    symbol: str
    confidence: float
    reason: str
    size: float
    price: float


class GateExchange:
    """Gate.io exchange wrapper"""
    
    def __init__(self):
        self.exchange = None
        self.balance = 0.0
        
    async def connect(self):
        """Connect to Gate.io"""
        self.exchange = ccxt.gateio({
            'apiKey': GATE_API_KEY,
            'secret': GATE_API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'defaultSettle': 'usdt',
            }
        })
        await self.exchange.load_markets()
        await self.check_balance()
        
    async def check_balance(self) -> Dict:
        """Check account balance"""
        try:
            balance = await self.exchange.fetch_balance()
            usdt_balance = float(balance.get('USDT', {}).get('free', 0))
            self.balance = usdt_balance
            logger.info(f"💰 Balance: ${usdt_balance:.2f}")
            
            if usdt_balance < MIN_BALANCE:
                logger.warning(f"⚠️ Balance below minimum: ${usdt_balance:.2f} < ${MIN_BALANCE}")
                
            return {
                'balance': usdt_balance,
                'above_minimum': usdt_balance >= MIN_BALANCE,
                'can_trade': usdt_balance >= TARGET_BALANCE
            }
        except Exception as e:
            logger.error(f"❌ Balance check failed: {e}")
            return {'balance': 0, 'above_minimum': False, 'can_trade': False}
    
    async def get_ticker(self, symbol: str) -> Optional[MarketState]:
        """Get market ticker data"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            bid = ticker['bid']
            ask = ticker['ask']
            spread = ask - bid
            spread_pct = (spread / bid) * 100 if bid > 0 else 0
            
            return MarketState(
                symbol=symbol,
                bid=bid,
                ask=ask,
                spread=spread,
                spread_pct=spread_pct,
                volume_24h=ticker['quoteVolume'],
                timestamp=time.time()
            )
        except Exception as e:
            logger.error(f"❌ Failed to fetch ticker for {symbol}: {e}")
            return None
    
    async def place_order(self, symbol: str, side: str, amount: float, price: float) -> Optional[Dict]:
        """Place an order"""
        try:
            order = await self.exchange.create_order(
                symbol, 'limit', side, amount, price
            )
            logger.info(f"✅ Order placed: {side.upper()} {amount} {symbol} @ ${price:.8f}")
            return order
        except Exception as e:
            logger.error(f"❌ Order failed: {e}")
            return None
    
    async def close_position(self, symbol: str) -> bool:
        """Close position for symbol"""
        try:
            positions = await self.exchange.fetch_positions([symbol])
            for pos in positions:
                if float(pos['contracts']) > 0:
                    side = 'sell' if pos['side'] == 'long' else 'buy'
                    ticker = await self.exchange.fetch_ticker(symbol)
                    price = ticker['last']
                    await self.place_order(symbol, side, abs(float(pos['contracts'])), price)
            return True
        except Exception as e:
            logger.error(f"❌ Failed to close position: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from exchange"""
        if self.exchange:
            await self.exchange.close()


class OllamaLLM:
    """Ollama LLM wrapper for AutoGen"""
    
    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL):
        self.model = model
        self.base_url = base_url
        self.session = None
        
    async def connect(self):
        """Connect to Ollama"""
        self.session = aiohttp.ClientSession()
        
    async def generate(self, prompt: str) -> str:
        """Generate response from Ollama"""
        try:
            async with self.session.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                }
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get('response', '')
                else:
                    logger.error(f"Ollama error: {resp.status}")
                    return "Error generating response"
        except Exception as e:
            logger.error(f"Ollama connection error: {e}")
            return "Connection error"
    
    async def disconnect(self):
        """Disconnect from Ollama"""
        if self.session:
            await self.session.close()


class TradingAgent:
    """Base trading agent"""
    
    def __init__(self, name: str, exchange: GateExchange, llm: OllamaLLM):
        self.name = name
        self.exchange = exchange
        self.llm = llm
        
    async def analyze_market(self, symbol: str) -> str:
        """Analyze market conditions"""
        market = await self.exchange.get_ticker(symbol)
        if not market:
            return f"No market data available for {symbol}"
        
        balance_info = await self.exchange.check_balance()
        
        analysis = f"""
Market Analysis for {symbol}:
- Bid: ${market.bid:.8f}
- Ask: ${market.ask:.8f}
- Spread: ${market.spread:.8f} ({market.spread_pct:.4f}%)
- Volume 24h: ${market.volume_24h:,.2f}
- Balance: ${balance_info['balance']:.2f}
- Can Trade: {balance_info['can_trade']}

Based on this data, provide a trading recommendation (buy/sell/hold/close) with confidence score (0-1) and reasoning.
"""
        return analysis


class MarketMakerAgent(TradingAgent):
    """Market making agent"""
    
    async def generate_signal(self, symbol: str) -> TradingSignal:
        """Generate trading signal using AI"""
        analysis = await self.analyze_market(symbol)
        
        prompt = f"""
You are a conservative market maker for Gate.io futures. Your goal is to provide liquidity while protecting a $3 balance.

{analysis}

Rules:
1. Only trade if balance >= ${TARGET_BALANCE}
2. Maximum position size: ${MAX_POSITION_SIZE}
3. Minimum spread: {SPREAD_THRESHOLD*100}%
4. Risk per trade: {RISK_PER_TRADE*100}% of balance
5. Always prioritize balance protection over profit

Respond in JSON format:
{{
    "action": "buy/sell/hold/close",
    "confidence": 0.0-1.0,
    "reason": "brief explanation",
    "size": float,
    "price": float
}}
"""
        
        response = await self.llm.generate(prompt)
        
        try:
            # Parse JSON from response
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return TradingSignal(
                    action=data.get('action', 'hold'),
                    symbol=symbol,
                    confidence=data.get('confidence', 0.0),
                    reason=data.get('reason', ''),
                    size=data.get('size', 0.0),
                    price=data.get('price', 0.0)
                )
        except:
            pass
        
        # Fallback to hold signal
        return TradingSignal(
            action='hold',
            symbol=symbol,
            confidence=0.0,
            reason='Failed to parse AI response',
            size=0.0,
            price=0.0
        )


class RiskAgent(TradingAgent):
    """Risk management agent"""
    
    async def check_risk(self, signal: TradingSignal) -> bool:
        """Check if signal meets risk criteria"""
        balance_info = await self.exchange.check_balance()
        
        if not balance_info['can_trade']:
            logger.warning("⚠️ Balance too low to trade")
            return False
        
        if signal.size > MAX_POSITION_SIZE:
            logger.warning(f"⚠️ Position size too large: ${signal.size} > ${MAX_POSITION_SIZE}")
            return False
        
        if signal.confidence < 0.5:
            logger.warning(f"⚠️ Low confidence signal: {signal.confidence}")
            return False
        
        return True


class BalanceAgent(TradingAgent):
    """Balance monitoring agent"""
    
    async def monitor_balance(self) -> Dict:
        """Monitor balance and alert if low"""
        balance_info = await self.exchange.check_balance()
        
        if not balance_info['above_minimum']:
            logger.critical(f"🚨 CRITICAL: Balance below minimum ${MIN_BALANCE}")
            # Emergency: close all positions
            # await self.exchange.close_all_positions()
        
        return balance_info


class AutoGenTradingBot:
    """Main trading bot using AutoGen"""
    
    def __init__(self):
        self.exchange = GateExchange()
        self.llm = OllamaLLM()
        self.market_maker = None
        self.risk_agent = None
        self.balance_agent = None
        self.running = False
        
    async def initialize(self):
        """Initialize bot components"""
        logger.info("🚀 Initializing AutoGen + Ollama Trading Bot...")
        
        # Connect to services
        await self.exchange.connect()
        await self.llm.connect()
        
        # Initialize agents
        self.market_maker = MarketMakerAgent("MarketMaker", self.exchange, self.llm)
        self.risk_agent = RiskAgent("RiskManager", self.exchange, self.llm)
        self.balance_agent = BalanceAgent("BalanceMonitor", self.exchange, self.llm)
        
        logger.info("✅ Bot initialized successfully")
        
    async def setup_autogen_agents(self):
        """Setup AutoGen agents"""
        # Create AutoGen agents
        market_maker_agent = AssistantAgent(
            name="market_maker",
            system_message="You are an expert market maker. Analyze market data and provide trading signals.",
            llm_config={"config_list": [{"model": "ollama/llama3.2"}]}
        )
        
        risk_agent = AssistantAgent(
            name="risk_manager",
            system_message="You are a risk manager. Validate all trading signals against risk parameters.",
            llm_config={"config_list": [{"model": "ollama/llama3.2"}]}
        )
        
        user_proxy = UserProxyAgent(
            name="user_proxy",
            human_input_mode="NEVER",
            max_consecutive_auto_reply=10
        )
        
        # Create group chat
        groupchat = GroupChat(
            agents=[user_proxy, market_maker_agent, risk_agent],
            messages=[],
            max_round=5
        )
        
        manager = GroupChatManager(groupchat=groupchat, name="manager")
        
        return manager
    
    async def run_trading_cycle(self, symbol: str):
        """Run one trading cycle"""
        logger.info(f"📊 Trading cycle for {symbol}")
        
        # Check balance
        balance_info = await self.balance_agent.monitor_balance()
        if not balance_info['can_trade']:
            logger.warning("⏸️ Skipping cycle - balance too low")
            return
        
        # Generate signal
        signal = await self.market_maker.generate_signal(symbol)
        logger.info(f"🎯 Signal: {signal.action.upper()} {signal.symbol} "
                   f"confidence={signal.confidence:.2f} reason={signal.reason}")
        
        # Risk check
        if await self.risk_agent.check_risk(signal):
            if signal.action in ['buy', 'sell']:
                # Execute trade
                await self.exchange.place_order(
                    signal.symbol,
                    signal.action,
                    signal.size,
                    signal.price
                )
            elif signal.action == 'close':
                await self.exchange.close_position(signal.symbol)
        else:
            logger.info("🛡️ Signal rejected by risk manager")
    
    async def run(self, symbols: List[str]):
        """Main trading loop"""
        logger.info("🎯 Starting trading bot...")
        self.running = True
        
        try:
            while self.running:
                for symbol in symbols:
                    if not self.running:
                        break
                    await self.run_trading_cycle(symbol)
                    await asyncio.sleep(1)
                
                # Balance check every cycle
                await self.balance_agent.monitor_balance()
                await asyncio.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("⏹️ Bot stopped by user")
        except Exception as e:
            logger.error(f"❌ Bot error: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Shutdown bot"""
        logger.info("🛑 Shutting down bot...")
        self.running = False
        await self.exchange.disconnect()
        await self.llm.disconnect()
        logger.info("✅ Bot shutdown complete")


async def main():
    """Main entry point"""
    # Check environment variables
    if not GATE_API_KEY or not GATE_API_SECRET:
        logger.error("❌ Missing GATE_API_KEY or GATE_API_SECRET in .env")
        return
    
    # Initialize bot
    bot = AutoGenTradingBot()
    await bot.initialize()
    
    # Trading symbols (micro-caps with good liquidity)
    symbols = ['FIO/USDT:USDT', 'NTRN/USDT:USDT', 'SKL/USDT:USDT']
    
    # Run trading
    await bot.run(symbols)


if __name__ == "__main__":
    asyncio.run(main())
