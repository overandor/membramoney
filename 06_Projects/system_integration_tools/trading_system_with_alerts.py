#!/usr/bin/env python3
"""
Complete Trading System with Sound Alerts
Uses environment variables for all configuration
"""

import os
import time
import json
import requests
import asyncio
import subprocess
from datetime import datetime
from typing import Dict, List, Optional

# Environment Variables
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ENABLE_SOUND = os.getenv("ENABLE_SOUND", "1") == "1"
ALERT_VOLUME = os.getenv("ALERT_VOLUME", "0.5")

class SoundAlertSystem:
    """Sound notification system for trading events"""
    
    def __init__(self, enabled=True, volume=0.5):
        self.enabled = enabled
        self.volume = volume
        self.sounds = {
            "trade": "Glass",           # For executed trades
            "alert": "Ping",            # For important alerts  
            "error": "Basso",           # For errors
            "profit": "Purr",           # For profit taking
            "market_open": "Blow",      # Market open
            "market_close": "Frog",     # Market close
        }
    
    def play_sound(self, sound_type: str):
        """Play a macOS system sound"""
        if not self.enabled:
            return
        
        try:
            sound_name = self.sounds.get(sound_type, "Ping")
            # Use macOS afplay command
            subprocess.run([
                "afplay", 
                "/System/Library/Sounds/{}.aiff".format(sound_name)
            ], capture_output=True, timeout=5)
            print(f"🔊 Played sound: {sound_name}")
        except Exception as e:
            print(f"❌ Sound error: {e}")
    
    def trade_executed(self, action: str, symbol: str):
        """Alert for trade execution"""
        print(f"🔊 TRADE ALERT: {action} {symbol}")
        self.play_sound("trade")
    
    def profit_taken(self, amount: float):
        """Alert for profit taking"""
        print(f"💰 PROFIT ALERT: ${amount:.2f}")
        self.play_sound("profit")
    
    def error_alert(self, error: str):
        """Alert for errors"""
        print(f"❌ ERROR ALERT: {error}")
        self.play_sound("error")
    
    def market_alert(self, message: str):
        """Alert for market events"""
        print(f"📢 MARKET ALERT: {message}")
        self.play_sound("alert")

