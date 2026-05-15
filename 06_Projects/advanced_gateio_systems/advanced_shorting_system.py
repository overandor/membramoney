#!/usr/bin/env python3
import os
"""
ADVANCED CRYPTO SHORTING SYSTEM
Automatically shorts coins that pump 10%+ across multiple exchanges
Focus on micro-cap coins (1¢ to 10¢ range)
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
import hashlib

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
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class ShortPosition:
    symbol: str
    exchange: str
    entry_price: float
    quantity: float
    entry_time: datetime
    target_price: float
    stop_loss: float
    status: str = "open"
    pnl: float = 0.0

class AdvancedShortingSystem:
    """Advanced crypto shorting system for micro-cap coins"""
    
    def __init__(self):
        self.exchanges = {
            'binance': {
                'api_key': 'your_binance_key',
                'api_secret': 'your_binance_secret',
                'futures_url': 'https://fapi.binance.com',
                'spot_url': 'https://api.binance.com'
            },
            'bybit': {
                'api_key': 'your_bybit_key', 
                'api_secret': 'your_bybit_secret',
                'futures_url': 'https://api.bybit.com',
                'spot_url': 'https://api.bybit.com'
            },
            'kucoin': {
                'api_key': 'your_kucoin_key',
                'api_secret': 'your_kucoin_secret', 
                'futures_url': 'https://api-futures.kucoin.com',
                'spot_url': 'https://api.kucoin.com'
            }
        }
        
        # Configuration
        self.min_price = 0.01  # 1 cent minimum
        self.max_price = 0.10  # 10 cent maximum
        self.pump_threshold = 0.10  # 10% pump threshold
        self.position_size_usd = 10  # $10 per position
        self.max_positions = 50  # Maximum concurrent positions
        self.target_profit = 0.05  # 5% profit target
        self.stop_loss = 0.03  # 3% stop loss
        
        # State tracking
        self.price_history = {}  # symbol -> list of prices
        self.active_positions = []  # List of ShortPosition
        self.monitored_coins = set()
        self.last_scan_time = datetime.now()
        
        # Statistics
        self.total_trades = 0
        self.successful_shorts = 0
        self.total_pnl = 0.0
        
        logger.info("🤖 Advanced Shorting System initialized")
        logger.info(f"🎯 Targeting coins ${self.min_price:.2f} - ${self.max_price:.2f} with {self.pump_threshold*100:.0f}%+ pumps")
    
    async def get_binance_tickers(self) -> List[CoinPrice]:
        """Get all Binance futures tickers"""
        try:
            url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        coins = []
                        
                        for ticker in data:
                            try:
                                symbol = ticker['symbol']
                                if not symbol.endswith('USDT'):
                                    continue
                                
                                price = float(ticker['lastPrice'])
                                price_change = float(ticker['priceChangePercent']) / 100
                                volume = float(ticker['volume'])
                                
                                # Calculate 24h ago price
                                price_24h_ago = price / (1 + price_change) if price_change != 0 else price
                                
                                # Filter for target price range
                                if self.min_price <= price <= self.max_price:
                                    coin = CoinPrice(
                                        symbol=symbol.replace('USDT', ''),
                                        price=price,
                                        price_24h_ago=price_24h_ago,
                                        volume_24h=volume,
                                        market_cap=0,  # Not available in this endpoint
                                        exchange='binance'
                                    )
                                    coins.append(coin)
                                    
                            except (ValueError, KeyError):
                                continue
                        
                        logger.info(f"📊 Binance: Found {len(coins)} coins in target range")
                        return coins
                        
        except Exception as e:
            logger.error(f"Binance API error: {e}")
        
        return []
    
    async def get_bybit_tickers(self) -> List[CoinPrice]:
        """Get all Bybit futures tickers"""
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
                                    volume = float(ticker['turnover24h']) / price  # Convert to volume
                                    
                                    price_24h_ago = price / (1 + price_change) if price_change != 0 else price
                                    
                                    if self.min_price <= price <= self.max_price:
                                        coin = CoinPrice(
                                            symbol=symbol.replace('USDT', ''),
                                            price=price,
                                            price_24h_ago=price_24h_ago,
                                            volume_24h=volume,
                                            market_cap=0,
                                            exchange='bybit'
                                        )
                                        coins.append(coin)
                                        
                                except (ValueError, KeyError):
                                    continue
                        
                        logger.info(f"📊 Bybit: Found {len(coins)} coins in target range")
                        return coins
                        
        except Exception as e:
            logger.error(f"Bybit API error: {e}")
        
        return []
    
    async def get_kucoin_tickers(self) -> List[CoinPrice]:
        """Get all KuCoin futures tickers"""
        try:
            url = "https://api-futures.kucoin.com/api/v1/allTickers"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        coins = []
                        
                        if data['code'] == '200' and data['data']:
                            for ticker in data['data']['ticker']:
                                try:
                                    symbol = ticker['symbol']
                                    if not symbol.endswith('USDTM'):
                                        continue
                                    
                                    price = float(ticker['last'])
                                    price_change = float(ticker['changeRate'])
                                    volume = float(ticker['vol'])
                                    
                                    price_24h_ago = price / (1 + price_change) if price_change != 0 else price
                                    
                                    if self.min_price <= price <= self.max_price:
                                        coin = CoinPrice(
                                            symbol=symbol.replace('USDTM', ''),
                                            price=price,
                                            price_24h_ago=price_24h_ago,
                                            volume_24h=volume,
                                            market_cap=0,
                                            exchange='kucoin'
                                        )
                                        coins.append(coin)
                                        
                                except (ValueError, KeyError):
                                    continue
                        
                        logger.info(f"📊 KuCoin: Found {len(coins)} coins in target range")
                        return coins
                        
        except Exception as e:
            logger.error(f"KuCoin API error: {e}")
        
        return []
    
    def identify_pumping_coins(self, coins: List[CoinPrice]) -> List[CoinPrice]:
        """Identify coins that have pumped 10%+"""
        pumping_coins = []
        
        for coin in coins:
            price_change = (coin.price - coin.price_24h_ago) / coin.price_24h_ago
            
            if price_change >= self.pump_threshold:
                pumping_coins.append(coin)
                logger.info(f"🚀 PUMP DETECTED: {coin.symbol} +{price_change*100:.1f}% (${coin.price:.4f}) on {coin.exchange}")
        
        return pumping_coins
    
    def calculate_position_size(self, coin_price: float) -> float:
        """Calculate position size based on price"""
        # Fixed USD position size
        return self.position_size_usd / coin_price
    
    def should_short_coin(self, coin: CoinPrice) -> bool:
        """Determine if we should short this coin"""
        # Check if we already have a position
        for pos in self.active_positions:
            if pos.symbol == coin.symbol and pos.exchange == coin.exchange:
                return False
        
        # Check maximum positions
        if len(self.active_positions) >= self.max_positions:
            return False
        
        # Check if we've recently shorted this coin
        coin_key = f"{coin.symbol}_{coin.exchange}"
        if coin_key in self.monitored_coins:
            return False
        
        return True
    
    async def place_short_order(self, coin: CoinPrice) -> Optional[ShortPosition]:
        """Place a short order (mock implementation)"""
        try:
            quantity = self.calculate_position_size(coin.price)
            
            # Create position (in real implementation, this would call exchange API)
            position = ShortPosition(
                symbol=coin.symbol,
                exchange=coin.exchange,
                entry_price=coin.price,
                quantity=quantity,
                entry_time=datetime.now(),
                target_price=coin.price * (1 - self.target_profit),
                stop_loss=coin.price * (1 + self.stop_loss)
            )
            
            self.active_positions.append(position)
            self.monitored_coins.add(f"{coin.symbol}_{coin.exchange}")
            self.total_trades += 1
            
            logger.info(f"📉 SHORT PLACED: {coin.symbol} @ ${coin.price:.4f} on {coin.exchange}")
            logger.info(f"   Quantity: {quantity:.2f}, Target: ${position.target_price:.4f}, Stop: ${position.stop_loss:.4f}")
            
            return position
            
        except Exception as e:
            logger.error(f"Failed to place short order for {coin.symbol}: {e}")
            return None
    
    async def monitor_positions(self):
        """Monitor and close profitable positions"""
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
            position.pnl = pnl
            
            # Check if target or stop loss hit
            if current_price <= position.target_price:
                # Take profit
                position.status = "closed_profit"
                self.successful_shorts += 1
                self.total_pnl += pnl
                self.active_positions.remove(position)
                
                logger.info(f"✅ PROFIT TAKEN: {position.symbol} @ ${current_price:.4f} (+${pnl:.2f})")
                
            elif current_price >= position.stop_loss:
                # Stop loss
                position.status = "closed_loss"
                self.total_pnl += pnl
                self.active_positions.remove(position)
                
                logger.info(f"❌ STOP LOSS: {position.symbol} @ ${current_price:.4f} (${pnl:.2f})")
    
    async def get_all_current_prices(self) -> Dict[str, float]:
        """Get current prices for all active positions"""
        prices = {}
        
        # This would normally call exchange APIs for current prices
        # For demo, we'll simulate price movements
        for position in self.active_positions:
            # Simulate small random price movements
            change = np.random.normal(0, 0.002)  # 0.2% standard deviation
            current_price = position.entry_price * (1 + change)
            prices[f"{position.symbol}_{position.exchange}"] = current_price
        
        return prices
    
    async def scan_and_short(self):
        """Main scanning and shorting loop"""
        logger.info("🔍 Scanning for pumping coins...")
        
        # Get all tickers from exchanges
        all_coins = []
        
        binance_coins = await self.get_binance_tickers()
        bybit_coins = await self.get_bybit_tickers()
        kucoin_coins = await self.get_kucoin_tickers()
        
        all_coins.extend(binance_coins)
        all_coins.extend(bybit_coins)
        all_coins.extend(kucoin_coins)
        
        logger.info(f"📊 Total coins in range: {len(all_coins)}")
        
        # Identify pumping coins
        pumping_coins = self.identify_pumping_coins(all_coins)
        logger.info(f"🚀 Found {len(pumping_coins)} pumping coins")
        
        # Place short orders
        new_shorts = 0
        for coin in pumping_coins:
            if self.should_short_coin(coin):
                position = await self.place_short_order(coin)
                if position:
                    new_shorts += 1
        
        logger.info(f"📉 Placed {new_shorts} new short positions")
        
        # Monitor existing positions
        await self.monitor_positions()
        
        # Update statistics
        self.last_scan_time = datetime.now()
    
    def print_status(self):
        """Print current system status"""
        print("\n" + "="*80)
        print("🤖 ADVANCED SHORTING SYSTEM STATUS")
        print("="*80)
        print(f"📊 Active Positions: {len(self.active_positions)}/{self.max_positions}")
        print(f"📈 Total Trades: {self.total_trades}")
        print(f"✅ Successful Shorts: {self.successful_shorts}")
        print(f"💰 Total PnL: ${self.total_pnl:.2f}")
        print(f"🎯 Target Range: ${self.min_price:.2f} - ${self.max_price:.2f}")
        print(f"📉 Pump Threshold: {self.pump_threshold*100:.0f}%+")
        print(f"⏰ Last Scan: {self.last_scan_time.strftime('%H:%M:%S')}")
        
        if self.active_positions:
            print(f"\n📋 Active Positions:")
            for pos in self.active_positions[:10]:  # Show top 10
                pnl_pct = (pos.pnl / (pos.entry_price * pos.quantity)) * 100
                print(f"   {pos.symbol} ({pos.exchange}): ${pos.entry_price:.4f} → PnL: ${pos.pnl:.2f} ({pnl_pct:+.1f}%)")
        
        print("="*80)
    
    def save_trade_log(self):
        """Save trade log to file"""
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'total_trades': self.total_trades,
            'successful_shorts': self.successful_shorts,
            'total_pnl': self.total_pnl,
            'active_positions': len(self.active_positions),
            'positions': [
                {
                    'symbol': pos.symbol,
                    'exchange': pos.exchange,
                    'entry_price': pos.entry_price,
                    'quantity': pos.quantity,
                    'entry_time': pos.entry_time.isoformat(),
                    'target_price': pos.target_price,
                    'stop_loss': pos.stop_loss,
                    'status': pos.status,
                    'pnl': pos.pnl
                }
                for pos in self.active_positions
            ]
        }
        
        with open('shorting_system_log.json', 'w') as f:
            json.dump(log_data, f, indent=2)
    
    async def run_shorting_system(self):
        """Main system loop"""
        logger.info("🚀 Starting Advanced Shorting System")
        logger.info(f"🎯 Targeting micro-cap coins with 10%+ pumps")
        
        self.is_running = True
        
        while self.is_running:
            try:
                # Scan for pumping coins and place shorts
                await self.scan_and_short()
                
                # Print status every 5 minutes
                if int(time.time()) % 300 == 0:
                    self.print_status()
                    self.save_trade_log()
                
                # Wait before next scan
                await asyncio.sleep(60)  # Scan every minute
                
            except KeyboardInterrupt:
                logger.info("🛑 Received interrupt signal")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                await asyncio.sleep(10)
        
        # Final status
        self.print_status()
        self.save_trade_log()

async def main():
    """Main function"""
    print("🤖 ADVANCED CRYPTO SHORTING SYSTEM")
    print("="*80)
    print("🎯 Automatically shorts micro-cap coins (1¢-10¢) that pump 10%+")
    print("📊 Monitors Binance, Bybit, and KuCoin futures")
    print("⚠️  DEMO MODE - No real trades executed")
    print("="*80)
    
    # Initialize system
    shorting_system = AdvancedShortingSystem()
    
    # Run the system
    await shorting_system.run_shorting_system()

if __name__ == "__main__":
    asyncio.run(main())
