#!/usr/bin/env python3
"""
Simple Live Trader - Places real orders on Gate.io
Sounds will come from the exchange interface, not this code
⚠️ WARNING: This places REAL trades with your money!
"""

import os
import time
import json
import requests
import hmac
import hashlib
from datetime import datetime

# Environment Variables
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

class SimpleLiveTrader:
    """Simple real trading bot - no artificial sounds"""
    
    def __init__(self):
        self.api_key = GATE_API_KEY
        self.secret = GATE_API_SECRET
        self.base_url = "https://api.gateio.ws/api/v4"
        self.settle = "usdt"
        
        print("🚀 SIMPLE LIVE TRADER")
        print("⚠️  WARNING: This will place REAL trades!")
        print("🔊 Listen for sounds from Gate.io exchange interface")
        print(f"🔑 API Key: {self.api_key[:10]}...")
    
    def _sign_request(self, method, path, query_string, payload):
        """Generate Gate.io API signature"""
        ts = str(int(time.time()))
        payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        sign_str = f"{method.upper()}\n{path}\n{query_string}\n{payload_hash}\n{ts}"
        sign = hmac.new(
            self.secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            digestmod=hashlib.sha512,
        ).hexdigest()
        
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "KEY": self.api_key,
            "Timestamp": ts,
            "SIGN": sign,
        }
    
    def place_order(self, symbol, side, size, price=None):
        """Place a live order - listen for exchange sound"""
        print(f"🎯 PLACING ORDER: {side} {size:.6f} {symbol} at ${price:.6f if price else 'MARKET'}")
        
        # Prepare order data
        order_data = {
            "settle": self.settle,
            "contract": symbol,
            "size": str(size),
            "price": str(price) if price else "0",  # 0 = market order
            "tif": "ioc"  # Immediate or Cancel
        }
        
        if side.upper() == "BUY":
            order_data["type"] = "limit" if price else "market"
        else:
            order_data["type"] = "limit" if price else "market"
        
        payload = json.dumps(order_data, separators=(",", ":"))
        path = f"/futures/{self.settle}/orders"
        headers = self._sign_request("POST", path, "", payload)
        
        try:
            response = requests.post(
                f"{self.base_url}{path}",
                headers=headers,
                data=payload,
                timeout=10
            )
            
            print(f"📡 Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                order_id = result.get('id', 'Unknown')
                print(f"✅ ORDER SUCCESS: ID {order_id}")
                print("🔊 Listen for Gate.io exchange sound...")
                return result
            else:
                error_msg = response.text
                print(f"❌ ORDER FAILED: {error_msg}")
                return None
                
        except Exception as e:
            print(f"❌ ORDER EXCEPTION: {e}")
            return None
    
    def get_market_price(self, symbol):
        """Get current market price"""
        try:
            response = requests.get(
                f"{self.base_url}/futures/{self.settle}/order_book?contract={symbol}&limit=1",
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                if data.get('asks') and data.get('bids'):
                    best_ask = float(data['asks'][0]['p'])
                    best_bid = float(data['bids'][0]['p'])
                    return best_bid, best_ask
            return None, None
        except Exception as e:
            print(f"❌ Price check failed: {e}")
            return None, None
    
    def run_live_trading(self, symbol="ENA_USDT", duration_minutes=3):
        """Run live trading - listen for exchange sounds"""
        print(f"\n🚀 STARTING LIVE TRADING")
        print(f"📊 Symbol: {symbol}")
        print(f"💰 Target nominal value: $0.01 - $0.10")
        print(f"⏱️ Duration: {duration_minutes} minutes")
        print("🔊 Keep Gate.io exchange open to hear order sounds")
        print("=" * 60)
        
        start_time = time.time()
        trade_count = 0
        
        while (time.time() - start_time) < duration_minutes * 60:
            try:
                # Get current price
                bid_price, ask_price = self.get_market_price(symbol)
                
                if bid_price and ask_price:
                    current_price = (bid_price + ask_price) / 2
                    print(f"\n📈 {symbol}: ${current_price:.6f} (Bid: ${bid_price:.6f}, Ask: ${ask_price:.6f})")
                    
                    # Calculate trade size for 0-10 cent nominal value
                    target_nominal = 0.05  # 5 cents target
                    trade_size = target_nominal / current_price
                    
                    # Ensure minimum order size
                    min_size = 0.001
                    trade_size = max(trade_size, min_size)
                    
                    nominal_value = trade_size * current_price
                    print(f"💰 Trade size: {trade_size:.6f} (nominal: ${nominal_value:.4f})")
                    
                    # Place alternating buy/sell orders
                    if trade_count % 2 == 0:
                        # Buy at bid price
                        print(f"🟢 BUYING at ${bid_price:.6f}")
                        result = self.place_order(symbol, "BUY", trade_size, bid_price)
                        if result:
                            trade_count += 1
                            print("⏳ Waiting 3 seconds...")
                            time.sleep(3)  # Wait between orders
                    else:
                        # Sell at ask price
                        print(f"🔴 SELLING at ${ask_price:.6f}")
                        result = self.place_order(symbol, "SELL", trade_size, ask_price)
                        if result:
                            trade_count += 1
                            print("⏳ Waiting 3 seconds...")
                            time.sleep(3)  # Wait between orders
                
                # Wait before next iteration
                print("⏳ Waiting 10 seconds before next trade...")
                time.sleep(10)
                
            except KeyboardInterrupt:
                print("\n🛑 Trading stopped by user")
                break
            except Exception as e:
                print(f"❌ Trading error: {e}")
                time.sleep(5)
        
        # Summary
        print(f"\n📊 TRADING COMPLETE")
        print(f"📈 Total orders placed: {trade_count}")
        print("🔊 You should have heard sounds from Gate.io exchange for each successful order")

def main():
    """Main function"""
    print("⚠️  LIVE TRADING WARNING ⚠️")
    print("This bot will place REAL orders with your money!")
    print("Keep Gate.io exchange open in your browser to hear order sounds")
    print("Press Ctrl+C to cancel immediately...")
    print("")
    
    # Check API keys
    if not GATE_API_KEY or not GATE_API_SECRET:
        print("❌ Missing GATE_API_KEY or GATE_API_SECRET")
        print("Run: source ~/.zshrc")
        return
    
    # Confirm before proceeding
    try:
        input("Press Enter to start live trading (or Ctrl+C to cancel)...")
    except KeyboardInterrupt:
        print("\n🛑 Cancelled")
        return
    
    # Create trader and start
    trader = SimpleLiveTrader()
    
    # Start with 0-10 cent trades on ENA_USDT
    trader.run_live_trading(
        symbol="ENA_USDT",
        duration_minutes=3  # 3 minutes for testing
    )

if __name__ == "__main__":
    main()
