#!/usr/bin/env python3
"""
Fully Connected 24/7 Hedging System
Proper API integration and AI configuration
"""

import os
import sys
import time
import signal
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Add project path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.enhanced_gateio_client import EnhancedGateIOClient

class ConnectedHedgingSystem:
    """Fully connected 24/7 hedging system with AI"""
    
    def __init__(self):
        # Initialize enhanced client
        self.client = EnhancedGateIOClient()
        
        # Configuration
        self.symbol = "ENA_USDT"
        self.min_nominal = 0.01
        self.max_nominal = 0.10
        self.target_nominal = (self.min_nominal + self.max_nominal) / 2
        self.profit_threshold = 0.002  # 0.2%
        
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
            'total_pnl': 0.0,
            'ai_decisions': 0
        }
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.logger.info("🚀 Connected Hedging System initialized")
        self.logger.info(f"📊 Symbol: {self.symbol}")
        self.logger.info(f"💰 Nominal Range: ${self.min_nominal}-${self.max_nominal}")
        self.logger.info(f"🎯 Profit Threshold: {self.profit_threshold:.1%}")
    
    def _setup_logging(self):
        """Setup comprehensive logging"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'hedging_connected_{datetime.now().strftime("%Y%m%d")}.log')
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='a'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger('ConnectedHedging')
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        self.running = False
    
    def test_full_connection(self) -> bool:
        """Test complete system connection"""
        self.logger.info("🔍 Testing full system connection...")
        
        # Test API connection
        api_test = self.client.test_connection()
        if not api_test.success:
            self.logger.error(f"❌ API connection failed: {api_test.error}")
            return False
        
        self.logger.info(f"✅ API connected: {api_test.data['contracts_count']} contracts")
        
        # Test market data
        best_bid, best_ask = self.client.get_best_bid_ask(self.symbol)
        if best_bid and best_ask:
            self.logger.info(f"✅ Market data: Bid ${best_bid:.6f} | Ask ${best_ask:.6f}")
        else:
            self.logger.error("❌ Cannot get market data")
            return False
        
        # Test AI connection
        ai_test = self.client.get_ai_decision({
            'symbol': self.symbol,
            'bid': best_bid,
            'ask': best_ask,
            'spread': (best_ask - best_bid) / best_bid
        })
        
        if ai_test:
            self.logger.info(f"✅ AI connected: {ai_test['action']} (confidence: {ai_test['confidence']:.2f})")
        else:
            self.logger.warning("⚠️  AI not available - will run without AI")
        
        return True
    
    def get_market_status(self) -> Dict:
        """Get comprehensive market status"""
        try:
            best_bid, best_ask = self.client.get_best_bid_ask(self.symbol)
            positions_result = self.client.get_positions()
            
            positions = []
            if positions_result.success:
                for pos in positions_result.data:
                    size = float(pos['size'])
                    if size != 0:
                        positions.append({
                            'symbol': pos['contract'],
                            'size': size,
                            'entry_price': float(pos['entry_price']),
                            'unrealized_pnl': float(pos['unrealised_pnl'])
                        })
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'symbol': self.symbol,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread_pct': ((best_ask - best_bid) / best_bid * 100) if best_bid and best_ask else None,
                'position_count': len(positions),
                'total_position_size': sum(abs(p['size']) for p in positions),
                'unrealized_pnl': sum(p['unrealized_pnl'] for p in positions),
                'system_connected': True
            }
            
            return status
            
        except Exception as e:
            self.logger.error(f"❌ Market status error: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'symbol': self.symbol,
                'system_connected': False,
                'error': str(e)
            }
    
    def place_hedging_orders(self) -> int:
        """Place best bid/ask hedging orders"""
        orders_placed = 0
        
        try:
            best_bid, best_ask = self.client.get_best_bid_ask(self.symbol)
            
            if not best_bid or not best_ask:
                self.logger.warning("❌ Cannot get market prices")
                return 0
            
            # Get AI decision
            market_data = {
                'symbol': self.symbol,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'spread': (best_ask - best_bid) / best_bid,
                'timestamp': datetime.now().isoformat()
            }
            
            ai_decision = self.client.get_ai_decision(market_data)
            self.daily_stats['ai_decisions'] += 1
            
            # Calculate order sizes
            bid_size = self.client.calculate_nominal_size(best_bid, self.target_nominal)
            ask_size = self.client.calculate_nominal_size(best_ask, self.target_nominal)
            
            nominal_bid = bid_size * best_bid
            nominal_ask = ask_size * best_ask
            
            # Check AI recommendation
            if ai_decision['action'] == 'BUY' and ai_decision['confidence'] > 0.7:
                # AI suggests buying - place larger buy order
                bid_size *= 1.5
                self.logger.info(f"🤖 AI suggests BUY with confidence {ai_decision['confidence']:.2f}")
            elif ai_decision['action'] == 'SELL' and ai_decision['confidence'] > 0.7:
                # AI suggests selling - place larger sell order
                ask_size *= 1.5
                self.logger.info(f"🤖 AI suggests SELL with confidence {ai_decision['confidence']:.2f}")
            
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
                self.logger.info(f"✅ BUY order: {bid_size:.6f} @ ${best_bid:.6f} (nominal: ${nominal_bid:.4f})")
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
                self.logger.info(f"✅ SELL order: {ask_size:.6f} @ ${best_ask:.6f} (nominal: ${nominal_ask:.4f})")
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
    
    def check_profit_opportunities(self) -> int:
        """Check and take profit opportunities"""
        profits_taken = 0
        
        try:
            positions_result = self.client.get_positions()
            
            if positions_result.success:
                for pos in positions_result.data:
                    size = float(pos['size'])
                    if size == 0:
                        continue
                    
                    entry_price = float(pos['entry_price'])
                    mark_price = float(pos['mark_price'])
                    unrealized_pnl = float(pos['unrealised_pnl'])
                    
                    # Calculate profit percentage
                    profit_pct = (mark_price - entry_price) / entry_price if entry_price > 0 else 0
                    
                    if profit_pct >= self.profit_threshold:
                        # Take profit
                        sell_size = abs(size)
                        sell_result = self.client.place_order(
                            symbol=pos['contract'],
                            side="SELL" if size > 0 else "BUY",
                            size=sell_size,
                            price=0,  # Market order
                            order_type="market"
                        )
                        
                        if sell_result.success:
                            profits_taken += 1
                            self.daily_stats['profits_taken'] += 1
                            self.daily_stats['total_pnl'] += unrealized_pnl
                            self.logger.info(f"💰 Profit taken: {profit_pct:.2%} (${unrealized_pnl:.4f})")
                        else:
                            self.logger.error(f"❌ Profit take failed: {sell_result.error}")
                            self.daily_stats['errors'] += 1
            
        except Exception as e:
            self.logger.error(f"❌ Profit check error: {e}")
            self.daily_stats['errors'] += 1
        
        return profits_taken
    
    def log_system_status(self):
        """Log comprehensive system status"""
        if self.cycle_count % 12 == 0:  # Every minute
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
            self.logger.info(f"🤖 AI Decisions: {self.daily_stats['ai_decisions']}")
            self.logger.info(f"📈 Daily Stats: {self.daily_stats['orders_placed']} orders, {self.daily_stats['profits_taken']} profits, {self.daily_stats['errors']} errors")
            
            # Check trading activity
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
            # Place hedging orders
            orders_placed = self.place_hedging_orders()
            
            # Check profit opportunities
            profits_taken = self.check_profit_opportunities()
            
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
            time.sleep(5)
    
    def run(self):
        """Main 24/7 trading loop"""
        self.logger.info("🚀 Starting Connected 24/7 Hedging System")
        self.logger.info("⚠️  LIVE TRADING MODE - Real orders will be placed!")
        self.logger.info("🔊 Keep Gate.io exchange open to hear order sounds")
        
        # Test full connection
        if not self.test_full_connection():
            self.logger.error("❌ System connection failed - cannot start trading")
            return
        
        self.start_time = time.time()
        self.running = True
        
        try:
            while self.running and not self.shutdown_requested:
                self.run_hedging_cycle()
                
        except KeyboardInterrupt:
            self.logger.info("🛑 System stopped by user")
        except Exception as e:
            self.logger.error(f"❌ Fatal system error: {e}")
        finally:
            self.logger.info("✅ Connected Hedging System shutdown complete")
            
            # Final status
            if self.start_time:
                total_uptime = time.time() - self.start_time
                self.logger.info(f"📊 Final Stats:")
                self.logger.info(f"   Total uptime: {str(timedelta(seconds=int(total_uptime)))}")
                self.logger.info(f"   Total cycles: {self.cycle_count}")
                self.logger.info(f"   AI decisions: {self.daily_stats['ai_decisions']}")
                self.logger.info(f"   Daily orders: {self.daily_stats['orders_placed']}")
                self.logger.info(f"   Daily profits: {self.daily_stats['profits_taken']}")
                self.logger.info(f"   Daily PnL: ${self.daily_stats['total_pnl']:.4f}")

def main():
    """Main entry point"""
    print("🚀 CONNECTED 24/7 HEDGING SYSTEM")
    print("=" * 50)
    print("📊 Gate.io Futures + AI Integration")
    print("💰 Nominal Value: $0.01-$0.10 per trade")
    print("🤖 AI-powered decisions")
    print("🔊 Exchange sounds on successful orders")
    print("=" * 50)
    
    # Create and run connected system
    system = ConnectedHedgingSystem()
    system.run()

if __name__ == "__main__":
    main()
