#!/usr/bin/env python3
"""
GATE.IO LLM-POWERED TRADING SYSTEM
Integrates LLM analysis with Gate.io trading API
REAL ACCOUNT CONNECTION - $7.38 BALANCE
"""

import asyncio
import aiohttp
import json
import hmac
import hashlib
import time
import base64
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dataclasses import dataclass
import openai
from enum import Enum
import os

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# REAL GATE.IO API CREDENTIALS
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
GATE_BASE_URL = "https://api.gateio.ws"

class TradingSignal(Enum):
    """Trading signal types"""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"

class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"

@dataclass
class TradingDecision:
    """LLM trading decision"""
    signal: TradingSignal
    confidence: float
    reasoning: str
    entry_price: Optional[float]
    stop_loss: Optional[float]
    take_profit: Optional[float]
    position_size: float
    risk_reward_ratio: float

@dataclass
class MarketData:
    """Market data structure"""
    symbol: str
    price: float
    volume_24h: float
    change_24h: float
    high_24h: float
    low_24h: float
    orderbook: Dict
    recent_trades: List[Dict]
    timestamp: datetime

class GateIOClient:
    """Gate.io API client with LLM integration"""
    
    def __init__(self, api_key: str, api_secret: str, openai_api_key: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.gateio.ws/api/v4"
        self.session = None
        
        # Initialize OpenAI
        openai.api_key = openai_api_key
        self.client = openai.OpenAI(api_key=openai_api_key)
        
        # Trading state
        self.positions = {}
        self.order_history = []
        self.balance = {}
        
        logger.info("🚀 Gate.io LLM Trading System initialized")
    
    def _sign_request(self, method: str, url: str, params: Dict = None, body: str = "") -> str:
        """Sign API request"""
        timestamp = str(int(time.time()))
        if params:
            query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
        else:
            query_string = ""
        
        message = f"{method}\n{url}\n{query_string}\n{body}\n{timestamp}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return f"KEY:{self.api_key},SIGN:{signature},TS:{timestamp}"
    
    async def _make_request(self, method: str, endpoint: str, params: Dict = None, body: Dict = None) -> Dict:
        """Make authenticated API request"""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        url = f"{self.base_url}{endpoint}"
        body_str = json.dumps(body) if body else ""
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': self._sign_request(method, endpoint, params, body_str)
        }
        
        try:
            async with self.session.request(method, url, headers=headers, params=params, json=body) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"API error {response.status}: {error_text}")
                    return {"error": error_text}
        except Exception as e:
            logger.error(f"Request failed: {e}")
            return {"error": str(e)}
    
    async def get_market_data(self, symbol: str) -> MarketData:
        """Get comprehensive market data for a symbol"""
        try:
            # Get ticker data
            ticker_url = f"/spot/tickers"
            ticker_params = {"currency_pair": symbol}
            ticker_data = await self._make_request("GET", ticker_url, ticker_params)
            
            if not ticker_data or len(ticker_data) == 0:
                raise Exception("No ticker data available")
            
            ticker = ticker_data[0]
            
            # Get orderbook
            orderbook_url = f"/spot/order_book"
            orderbook_params = {"currency_pair": symbol, "limit": 20}
            orderbook_data = await self._make_request("GET", orderbook_url, orderbook_params)
            
            # Get recent trades
            trades_url = f"/spot/trades"
            trades_params = {"currency_pair": symbol, "limit": 50}
            trades_data = await self._make_request("GET", trades_url, trades_params)
            
            market_data = MarketData(
                symbol=symbol,
                price=float(ticker.get("last", 0)),
                volume_24h=float(ticker.get("base_volume", 0)),
                change_24h=float(ticker.get("change_percentage", 0)),
                high_24h=float(ticker.get("high_24h", 0)),
                low_24h=float(ticker.get("low_24h", 0)),
                orderbook=orderbook_data,
                recent_trades=trades_data or [],
                timestamp=datetime.now()
            )
            
            logger.info(f"📊 Market data for {symbol}: ${market_data.price:.4f} ({market_data.change_24h:+.2f}%)")
            return market_data
            
        except Exception as e:
            logger.error(f"Failed to get market data for {symbol}: {e}")
            raise
    
    async def get_account_balance(self) -> Dict:
        """Get account balance"""
        try:
            balance_url = "/spot/accounts"
            balance_data = await self._make_request("GET", balance_url)
            
            if balance_data:
                self.balance = {}
                for asset in balance_data:
                    currency = asset.get("currency", "")
                    available = float(asset.get("available", 0))
                    frozen = float(asset.get("frozen", 0))
                    total = available + frozen
                    
                    if total > 0:
                        self.balance[currency] = {
                            "available": available,
                            "frozen": frozen,
                            "total": total
                        }
                
                logger.info(f"💰 Account balance updated: {len(self.balance)} assets")
                return self.balance
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return {}
    
    async def place_order(self, symbol: str, side: str, order_type: str, amount: float, 
                         price: float = None, stop_price: float = None) -> Dict:
        """Place trading order"""
        try:
            order_url = "/spot/orders"
            
            order_data = {
                "currency_pair": symbol,
                "side": side,
                "type": order_type,
                "amount": str(amount)
            }
            
            if price:
                order_data["price"] = str(price)
            if stop_price:
                order_data["price"] = str(stop_price)
                order_data["type"] = "stop_limit"
            
            result = await self._make_request("POST", order_url, body=order_data)
            
            if "id" in result:
                order_info = {
                    "order_id": result["id"],
                    "symbol": symbol,
                    "side": side,
                    "type": order_type,
                    "amount": amount,
                    "price": price,
                    "status": result.get("status", "open"),
                    "timestamp": datetime.now().isoformat()
                }
                
                self.order_history.append(order_info)
                logger.info(f"📈 Order placed: {side} {amount} {symbol} at ${price}")
                return order_info
            else:
                logger.error(f"Failed to place order: {result}")
                return {"error": result}
                
        except Exception as e:
            logger.error(f"Order placement failed: {e}")
            return {"error": str(e)}
    
    async def analyze_market_with_llm(self, market_data: MarketData, additional_context: str = "") -> TradingDecision:
        """Use LLM to analyze market and generate trading decision"""
        try:
            # Prepare market analysis prompt
            bid_price = float(market_data.orderbook.get('bids', [])[0][0]) if market_data.orderbook.get('bids') else 0
            ask_price = float(market_data.orderbook.get('asks', [])[0][0]) if market_data.orderbook.get('asks') else 0
            spread = ask_price - bid_price if bid_price > 0 and ask_price > 0 else 0
            
            prompt = f"""
            You are an expert cryptocurrency trading analyst. Analyze the following market data for {market_data.symbol} and provide a trading recommendation.
            
            CURRENT MARKET DATA:
            - Symbol: {market_data.symbol}
            - Current Price: ${market_data.price:.6f}
            - 24h Change: {market_data.change_24h:+.2f}%
            - 24h Volume: {market_data.volume_24h:,.2f}
            - 24h High: ${market_data.high_24h:.6f}
            - 24h Low: ${market_data.low_24h:.6f}
            
            ORDER BOOK ANALYSIS:
            - Best Bid: ${bid_price:.6f}
            - Best Ask: ${ask_price:.6f}
            - Bid-Ask Spread: ${spread:.6f}
            
            RECENT TRADES:
            - Last 5 trades: {[{'price': float(t[0]), 'amount': float(t[1]), 'side': t[2]} for t in (market_data.recent_trades[:5] if market_data.recent_trades else [])]}
            
            {additional_context}
            
            Provide a detailed analysis and trading recommendation in the following JSON format:
            {{
                "signal": "STRONG_BUY|BUY|HOLD|SELL|STRONG_SELL",
                "confidence": 0.0-1.0,
                "reasoning": "Detailed explanation of your analysis",
                "entry_price": recommended_entry_price,
                "stop_loss": recommended_stop_loss,
                "take_profit": recommended_take_profit,
                "position_size": recommended_position_size_as_percentage,
                "risk_reward_ratio": calculated_risk_reward_ratio
            }}
            
            Consider:
            1. Technical analysis (price action, volume, support/resistance)
            2. Market sentiment and momentum
            3. Risk management and position sizing
            4. Current market volatility
            5. Order book depth and liquidity
            
            Be conservative but decisive. Focus on risk management.
            """
            
            # Get LLM analysis
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert cryptocurrency trading analyst providing data-driven trading recommendations."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1000
            )
            
            llm_response = response.choices[0].message.content
            
            # Extract JSON from response
            try:
                # Find JSON in the response
                start_idx = llm_response.find('{')
                end_idx = llm_response.rfind('}') + 1
                json_str = llm_response[start_idx:end_idx]
                
                decision_data = json.loads(json_str)
                
                decision = TradingDecision(
                    signal=TradingSignal(decision_data["signal"]),
                    confidence=float(decision_data["confidence"]),
                    reasoning=decision_data["reasoning"],
                    entry_price=float(decision_data.get("entry_price", market_data.price)),
                    stop_loss=float(decision_data.get("stop_loss")),
                    take_profit=float(decision_data.get("take_profit")),
                    position_size=float(decision_data.get("position_size", 0.1)),
                    risk_reward_ratio=float(decision_data.get("risk_reward_ratio", 0))
                )
                
                logger.info(f"🧠 LLM Analysis: {decision.signal.value} (confidence: {decision.confidence:.2f})")
                logger.info(f"📝 Reasoning: {decision.reasoning[:200]}...")
                
                return decision
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {e}")
                logger.error(f"Raw response: {llm_response}")
                
                # Return conservative default
                return TradingDecision(
                    signal=TradingSignal.HOLD,
                    confidence=0.1,
                    reasoning="Failed to parse LLM analysis - holding position",
                    entry_price=market_data.price,
                    stop_loss=None,
                    take_profit=None,
                    position_size=0.0,
                    risk_reward_ratio=0.0
                )
                
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return TradingDecision(
                signal=TradingSignal.HOLD,
                confidence=0.0,
                reasoning=f"Analysis failed: {str(e)}",
                entry_price=market_data.price,
                stop_loss=None,
                take_profit=None,
                position_size=0.0,
                risk_reward_ratio=0.0
            )
    
    async def execute_llm_trading_decision(self, symbol: str, decision: TradingDecision) -> Dict:
        """Execute trading decision based on LLM analysis"""
        try:
            # Get current balance
            await self.get_account_balance()
            
            # Get base and quote currencies
            base_currency = symbol.split('_')[0]
            quote_currency = symbol.split('_')[1]
            
            # Calculate position size
            quote_balance = self.balance.get(quote_currency, {}).get("available", 0)
            position_value = quote_balance * decision.position_size
            
            if decision.position_size == 0:
                return {"status": "no_action", "reason": "Position size is 0"}
            
            # Execute based on signal
            if decision.signal in [TradingSignal.BUY, TradingSignal.STRONG_BUY]:
                if position_value > 10:  # Minimum trade size
                    amount = position_value / decision.entry_price
                    
                    # Place buy order
                    order_result = await self.place_order(
                        symbol=symbol,
                        side="buy",
                        order_type="limit",
                        amount=amount,
                        price=decision.entry_price
                    )
                    
                    if "order_id" in order_result:
                        # Place stop loss if specified
                        if decision.stop_loss:
                            await self.place_order(
                                symbol=symbol,
                                side="sell",
                                order_type="stop_loss",
                                amount=amount,
                                stop_price=decision.stop_loss
                            )
                        
                        # Place take profit if specified
                        if decision.take_profit:
                            await self.place_order(
                                symbol=symbol,
                                side="sell",
                                order_type="limit",
                                amount=amount,
                                price=decision.take_profit
                            )
                        
                        return {
                            "status": "buy_executed",
                            "order_id": order_result["order_id"],
                            "amount": amount,
                            "entry_price": decision.entry_price,
                            "stop_loss": decision.stop_loss,
                            "take_profit": decision.take_profit
                        }
                    else:
                        return {"status": "buy_failed", "error": order_result}
                else:
                    return {"status": "insufficient_balance", "available": quote_balance}
            
            elif decision.signal in [TradingSignal.SELL, TradingSignal.STRONG_SELL]:
                # Check if we have position to sell
                base_balance = self.balance.get(base_currency, {}).get("available", 0)
                
                if base_balance > 0:
                    sell_amount = base_balance * decision.position_size
                    
                    order_result = await self.place_order(
                        symbol=symbol,
                        side="sell",
                        order_type="limit",
                        amount=sell_amount,
                        price=decision.entry_price
                    )
                    
                    if "order_id" in order_result:
                        return {
                            "status": "sell_executed",
                            "order_id": order_result["order_id"],
                            "amount": sell_amount,
                            "entry_price": decision.entry_price
                        }
                    else:
                        return {"status": "sell_failed", "error": order_result}
                else:
                    return {"status": "no_position_to_sell", "balance": base_balance}
            
            else:  # HOLD
                return {"status": "hold", "reason": decision.reasoning}
                
        except Exception as e:
            logger.error(f"Failed to execute trading decision: {e}")
            return {"status": "execution_failed", "error": str(e)}
    
    async def run_llm_trading_cycle(self, symbol: str, additional_context: str = "") -> Dict:
        """Run complete LLM trading cycle"""
        try:
            logger.info(f"🚀 Starting LLM trading cycle for {symbol}")
            
            # 1. Get market data
            market_data = await self.get_market_data(symbol)
            
            # 2. Get LLM analysis
            decision = await self.analyze_market_with_llm(market_data, additional_context)
            
            # 3. Execute trading decision
            execution_result = await self.execute_llm_trading_decision(symbol, decision)
            
            # 4. Log results
            result_summary = {
                "timestamp": datetime.now().isoformat(),
                "symbol": symbol,
                "market_price": market_data.price,
                "signal": decision.signal.value,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "execution": execution_result
            }
            
            logger.info(f"📊 Trading cycle completed: {execution_result.get('status', 'unknown')}")
            
            return result_summary
            
        except Exception as e:
            logger.error(f"Trading cycle failed: {e}")
            return {"status": "cycle_failed", "error": str(e)}
    
    async def close(self):
        """Close session"""
        if self.session:
            await self.session.close()

