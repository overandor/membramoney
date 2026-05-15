#!/usr/bin/env python3
import os
"""
PRECISION SHORTING SYSTEM
Targets smallest notional values with 5%+ pumps
Immediate profit taking and position trimming
"""

import asyncio
import aiohttp
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
import logging
from dataclasses import dataclass, field
from enum import Enum
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class OrderSide(Enum):
    SHORT = "sell"
    COVER = "buy"

@dataclass
class CoinPrice:
    symbol: str
    price: float
    price_24h_ago: float
    volume_24h: float
    market_cap: float
    exchange: str
    notional_value: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ShortPosition:
    symbol: str
    exchange: str
    entry_price: float
    quantity: float
    entry_time: datetime
    notional_value: float
    status: str = "open"
    pnl: float = 0.0
    profit_taken: bool = False

class PrecisionShortingSystem:
    """Precision shorting system for micro-cap coins with immediate profit taking"""
    
    def __init__(self):
        # Exchange configurations with minimum notional values
        self.exchanges = {
            'bybit': {
                'api_key': 'your_bybit_key',
                'api_secret': 'your_bybit_secret',
                'futures_url': 'https://api.bybit.com',
                'min_notional': 5.0,  # $5 minimum
                'maker_fee': 0.0001,
                'taker_fee': 0.0006
            },
            'bitget': {
                'api_key': 'your_bitget_key',
                'api_secret': 'your_bitget_secret',
                'futures_url': 'https://api.bitget.com',
                'min_notional': 5.0,  # $5 minimum
                'maker_fee': 0.0001,
                'taker_fee': 0.0004
            },
            'mexc': {
                'api_key': 'your_mexc_key',
                'api_secret': 'your_mexc_secret',
                'futures_url': 'https://api.mexc.com',
                'min_notional': 5.0,  # $5 minimum
                'maker_fee': 0.0002,
                'taker_fee': 0.0004
            }
        }
        
        # Precision targeting
        self.min_notional_threshold = 5.0  # $5 minimum notional
        self.max_notional_threshold = 50.0  # $50 maximum to stay small
        self.pump_threshold = 0.05  # 5% pump threshold (lowered from 10%)
        self.position_size_usd = 5.0  # Use minimum notional value
        self.max_positions = 20  # Maximum concurrent positions
        self.profit_target = 0.01  # 1% profit target (immediate taking)
        self.stop_loss = 0.02  # 2% stop loss
        
        # State tracking
        self.active_positions = []
        self.profit_symbols_today = set()  # Track symbols that hit profit today
        self.last_scan_time = datetime.now()
        self.daily_reset_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Statistics
        self.total_trades = 0
        self.successful_shorts = 0
        self.total_pnl = 0.0
        self.immediate_profits = 0
        
        logger.info("🎯 Precision Shorting System initialized")
        logger.info(f"💰 Target notional: ${self.min_notional_threshold}-${self.max_notional_threshold}")
        logger.info(f"📈 Pump threshold: {self.pump_threshold*100:.0f}%+")
        logger.info(f"⚡ Immediate profit target: {self.profit_target*100:.0f}%")
    
    async def get_bybit_tickers(self) -> List[CoinPrice]:
        """Get Bybit futures tickers with notional filtering"""
        try:
            url = "https://api.bybit.com/v5/market/tickers?category=linear&instType=USDT-FUTURES"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        coins = []
                        
                        if data['retCode'] == 0 and data['result']['list']:
                            for ticker in data['result']['list']:
                                try:
                                    symbol = ticker['symbol']
                                    if not symbol.endswith('USDT'):
                                        continue
                                    
                                    price = float(ticker['lastPrice'])
                                    price_change = float(ticker['price24hPcnt'])
                                    volume = float(ticker['turnover24h']) / price
                                    
                                    # Calculate 24h ago price
                                    price_24h_ago = price / (1 + price_change) if price_change != 0 else price
                                    
                                    # Calculate notional value for minimum order size
                                    min_qty = 0.0001  # Typical minimum quantity
                                    notional_value = min_qty * price
                                    
                                    # Filter by notional value range
                                    if self.min_notional_threshold <= notional_value <= self.max_notional_threshold:
                                        coin = CoinPrice(
                                            symbol=symbol.replace('USDT', ''),
                                            price=price,
                                            price_24h_ago=price_24h_ago,
                                            volume_24h=volume,
                                            market_cap=0,
                                            exchange='bybit',
                                            notional_value=notional_value
                                        )
                                        coins.append(coin)
                                        
                                except (ValueError, KeyError):
                                    continue
                        
                        logger.info(f"📊 Bybit: Found {len(coins)} coins in notional range")
                        return coins
                        
        except Exception as e:
            logger.error(f"Bybit API error: {e}")
        
        return []
    
    async def get_bitget_tickers(self) -> List[CoinPrice]:
        """Get Bitget futures tickers with notional filtering"""
        try:
            url = "https://api.bitget.com/api/v2/market/tickers?productType=USDT-FUTURES"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        coins = []
                        
                        if data['code'] == '00000' and data['data']:
                            for ticker in data['data']:
                                try:
                                    symbol = ticker['symbol']
                                    if not symbol.endswith('USDT'):
                                        continue
                                    
                                    price = float(ticker['lastPr'])
                                    price_change = float(ticker['changePercent']) / 100
                                    volume = float(ticker['baseVolume'])
                                    
                                    price_24h_ago = price / (1 + price_change) if price_change != 0 else price
                                    
                                    # Calculate notional value
                                    min_qty = float(ticker.get('minSize', 0.0001))
                                    notional_value = min_qty * price
                                    
                                    if self.min_notional_threshold <= notional_value <= self.max_notional_threshold:
                                        coin = CoinPrice(
                                            symbol=symbol.replace('USDT', ''),
                                            price=price,
                                            price_24h_ago=price_24h_ago,
                                            volume_24h=volume,
                                            market_cap=0,
                                            exchange='bitget',
                                            notional_value=notional_value
                                        )
                                        coins.append(coin)
                                        
                                except (ValueError, KeyError):
                                    continue
                        
                        logger.info(f"📊 Bitget: Found {len(coins)} coins in notional range")
                        return coins
                        
        except Exception as e:
            logger.error(f"Bitget API error: {e}")
        
        return []
    
    def identify_pumping_coins(self, coins: List[CoinPrice]) -> List[CoinPrice]:
        """Identify coins that have pumped 5%+ and filter by notional value"""
        pumping_coins = []
        
        for coin in coins:
            price_change = (coin.price - coin.price_24h_ago) / coin.price_24h_ago
            
            if price_change >= self.pump_threshold:
                # Additional filter: exclude symbols that already hit profit today
                symbol_exchange_key = f"{coin.symbol}_{coin.exchange}"
                if symbol_exchange_key not in self.profit_symbols_today:
                    pumping_coins.append(coin)
                    logger.info(f"🚀 PRECISION TARGET: {coin.symbol} +{price_change*100:.1f}% "
                              f"${coin.price:.6f} | Notional: ${coin.notional_value:.2f} | {coin.exchange}")
        
        # Sort by notional value (smallest first)
        pumping_coins.sort(key=lambda x: x.notional_value)
        
        return pumping_coins
    
    def should_short_coin(self, coin: CoinPrice) -> bool:
        """Determine if we should short this coin with precision criteria"""
        # Check if we already have a position
        for pos in self.active_positions:
            if pos.symbol == coin.symbol and pos.exchange == coin.exchange:
                return False
        
        # Check maximum positions
        if len(self.active_positions) >= self.max_positions:
            return False
        
        # Check if symbol already hit profit today
        symbol_exchange_key = f"{coin.symbol}_{coin.exchange}"
        if symbol_exchange_key in self.profit_symbols_today:
            return False
        
        # Prioritize smallest notional values
        return True
    
    async def place_short_order(self, coin: CoinPrice) -> Optional[ShortPosition]:
        """Place a precision short order at minimum notional value"""
        try:
            # Use exact minimum notional value
            quantity = self.position_size_usd / coin.price
            
            # Create position
            position = ShortPosition(
                symbol=coin.symbol,
                exchange=coin.exchange,
                entry_price=coin.price,
                quantity=quantity,
                entry_time=datetime.now(),
                notional_value=self.position_size_usd
            )
            
            self.active_positions.append(position)
            self.total_trades += 1
            
            logger.info(f"📉 PRECISION SHORT: {coin.symbol} @ ${coin.price:.6f}")
            logger.info(f"   Exchange: {coin.exchange} | Notional: ${position.notional_value:.2f}")
            logger.info(f"   Quantity: {quantity:.6f} | Target: {self.profit_target*100:.0f}% profit")
            
            return position
            
        except Exception as e:
            logger.error(f"Failed to place short order for {coin.symbol}: {e}")
            return None
    
    async def monitor_and_close_positions(self):
        """Monitor positions and immediately take profits"""
        current_prices = await self.get_all_current_prices()
        
        for position in self.active_positions[:]:  # Copy list to allow modification
            if position.status != "open":
                continue
            
            # Get current price
            current_price = current_prices.get(f"{position.symbol}_{position.exchange}")
            if not current_price:
                continue
            
            # Calculate PnL
            pnl = (position.entry_price - current_price) * position.quantity
            pnl_pct = (pnl / position.notional_value) * 100
            position.pnl = pnl
            
            # Check for immediate profit taking
            if pnl_pct >= self.profit_target * 100:
                # IMMEDIATE PROFIT TAKEN
                position.status = "profit_taken"
                position.profit_taken = True
                self.successful_shorts += 1
                self.immediate_profits += 1
                self.total_pnl += pnl
                self.active_positions.remove(position)
                
                # Add to profit symbols list (no more shorts today)
                symbol_exchange_key = f"{position.symbol}_{position.exchange}"
                self.profit_symbols_today.add(symbol_exchange_key)
                
                logger.info(f"⚡ IMMEDIATE PROFIT: {position.symbol} @ ${current_price:.6f}")
                logger.info(f"   Profit: ${pnl:.4f} ({pnl_pct:.2f}%) | TRIMMING COMPLETE")
                logger.info(f"   🚫 No more shorts for {position.symbol} today")
                
            elif pnl_pct <= -self.stop_loss * 100:
                # Stop loss
                position.status = "stop_loss"
                self.total_pnl += pnl
                self.active_positions.remove(position)
                
                logger.info(f"❌ STOP LOSS: {position.symbol} @ ${current_price:.6f} (${pnl:.4f})")
    
    async def get_all_current_prices(self) -> Dict[str, float]:
        """Get current prices for all active positions"""
        prices = {}
        
        for position in self.active_positions:
            # Simulate small random price movements
            change = np.random.normal(0, 0.003)  # 0.3% standard deviation
            current_price = position.entry_price * (1 + change)
            prices[f"{position.symbol}_{position.exchange}"] = current_price
        
        return prices
    
    def check_daily_reset(self):
        """Check if we need to reset daily profit tracking"""
        now = datetime.now()
        if now.date() > self.daily_reset_time.date():
            # Reset daily tracking
            old_count = len(self.profit_symbols_today)
            self.profit_symbols_today.clear()
            self.daily_reset_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
            
            logger.info(f"🔄 DAILY RESET: Cleared {old_count} symbols from profit list")
    
    async def scan_and_short_precision(self):
        """Main precision scanning and shorting loop"""
        logger.info("🔍 Precision scanning for smallest notional pumps...")
        
        # Check daily reset
        self.check_daily_reset()
        
        # Get all tickers from exchanges
        all_coins = []
        
        bybit_coins = await self.get_bybit_tickers()
        bitget_coins = await self.get_bitget_tickers()
        
        all_coins.extend(bybit_coins)
        all_coins.extend(bitget_coins)
        
        logger.info(f"📊 Total coins in notional range: {len(all_coins)}")
        
        # Identify pumping coins with 5%+ threshold
        pumping_coins = self.identify_pumping_coins(all_coins)
        logger.info(f"🚀 Found {len(pumping_coins)} precision targets (5%+ pumps)")
        
        # Place precision short orders (prioritize smallest notional)
        new_shorts = 0
        for coin in pumping_coins:
            if self.should_short_coin(coin):
                position = await self.place_short_order(coin)
                if position:
                    new_shorts += 1
                
                # Limit to top 5 smallest notional values per scan
                if new_shorts >= 5:
                    break
        
        logger.info(f"📉 Placed {new_shorts} precision short positions")
        
        # Monitor and immediately close profitable positions
        await self.monitor_and_close_positions()
        
        # Update statistics
        self.last_scan_time = datetime.now()
    
    def print_precision_status(self):
        """Print precision system status"""
        print("\n" + "="*100)
        print("🎯 PRECISION SHORTING SYSTEM STATUS")
        print("="*100)
        print(f"💰 Notional Range: ${self.min_notional_threshold}-${self.max_notional_threshold}")
        print(f"📈 Pump Threshold: {self.pump_threshold*100:.0f}%+")
        print(f"⚡ Profit Target: {self.profit_target*100:.0f}% (immediate)")
        print(f"📊 Active Positions: {len(self.active_positions)}/{self.max_positions}")
        print(f"✅ Total Trades: {self.total_trades}")
        print(f"⚡ Immediate Profits: {self.immediate_profits}")
        print(f"💰 Total PnL: ${self.total_pnl:.4f}")
        print(f"🚫 Symbols Blocked Today: {len(self.profit_symbols_today)}")
        print(f"⏰ Last Scan: {self.last_scan_time.strftime('%H:%M:%S')}")
        
        if self.active_positions:
            print(f"\n📋 Active Precision Positions:")
            for pos in self.active_positions[:10]:  # Show top 10
                pnl_pct = (pos.pnl / pos.notional_value) * 100 if pos.notional_value > 0 else 0
                status = "⚡ PROFIT" if pos.profit_taken else "📈 OPEN"
                print(f"   {pos.symbol} ({pos.exchange}): ${pos.entry_price:.6f} → "
                      f"PnL: ${pos.pnl:.4f} ({pnl_pct:+.2f}%) | {status}")
        
        if self.profit_symbols_today:
            print(f"\n🚫 Blocked Symbols (profit taken):")
            for symbol in list(self.profit_symbols_today)[:10]:
                print(f"   {symbol}")
        
        print("="*100)
    
    async def run_precision_shorting(self):
        """Main precision shorting loop"""
        logger.info("🎯 Starting Precision Shorting System")
        logger.info(f"💰 Targeting smallest notional values with 5%+ pumps")
        logger.info(f"⚡ Immediate profit taking and position trimming")
        
        self.is_running = True
        
        while self.is_running:
            try:
                # Precision scan and short
                await self.scan_and_short_precision()
                
                # Print status every 2 minutes
                if int(time.time()) % 120 == 0:
                    self.print_precision_status()
                
                # Wait before next scan
                await asyncio.sleep(30)  # Scan every 30 seconds
                
            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(10)
        
        # Final status
        self.print_precision_status()

async def main():
    """Main function"""
    print("🎯 PRECISION SHORTING SYSTEM")
    print("="*100)
    print("💰 Targets smallest notional values ($5-$50)")
    print("📈 5%+ pump detection (lowered threshold)")
    print("⚡ Immediate profit taking (1% target)")
    print("🚫 Position trimming after profit")
    print("⚠️  DEMO MODE - No real trades executed")
    print("="*100)
    
    # Initialize system
    shorting_system = PrecisionShortingSystem()
    
    # Run the system
    await shorting_system.run_precision_shorting()

if __name__ == "__main__":
    asyncio.run(main())
