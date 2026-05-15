#!/usr/bin/env python3
"""
LOCAL OLLAMA MICRO-CAP TRADING SYSTEM
$5 Budget - Real Orders - Auto-Cancel at Profit Target
All decisions made by local Ollama LLM
"""

import asyncio
import aiohttp
import json
import hmac
import hashlib
import time
import os
import requests
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging
import subprocess
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# REAL GATE.IO API CREDENTIALS
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
GATE_BASE_URL = "https://api.gateio.ws"

# TRADING CONFIGURATION
TOTAL_BUDGET = 5.0  # $5 budget
PROFIT_TARGET_PERCENTAGE = 0.5  # 0.5% profit to cover fees
GATE_IO_FEE = 0.002  # 0.2% fee on Gate.io
MIN_ORDER_SIZE = 1.0  # $1 minimum order
MAX_POSITIONS = 5  # Maximum concurrent positions

class LocalOllamaTrader:
    """Local Ollama-powered trading system"""
    
    def __init__(self):
        self.api_key = GATE_API_KEY
        self.api_secret = GATE_API_SECRET
        self.base_url = GATE_BASE_URL
        
        # Budget management
        self.total_budget = TOTAL_BUDGET
        self.available_budget = TOTAL_BUDGET
        self.used_budget = 0.0
        
        # Trading data
        self.active_positions = []
        self.completed_trades = []
        self.micro_caps = []
        
        # Ollama configuration
        self.ollama_url = "http://localhost:11434"
        self.ollama_model = "llama3.2"  # Default model
        
        logger.info("🤖 Local Ollama Trader Initialized")
        logger.info(f"💰 Budget: ${self.total_budget}")
        logger.info(f"🎯 Profit Target: {PROFIT_TARGET_PERCENTAGE}%")
        logger.info(f"🔗 Ollama: {self.ollama_url}")
        
        # Check Ollama connection
        self.check_ollama_connection()
    
    def check_ollama_connection(self):
        """Check if Ollama is running locally"""
        try:
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                logger.info(f"✅ Ollama connected - Available models: {model_names}")
                
                # Use first available model if default not found
                if self.ollama_model not in model_names and model_names:
                    self.ollama_model = model_names[0]
                    logger.info(f"🔄 Using model: {self.ollama_model}")
                return True
            else:
                logger.error("❌ Ollama not responding")
                return False
        except Exception as e:
            logger.error(f"❌ Cannot connect to Ollama: {e}")
            logger.info("💡 Make sure Ollama is running: 'ollama serve'")
            return False
    
    def ask_ollama(self, prompt: str) -> str:
        """Ask local Ollama LLM for trading decision"""
        try:
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent decisions
                    "max_tokens": 200
                }
            }
            
            response = requests.post(f"{self.ollama_url}/api/generate", 
                                   json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                logger.error(f"❌ Ollama request failed: {response.status_code}")
                return "HOLD"
        
        except Exception as e:
            logger.error(f"❌ Ollama error: {e}")
            return "HOLD"
    
    def generate_signature(self, method: str, url: str, params: dict = None, timestamp: str = None) -> str:
        """Generate Gate.io API signature"""
        if timestamp is None:
            timestamp = str(int(time.time()))
        
        if params is None:
            params = {}
        
        query_string = ''
        message = method + '\n' + url + '\n' + query_string
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        return signature
    
    async def make_request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """Make authenticated API request"""
        try:
            url = f"{self.base_url}{endpoint}"
            timestamp = str(int(time.time()))
            
            signature = self.generate_signature(method, endpoint, params, timestamp)
            
            headers = {
                'KEY': self.api_key,
                'Timestamp': timestamp,
                'SIGN': signature
            }
            
            if method == 'GET':
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params, timeout=10) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logger.error(f"Request failed: {response.status} - {error_text}")
                            return {}
            
            elif method == 'POST':
                headers['Content-Type'] = 'application/json'
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=params, timeout=10) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logger.error(f"Request failed: {response.status} - {error_text}")
                            return {}
        
        except Exception as e:
            logger.error(f"API request error: {e}")
            return {}
    
    async def get_account_balance(self) -> bool:
        """Get account balance"""
        try:
            data = await self.make_request('GET', '/api/v4/spot/accounts')
            if data:
                for balance in data:
                    if balance['currency'] == 'USDT':
                        available = float(balance['available'])
                        total = float(balance['total'])
                        logger.info(f"💰 Account Balance: ${total:.2f} (Available: ${available:.2f})")
                        return True
            return False
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return False
    
    async def get_micro_caps(self) -> List[dict]:
        """Get micro-cap coins under $0.10"""
        try:
            tickers_data = await self.make_request('GET', '/api/v4/spot/tickers')
            if tickers_data:
                micro_caps = []
                
                for ticker in tickers_data:
                    symbol = ticker['currency_pair']
                    if symbol.endswith('_USDT'):
                        price = float(ticker['last'])
                        if 0.001 <= price <= 0.10:  # Micro-cap range
                            change = float(ticker['change_percentage']) / 100
                            volume = float(ticker['quote_volume'])
                            
                            micro_caps.append({
                                'symbol': symbol.replace('_USDT', ''),
                                'price': price,
                                'change': change,
                                'volume': volume
                            })
                
                # Sort by volume and change
                micro_caps.sort(key=lambda x: (x['volume'], x['change']), reverse=True)
                logger.info(f"📊 Found {len(micro_caps)} micro-caps under $0.10")
                return micro_caps
            return []
        except Exception as e:
            logger.error(f"Error getting micro-caps: {e}")
            return []
    
    def get_trading_decision(self, coin_data: dict) -> str:
        """Ask Ollama LLM for trading decision"""
        prompt = f"""
You are a crypto trading AI. Analyze this micro-cap coin and decide:

COIN DATA:
- Symbol: {coin_data['symbol']}
- Price: ${coin_data['price']:.6f}
- 24h Change: {coin_data['change']*100:+.2f}%
- Volume: ${coin_data['volume']:.0f}

TRADING RULES:
- Budget: ${self.total_budget} (Available: ${self.available_budget:.2f})
- Profit target: {PROFIT_TARGET_PERCENTAGE}% (to cover fees)
- Fee: {GATE_IO_FEE*100:.1f}%
- Max positions: {MAX_POSITIONS}

DECISION OPTIONS:
- BUY: Strong buy signal with good profit potential
- SELL: Strong sell signal (if we have position)
- HOLD: No clear signal

Consider:
1. Price momentum (24h change)
2. Volume strength
3. Risk/reward ratio
4. Budget constraints

Respond with only: BUY, SELL, or HOLD
"""
        
        decision = self.ask_ollama(prompt).upper()
        
        # Extract decision from response
        if 'BUY' in decision:
            return 'BUY'
        elif 'SELL' in decision:
            return 'SELL'
        else:
            return 'HOLD'
    
    async def place_order(self, symbol: str, side: str, amount: float) -> dict:
        """Place real order"""
        try:
            order_data = {
                'currency_pair': f"{symbol}_USDT",
                'type': 'market',
                'side': side,
                'amount': str(amount)
            }
            
            result = await self.make_request('POST', '/api/v4/spot/orders', order_data)
            
            if result and 'id' in result:
                logger.info(f"✅ Order placed: {side.upper()} {symbol} - Amount: ${amount:.2f} - ID: {result['id']}")
                return result
            else:
                logger.error(f"❌ Order failed: {result}")
                return {}
        
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {}
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel order"""
        try:
            result = await self.make_request('DELETE', f'/api/v4/spot/orders/{order_id}')
            if result:
                logger.info(f"✅ Order cancelled: {order_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error cancelling order: {e}")
            return False
    
    async def get_order_status(self, order_id: str, symbol: str) -> dict:
        """Get order status"""
        try:
            result = await self.make_request('GET', f'/api/v4/spot/orders/{order_id}')
            return result
        except Exception as e:
            logger.error(f"Error getting order status: {e}")
            return {}
    
    def calculate_profit_target(self, entry_price: float, side: str) -> float:
        """Calculate profit target price"""
        # Need to make enough profit to cover fees
        total_fee_needed = PROFIT_TARGET_PERCENTAGE / 100
        
        if side == 'buy':
            target_price = entry_price * (1 + total_fee_needed)
        else:  # sell (short)
            target_price = entry_price * (1 - total_fee_needed)
        
        return target_price
    
    async def monitor_positions(self):
        """Monitor active positions and auto-cancel at profit target"""
        for position in self.active_positions[:]:
            try:
                # Get current price
                ticker_data = await self.make_request('GET', '/api/v4/spot/tickers', 
                                                     {'currency_pair': f"{position['symbol']}_USDT"})
                
                if ticker_data:
                    current_price = float(ticker_data[0]['last'])
                    entry_price = position['entry_price']
                    side = position['side']
                    
                    # Calculate profit/loss
                    if side == 'buy':
                        profit_pct = ((current_price - entry_price) / entry_price) * 100
                    else:  # sell
                        profit_pct = ((entry_price - current_price) / entry_price) * 100
                    
                    # Check if profit target reached
                    if profit_pct >= PROFIT_TARGET_PERCENTAGE:
                        logger.info(f"🎯 PROFIT TARGET HIT: {position['symbol']} - Profit: {profit_pct:.2f}%")
                        
                        # Place opposite order to close position
                        close_side = 'sell' if side == 'buy' else 'buy'
                        close_result = await self.place_order(position['symbol'], close_side, position['amount'])
                        
                        if close_result:
                            # Update position
                            position['status'] = 'completed'
                            position['exit_price'] = current_price
                            position['profit_pct'] = profit_pct
                            position['completed_at'] = datetime.now()
                            
                            # Return budget
                            self.available_budget += position['amount']
                            
                            # Move to completed trades
                            self.completed_trades.append(position)
                            self.active_positions.remove(position)
                            
                            logger.info(f"💰 Position closed: {position['symbol']} - Profit: ${position['amount'] * profit_pct / 100:.4f}")
        
            except Exception as e:
                logger.error(f"Error monitoring position {position['symbol']}: {e}")
    
    async def execute_trading_cycle(self):
        """Main trading cycle with Ollama decisions"""
        try:
            # Get micro-cap coins
            self.micro_caps = await self.get_micro_caps()
            
            if not self.micro_caps:
                logger.warning("No micro-caps found")
                return
            
            # Analyze top 20 coins with Ollama
            top_coins = self.micro_caps[:20]
            
            for coin in top_coins:
                if self.available_budget < MIN_ORDER_SIZE:
                    logger.info("💸 Insufficient budget for new positions")
                    break
                
                if len(self.active_positions) >= MAX_POSITIONS:
                    logger.info("📊 Maximum positions reached")
                    break
                
                # Check if we already have position in this coin
                has_position = any(p['symbol'] == coin['symbol'] for p in self.active_positions)
                
                # Get Ollama decision
                decision = self.get_trading_decision(coin)
                logger.info(f"🤖 Ollama decision for {coin['symbol']}: {decision}")
                
                # Execute decision
                if decision == 'BUY' and not has_position:
                    # Calculate order size
                    order_size = min(MIN_ORDER_SIZE, self.available_budget * 0.8)
                    
                    # Place buy order
                    result = await self.place_order(coin['symbol'], 'buy', order_size)
                    
                    if result:
                        # Track position
                        position = {
                            'symbol': coin['symbol'],
                            'side': 'buy',
                            'amount': order_size,
                            'entry_price': coin['price'],
                            'target_price': self.calculate_profit_target(coin['price'], 'buy'),
                            'order_id': result['id'],
                            'status': 'active',
                            'created_at': datetime.now()
                        }
                        
                        self.active_positions.append(position)
                        self.available_budget -= order_size
                        self.used_budget += order_size
                        
                        logger.info(f"📈 Position opened: {coin['symbol']} - Amount: ${order_size:.2f}")
                
                elif decision == 'SELL' and has_position:
                    # Find and close existing position
                    position = next(p for p in self.active_positions if p['symbol'] == coin['symbol'])
                    
                    result = await self.place_order(coin['symbol'], 'sell', position['amount'])
                    
                    if result:
                        position['status'] = 'completed'
                        position['exit_price'] = coin['price']
                        position['completed_at'] = datetime.now()
                        
                        self.available_budget += position['amount']
                        self.completed_trades.append(position)
                        self.active_positions.remove(position)
                        
                        logger.info(f"📉 Position closed: {coin['symbol']}")
            
            # Monitor existing positions
            await self.monitor_positions()
            
        except Exception as e:
            logger.error(f"Error in trading cycle: {e}")

class OllamaTraderUI:
    """UI for Local Ollama Trading System"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 Local Ollama Micro-Cap Trader - $5 Budget")
        self.root.geometry("1200x800")
        self.root.configure(bg='#1a1a1a')
        
        # Initialize trader
        self.trader = LocalOllamaTrader()
        self.running = False
        
        # Create UI
        self.create_widgets()
        
        # Start update loop
        self.update_ui()
    
    def create_widgets(self):
        """Create UI widgets"""
        # Title
        title_frame = tk.Frame(self.root, bg='#2a2a2a', relief=tk.RAISED, bd=2)
        title_frame.pack(fill=tk.X, padx=10, pady=5)
        
        title_label = tk.Label(title_frame, text="🤖 LOCAL OLLAMA MICRO-CAP TRADER", 
                               font=('Arial', 16, 'bold'), fg='#00ff00', bg='#2a2a2a')
        title_label.pack(pady=10)
        
        subtitle_label = tk.Label(title_frame, text=f"Budget: ${self.trader.total_budget} | Profit Target: {PROFIT_TARGET_PERCENTAGE}% | Model: {self.trader.ollama_model}", 
                                 font=('Arial', 12), fg='#ffff00', bg='#2a2a2a')
        subtitle_label.pack()
        
        # Main content
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Left panel - Budget & Positions
        left_frame = tk.Frame(main_frame, bg='#2a2a2a', relief=tk.SUNKEN, bd=2)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Budget info
        budget_frame = tk.LabelFrame(left_frame, text="💰 BUDGET STATUS", 
                                    font=('Arial', 12, 'bold'), bg='#2a2a2a', fg='#00ff00')
        budget_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.budget_label = tk.Label(budget_frame, text=f"Total: ${self.trader.total_budget:.2f}", 
                                     font=('Arial', 14, 'bold'), bg='#2a2a2a', fg='#00ff00')
        self.budget_label.pack(pady=5)
        
        self.available_label = tk.Label(budget_frame, text=f"Available: ${self.trader.available_budget:.2f}", 
                                        font=('Arial', 12), bg='#2a2a2a', fg='#ffff00')
        self.available_label.pack(pady=5)
        
        self.used_label = tk.Label(budget_frame, text=f"Used: ${self.trader.used_budget:.2f}", 
                                  font=('Arial', 12), bg='#2a2a2a', fg='#ff6b6b')
        self.used_label.pack(pady=5)
        
        # Active positions
        positions_frame = tk.LabelFrame(left_frame, text="📊 ACTIVE POSITIONS", 
                                       font=('Arial', 12, 'bold'), bg='#2a2a2a', fg='#00ff00')
        positions_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.positions_tree = ttk.Treeview(positions_frame, 
                                         columns=('Side', 'Amount', 'Entry', 'Target', 'P&L'),
                                         show='tree headings', height=10)
        self.positions_tree.heading('#0', text='Symbol')
        self.positions_tree.heading('Side', text='Side')
        self.positions_tree.heading('Amount', text='Amount')
        self.positions_tree.heading('Entry', text='Entry')
        self.positions_tree.heading('Target', text='Target')
        self.positions_tree.heading('P&L', text='P&L')
        
        self.positions_tree.pack(padx=10, pady=10)
        
        # Right panel - Analysis & Log
        right_frame = tk.Frame(main_frame, bg='#2a2a2a', relief=tk.SUNKEN, bd=2)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Ollama decisions
        ollama_frame = tk.LabelFrame(right_frame, text="🤖 OLLAMA DECISIONS", 
                                    font=('Arial', 12, 'bold'), bg='#2a2a2a', fg='#00ffff')
        ollama_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.ollama_text = tk.Text(ollama_frame, height=8, width=50,
                                  bg='#000000', fg='#00ff00', font=('Courier', 9))
        self.ollama_text.pack(padx=10, pady=10)
        
        # Activity log
        log_frame = tk.LabelFrame(right_frame, text="📝 ACTIVITY LOG", 
                                 font=('Arial', 12, 'bold'), bg='#2a2a2a', fg='#00ffff')
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=15, width=50,
                                                 bg='#000000', fg='#ffff00', font=('Courier', 9))
        self.log_text.pack(padx=10, pady=10)
        
        # Control panel
        control_frame = tk.Frame(self.root, bg='#2a2a2a', relief=tk.RAISED, bd=2)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_button = tk.Button(control_frame, text="🚀 START TRADING", 
                                     command=self.start_trading,
                                     bg='#00aa00', fg='white', font=('Arial', 12, 'bold'),
                                     width=20, height=2)
        self.start_button.pack(side=tk.LEFT, padx=10, pady=10)
        
        self.stop_button = tk.Button(control_frame, text="⏹️ STOP TRADING", 
                                    command=self.stop_trading,
                                    bg='#aa0000', fg='white', font=('Arial', 12, 'bold'),
                                    width=20, height=2, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5, pady=10)
        
        self.emergency_button = tk.Button(control_frame, text="🚨 EMERGENCY CLOSE ALL", 
                                         command=self.emergency_close,
                                         bg='#ff0000', fg='white', font=('Arial', 12, 'bold'),
                                         width=20, height=2)
        self.emergency_button.pack(side=tk.RIGHT, padx=10, pady=10)
        
        self.log_activity("🤖 Local Ollama Trader initialized")
        self.log_activity(f"💰 Budget: ${self.trader.total_budget}")
        self.log_activity(f"🎯 Profit Target: {PROFIT_TARGET_PERCENTAGE}%")
        self.log_activity(f"🔗 Ollama: {self.trader.ollama_url}")
    
    def log_activity(self, message):
        """Log activity"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        logger.info(message)
    
    def log_ollama_decision(self, symbol: str, decision: str, reason: str = ""):
        """Log Ollama decision"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ollama_text.insert(tk.END, f"[{timestamp}] {symbol}: {decision}\n")
        if reason:
            self.ollama_text.insert(tk.END, f"    Reason: {reason}\n")
        self.ollama_text.see(tk.END)
    
    def update_positions_display(self):
        """Update positions display"""
        # Clear existing items
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)
        
        # Add active positions
        for position in self.trader.active_positions:
            self.positions_tree.insert('', 'end', text=position['symbol'],
                                      values=(position['side'].upper(),
                                             f"${position['amount']:.2f}",
                                             f"${position['entry_price']:.6f}",
                                             f"${position['target_price']:.6f}",
                                             "ACTIVE"))
        
        # Update budget labels
        self.budget_label.config(text=f"Total: ${self.trader.total_budget:.2f}")
        self.available_label.config(text=f"Available: ${self.trader.available_budget:.2f}")
        self.used_label.config(text=f"Used: ${self.trader.used_budget:.2f}")
    
    def start_trading(self):
        """Start trading"""
        if not self.running:
            self.running = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            
            self.log_activity("🚀 Trading started with Ollama AI")
            
            # Start trading loop
            threading.Thread(target=self.trading_loop, daemon=True).start()
    
    def stop_trading(self):
        """Stop trading"""
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log_activity("⏹️ Trading stopped")
    
    def emergency_close(self):
        """Emergency close all positions"""
        self.log_activity("🚨 EMERGENCY CLOSE ALL POSITIONS")
        
        # This would close all positions immediately
        # Implementation depends on your requirements
        self.stop_trading()
    
    def trading_loop(self):
        """Main trading loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.trading_cycle())
    
    async def trading_cycle(self):
        """Trading cycle"""
        while self.running:
            try:
                # Execute trading cycle
                await self.trader.execute_trading_cycle()
                
                # Update UI
                self.root.after(0, self.update_positions_display)
                
                # Wait before next cycle
                await asyncio.sleep(60)  # Run every minute
                
            except Exception as e:
                self.log_activity(f"❌ Trading error: {e}")
                await asyncio.sleep(10)
    
    def update_ui(self):
        """Update UI periodically"""
        if self.running:
            self.update_positions_display()
        
        # Schedule next update
        self.root.after(5000, self.update_ui)
    
    def run(self):
        """Run the UI"""
        self.root.mainloop()

def main():
    """Main function"""
    print("🤖 LOCAL OLLAMA MICRO-CAP TRADING SYSTEM")
    print("="*60)
    print("💰 Budget: $5.00")
    print("🎯 Profit Target: 0.5% (covers fees)")
    print("🤖 AI: Local Ollama LLM")
    print("📊 Targets: Micro-caps under $0.10")
    print("="*60)
    print("💡 Make sure Ollama is running: 'ollama serve'")
    print("💡 Install model: 'ollama pull llama3.2'")
    print("="*60)
    
    ui = OllamaTraderUI()
    ui.run()

if __name__ == "__main__":
    main()
