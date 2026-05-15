#!/usr/bin/env python3
"""
OpenRouter AI Trading Supervisor
Autonomous AI-powered trading decisions using OpenRouter API
"""

import os
import time
import json
import requests
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

class OpenRouterAITrader:
    """AI Trading Supervisor using OpenRouter"""
    
    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.model = "anthropic/claude-3-haiku"  # Fast and cheap
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.running = False
        self.decision_history = []
        
        # Trading parameters
        self.symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "ENA_USDT"]
        self.max_position_size = 1000  # USDT
        self.risk_per_trade = 0.02  # 2% risk
        
    def call_ai(self, prompt: str, max_tokens: int = 500) -> str:
        """Call OpenRouter API for AI decision"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/alep/trading-bot",
                "X-Title": "AI Trading Supervisor"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system", 
                        "content": """You are an expert cryptocurrency trading AI. 
                        Analyze market conditions and make trading decisions.
                        Respond with JSON format: {"action": "BUY/SELL/HOLD", "symbol": "SYMBOL", "confidence": 0.0-1.0, "reasoning": "brief explanation"}"""
                    },
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.3
            }
            
            response = requests.post(self.base_url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"API Error: {response.text}"
                
        except Exception as e:
            return f"Exception: {str(e)}"
    
    def get_mock_market_data(self) -> Dict:
        """Get mock market data for demonstration"""
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
            variation = random.uniform(-0.02, 0.02)  # ±2% variation
            current_price = base * (1 + variation)
            
            data[symbol] = {
                "price": current_price,
                "volume_24h": random.uniform(1000000, 10000000),
                "change_1h": random.uniform(-0.05, 0.05),
                "change_24h": random.uniform(-0.1, 0.1),
                "rsi": random.uniform(20, 80),
                "macd": random.uniform(-0.5, 0.5)
            }
        
        return data
    
    def analyze_market(self, market_data: Dict) -> Dict:
        """Use AI to analyze market and make trading decisions"""
        prompt = f"""
        Analyze these market conditions and provide a trading recommendation:
        
        Market Data:
        {json.dumps(market_data, indent=2)}
        
        Current Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        
        Consider:
        - Recent price movements and momentum
        - Volume trends
        - Technical indicators (RSI, MACD)
        - Risk management (max 2% per trade)
        
        Provide decision in JSON format with action, symbol, confidence (0-1), and reasoning.
        """
        
        ai_response = self.call_ai(prompt)
        
        try:
            # Try to parse JSON response
            if "```json" in ai_response:
                json_str = ai_response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = ai_response.strip()
            
            decision = json.loads(json_str)
            return decision
        except:
            # Fallback if JSON parsing fails
            return {
                "action": "HOLD",
                "symbol": "BTC_USDT", 
                "confidence": 0.5,
                "reasoning": f"AI response parsing failed: {ai_response[:100]}"
            }
    
    def execute_trade(self, decision: Dict) -> bool:
        """Execute trading decision (mock implementation)"""
        action = decision.get("action", "HOLD")
        symbol = decision.get("symbol", "")
        confidence = decision.get("confidence", 0.0)
        
        if action == "HOLD" or confidence < 0.6:
            print(f"  🤚 HOLD - Confidence too low: {confidence:.2f}")
            return False
        
        print(f"  🎯 EXECUTE: {action} {symbol} (confidence: {confidence:.2f})")
        print(f"  📝 Reasoning: {decision.get('reasoning', 'N/A')}")
        
        # In real implementation, this would call the trading API
        # For now, just log the decision
        trade_record = {
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "symbol": symbol,
            "confidence": confidence,
            "reasoning": decision.get("reasoning"),
            "status": "SIMULATED"
        }
        
        self.decision_history.append(trade_record)
        return True
    
    async def run_supervisor(self, duration_minutes: int = 60):
        """Run AI trading supervisor"""
        print(f"🚀 Starting OpenRouter AI Trading Supervisor")
        print(f"🤖 Model: {self.model}")
        print(f"⏱️  Duration: {duration_minutes} minutes")
        print(f"📊 Symbols: {', '.join(self.symbols)}")
        print(f"💰 Max position size: ${self.max_position_size}")
        print("=" * 60)
        
        self.running = True
        start_time = time.time()
        cycle = 0
        
        while self.running and (time.time() - start_time) < duration_minutes * 60:
            cycle += 1
            cycle_start = time.time()
            
            try:
                print(f"\n🔄 Cycle {cycle} - {datetime.now().strftime('%H:%M:%S')}")
                
                # Get market data
                market_data = self.get_mock_market_data()
                print(f"📈 Market: {len(market_data)} symbols analyzed")
                
                # AI Analysis
                print("🧠 AI analyzing market conditions...")
                decision = self.analyze_market(market_data)
                
                # Execute decision
                print("⚡ Executing trading decision...")
                self.execute_trade(decision)
                
                # Show portfolio status
                print(f"📊 Decisions made: {len(self.decision_history)}")
                
                # Wait for next cycle (30 seconds)
                elapsed = time.time() - cycle_start
                sleep_time = max(0, 30 - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                
            except KeyboardInterrupt:
                print("\n🛑 Supervisor stopped by user")
                break
            except Exception as e:
                print(f"❌ Error in cycle {cycle}: {e}")
                await asyncio.sleep(5)
        
        # Show summary
        self.show_summary()
    
    def show_summary(self):
        """Show trading summary"""
        print("\n" + "=" * 60)
        print("📊 TRADING SUMMARY")
        print("=" * 60)
        
        total_decisions = len(self.decision_history)
        if total_decisions == 0:
            print("No trading decisions made.")
            return
        
        actions = {}
        for record in self.decision_history:
            action = record["action"]
            actions[action] = actions.get(action, 0) + 1
        
        print(f"Total decisions: {total_decisions}")
        for action, count in actions.items():
            print(f"  {action}: {count}")
        
        print(f"\nLast 5 decisions:")
        for record in self.decision_history[-5:]:
            print(f"  {record['timestamp'][-8:]} {record['action']} {record['symbol']} (conf: {record['confidence']:.2f})")

async def main():
    """Main function"""
    if not OPENROUTER_API_KEY:
        print("❌ Missing OPENROUTER_API_KEY")
        print("Run: export OPENROUTER_API_KEY='your-key-here'")
        return
    
    trader = OpenRouterAITrader()
    
    # Run for 5 minutes for demo
    await trader.run_supervisor(duration_minutes=5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 AI Trader stopped!")
