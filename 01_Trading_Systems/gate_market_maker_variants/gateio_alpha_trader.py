#!/usr/bin/env python3
"""
Gate.io Alpha Trading Bot with Order Execution & P&L Tracking
Real trading with alpha generation and comprehensive P&L analytics
"""

import asyncio
import aiohttp
import json
import logging
import hmac
import hashlib
import time
import os
from decimal import Decimal, ROUND_DOWN
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('gateio_alpha_trader.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class Order:
    symbol: str
    side: str  # 'buy' or 'sell'
    order_type: str  # 'limit', 'market'
    amount: Decimal
    price: Optional[Decimal] = None
    order_id: Optional[str] = None
    status: str = 'pending'
    filled_amount: Decimal = Decimal('0')
    filled_price: Optional[Decimal] = None
    timestamp: Optional[datetime] = None
    fee: Decimal = Decimal('0')

@dataclass
class Position:
    symbol: str
    side: str  # 'long' or 'short'
    size: Decimal
    entry_price: Decimal
    current_price: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal
    timestamp: datetime

@dataclass
class TradeSignal:
    symbol: str
    side: str
    confidence: float
    entry_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    reasoning: str

class GateIOAlphaTrader:
    def __init__(self, api_key: str, api_secret: str, testnet: bool = False):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.gateio.ws/api/v4" if not testnet else "https://api.gateio.ws/api/v4"
        self.ws_url = "wss://api.gateio.ws/ws/v4/" if not testnet else "wss://api.gateio.ws/ws/v4/"
        
        self.session: Optional[aiohttp.ClientSession] = None
        self.positions: Dict[str, Position] = {}
        self.orders: List[Order] = []
        self.trades: List[Dict] = []
        self.balance: Dict[str, Decimal] = {}
        self.running = False
        
        # Alpha parameters
        self.risk_per_trade = Decimal('0.02')  # 2% risk per trade
        self.max_positions = 5
        self.min_order_size = Decimal('10')  # USDT minimum
        
    async def start(self):
        """Start the trading bot"""
        self.session = aiohttp.ClientSession()
        self.running = True
        
        logger.info("🚀 Gate.io Alpha Trader starting...")
        
        # Initialize account data
        await self.update_balance()
        await self.update_positions()
        
        # Start main trading loop
        await self.trading_loop()
        
    async def stop(self):
        """Stop the trading bot"""
        self.running = False
        if self.session:
            await self.session.close()
        logger.info("🛑 Gate.io Alpha Trader stopped")
        
    def _sign(self, method: str, url: str, params: str = '') -> str:
        """Generate signature for API requests"""
        message = method + url + params
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        return signature
        
    async def _request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated API request"""
        if not self.session:
            raise RuntimeError("Session not initialized")
            
        url = f"{self.base_url}{endpoint}"
        params_str = ''
        
        if method == 'GET' and params:
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            url += f"?{query_string}"
            params_str = query_string
        elif method == 'POST' and params:
            params_str = json.dumps(params)
            
        headers = {
            'KEY': self.api_key,
            'SIGN': self._sign(method, endpoint, params_str),
            'Content-Type': 'application/json'
        }
        
        async with self.session.request(method, url, headers=headers, data=params_str if method == 'POST' else None) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(f"API Error {response.status}: {error_text}")
                raise Exception(f"API request failed: {response.status} - {error_text}")
            return await response.json()
            
    async def get_balance(self) -> Dict:
        """Get account balance"""
        try:
            result = await self._request('GET', '/spot/accounts')
            balance = {}
            for item in result:
                currency = item['currency']
                available = Decimal(str(item['available']))
                if available > 0:
                    balance[currency] = available
            return balance
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {}
            
    async def update_balance(self):
        """Update account balance"""
        self.balance = await self.get_balance()
        logger.info(f"💰 Balance updated: {dict(self.balance)}")
        
    async def get_ticker(self, symbol: str) -> Dict:
        """Get ticker data for symbol"""
        try:
            result = await self._request('GET', f'/spot/tickers', {'currency_pair': symbol})
            if result:
                return result[0]
            return {}
        except Exception as e:
            logger.error(f"Failed to get ticker for {symbol}: {e}")
            return {}
            
    async def get_orderbook(self, symbol: str, limit: int = 20) -> Dict:
        """Get orderbook for symbol"""
        try:
            result = await self._request('GET', f'/spot/order_book', {'currency_pair': symbol, 'limit': limit})
            return result
        except Exception as e:
            logger.error(f"Failed to get orderbook for {symbol}: {e}")
            return {}
            
    async def place_order(self, order: Order) -> Dict:
        """Place an order"""
        try:
            params = {
                'currency_pair': order.symbol,
                'side': order.side,
                'amount': str(order.amount),
                'type': order.order_type
            }
            
            if order.order_type == 'limit' and order.price:
                params['price'] = str(order.price)
                
            result = await self._request('POST', '/spot/orders', params)
            order.order_id = result['id']
            order.status = result['status']
            order.timestamp = datetime.now()
            
            logger.info(f"📈 Order placed: {order.side.upper()} {order.amount} {order.symbol} @ {order.price}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to place order: {e}")
            order.status = 'failed'
            return {}
            
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an order"""
        try:
            await self._request('DELETE', f'/spot/orders/{order_id}', {'currency_pair': symbol})
            logger.info(f"❌ Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False
            
    async def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """Get open orders"""
        try:
            params = {}
            if symbol:
                params['currency_pair'] = symbol
            result = await self._request('GET', '/spot/orders', params)
            return result
        except Exception as e:
            logger.error(f"Failed to get open orders: {e}")
            return []
            
    async def get_order_status(self, order_id: str, symbol: str) -> Dict:
        """Get order status"""
        try:
            result = await self._request('GET', f'/spot/orders/{order_id}', {'currency_pair': symbol})
            return result
        except Exception as e:
            logger.error(f"Failed to get order status: {e}")
            return {}
            
    def generate_alpha_signal(self, symbol: str, market_data: Dict) -> Optional[TradeSignal]:
        """Generate alpha trading signals using simple technical analysis"""
        try:
            # Get ticker data
            ticker = market_data.get('ticker', {})
            if not ticker:
                return None
                
            current_price = Decimal(str(ticker.get('last', 0)))
            volume = Decimal(str(ticker.get('base_volume', 0)))
            change_24h = float(ticker.get('change_percentage', 0))
            
            # Simple momentum strategy
            if change_24h > 3.0 and volume > 1000000:  # Strong uptrend with volume
                return TradeSignal(
                    symbol=symbol,
                    side='buy',
                    confidence=0.7,
                    entry_price=current_price,
                    stop_loss=current_price * Decimal('0.98'),  # 2% stop loss
                    take_profit=current_price * Decimal('1.05'),  # 5% take profit
                    reasoning=f"Strong momentum: {change_24h:.2f}% change, high volume"
                )
            elif change_24h < -3.0 and volume > 1000000:  # Strong downtrend with volume
                return TradeSignal(
                    symbol=symbol,
                    side='sell',
                    confidence=0.7,
                    entry_price=current_price,
                    stop_loss=current_price * Decimal('1.02'),  # 2% stop loss
                    take_profit=current_price * Decimal('0.95'),  # 5% take profit
                    reasoning=f"Strong reversal: {change_24h:.2f}% change, high volume"
                )
                
            return None
            
        except Exception as e:
            logger.error(f"Failed to generate signal for {symbol}: {e}")
            return None
            
    def calculate_position_size(self, signal: TradeSignal) -> Decimal:
        """Calculate position size based on risk management"""
        try:
            # Get available USDT balance
            usdt_balance = self.balance.get('USDT', Decimal('0'))
            
            # Calculate risk amount
            risk_amount = usdt_balance * self.risk_per_trade
            
            # Calculate position size based on stop loss
            risk_per_unit = abs(signal.entry_price - signal.stop_loss)
            if risk_per_unit == 0:
                return Decimal('0')
                
            position_size = risk_amount / risk_per_unit
            
            # Apply minimum order size
            if position_size * signal.entry_price < self.min_order_size:
                return Decimal('0')
                
            # Cap position size to 20% of balance
            max_position = (usdt_balance * Decimal('0.2')) / signal.entry_price
            position_size = min(position_size, max_position)
            
            return position_size
            
        except Exception as e:
            logger.error(f"Failed to calculate position size: {e}")
            return Decimal('0')
            
    async def execute_signal(self, signal: TradeSignal) -> bool:
        """Execute a trading signal"""
        try:
            # Check if we already have position in this symbol
            if signal.symbol in self.positions:
                logger.info(f"Already have position in {signal.symbol}, skipping signal")
                return False
                
            # Check max positions limit
            if len(self.positions) >= self.max_positions:
                logger.info(f"Max positions reached ({self.max_positions}), skipping signal")
                return False
                
            # Calculate position size
            position_size = self.calculate_position_size(signal)
            if position_size == 0:
                logger.info(f"Position size too small for {signal.symbol}")
                return False
                
            # Place order
            order = Order(
                symbol=signal.symbol,
                side=signal.side,
                order_type='limit',
                amount=position_size,
                price=signal.entry_price
            )
            
            result = await self.place_order(order)
            if not result:
                return False
                
            # Track order
            self.orders.append(order)
            
            # Create position tracking
            self.positions[signal.symbol] = Position(
                symbol=signal.symbol,
                side='long' if signal.side == 'buy' else 'short',
                size=position_size,
                entry_price=signal.entry_price,
                current_price=signal.entry_price,
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0'),
                timestamp=datetime.now()
            )
            
            logger.info(f"✅ Signal executed: {signal.side.upper()} {position_size} {signal.symbol} @ {signal.entry_price}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to execute signal: {e}")
            return False
            
    async def update_positions(self):
        """Update position status and P&L"""
        try:
            for symbol, position in list(self.positions.items()):
                # Get current price
                ticker = await self.get_ticker(symbol)
                if ticker:
                    current_price = Decimal(str(ticker['last']))
                    position.current_price = current_price
                    
                    # Calculate unrealized P&L
                    if position.side == 'long':
                        position.unrealized_pnl = (current_price - position.entry_price) * position.size
                    else:
                        position.unrealized_pnl = (position.entry_price - current_price) * position.size
                        
            # Log positions
            total_pnl = sum(pos.unrealized_pnl for pos in self.positions.values())
            logger.info(f"📊 Positions: {len(self.positions)}, Total P&L: {total_pnl:.2f} USDT")
            
        except Exception as e:
            logger.error(f"Failed to update positions: {e}")
            
    async def manage_positions(self):
        """Manage open positions (stop loss, take profit)"""
        try:
            for symbol, position in list(self.positions.items()):
                current_price = position.current_price
                
                # Check stop loss
                if position.side == 'long' and current_price <= position.entry_price * Decimal('0.98'):
                    logger.info(f"🛑 Stop loss triggered for {symbol}")
                    await self.close_position(symbol, reason='stop_loss')
                elif position.side == 'short' and current_price >= position.entry_price * Decimal('1.02'):
                    logger.info(f"🛑 Stop loss triggered for {symbol}")
                    await self.close_position(symbol, reason='stop_loss')
                    
                # Check take profit
                elif position.side == 'long' and current_price >= position.entry_price * Decimal('1.05'):
                    logger.info(f"🎯 Take profit triggered for {symbol}")
                    await self.close_position(symbol, reason='take_profit')
                elif position.side == 'short' and current_price <= position.entry_price * Decimal('0.95'):
                    logger.info(f"🎯 Take profit triggered for {symbol}")
                    await self.close_position(symbol, reason='take_profit')
                    
        except Exception as e:
            logger.error(f"Failed to manage positions: {e}")
            
    async def close_position(self, symbol: str, reason: str = 'manual'):
        """Close a position"""
        try:
            if symbol not in self.positions:
                return
                
            position = self.positions[symbol]
            
            # Determine order side to close
            close_side = 'sell' if position.side == 'long' else 'buy'
            
            # Place closing order
            order = Order(
                symbol=symbol,
                side=close_side,
                order_type='market',
                amount=position.size
            )
            
            result = await self.place_order(order)
            if result:
                # Update position
                position.realized_pnl = position.unrealized_pnl
                
                # Record trade
                trade = {
                    'symbol': symbol,
                    'side': position.side,
                    'size': float(position.size),
                    'entry_price': float(position.entry_price),
                    'exit_price': float(position.current_price),
                    'pnl': float(position.realized_pnl),
                    'reason': reason,
                    'timestamp': datetime.now().isoformat()
                }
                self.trades.append(trade)
                
                # Remove position
                del self.positions[symbol]
                
                logger.info(f"✅ Position closed: {symbol}, P&L: {position.realized_pnl:.2f} USDT")
                
        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            
    async def trading_loop(self):
        """Main trading loop"""
        symbols = ['BTC_USDT', 'ETH_USDT', 'SOL_USDT', 'DOGE_USDT', 'SHIB_USDT']
        
        while self.running:
            try:
                logger.info("🔄 Trading cycle started...")
                
                # Update balance and positions
                await self.update_balance()
                await self.update_positions()
                
                # Generate and execute signals
                for symbol in symbols:
                    try:
                        # Get market data
                        ticker = await self.get_ticker(symbol)
                        market_data = {'ticker': ticker}
                        
                        # Generate signal
                        signal = self.generate_alpha_signal(symbol, market_data)
                        if signal and signal.confidence > 0.6:
                            logger.info(f"🎯 Signal generated: {signal.side.upper()} {symbol} - {signal.reasoning}")
                            await self.execute_signal(signal)
                            
                    except Exception as e:
                        logger.error(f"Error processing {symbol}: {e}")
                        
                # Manage existing positions
                await self.manage_positions()
                
                # Print daily P&L summary
                await self.print_daily_summary()
                
                # Wait for next cycle
                await asyncio.sleep(60)  # 1 minute cycles
                
            except Exception as e:
                logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(10)
                
    async def print_daily_summary(self):
        """Print daily P&L summary"""
        try:
            today = datetime.now().date()
            today_trades = [t for t in self.trades if datetime.fromisoformat(t['timestamp']).date() == today]
            
            if today_trades:
                total_pnl = sum(t['pnl'] for t in today_trades)
                win_rate = len([t for t in today_trades if t['pnl'] > 0]) / len(today_trades) * 100
                
                logger.info(f"📈 Daily Summary - Trades: {len(today_trades)}, P&L: {total_pnl:.2f} USDT, Win Rate: {win_rate:.1f}%")
                
        except Exception as e:
            logger.error(f"Failed to print daily summary: {e}")

async def main():
    """Main function"""
    # Get API credentials from environment
    api_key = os.getenv('GATEIO_API_KEY')
    api_secret = os.getenv('GATEIO_API_SECRET')
    
    if not api_key or not api_secret:
        logger.error("❌ Please set GATEIO_API_KEY and GATEIO_API_SECRET environment variables")
        return
        
    # Create and start trader
    trader = GateIOAlphaTrader(api_key, api_secret, testnet=False)
    
    try:
        await trader.start()
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
        await trader.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await trader.stop()

if __name__ == "__main__":
    asyncio.run(main())