# Example usage and configuration
async def main():
    """Main function to demonstrate LLM-powered trading"""
    
    # Configuration - REPLACE WITH YOUR ACTUAL API KEYS
    GATEIO_API_KEY = "your_gateio_api_key_here"
    GATEIO_API_SECRET = "your_gateio_api_secret_here"
    OPENAI_API_KEY = "your_openai_api_key_here"
    
    # Initialize trading client
    trader = GateIOClient(GATEIO_API_KEY, GATEIO_API_SECRET, OPENAI_API_KEY)
    
    try:
        # Example: Analyze and trade BTC_USDT
        symbol = "BTC_USDT"
        
        # Additional context for LLM (news, events, etc.)
        additional_context = """
        Recent market events to consider:
        - Bitcoin ETF approvals have increased institutional demand
        - Recent Fed announcement suggests dovish stance
        - Technical indicators show bullish momentum on daily timeframe
        - Large wallet movements detected in past 24 hours
        """
        
        # Run trading cycle
        result = await trader.run_llm_trading_cycle(symbol, additional_context)
        
        print("\n" + "="*80)
        print("🤖 LLM TRADING ANALYSIS RESULTS")
        print("="*80)
        print(f"Symbol: {result['symbol']}")
        print(f"Market Price: ${result['market_price']:,.2f}")
        print(f"LLM Signal: {result['signal']}")
        print(f"Confidence: {result['confidence']:.2f}")
        print(f"Execution Status: {result['execution'].get('status', 'unknown')}")
        print(f"Reasoning: {result['reasoning']}")
        print("="*80)
        
    finally:
        await trader.close()

if __name__ == "__main__":
    print("🚀 Gate.io LLM Trading System")
    print("⚠️  NOTE: Update API keys in main() function before running")
    print("📋 This system integrates OpenAI GPT-4 with Gate.io API for intelligent trading")
    
    # Uncomment to run (requires API keys)
    # asyncio.run(main())