class TradingSystem:
    """Main trading system with AI and sound alerts"""
    
    def __init__(self):
        self.sound = SoundAlertSystem(ENABLE_SOUND, float(ALERT_VOLUME))
        self.openrouter_key = OPENROUTER_API_KEY
        self.gate_key = GATE_API_KEY
        self.gate_secret = GATE_API_SECRET
        
        # Trading configuration
        self.symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "ENA_USDT"]
        self.running = False
        self.trade_history = []
        
        print("🚀 Trading System Initialized")
        print(f"🔊 Sound Alerts: {'Enabled' if ENABLE_SOUND else 'Disabled'}")
        print(f"🤖 AI Assistant: {'Ready' if self.openrouter_key else 'Disabled'}")
        print(f"🔗 Gate.io API: {'Configured' if self.gate_key else 'Missing'}")
    
    def get_ai_decision(self, market_data: Dict) -> Dict:
        """Get AI trading decision from OpenRouter"""
        if not self.openrouter_key:
            return {
                "action": "HOLD",
                "symbol": "BTC_USDT",
                "confidence": 0.5,
                "reasoning": "AI disabled - using rule-based system"
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/alep/trading-bot",
                "X-Title": "AI Trading System"
            }
            
            prompt = f"""
            Analyze these market conditions and provide a trading decision:
            
            Market Data: {json.dumps(market_data, indent=2)}
            Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            
            Return JSON: {{"action": "BUY/SELL/HOLD", "symbol": "SYMBOL", "confidence": 0.0-1.0, "reasoning": "explanation"}}
            """
            
            data = {
                "model": "anthropic/claude-3-haiku",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.3
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Parse JSON response
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = content.strip()
                
                return json.loads(json_str)
            else:
                self.sound.error_alert(f"AI API error: {response.status_code}")
                return {"action": "HOLD", "confidence": 0.5, "reasoning": "API error"}
                
        except Exception as e:
            self.sound.error_alert(f"AI exception: {str(e)}")
            return {"action": "HOLD", "confidence": 0.5, "reasoning": f"Exception: {str(e)}"}
    
    def get_market_data(self) -> Dict:
        """Get mock market data (replace with real API)"""
        import random
        
        data = {}
        for symbol in self.symbols:
            base_prices = {
                "BTC_USDT": 65000,
                "ETH_USDT": 3500,
                "SOL_USDT": 180, 
                "ENA_USDT": 0.85
            }
            
            base = base_prices[symbol]
            variation = random.uniform(-0.03, 0.03)
            current_price = base * (1 + variation)
            
            data[symbol] = {
                "price": current_price,
                "volume_24h": random.uniform(1000000, 10000000),
                "change_1h": random.uniform(-0.05, 0.05),
                "change_24h": random.uniform(-0.15, 0.15),
                "rsi": random.uniform(20, 80),
                "macd": random.uniform(-0.5, 0.5),
                "volatility": random.uniform(0.01, 0.05)
            }
        
        return data
    
    def execute_trade(self, decision: Dict):
        """Execute trading decision with sound alerts"""
        action = decision.get("action", "HOLD")
        symbol = decision.get("symbol", "")
        confidence = decision.get("confidence", 0.0)
        
        if action == "HOLD" or confidence < 0.6:
            print(f"  🤚 HOLD - Confidence: {confidence:.2f}")
            return
        
        # Sound alert for trade
        self.sound.trade_executed(action, symbol)
        
        # Record trade
        trade = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "symbol": symbol,
            "confidence": confidence,
            "reasoning": decision.get("reasoning", ""),
            "status": "SIMULATED"
        }
        
        self.trade_history.append(trade)
        
        print(f"  🎯 EXECUTED: {action} {symbol}")
        print(f"  📊 Confidence: {confidence:.2f}")
        print(f"  💭 Reasoning: {decision.get('reasoning', 'N/A')}")
        
        # Simulate profit/loss
        if random.random() > 0.4:  # 60% win rate
            profit = random.uniform(10, 100)
            self.sound.profit_taken(profit)
            trade["profit"] = profit
    
    async def run_trading_session(self, duration_minutes: int = 10):
        """Run trading session with alerts"""
        print(f"\n🚀 Starting Trading Session")
        print(f"⏱️ Duration: {duration_minutes} minutes")
        print(f"📊 Symbols: {', '.join(self.symbols)}")
        print("=" * 60)
        
        # Market open alert
        self.sound.market_alert("Trading session started")
        
        self.running = True
        start_time = time.time()
        cycle = 0
        
        while self.running and (time.time() - start_time) < duration_minutes * 60:
            cycle += 1
            cycle_start = time.time()
            
            try:
                print(f"\n🔄 Cycle {cycle} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Get market data
                market_data = self.get_market_data()
                print(f"📈 Market: {len(market_data)} symbols analyzed")
                
                # AI decision
                print("🧠 AI analyzing market...")
                decision = self.get_ai_decision(market_data)
                
                # Execute trade
                print("⚡ Processing decision...")
                self.execute_trade(decision)
                
                # Show status
                total_trades = len(self.trade_history)
                profitable = sum(1 for t in self.trade_history if t.get("profit", 0) > 0)
                print(f"📊 Status: {total_trades} trades, {profitable} profitable")
                
                # Wait for next cycle
                elapsed = time.time() - cycle_start
                sleep_time = max(0, 20 - elapsed)  # 20 second cycles
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                print("\n🛑 Session stopped by user")
                self.sound.market_alert("Trading session stopped")
                break
            except Exception as e:
                self.sound.error_alert(f"Cycle error: {str(e)}")
                await asyncio.sleep(5)
        
        # Session summary
        self.show_session_summary()
    
    def show_session_summary(self):
        """Show trading session summary"""
        print("\n" + "=" * 60)
        print("📊 TRADING SESSION SUMMARY")
        print("=" * 60)
        
        total_trades = len(self.trade_history)
        if total_trades == 0:
            print("No trades executed.")
            return
        
        # Calculate stats
        actions = {}
        total_profit = 0
        profitable_trades = 0
        
        for trade in self.trade_history:
            action = trade["action"]
            actions[action] = actions.get(action, 0) + 1
            profit = trade.get("profit", 0)
            total_profit += profit
            if profit > 0:
                profitable_trades += 1
        
        print(f"📈 Total Trades: {total_trades}")
        print(f"💰 Total Profit: ${total_profit:.2f}")
        print(f"✅ Win Rate: {profitable_trades}/{total_trades} ({profitable_trades/total_trades*100:.1f}%)")
        
        print(f"\n🎯 Actions:")
        for action, count in actions.items():
            print(f"  {action}: {count}")
        
        print(f"\n📝 Last 5 Trades:")
        for trade in self.trade_history[-5:]:
            profit_str = f" (+${trade.get('profit', 0):.2f})" if trade.get('profit', 0) > 0 else ""
            print(f"  {trade['timestamp'][-8:]} {trade['action']} {trade['symbol']} (conf: {trade['confidence']:.2f}){profit_str}")

async def main():
    """Main function"""
    print("🚀 TRADING SYSTEM WITH SOUND ALERTS")
    print("=" * 50)
    
    # Check environment variables
    required_vars = {
        "GATE_API_KEY": GATE_API_KEY,
        "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
        "ENABLE_SOUND": ENABLE_SOUND
    }
    
    print("🔧 Environment Variables:")
    for var, value in required_vars.items():
        status = "✅ Set" if value else "❌ Missing"
        print(f"  {var}: {status}")
    
    if not GATE_API_KEY:
        print("\n⚠️  Running in simulation mode (no Gate.io API)")
    
    if not OPENROUTER_API_KEY:
        print("\n⚠️  AI disabled (no OpenRouter API)")
    
    # Create and run trading system
    trader = TradingSystem()
    
    # Run for 5 minutes for demo
    await trader.run_trading_session(duration_minutes=5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Trading system stopped!")
