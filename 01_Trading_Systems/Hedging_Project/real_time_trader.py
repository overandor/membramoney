#!/usr/bin/env python3
"""
REAL-TIME TRADING SCANNER
Connects to Gate.io and trades the exact tokens you listed
"""

import os
import time
import json
import requests
import hmac
import hashlib
from datetime import datetime
import threading
import queue

# EXACT TOKENS YOU PROVIDED
TRADING_TOKENS = [
    {"symbol": "HIPPO_USDT", "price": 0.000239, "change": -22.21, "volume": 11137302273},
    {"symbol": "NATIX_USDT", "price": 0.000101, "change": 8.39, "volume": 5239695213},
    {"symbol": "TOSHI_USDT", "price": 0.000187, "change": 8.17, "volume": 3003309098},
    {"symbol": "ELIZAOS_USDT", "price": 0.000838, "change": 7.93, "volume": 1447897904},
    {"symbol": "ETH5S_USDT", "price": 0.005350, "change": -37.41, "volume": 1395317878},
    {"symbol": "PUMP_USDT", "price": 0.001819, "change": 7.31, "volume": 992958762},
    {"symbol": "COMMON_USDT", "price": 0.000365, "change": 34.63, "volume": 967736550},
    {"symbol": "XRP5L_USDT", "price": 0.001275, "change": 28.34, "volume": 918108054},
    {"symbol": "MRLN_USDT", "price": 0.000151, "change": -24.58, "volume": 673241384},
    {"symbol": "LINK5L_USDT", "price": 0.001650, "change": 33.17, "volume": 602449379},
    {"symbol": "XPIN_USDT", "price": 0.001435, "change": 22.39, "volume": 569121348},
    {"symbol": "RLS_USDT", "price": 0.002627, "change": -7.33, "volume": 568174264},
    {"symbol": "AVAX5L_USDT", "price": 0.001762, "change": 45.37, "volume": 495150761},
    {"symbol": "MEMEFI_USDT", "price": 0.000180, "change": 48.10, "volume": 488739465},
    {"symbol": "FARTCOIN5S_USDT", "price": 0.001155, "change": -61.18, "volume": 464223622},
    {"symbol": "OMI_USDT", "price": 0.000130, "change": 1.87, "volume": 463075540},
    {"symbol": "DOGE_USDT", "price": 0.094740, "change": 4.51, "volume": 433636957},
    {"symbol": "PTB_USDT", "price": 0.000982, "change": -8.30, "volume": 399321349},
    {"symbol": "DOGE3S_USDT", "price": 0.004231, "change": -14.26, "volume": 398377334},
    {"symbol": "XEM_USDT", "price": 0.000665, "change": 2.70, "volume": 387611345},
    {"symbol": "BLUAI_USDT", "price": 0.008946, "change": 11.88, "volume": 373938017},
    {"symbol": "ADA5L_USDT", "price": 0.001864, "change": 32.76, "volume": 331653806},
    {"symbol": "TREAT_USDT", "price": 0.000198, "change": 13.27, "volume": 327670639},
    {"symbol": "BTC5L_USDT", "price": 0.008375, "change": 27.37, "volume": 314726825},
    {"symbol": "ROOBEE_USDT", "price": 0.000105, "change": 1.16, "volume": 312512589},
    {"symbol": "PEPE5S_USDT", "price": 0.005005, "change": -40.62, "volume": 312484534},
    {"symbol": "ART_USDT", "price": 0.000313, "change": 0.67, "volume": 302345159},
    {"symbol": "XNL_USDT", "price": 0.000201, "change": 0.90, "volume": 293096830},
    {"symbol": "HMSTR_USDT", "price": 0.000142, "change": 5.43, "volume": 289747018},
    {"symbol": "BLAST_USDT", "price": 0.000462, "change": 2.80, "volume": 285204866}
]

