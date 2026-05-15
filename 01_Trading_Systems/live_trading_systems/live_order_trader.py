#!/usr/bin/env python3
"""
Live Order Trader - Places real orders and plays sound alerts
⚠️ WARNING: This places REAL trades with your money!
"""

import os
import time
import json
import requests
import hmac
import hashlib
import subprocess
from datetime import datetime

# Environment Variables
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
ENABLE_SOUND = os.getenv("ENABLE_SOUND", "1") == "1"

class LiveOrderTrader:
    """Real trading bot that places live orders"""
    
    def __init__(self):
        self.api_key = GATE_API_KEY
        self.secret = GATE_API_SECRET
        self.base_url = "https://api.gateio.ws/api/v4"
        self.settle = "usdt"
        
        # Sound system
        self.sound_enabled = ENABLE_SOUND
        
        print("🚀 LIVE ORDER TRADER INITIALIZED")
        print("⚠️  WARNING: This will place REAL trades!")
        print(f"🔑 API Key: {self.api_key[:10]}...")
        print(f"🔊 Sound: {'Enabled' if self.sound_enabled else 'Disabled'}")
    
    def play_sound(self, sound_name):
        """Play macOS system sound"""
        if not self.sound_enabled:
            return
        
        try:
            subprocess.run([
                "afplay", 
                f"/System/Library/Sounds/{sound_name}.aiff"
            ], capture_output=True, timeout=5)
            print(f"🔊 Played: {sound_name}")
        except Exception as e:
            print(f"❌ Sound error: {e}")
    
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
        """Place a live order"""
        print(f"🎯 PLACING LIVE ORDER: {side} {size} {symbol}")
        
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
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ ORDER PLACED: {result.get('id', 'Unknown ID')}")
                self.play_sound("Glass")  # Trade executed sound
                return result
            else:
                error_msg = response.text
                print(f"❌ ORDER FAILED: {error_msg}")
                self.play_sound("Basso")  # Error sound
                return None
                
        except Exception as e:
            print(f"❌ ORDER EXCEPTION: {e}")
            self.play_sound("Basso")
            return None
    
    def get_account_balance(self):
        """Get account balance"""
        path = f"/futures/{self.settle}/accounts"
        headers = self._sign_request("GET", path, "", "")
        
        try:
            response = requests.get(f"{self.base_url}{path}", headers=headers, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Balance check failed: {response.text}")
                return None
        except Exception as e:
            print(f"❌ Balance exception: {e}")
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
    
    def run_live_trading(self, symbol="ENA_USDT", duration_minutes=2):
        """Run live trading session with 0-10 cent nominal value"""
        print(f"\n🚀 STARTING LIVE TRADING")
        print(f"📊 Symbol: {symbol}")
        print(f"💰 Target nominal value: $0.01 - $0.10")
        print(f"⏱️ Duration: {duration_minutes} minutes")
        print("=" * 50)
        
        # Check balance first
        balance = self.get_account_balance()
        if balance:
            available = float(balance.get('available', 0))
            print(f"💳 Available balance: ${available:.2f}")
        else:
            print("❌ Cannot check balance - stopping")
            return
        
        self.play_sound("Ping")  # Start alert
        
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
                            time.sleep(2)  # Wait between orders
                    else:
                        # Sell at ask price
                        print(f"🔴 SELLING at ${ask_price:.6f}")
                        result = self.place_order(symbol, "SELL", trade_size, ask_price)
                        if result:
                            trade_count += 1
                            time.sleep(2)  # Wait between orders
                
                # Wait before next iteration
                time.sleep(5)
                
            except KeyboardInterrupt:
                print("\n🛑 Trading stopped by user")
                break
            except Exception as e:
                print(f"❌ Trading error: {e}")
                time.sleep(5)
        
        # Summary
        print(f"\n📊 TRADING COMPLETE")
        print(f"📈 Total trades placed: {trade_count}")
        self.play_sound("Ping")  # End alert

def main():
    """Main function"""
    print("⚠️  LIVE TRADING WARNING ⚠️")
    print("This bot will place REAL orders with your money!")
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
    trader = LiveOrderTrader()
    
    # Start with 0-10 cent trades on ENA_USDT
    trader.run_live_trading(
        symbol="ENA_USDT",
        duration_minutes=2  # Short duration for testing
    )

if __name__ == "__main__":
    main()
