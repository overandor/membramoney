#!/usr/bin/env python3
"""
TRADING ENGINE FOR ENA HEDGING SYSTEM
Core trading logic and order management
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple
import gate_api
from gate_api import ApiClient, Configuration, FuturesApi

log = logging.getLogger(__name__)

class OrderManager:
    """Manages order placement and tracking"""
    
    def __init__(self, config, api_client):
        self.config = config
        self.api = api_client
        self.active_orders = {}  # order_id -> order info
        self.order_history = []  # Order history
        self.pending_orders = {}  # client_order_id -> order info
        
    async def place_limit_order(self, symbol: str, side: str, size: float, 
                               price: float, client_order_id: str = None,
                               post_only: bool = True) -> Optional[str]:
        """Place a limit order"""
        try:
            if not client_order_id:
                client_order_id = f"order_{int(time.time() * 1000)}"
            
            order = gate_api.FuturesOrder(
                contract=symbol,
                size=size,
                price=price,
                side=side,
                type='limit',
                time_in_force='post_only' if post_only else 'gtc',
                client_order_id=client_order_id
            )
            
            result = self.api.create_futures_order(settle='usdt', order=order)
            
            order_info = {
                'order_id': result.id,
                'client_order_id': client_order_id,
                'symbol': symbol,
                'side': side,
                'size': size,
                'price': price,
                'status': result.status,
                'filled_size': result.filled_size,
                'created_time': time.time(),
                'type': 'limit'
            }
            
            self.active_orders[result.id] = order_info
            self.pending_orders[client_order_id] = order_info
            
            log.info(f"📈 Limit order placed: {side.upper()} {size:.6f} @ ${price:.6f} (ID: {result.id})")
            return result.id
            
        except Exception as e:
            log.error(f"❌ Failed to place limit order: {e}")
            return None
    
    async def place_market_order(self, symbol: str, side: str, size: float,
                                client_order_id: str = None) -> Optional[str]:
        """Place a market order"""
        try:
            if not client_order_id:
                client_order_id = f"market_{int(time.time() * 1000)}"
            
            order = gate_api.FuturesOrder(
                contract=symbol,
                size=size,
                side=side,
                type='market',
                client_order_id=client_order_id
            )
            
            result = self.api.create_futures_order(settle='usdt', order=order)
            
            order_info = {
                'order_id': result.id,
                'client_order_id': client_order_id,
                'symbol': symbol,
                'side': side,
                'size': size,
                'status': result.status,
                'filled_size': result.filled_size,
                'created_time': time.time(),
                'type': 'market'
            }
            
            self.active_orders[result.id] = order_info
            self.pending_orders[client_order_id] = order_info
            
            log.info(f"⚡ Market order placed: {side.upper()} {size:.6f} (ID: {result.id})")
            return result.id
            
        except Exception as e:
            log.error(f"❌ Failed to place market order: {e}")
            return None
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        try:
            result = self.api.cancel_futures_order(settle='usdt', order_id=order_id)
            
            if order_id in self.active_orders:
                order_info = self.active_orders[order_id]
                order_info['status'] = 'cancelled'
                order_info['cancelled_time'] = time.time()
                self.order_history.append(order_info)
                del self.active_orders[order_id]
            
            log.info(f"❌ Order cancelled: {order_id}")
            return True
            
        except Exception as e:
            log.error(f"❌ Failed to cancel order {order_id}: {e}")
            return False
    
    async def cancel_all_orders(self, symbol: str = None) -> int:
        """Cancel all orders (optionally for specific symbol)"""
        try:
            if symbol:
                # Cancel specific symbol orders
                orders_to_cancel = [
                    order_id for order_id, order_info in self.active_orders.items()
                    if order_info['symbol'] == symbol
                ]
            else:
                # Cancel all orders
                orders_to_cancel = list(self.active_orders.keys())
            
            cancelled_count = 0
            for order_id in orders_to_cancel:
                if await self.cancel_order(order_id):
                    cancelled_count += 1
            
            log.info(f"🗑️ Cancelled {cancelled_count} orders")
            return cancelled_count
            
        except Exception as e:
            log.error(f"❌ Failed to cancel orders: {e}")
            return 0
    
    async def update_order_status(self, order_id: str) -> bool:
        """Update order status from exchange"""
        try:
            result = self.api.get_futures_order(settle='usdt', order_id=order_id)
            
            if order_id in self.active_orders:
                order_info = self.active_orders[order_id]
                old_status = order_info['status']
                
                order_info.update({
                    'status': result.status,
                    'filled_size': result.filled_size,
                    'updated_time': time.time()
                })
                
                # Move to history if filled or cancelled
                if result.status in ['filled', 'cancelled']:
                    self.order_history.append(order_info)
                    del self.active_orders[order_id]
                    
                    if old_status != result.status:
                        log.info(f"📊 Order {order_id} status: {old_status} -> {result.status}")
                
                return True
            else:
                # Order might be in pending orders
                for client_id, order_info in list(self.pending_orders.items()):
                    if order_info['order_id'] == order_id:
                        order_info.update({
                            'status': result.status,
                            'filled_size': result.filled_size,
                            'updated_time': time.time()
                        })
                        break
                
        except Exception as e:
            log.error(f"❌ Failed to update order status {order_id}: {e}")
            return False
    
    async def get_active_orders(self, symbol: str = None) -> List[Dict]:
        """Get active orders (optionally for specific symbol)"""
        if symbol:
            return [
                order_info for order_info in self.active_orders.values()
                if order_info['symbol'] == symbol
            ]
        return list(self.active_orders.values())
    
    def get_order_info(self, order_id: str) -> Optional[Dict]:
        """Get order information"""
        return self.active_orders.get(order_id)

class PositionManager:
    """Manages position tracking and risk"""
    
    def __init__(self, config, api_client):
        self.config = config
        self.api = api_client
        self.positions = {}  # symbol -> position info
        self.last_update = 0
        
    async def update_positions(self) -> bool:
        """Update positions from exchange"""
        try:
            positions = self.api.list_futures_positions(settle='usdt')
            
            new_positions = {}
            for pos in positions:
                if float(pos.size) != 0:  # Only non-zero positions
                    symbol = pos.contract
                    position_info = {
                        'symbol': symbol,
                        'size': float(pos.size),
                        'side': 'long' if float(pos.size) > 0 else 'short',
                        'entry_price': float(pos.entry_price),
                        'mark_price': float(pos.mark_price),
                        'unrealized_pnl': float(pos.unrealised_pnl),
                        'percentage_pnl': float(pos.unrealised_pnl) / (float(pos.size) * float(pos.entry_price)) * 100 if float(pos.size) * float(pos.entry_price) != 0 else 0,
                        'margin': float(pos.margin),
                        'leverage': float(pos.leverage),
                        'updated_time': time.time()
                    }
                    new_positions[symbol] = position_info
            
            self.positions = new_positions
            self.last_update = time.time()
            
            # Log positions
            for symbol, pos in self.positions.items():
                log.info(f"📊 Position {symbol}: {pos['side']} {abs(pos['size']):.6f} @ ${pos['entry_price']:.6f} (PnL: ${pos['unrealized_pnl']:.4f})")
            
            return True
            
        except Exception as e:
            log.error(f"❌ Failed to update positions: {e}")
            return False
    
    def get_position(self, symbol: str) -> Optional[Dict]:
        """Get position for specific symbol"""
        return self.positions.get(symbol)
    
    def get_total_exposure(self) -> float:
        """Get total exposure across all positions"""
        return sum(abs(pos['size']) for pos in self.positions.values())
    
    def get_total_unrealized_pnl(self) -> float:
        """Get total unrealized PnL"""
        return sum(pos['unrealized_pnl'] for pos in self.positions.values())

class BalanceManager:
    """Manages balance tracking and risk limits"""
    
    def __init__(self, config, api_client):
        self.config = config
        self.api = api_client
        self.balance_info = {}
        self.last_update = 0
        
    async def update_balance(self) -> bool:
        """Update balance from exchange"""
        try:
            account = self.api.get_futures_account(settle='usdt')
            
            self.balance_info = {
                'total': float(account.total),
                'available': float(account.available),
                'used': float(account.used),
                'unrealized_pnl': float(account.unrealised_pnl),
                'margin': float(account.margin),
                'margin_free': float(account.margin_free),
                'margin_ratio': float(account.margin_ratio) if account.margin_ratio else 0,
                'maintenance_margin': float(account.maintenance_margin) if account.maintenance_margin else 0,
                'updated_time': time.time()
            }
            
            self.last_update = time.time()
            log.info(f"💰 Balance: ${self.balance_info['available']:.2f} available, ${self.balance_info['total']:.2f} total")
            return True
            
        except Exception as e:
            log.error(f"❌ Failed to update balance: {e}")
            return False
    
    def get_available_balance(self) -> float:
        """Get available balance"""
        return self.balance_info.get('available', 0.0)
    
    def get_total_balance(self) -> float:
        """Get total balance"""
        return self.balance_info.get('total', 0.0)
    
    def get_margin_ratio(self) -> float:
        """Get margin ratio"""
        return self.balance_info.get('margin_ratio', 0.0)
    
    def is_margin_safe(self) -> bool:
        """Check if margin ratio is safe"""
        margin_ratio = self.get_margin_ratio()
        return margin_ratio > 0.1  # 10% minimum margin ratio
    
    def can_afford_order(self, order_value_usd: float) -> bool:
        """Check if we can afford an order"""
        available = self.get_available_balance()
        return available >= order_value_usd * 1.1  # 10% buffer

class TradingEngine:
    """Main trading engine coordinating all components"""
    
    def __init__(self, config, ui):
        self.config = config
        self.ui = ui
        
        # Initialize API
        cfg = Configuration(key=config.api_key, secret=config.api_secret)
        self.api = FuturesApi(ApiClient(cfg))
        
        # Initialize managers
        self.order_manager = OrderManager(config, self.api)
        self.position_manager = PositionManager(config, self.api)
        self.balance_manager = BalanceManager(config, self.api)
        
        # Trading state
        self.is_trading = False
        self.current_symbol = config.symbol
        
        # Statistics
        self.stats = {
            'orders_placed': 0,
            'orders_filled': 0,
            'orders_cancelled': 0,
            'total_volume': 0.0,
            'total_pnl': 0.0,
            'start_time': time.time()
        }
    
    async def initialize(self) -> bool:
        """Initialize trading engine"""
        try:
            # Update initial data
            await self.update_all_data()
            
            # Cancel any existing orders
            cancelled = await self.order_manager.cancel_all_orders(self.current_symbol)
            if cancelled > 0:
                self.ui.add_log(f"🗑️ Cancelled {cancelled} existing orders", 'WARNING')
            
            self.ui.add_log("✅ Trading engine initialized", 'SUCCESS')
            return True
            
        except Exception as e:
            self.ui.add_log(f"❌ Failed to initialize trading engine: {e}", 'ERROR')
            return False
    
    async def update_all_data(self):
        """Update all trading data"""
        await asyncio.gather(
            self.balance_manager.update_balance(),
            self.position_manager.update_positions()
        )
    
    async def place_hedge_order(self, side: str, price: float, size: float) -> Optional[str]:
        """Place a hedge order"""
        if not self.is_trading:
            self.ui.add_log("⚠️ Trading not active", 'WARNING')
            return None
        
        # Check if we can afford the order
        order_value = size * price
        if not self.balance_manager.can_afford_order(order_value):
            self.ui.add_log(f"❌ Insufficient balance for order: ${order_value:.2f}", 'ERROR')
            return None
        
        # Place the order
        order_id = await self.order_manager.place_limit_order(
            self.current_symbol, side, size, price, 
            client_order_id=f"hedge_{int(time.time() * 1000)}",
            post_only=True
        )
        
        if order_id:
            self.stats['orders_placed'] += 1
            self.ui.add_log(f"🛡️ HEDGE PLACED: {side.upper()} {size:.6f} @ ${price:.6f}", 'HEDGE')
        
        return order_id
    
    async def close_hedge_position(self, hedge_info: Dict, close_price: float, reason: str) -> bool:
        """Close a hedge position with market order"""
        if not self.is_trading:
            return False
        
        try:
            close_side = 'sell' if hedge_info['side'] == 'buy' else 'buy'
            
            # Place market order to close
            order_id = await self.order_manager.place_market_order(
                self.current_symbol, close_side, hedge_info['size'],
                client_order_id=f"close_hedge_{int(time.time() * 1000)}"
            )
            
            if order_id:
                # Calculate profit
                if hedge_info['side'] == 'buy':
                    profit_per_unit = close_price - hedge_info['price']
                else:
                    profit_per_unit = hedge_info['price'] - close_price
                
                total_profit = profit_per_unit * hedge_info['size']
                
                # Update statistics
                self.stats['total_pnl'] += total_profit
                
                profit_color = "+" if total_profit >= 0 else ""
                self.ui.add_log(f"💰 HEDGE CLOSED ({reason}): ${profit_color}{total_profit:.4f}", 
                              'PROFIT' if total_profit >= 0 else 'LOSS')
                
                return True
            
        except Exception as e:
            self.ui.add_log(f"❌ Failed to close hedge: {e}", 'ERROR')
        
        return False
    
    async def check_risk_limits(self) -> bool:
        """Check if current risk is within limits"""
        # Check margin ratio
        if not self.balance_manager.is_margin_safe():
            self.ui.add_log("⚠️ Margin ratio too low, stopping trading", 'ERROR')
            return False
        
        # Check daily loss limit
        if self.stats['total_pnl'] < -self.config.max_daily_loss_usd:
            self.ui.add_log(f"⚠️ Daily loss limit reached: ${self.stats['total_pnl']:.2f}", 'ERROR')
            return False
        
        # Check position limits
        position = self.position_manager.get_position(self.current_symbol)
        if position and abs(position['size']) > self.config.max_hedge_position:
            self.ui.add_log(f"⚠️ Position limit exceeded: {abs(position['size']):.6f}", 'ERROR')
            return False
        
        return True
    
    async def emergency_stop(self):
        """Emergency stop all trading"""
        self.is_trading = False
        
        # Cancel all orders
        cancelled = await self.order_manager.cancel_all_orders()
        self.ui.add_log(f"🛑 Emergency stop: Cancelled {cancelled} orders", 'ERROR')
        
        # Close all positions if configured
        if hasattr(self.config, 'emergency_close_positions') and self.config.emergency_close_positions:
            # Implementation for closing positions would go here
            self.ui.add_log("🛑 Emergency position closing not implemented", 'WARNING')
    
    def set_symbol(self, symbol: str):
        """Change trading symbol"""
        self.current_symbol = symbol
        self.config.symbol = symbol
        self.config.update_symbol_config(symbol)
        self.ui.add_log(f"📊 Symbol changed to: {symbol}", 'INFO')
    
    def start_trading(self):
        """Start trading"""
        self.is_trading = True
        self.ui.add_log(f"🚀 Trading started for {self.current_symbol}", 'SUCCESS')
    
    def stop_trading(self):
        """Stop trading"""
        self.is_trading = False
        self.ui.add_log("⏹️ Trading stopped", 'WARNING')
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        runtime = time.time() - self.stats['start_time']
        
        return {
            **self.stats,
            'runtime_hours': runtime / 3600,
            'orders_per_hour': self.stats['orders_placed'] / (runtime / 3600) if runtime > 0 else 0,
            'current_symbol': self.current_symbol,
            'is_trading': self.is_trading,
            'available_balance': self.balance_manager.get_available_balance(),
            'total_balance': self.balance_manager.get_total_balance(),
            'current_position': self.position_manager.get_position(self.current_symbol)
        }