class RealTimeTrader:
    """Real-time trading scanner for your exact tokens"""
    
    def __init__(self):
        self.api_key = os.getenv("GATE_API_KEY", "")
        self.api_secret = os.getenv("GATE_API_SECRET", "")
        self.base_url = "https://api.gateio.ws/api/v4"
        self.running = False
        self.trade_count = 0
        self.total_pnl = 0.0
        
        print("🚀 REAL-TIME TRADING SCANNER")
        print("=" * 60)
        print(f"📊 Trading {len(TRADING_TOKENS)} tokens you specified:")
        for i, token in enumerate(TRADING_TOKENS[:10], 1):
            print(f"   {i:2d}. {token['symbol']} - ${token['price']:.6f} ({token['change']:+.2f}%)")
        print(f"   ... and {len(TRADING_TOKENS)-10} more tokens")
        print("=" * 60)
        
        # Check API keys
        if not self.api_key or not self.api_secret:
            print("⚠️  DEMO MODE - No API keys found")
            print("   Set GATE_API_KEY and GATE_API_SECRET for live trading")
        else:
            print(f"✅ API Key: {self.api_key[:10]}...")
            print("✅ Ready for live trading")
    
    def sign_request(self, method, path, payload):
        """Generate Gate.io signature"""
        if not self.api_key or not self.api_secret:
            return {}
        
        ts = str(int(time.time()))
        payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        sign_str = f"{method.upper()}\n{path}\n{payload_hash}\n{ts}"
        sign = hmac.new(self.api_secret.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
        
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "KEY": self.api_key,
            "Timestamp": ts,
            "SIGN": sign,
        }
    
    def make_request(self, method, path, payload="", private=True):
        """Make API request"""
        headers = self.sign_request(method, path, payload) if private else {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.request(
                method, 
                f"{self.base_url}{path}", 
                headers=headers, 
                data=payload if payload else None, 
                timeout=10
            )
            
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_real_time_data(self, symbol):
        """Get real-time data for a specific token"""
        # Get ticker
        ticker_result = self.make_request("GET", f"/spot/tickers?currency_pair={symbol}", private=False)
        if not ticker_result["success"]:
            return None
        
        ticker = ticker_result["data"][0] if ticker_result["data"] else None
        if not ticker:
            return None
        
        # Get order book
        book_result = self.make_request("GET", f"/spot/order_book?currency_pair={symbol}&limit=1", private=False)
        if not book_result["success"]:
            return None
        
        book = book_result["data"]
        if not book.get("bids") or not book.get("asks"):
            return None
        
        return {
            "symbol": symbol,
            "price": float(ticker.get("last", 0)),
            "bid": float(book["bids"][0][0]),
            "ask": float(book["asks"][0][0]),
            "volume": float(ticker.get("base_volume", 0)),
            "change": float(ticker.get("change_percentage", 0)),
            "spread": float(book["asks"][0][0]) - float(book["bids"][0][0]),
            "spread_pct": ((float(book["asks"][0][0]) - float(book["bids"][0][0])) / float(book["bids"][0][0])) * 100
        }
    
    def place_order(self, symbol, side, size, price):
        """Place real order"""
        if not self.api_key or not self.api_secret:
            print(f"🧪 DEMO ORDER: {side} {size:.6f} {symbol} @ ${price:.6f}")
            return {"success": True, "data": {"id": f"demo_{int(time.time())}"}}
        
        order_data = {
            "currency_pair": symbol,
            "type": "limit",
            "side": side,
            "amount": str(size),
            "price": str(price),
            "time_in_force": "ioc"
        }
        
        payload = json.dumps(order_data, separators=(",", ":"))
        result = self.make_request("POST", "/spot/orders", payload, private=True)
        
        if result["success"]:
            print(f"✅ ORDER PLACED: {side} {size:.6f} {symbol} @ ${price:.6f}")
            print("🔊 Listen for Gate.io exchange sound!")
        else:
            print(f"❌ ORDER FAILED: {result.get('error', 'Unknown')}")
        
        return result
    
    def get_account_balance(self):
        """Get account balance"""
        if not self.api_key or not self.api_secret:
            return {"available": 1000.0, "total": 1000.0}  # Demo balance
        
        result = self.make_request("GET", "/spot/accounts", "", private=True)
        if not result["success"]:
            return {"available": 0.0, "total": 0.0}
        
        for account in result["data"]:
            if account.get("currency") == "USDT":
                return {
                    "available": float(account.get("available", 0)),
                    "total": float(account.get("available", 0)) + float(account.get("frozen", 0))
                }
        
        return {"available": 0.0, "total": 0.0}
    
    def analyze_trading_opportunity(self, token_data, original_data):
        """Analyze if token is good for trading"""
        if not token_data:
            return None
        
        # Volume check
        if token_data["volume"] < 1000000:  # Less than $1M volume
            return None
        
        # Spread check
        if token_data["spread_pct"] > 1.0:  # More than 1% spread
            return None
        
        # Price movement check
        price_change = ((token_data["price"] - original_data["price"]) / original_data["price"]) * 100
        
        # Trading logic
        if price_change > 5.0:  # Price moved up more than 5%
            return {
                "action": "SELL",
                "reasoning": f"Price increased {price_change:.2f}% from ${original_data['price']:.6f}",
                "confidence": min(price_change / 10.0, 1.0),
                "price": token_data["bid"]
            }
        elif price_change < -5.0:  # Price moved down more than 5%
            return {
                "action": "BUY",
                "reasoning": f"Price decreased {abs(price_change):.2f}% from ${original_data['price']:.6f}",
                "confidence": min(abs(price_change) / 10.0, 1.0),
                "price": token_data["ask"]
            }
        
        return None
    
    def scan_and_trade(self):
        """Main scanning and trading loop"""
        print(f"\n🔍 SCANNING {len(TRADING_TOKENS)} TOKENS FOR TRADING OPPORTUNITIES...")
        print("=" * 60)
        
        # Get account balance
        balance = self.get_account_balance()
        print(f"💰 Account Balance: ${balance['available']:.2f}")
        
        opportunities = []
        
        # Scan all tokens
        for token in TRADING_TOKENS:
            print(f"\n📊 Scanning {token['symbol']}...")
            
            # Get real-time data
            real_data = self.get_real_time_data(token["symbol"])
            
            if real_data:
                print(f"   Current: ${real_data['price']:.6f} ({real_data['change']:+.2f}%)")
                print(f"   Volume: ${real_data['volume']/1000000:.1f}M")
                print(f"   Spread: {real_data['spread_pct']:.3f}%")
                
                # Analyze opportunity
                opportunity = self.analyze_trading_opportunity(real_data, token)
                
                if opportunity:
                    opportunities.append({
                        "symbol": token["symbol"],
                        "opportunity": opportunity,
                        "real_data": real_data
                    })
                    print(f"   🎯 OPPORTUNITY: {opportunity['action']} - {opportunity['reasoning']}")
                    print(f"   📈 Confidence: {opportunity['confidence']:.2f}")
                else:
                    print(f"   ⏸️  No trading opportunity")
            else:
                print(f"   ❌ Failed to get data")
        
        # Sort opportunities by confidence
        opportunities.sort(key=lambda x: x["opportunity"]["confidence"], reverse=True)
        
        print(f"\n🎯 FOUND {len(opportunities)} TRADING OPPORTUNITIES:")
        print("=" * 60)
        
        # Execute trades on top opportunities
        for i, opp in enumerate(opportunities[:5], 1):  # Top 5
            symbol = opp["symbol"]
            opportunity = opp["opportunity"]
            real_data = opp["real_data"]
            
            print(f"\n{i}. {symbol}")
            print(f"   Action: {opportunity['action']}")
            print(f"   Reasoning: {opportunity['reasoning']}")
            print(f"   Confidence: {opportunity['confidence']:.2f}")
            
            # Calculate order size (target $0.05 nominal)
            target_nominal = 0.05
            order_size = target_nominal / opportunity["price"]
            
            # Place order
            result = self.place_order(
                symbol, 
                opportunity["action"].lower(), 
                order_size, 
                opportunity["price"]
            )
            
            if result["success"]:
                self.trade_count += 1
                nominal_value = order_size * opportunity["price"]
                print(f"   ✅ Trade executed: ${nominal_value:.4f} nominal")
                
                # Simulate PnL for demo
                if not self.api_key:  # Demo mode
                    simulated_pnl = nominal_value * 0.001 * (1 if opportunity["action"] == "BUY" else -1)
                    self.total_pnl += simulated_pnl
                    print(f"   💰 Simulated PnL: ${simulated_pnl:.4f}")
        
        print(f"\n📊 SUMMARY:")
        print(f"   Tokens Scanned: {len(TRADING_TOKENS)}")
        print(f"   Opportunities Found: {len(opportunities)}")
        print(f"   Trades Executed: {self.trade_count}")
        print(f"   Total PnL: ${self.total_pnl:.4f}")
        print(f"   Account Balance: ${balance['available']:.2f}")
    
    def run_continuous(self):
        """Run continuous scanning"""
        self.running = True
        cycle = 0
        
        try:
            while self.running:
                cycle += 1
                print(f"\n{'='*80}")
                print(f"🚀 TRADING CYCLE {cycle} - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'='*80}")
                
                self.scan_and_trade()
                
                if self.running:
                    print(f"\n⏳ Waiting 30 seconds for next cycle...")
                    time.sleep(30)
                    
        except KeyboardInterrupt:
            print(f"\n🛑 Trading stopped by user")
        finally:
            self.running = False
    
    def run_single(self):
        """Run single scan"""
        self.scan_and_trade()

def main():
    """Main function"""
    print("🚀 REAL-TIME TRADING SCANNER")
    print("Trading the exact tokens you provided")
    print("")
    
    trader = RealTimeTrader()
    
    print("\n🎯 Choose mode:")
    print("1. Single scan (test)")
    print("2. Continuous trading (30-second cycles)")
    
    try:
        choice = input("\nEnter choice (1 or 2): ").strip()
        
        if choice == "1":
            trader.run_single()
        elif choice == "2":
            trader.run_continuous()
        else:
            print("❌ Invalid choice")
            
    except KeyboardInterrupt:
        print("\n🛑 Exiting...")
    
    print(f"\n✅ Trading complete!")
    print(f"📊 Final Stats: {trader.trade_count} trades, ${trader.total_pnl:.4f} PnL")

if __name__ == "__main__":
    main()
