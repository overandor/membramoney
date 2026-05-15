#!/usr/bin/env python3
"""
Simple Gate.io Market Maker with $3 Balance Protection
======================================================
Rule-based market making without AI dependencies
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

# Load environment variables
load_dotenv()

GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

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
        logging.FileHandler('/Users/alep/Downloads/simple_gate_mm.log'),
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


class RuleBasedMarketMaker:
    """Rule-based market maker without AI"""
    
    def __init__(self, exchange: GateExchange):
        self.exchange = exchange
        
    def generate_signal(self, market: MarketState) -> TradingSignal:
        """Generate trading signal using rules"""
        
        # Rule 1: Check spread
        if market.spread_pct < SPREAD_THRESHOLD * 100:
            return TradingSignal(
                action='hold',
                symbol=market.symbol,
                confidence=0.0,
                reason=f'Spread too small: {market.spread_pct:.4f}% < {SPREAD_THRESHOLD*100}%',
                size=0.0,
                price=0.0
            )
        
        # Rule 2: Check volume
        if market.volume_24h < 10000:
            return TradingSignal(
                action='hold',
                symbol=market.symbol,
                confidence=0.0,
                reason=f'Volume too low: ${market.volume_24h:,.2f}',
                size=0.0,
                price=0.0
            )
        
        # Rule 3: Calculate position size based on balance
        balance_info = asyncio.run(self.exchange.check_balance())
        if not balance_info['can_trade']:
            return TradingSignal(
                action='hold',
                symbol=market.symbol,
                confidence=0.0,
                reason=f'Balance too low: ${balance_info["balance"]:.2f}',
                size=0.0,
                price=0.0
            )
        
        # Calculate position size (10% of balance, max $1)
        position_size = min(
            balance_info['balance'] * RISK_PER_TRADE,
            MAX_POSITION_SIZE
        )
        
        # Rule 4: Market making - place orders on both sides
        # We'll alternate between buy and sell to provide liquidity
        import random
        if random.random() > 0.5:
            return TradingSignal(
                action='buy',
                symbol=market.symbol,
                confidence=0.7,
                reason=f'Market making - spread {market.spread_pct:.4f}% adequate',
                size=position_size / market.bid,  # Convert USD to contracts
                price=market.bid
            )
        else:
            return TradingSignal(
                action='sell',
                symbol=market.symbol,
                confidence=0.7,
                reason=f'Market making - spread {market.spread_pct:.4f}% adequate',
                size=position_size / market.ask,  # Convert USD to contracts
                price=market.ask
            )


class SimpleTradingBot:
    """Simple trading bot with balance protection"""
    
    def __init__(self):
        self.exchange = GateExchange()
        self.market_maker = None
        self.running = False
        
    async def initialize(self):
        """Initialize bot components"""
        logger.info("🚀 Initializing Simple Gate.io Market Maker...")
        
        # Connect to exchange
        await self.exchange.connect()
        
        # Initialize market maker
        self.market_maker = RuleBasedMarketMaker(self.exchange)
        
        logger.info("✅ Bot initialized successfully")
        
    async def run_trading_cycle(self, symbol: str):
        """Run one trading cycle"""
        logger.info(f"📊 Trading cycle for {symbol}")
        
        # Check balance
        balance_info = await self.exchange.check_balance()
        if not balance_info['can_trade']:
            logger.warning("⏸️ Skipping cycle - balance too low")
            return
        
        # Get market data
        market = await self.exchange.get_ticker(symbol)
        if not market:
            logger.warning("⏸️ Skipping cycle - no market data")
            return
        
        # Generate signal
        signal = self.market_maker.generate_signal(market)
        logger.info(f"🎯 Signal: {signal.action.upper()} {signal.symbol} "
                   f"confidence={signal.confidence:.2f} reason={signal.reason}")
        
        # Execute trade if signal is buy/sell
        if signal.action in ['buy', 'sell'] and signal.confidence > 0.5:
            await self.exchange.place_order(
                signal.symbol,
                signal.action,
                int(signal.size),  # Round to integer contracts
                signal.price
            )
        elif signal.action == 'close':
            await self.exchange.close_position(signal.symbol)
    
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
                    await asyncio.sleep(2)
                
                # Balance check every cycle
                balance_info = await self.exchange.check_balance()
                if not balance_info['above_minimum']:
                    logger.critical(f"🚨 CRITICAL: Balance below minimum ${MIN_BALANCE}")
                    # Close all positions
                    for symbol in symbols:
                        await self.exchange.close_position(symbol)
                
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
        logger.info("✅ Bot shutdown complete")


async def main():
    """Main entry point"""
    # Check environment variables
    if not GATE_API_KEY or not GATE_API_SECRET:
        logger.error("❌ Missing GATE_API_KEY or GATE_API_SECRET in .env")
        return
    
    # Initialize bot
    bot = SimpleTradingBot()
    await bot.initialize()
    
    # Trading symbols (micro-caps with good liquidity)
    symbols = ['FIO/USDT:USDT', 'NTRN/USDT:USDT', 'SKL/USDT:USDT']
    
    # Run trading
    await bot.run(symbols)


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create a task
            loop.create_task(main())
        else:
            loop.run_until_complete(main())
    except RuntimeError:
        # No loop exists, create one
        asyncio.run(main())
