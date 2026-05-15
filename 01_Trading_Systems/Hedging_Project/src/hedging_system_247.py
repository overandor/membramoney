#!/usr/bin/env python3
"""
24/7 Professional Hedging System
Continuous trading with proper exchange integration
"""

import os
import sys
import time
import json
import signal
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add project path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.gateio_client import GateIOClient
from utils.position_manager import PositionManager

class HedgingSystem247:
    """24/7 Professional hedging system"""
    
    def __init__(self):
        # Environment variables
        self.gate_api_key = os.getenv("GATE_API_KEY", "")
        self.gate_api_secret = os.getenv("GATE_API_SECRET", "")
        self.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        
        # Validate environment
        self._validate_environment()
        
        # Configuration
        self.symbol = "ENA_USDT"
        self.min_nominal = 0.01
        self.max_nominal = 0.10
        self.target_nominal = (self.min_nominal + self.max_nominal) / 2
        
        # Initialize clients
        self.client = GateIOClient()
        self.position_manager = PositionManager(self.client, profit_threshold=0.002)
        
        # Setup logging
        self._setup_logging()
        
        # System state
        self.running = False
        self.shutdown_requested = False
        self.cycle_count = 0
        self.start_time = None
        self.last_trade_time = None
        self.daily_stats = {
            'orders_placed': 0,
            'profits_taken': 0,
            'errors': 0,
            'total_pnl': 0.0
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("🚀 24/7 Hedging System initialized")
        self.logger.info(f"🔑 Gate.io API: {'✅ Configured' if self.gate_api_key else '❌ Missing'}")
        self.logger.info(f"🤖 OpenRouter API: {'✅ Configured' if self.openrouter_api_key else '❌ Missing'}")
        self.logger.info(f"📊 Trading Symbol: {self.symbol}")
        self.logger.info(f"💰 Nominal Range: ${self.min_nominal}-${self.max_nominal}")
    
    def _validate_environment(self):
        """Validate required environment variables"""
        missing = []
        
        if not self.gate_api_key:
            missing.append("GATE_API_KEY")
        if not self.gate_api_secret:
            missing.append("GATE_API_SECRET")
        
        if missing:
            print(f"❌ Missing environment variables: {', '.join(missing)}")
            print("Please set them and restart:")
            for var in missing:
                print(f"   export {var}='your-value'")
            sys.exit(1)
    
    def _setup_logging(self):
        """Setup comprehensive logging"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'hedging_247_{datetime.now().strftime("%Y%m%d")}.log')
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='a'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger('Hedging247')
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.running = False
    
    def test_exchange_connection(self) -> bool:
        """Test connection to Gate.io exchange"""
        self.logger.info("🔍 Testing exchange connection...")
        
        try:
            # Test public endpoint
            contracts = self.client.get_contracts()
            if contracts.success:
                self.logger.info(f"✅ Exchange connected: {len(contracts.data)} contracts available")
            else:
                self.logger.error(f"❌ Exchange connection failed: {contracts.error}")
                return False
            
            # Test private endpoint
            if self.gate_api_key and self.gate_api_secret:
                account = self.client.get_account()
                if account.success:
                    balance = float(account.data.get('total', 0))
                    self.logger.info(f"✅ Account connected: Balance ${balance:.2f}")
                else:
                    self.logger.error(f"❌ Account connection failed: {account.error}")
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Connection test failed: {e}")
            return False
    
    def get_market_status(self) -> Dict:
        """Get comprehensive market status"""
        try:
            best_bid, best_ask = self.client.get_best_bid_ask(self.symbol)
            positions = self.position_manager.get_positions()
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'symbol': self.symbol,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread_pct': ((best_ask - best_bid) / best_bid * 100) if best_bid and best_ask else None,
                'position_count': len(positions),
                'total_position_size': sum(abs(p.size) for p in positions),
                'unrealized_pnl': sum(p.unrealized_pnl for p in positions),
                'exchange_connected': True
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"❌ Market status error: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'symbol': self.symbol,
                'exchange_connected': False,
                'error': str(e)
            }
    
    def place_best_bid_ask_orders(self) -> int:
        """Place orders at best bid and ask prices"""
        orders_placed = 0
        
        try:
            best_bid, best_ask = self.client.get_best_bid_ask(self.symbol)
            
            if not best_bid or not best_ask:
                self.logger.warning("❌ Cannot get market prices")
                return 0
            
            # Calculate order sizes
            bid_size = self.client.calculate_nominal_size(best_bid, self.target_nominal)
            ask_size = self.client.calculate_nominal_size(best_ask, self.target_nominal)
            
            nominal_bid = bid_size * best_bid
            nominal_ask = ask_size * best_ask
            
            # Place buy order at best bid
            bid_result = self.client.place_order(
                symbol=self.symbol,
                side="BUY",
                size=bid_size,
                price=best_bid,
                order_type="limit",
                tif="ioc"
            )
            
            if bid_result.success:
                order_id = bid_result.data.get('id')
                self.logger.info(f"✅ BUY order placed: {bid_size:.6f} @ ${best_bid:.6f} (nominal: ${nominal_bid:.4f})")
                orders_placed += 1
                self.last_trade_time = time.time()
                self.daily_stats['orders_placed'] += 1
            else:
                self.logger.error(f"❌ BUY order failed: {bid_result.error}")
                self.daily_stats['errors'] += 1
            
            # Place sell order at best ask
            ask_result = self.client.place_order(
                symbol=self.symbol,
                side="SELL",
                size=ask_size,
                price=best_ask,
                order_type="limit",
                tif="ioc"
            )
            
            if ask_result.success:
                order_id = ask_result.data.get('id')
                self.logger.info(f"✅ SELL order placed: {ask_size:.6f} @ ${best_ask:.6f} (nominal: ${nominal_ask:.4f})")
                orders_placed += 1
                self.last_trade_time = time.time()
                self.daily_stats['orders_placed'] += 1
            else:
                self.logger.error(f"❌ SELL order failed: {ask_result.error}")
                self.daily_stats['errors'] += 1
            
        except Exception as e:
            self.logger.error(f"❌ Order placement error: {e}")
            self.daily_stats['errors'] += 1
        
        return orders_placed
    
    def check_and_take_profits(self) -> int:
        """Check for profitable positions and take profits"""
        profits_taken = 0
        
        try:
            profitable_positions = self.position_manager.get_profitable_positions()
            
            for position in profitable_positions:
                if self.position_manager.should_sell_position(position):
                    success = self.position_manager.close_position_for_profit(position)
                    if success:
                        profits_taken += 1
                        self.daily_stats['profits_taken'] += 1
                        self.daily_stats['total_pnl'] += position.unrealized_pnl
                        self.logger.info(f"💰 Profit taken: {position.unrealized_pct:.2%} (${position.unrealized_pnl:.4f})")
            
        except Exception as e:
            self.logger.error(f"❌ Profit taking error: {e}")
            self.daily_stats['errors'] += 1
        
        return profits_taken
    
    def log_system_status(self):
        """Log comprehensive system status"""
        if self.cycle_count % 12 == 0:  # Every minute (assuming 5-second cycles)
            uptime = time.time() - self.start_time if self.start_time else 0
            uptime_str = str(timedelta(seconds=int(uptime)))
            
            status = self.get_market_status()
            
            self.logger.info("📊 SYSTEM STATUS UPDATE")
            self.logger.info(f"⏱️  Uptime: {uptime_str}")
            self.logger.info(f"🔄 Cycles: {self.cycle_count}")
            self.logger.info(f"📈 {self.symbol}: Bid ${status['best_bid']:.6f} | Ask ${status['best_ask']:.6f}")
            if status['spread_pct']:
                self.logger.info(f"📊 Spread: {status['spread_pct']:.3f}%")
            self.logger.info(f"💼 Positions: {status['position_count']} (size: {status.get('total_position_size', 0):.6f})")
            self.logger.info(f"💰 Daily PnL: ${self.daily_stats['total_pnl']:.4f}")
            self.logger.info(f"📈 Daily Stats: {self.daily_stats['orders_placed']} orders, {self.daily_stats['profits_taken']} profits, {self.daily_stats['errors']} errors")
            
            # Check if we haven't traded recently
            if self.last_trade_time:
                time_since_trade = time.time() - self.last_trade_time
                if time_since_trade > 300:  # 5 minutes
                    self.logger.warning(f"⚠️  No trades for {int(time_since_trade/60)} minutes")
    
    def run_hedging_cycle(self):
        """Run one complete hedging cycle"""
        if self.shutdown_requested:
            return
        
        self.cycle_count += 1
        cycle_start = time.time()
        
        try:
            # Place best bid/ask orders
            orders_placed = self.place_best_bid_ask_orders()
            
            # Check for profit opportunities
            profits_taken = self.check_and_take_profits()
            
            # Log status periodically
            self.log_system_status()
            
            # Cycle timing
            elapsed = time.time() - cycle_start
            sleep_time = max(0, 5 - elapsed)  # 5-second cycles
            
            if sleep_time > 0:
                time.sleep(sleep_time)
            
        except Exception as e:
            self.logger.error(f"❌ Cycle {self.cycle_count} error: {e}")
            self.daily_stats['errors'] += 1
            time.sleep(5)  # Wait before retrying
    
    def reset_daily_stats(self):
        """Reset daily statistics at midnight"""
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:
            self.logger.info("📅 Resetting daily statistics")
            self.daily_stats = {
                'orders_placed': 0,
                'profits_taken': 0,
                'errors': 0,
                'total_pnl': 0.0
            }
    
    def run(self):
        """Main 24/7 trading loop"""
        self.logger.info("🚀 Starting 24/7 Professional Hedging System")
        self.logger.info("⚠️  LIVE TRADING MODE - Real orders will be placed!")
        self.logger.info("🔊 Keep Gate.io exchange open to hear order sounds")
        
        # Test exchange connection
        if not self.test_exchange_connection():
            self.logger.error("❌ Exchange connection failed - cannot start trading")
            return
        
        self.start_time = time.time()
        self.running = True
        
        try:
            while self.running and not self.shutdown_requested:
                self.reset_daily_stats()
                self.run_hedging_cycle()
                
        except KeyboardInterrupt:
            self.logger.info("🛑 System stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Fatal system error: {e}")
        finally:
            self.logger.info("✅ 24/7 Hedging System shutdown complete")
            
            # Final status
            if self.start_time:
                total_uptime = time.time() - self.start_time
                self.logger.info(f"📊 Final Stats:")
                self.logger.info(f"   Total uptime: {str(timedelta(seconds=int(total_uptime)))}")
                self.logger.info(f"   Total cycles: {self.cycle_count}")
                self.logger.info(f"   Daily orders: {self.daily_stats['orders_placed']}")
                self.logger.info(f"   Daily profits: {self.daily_stats['profits_taken']}")
                self.logger.info(f"   Daily PnL: ${self.daily_stats['total_pnl']:.4f}")

def main():
    """Main entry point"""
    print("🚀 24/7 PROFESSIONAL HEDGING SYSTEM")
    print("=" * 50)
    print("📊 Continuous Gate.io Futures Trading")
    print("💰 Nominal Value: $0.01-$0.10 per trade")
    print("🔊 Listen for exchange sounds on successful orders")
    print("=" * 50)
    
    # Create and run 24/7 system
    system = HedgingSystem247()
    system.run()

if __name__ == "__main__":
    main()
