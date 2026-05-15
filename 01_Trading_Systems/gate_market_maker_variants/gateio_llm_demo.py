#!/usr/bin/env python3
"""
GATE.IO LLM TRADING DEMO
Demonstrates LLM-powered trading analysis without live API calls
"""

import asyncio
import json
from datetime import datetime
from gateio_llm_trader import GateIOClient, MarketData, TradingDecision, TradingSignal

class MockGateIOClient(GateIOClient):
    """Mock client for demonstration without API keys"""
    
    def __init__(self, api_key: str, api_secret: str, openai_api_key: str):
        # Initialize without actual API calls
        self.api_key = api_key
        self.api_secret = api_secret
        self.openai_api_key = openai_api_key
        
        # Import here to avoid issues if not installed
        try:
            import openai
            self.client = openai.OpenAI(api_key=openai_api_key)
        except ImportError:
            print("⚠️  OpenAI package not installed. Install with: pip install openai")
            self.client = None
        
        self.positions = {}
        self.order_history = []
        self.balance = {"USDT": {"available": 10000, "frozen": 0, "total": 10000}}
        
        print("🤖 Mock Gate.io LLM Trading Client initialized for demo")
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Return mock market data"""
        print(f"📊 Fetching mock market data for {symbol}...")
        
        # Simulate realistic market data
        mock_data = {
            "BTC_USDT": {
                "price": 67543.21,
                "volume_24h": 1234567890,
                "change_24h": 2.34,
                "high_24h": 68234.56,
                "low_24h": 65432.10
            },
            "ETH_USDT": {
                "price": 3456.78,
                "volume_24h": 987654321,
                "change_24h": -1.23,
                "high_24h": 3523.45,
                "low_24h": 3398.76
            },
            "SOL_USDT": {
                "price": 145.67,
                "volume_24h": 456789012,
                "change_24h": 5.67,
                "high_24h": 148.90,
                "low_24h": 138.45
            }
        }
        
        data = mock_data.get(symbol, mock_data["BTC_USDT"])
        
        # Mock orderbook
        orderbook = {
            "bids": [[data["price"] - 0.01, 1.5], [data["price"] - 0.02, 2.3]],
            "asks": [[data["price"] + 0.01, 1.2], [data["price"] + 0.02, 1.8]]
        }
        
        # Mock recent trades
        recent_trades = [
            [data["price"], 0.5, "buy"],
            [data["price"] - 0.01, 0.3, "sell"],
            [data["price"] + 0.01, 0.7, "buy"]
        ]
        
        market_data = MarketData(
            symbol=symbol,
            price=data["price"],
            volume_24h=data["volume_24h"],
            change_24h=data["change_24h"],
            high_24h=data["high_24h"],
            low_24h=data["low_24h"],
            orderbook=orderbook,
            recent_trades=recent_trades,
            timestamp=datetime.now()
        )
        
        print(f"✅ Mock data ready: {symbol} @ ${market_data.price:.2f} ({market_data.change_24h:+.2f}%)")
        return market_data
    
    async def get_account_balance(self) -> dict:
        """Return mock balance"""
        print("💰 Using mock account balance: $10,000 USDT")
        return self.balance
    
    async def place_order(self, symbol: str, side: str, order_type: str, amount: float, 
                         price: float = None, stop_price: float = None) -> dict:
        """Mock order placement"""
        order_id = f"mock_order_{int(datetime.now().timestamp())}"
        
        print(f"📈 MOCK ORDER: {side.upper()} {amount:.6f} {symbol} at ${price:.2f}")
        
        order_info = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "amount": amount,
            "price": price,
            "status": "filled",
            "timestamp": datetime.now().isoformat()
        }
        
        self.order_history.append(order_info)
        return order_info

async def demo_llm_trading():
    """Demonstrate LLM-powered trading analysis"""
    
    print("🚀 GATE.IO LLM TRADING DEMO")
    print("="*80)
    
    # Check for OpenAI API key
    import os
    openai_key = os.getenv("OPENAI_API_KEY", "your_openai_api_key_here")
    
    if openai_key == "your_openai_api_key_here":
        print("⚠️  DEMO MODE: No OpenAI API key found")
        print("   Set OPENAI_API_KEY environment variable to use real LLM analysis")
        print("   Using mock analysis for demonstration...\n")
    
    # Initialize mock client
    trader = MockGateIOClient("mock_key", "mock_secret", openai_key)
    
    # Test symbols
    symbols = ["BTC_USDT", "ETH_USDT", "SOL_USDT"]
    
    for symbol in symbols:
        print(f"\n🎯 ANALYZING {symbol}")
        print("-" * 50)
        
        try:
            # Get market data
            market_data = await trader.get_market_data(symbol)
            
            # Additional context for analysis
            additional_context = f"""
            Market context for {symbol}:
            - Recent institutional adoption news
            - Technical analysis shows bullish patterns
            - Market volatility is moderate
            - Volume is above average
            - Recent whale activity detected
            """
            
            if trader.client:
                # Use real LLM analysis
                decision = await trader.analyze_market_with_llm(market_data, additional_context)
                
                print(f"🧠 LLM Analysis Results:")
                print(f"   Signal: {decision.signal.value}")
                print(f"   Confidence: {decision.confidence:.2f}")
                print(f"   Entry Price: ${decision.entry_price:.2f}")
                print(f"   Stop Loss: ${decision.stop_loss:.2f}" if decision.stop_loss else "   Stop Loss: Not set")
                print(f"   Take Profit: ${decision.take_profit:.2f}" if decision.take_profit else "   Take Profit: Not set")
                print(f"   Position Size: {decision.position_size*100:.1f}%")
                print(f"   Risk/Reward: {decision.risk_reward_ratio:.2f}")
                print(f"   Reasoning: {decision.reasoning[:200]}...")
                
                # Execute mock trade
                execution = await trader.execute_llm_trading_decision(symbol, decision)
                print(f"\n📊 Execution Result: {execution.get('status', 'unknown')}")
                
            else:
                # Mock analysis
                mock_decision = TradingDecision(
                    signal=TradingSignal.BUY if market_data.change_24h > 0 else TradingSignal.HOLD,
                    confidence=0.75,
                    reasoning="Mock analysis based on positive price momentum and volume",
                    entry_price=market_data.price,
                    stop_loss=market_data.price * 0.98,
                    take_profit=market_data.price * 1.05,
                    position_size=0.1,
                    risk_reward_ratio=2.5
                )
                
                print(f"🤖 MOCK Analysis Results:")
                print(f"   Signal: {mock_decision.signal.value}")
                print(f"   Confidence: {mock_decision.confidence:.2f}")
                print(f"   Entry Price: ${mock_decision.entry_price:.2f}")
                print(f"   Stop Loss: ${mock_decision.stop_loss:.2f}")
                print(f"   Take Profit: ${mock_decision.take_profit:.2f}")
                print(f"   Position Size: {mock_decision.position_size*100:.1f}%")
                print(f"   Reasoning: {mock_decision.reasoning}")
                
                # Execute mock trade
                execution = await trader.execute_llm_trading_decision(symbol, mock_decision)
                print(f"\n📊 Execution Result: {execution.get('status', 'unknown')}")
            
        except Exception as e:
            print(f"❌ Error analyzing {symbol}: {e}")
    
    # Show summary
    print(f"\n📈 TRADING SUMMARY")
    print("="*80)
    print(f"Total Orders Placed: {len(trader.order_history)}")
    print(f"Account Balance: ${trader.balance['USDT']['available']:,.2f} USDT")
    
    if trader.order_history:
        print(f"\nRecent Orders:")
        for order in trader.order_history[-3:]:
            print(f"   {order['side'].upper()} {order['amount']:.6f} {order['symbol']} @ ${order['price']:.2f}")
    
    print(f"\n✅ Demo completed! This shows how LLM integrates with Gate.io trading.")
    print(f"💡 To use with real API:")
    print(f"   1. Get Gate.io API keys from https://www.gate.io/")
    print(f"   2. Get OpenAI API key from https://platform.openai.com/")
    print(f"   3. Replace mock keys in gateio_llm_trader.py")
    print(f"   4. Run: python gateio_llm_trader.py")

if __name__ == "__main__":
    asyncio.run(demo_llm_trading())
