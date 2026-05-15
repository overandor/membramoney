#!/usr/bin/env python3
"""
Multi-Token Trading System
Trade all high-volume tokens with AI optimization
"""

import os
import sys
import time
import json
import signal
import logging
import asyncio
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import requests
import hmac
import hashlib
from dataclasses import dataclass
from collections import deque
import queue
import math

# High-volume tokens from your list
TRADING_SYMBOLS = [
    "HIPPO_USDT", "NATIX_USDT", "TOSHI_USDT", "ELIZAOS_USDT", "ETH5S_USDT",
    "PUMP_USDT", "COMMON_USDT", "XRP5L_USDT", "MRLN_USDT", "LINK5L_USDT",
    "XPIN_USDT", "RLS_USDT", "AVAX5L_USDT", "MEMEFI_USDT", "FARTCOIN5S_USDT",
    "OMI_USDT", "DOGE_USDT", "PTB_USDT", "DOGE3S_USDT", "XEM_USDT",
    "BLUAI_USDT", "ADA5L_USDT", "TREAT_USDT", "BTC5L_USDT", "ROOBEE_USDT",
    "PEPE5S_USDT", "ART_USDT", "XNL_USDT", "HMSTR_USDT", "BLAST_USDT"
]

@dataclass
class TokenData:
    symbol: str
    price: float
    bid: float
    ask: float
    volume: float
    change_24h: float
    spread_pct: float
    timestamp: float

@dataclass
class TokenTrade:
    timestamp: float
    symbol: str
    side: str
    size: float
    price: float
    nominal_value: float
    pnl: float = 0.0

class MultiTokenClient:
    """Enhanced client for multi-token trading"""
    
    def __init__(self):
        self.api_key = os.getenv("GATE_API_KEY", "")
        self.api_secret = os.getenv("GATE_API_SECRET", "")
        self.base_url = "https://api.gateio.ws/api/v4"
        self.settle = "usdt"
        self.session = requests.Session()
        self.logger = logging.getLogger('MultiTokenClient')
        
    def _sign_request(self, method: str, path: str, payload: str) -> Dict[str, str]:
        if not self.api_key or not self.api_secret:
            return {}
        
        ts = str(int(time.time()))
        payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        sign_str = f"{method.upper()}\n{path}\n{payload_hash}\n{ts}"
        sign = hmac.new(self.api_key.encode(), sign_str.encode(), hashlib.sha512).hexdigest()
        
        return {"KEY": self.api_key, "Timestamp": ts, "SIGN": sign}
    
    def _make_request(self, method: str, path: str, payload: str = "", private: bool = False) -> Dict:
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if private:
            headers.update(self._sign_request(method, path, payload))
        
        try:
            response = self.session.request(method, f"{self.base_url}{path}", headers=headers, 
                                         data=payload if payload else None, timeout=10)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_all_token_data(self) -> List[TokenData]:
        """Get data for all trading tokens"""
        tokens = []
        
        for symbol in TRADING_SYMBOLS:
            try:
                # Get ticker data
                ticker_result = self._make_request("GET", f"/spot/tickers?currency_pair={symbol}")
                if not ticker_result["success"]:
                    continue
                
                ticker = ticker_result["data"][0] if ticker_result["data"] else None
                if not ticker:
                    continue
                
                # Get order book
                book_result = self._make_request("GET", f"/spot/order_book?currency_pair={symbol}&limit=1")
                if not book_result["success"]:
                    continue
                
                book = book_result["data"]
                if not book.get("bids") or not book.get("asks"):
                    continue
                
                bid = float(book["bids"][0][0])
                ask = float(book["asks"][0][0])
                base_volume = float(ticker.get("base_volume", 0))
                change_pct = float(ticker.get("change_percentage", 0))
                
                token = TokenData(
                    symbol=symbol,
                    price=float(ticker.get("last", 0)),
                    bid=bid,
                    ask=ask,
                    volume=base_volume,
                    change_24h=change_pct,
                    spread_pct=((ask - bid) / bid) * 100 if bid > 0 else 0,
                    timestamp=time.time()
                )
                
                tokens.append(token)
                
            except Exception as e:
                self.logger.error(f"Error getting data for {symbol}: {e}")
                continue
        
        return tokens
    
    def place_order(self, symbol: str, side: str, size: float, price: float) -> Dict:
        """Place order for any token"""
        order_data = {
            "currency_pair": symbol,
            "type": "limit",
            "side": side,
            "amount": str(size),
            "price": str(price),
            "time_in_force": "ioc"
        }
        
        payload = json.dumps(order_data, separators=(",", ":"))
        return self._make_request("POST", "/spot/orders", payload, private=True)
    
    def get_account(self) -> Dict:
        """Get account balance"""
        result = self._make_request("GET", "/spot/accounts", "", private=True)
        return result.get("data", []) if result["success"] else []
    
    def calculate_order_size(self, price: float, target_nominal: float = 0.05) -> float:
        """Calculate order size for target nominal value"""
        if price <= 0:
            return 0
        size = target_nominal / price
        min_size = 0.001
        return max(size, min_size)

class MultiTokenTrader:
    """Multi-token trading engine with AI optimization"""
    
    def __init__(self):
        self.client = MultiTokenClient()
        self.symbols = TRADING_SYMBOLS
        self.min_nominal = 0.01
        self.max_nominal = 0.10
        self.target_nominal = 0.05
        
        # Trading state
        self.running = False
        self.cycle_count = 0
        self.start_time = time.time()
        
        # Data storage
        self.token_data = deque(maxlen=100)
        self.trades = deque(maxlen=1000)
        self.performance = {}
        
        # Initialize performance tracking
        for symbol in self.symbols:
            self.performance[symbol] = {
                "trades": 0,
                "profits": 0,
                "losses": 0,
                "total_pnl": 0.0
            }
        
        self.logger = logging.getLogger('MultiTokenTrader')
        
    def analyze_token_opportunities(self, tokens: List[TokenData]) -> List[Dict]:
        """Analyze tokens for trading opportunities"""
        opportunities = []
        
        for token in tokens:
            # Volume filter - only high volume tokens
            if token.volume < 1000000:  # $1M minimum volume
                continue
            
            # Spread filter - reasonable spreads only
            if token.spread_pct > 1.0:  # Max 1% spread
                continue
            
            # Volatility filter - look for movement
            if abs(token.change_24h) < 2.0:  # Min 2% movement
                continue
            
            # Calculate opportunity score
            volume_score = min(token.volume / 10000000, 1.0)  # Max at $10M volume
            volatility_score = min(abs(token.change_24h) / 20.0, 1.0)  # Max at 20% movement
            spread_score = max(0, 1.0 - token.spread_pct)  # Lower spread is better
            
            opportunity_score = (volume_score * 0.4 + volatility_score * 0.4 + spread_score * 0.2)
            
            # Determine trading direction
            if token.change_24h > 5.0:  # Strong uptrend - look for pullbacks to buy
                direction = "BUY_DIP"
                reasoning = f"Strong uptrend (+{token.change_24h:.1f}%) - buying on pullbacks"
            elif token.change_24h < -5.0:  # Strong downtrend - look for bounces to sell
                direction = "SELL_RALLY"
                reasoning = f"Strong downtrend ({token.change_24h:.1f}%) - selling on rallies"
            elif token.change_24h > 0:  # Moderate uptrend
                direction = "BUY"
                reasoning = f"Uptrend (+{token.change_24h:.1f}%) - momentum buying"
            else:  # Moderate downtrend
                direction = "SELL"
                reasoning = f"Downtrend ({token.change_24h:.1f}%) - momentum selling"
            
            opportunities.append({
                "symbol": token.symbol,
                "direction": direction,
                "score": opportunity_score,
                "reasoning": reasoning,
                "token": token
            })
        
        # Sort by opportunity score
        opportunities.sort(key=lambda x: x["score"], reverse=True)
        
        return opportunities[:10]  # Top 10 opportunities
    
    def execute_trades(self, opportunities: List[Dict]) -> List[TokenTrade]:
        """Execute trades on best opportunities"""
        executed_trades = []
        
        # Take top 3 opportunities
        for opp in opportunities[:3]:
            if opp["score"] < 0.3:  # Minimum score threshold
                continue
            
            token = opp["token"]
            direction = opp["direction"]
            
            # Calculate order size based on opportunity strength
            nominal_multiplier = 0.5 + (opp["score"] * 0.5)  # 0.5x to 1.0x based on score
            target_nominal = self.target_nominal * nominal_multiplier
            
            try:
                if "BUY" in direction:
                    # Buy at best bid
                    size = self.client.calculate_order_size(token.bid, target_nominal)
                    result = self.client.place_order(token.symbol, "buy", size, token.bid)
                    
                    if result["success"]:
                        trade = TokenTrade(
                            timestamp=time.time(),
                            symbol=token.symbol,
                            side="BUY",
                            size=size,
                            price=token.bid,
                            nominal_value=size * token.bid
                        )
                        executed_trades.append(trade)
                        self.trades.append(trade)
                        self.performance[token.symbol]["trades"] += 1
                        self.logger.info(f"✅ BUY {token.symbol}: {size:.6f} @ ${token.bid:.6f} (${trade.nominal_value:.4f})")
                    
                elif "SELL" in direction:
                    # Sell at best ask
                    size = self.client.calculate_order_size(token.ask, target_nominal)
                    result = self.client.place_order(token.symbol, "sell", size, token.ask)
                    
                    if result["success"]:
                        trade = TokenTrade(
                            timestamp=time.time(),
                            symbol=token.symbol,
                            side="SELL",
                            size=size,
                            price=token.ask,
                            nominal_value=size * token.ask
                        )
                        executed_trades.append(trade)
                        self.trades.append(trade)
                        self.performance[token.symbol]["trades"] += 1
                        self.logger.info(f"✅ SELL {token.symbol}: {size:.6f} @ ${token.ask:.6f} (${trade.nominal_value:.4f})")
                
            except Exception as e:
                self.logger.error(f"❌ Trade execution error for {token.symbol}: {e}")
        
        return executed_trades
    
    def run_trading_cycle(self) -> Dict:
        """Run one complete trading cycle"""
        self.cycle_count += 1
        cycle_start = time.time()
        
        try:
            # Get all token data
            tokens = self.client.get_all_token_data()
            self.token_data.append(tokens)
            
            # Analyze opportunities
            opportunities = self.analyze_token_opportunities(tokens)
            
            # Execute trades
            executed_trades = self.execute_trades(opportunities)
            
            # Calculate cycle stats
            total_nominal = sum(trade.nominal_value for trade in executed_trades)
            
            elapsed = time.time() - cycle_start
            
            return {
                "success": True,
                "cycle": self.cycle_count,
                "tokens_analyzed": len(tokens),
                "opportunities_found": len(opportunities),
                "trades_executed": len(executed_trades),
                "total_nominal": total_nominal,
                "cycle_time": elapsed,
                "top_opportunities": opportunities[:5]
            }
            
        except Exception as e:
            self.logger.error(f"❌ Cycle {self.cycle_count} error: {e}")
            return {"success": False, "error": str(e)}
    
    def get_account_summary(self) -> Dict:
        """Get account balance summary"""
        accounts = self.client.get_account()
        
        summary = {
            "total_balance": 0.0,
            "available_balance": 0.0,
            "currencies": {}
        }
        
        for account in accounts:
            currency = account.get("currency", "")
            available = float(account.get("available", 0))
            frozen = float(account.get("frozen", 0))
            
            if currency == "USDT":
                summary["available_balance"] = available
                summary["total_balance"] = available + frozen
            
            if available > 0:
                summary["currencies"][currency] = {
                    "available": available,
                    "frozen": frozen,
                    "total": available + frozen
                }
        
        return summary

class MultiTokenDashboard:
    """Dashboard for multi-token trading"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🚀 Multi-Token Trading Dashboard - 30 High-Volume Tokens")
        self.root.geometry("1600x1000")
        self.root.configure(bg='#0a0a0a')
        
        # Initialize trader
        self.trader = MultiTokenTrader()
        
        # Setup logging
        self.setup_logging()
        
        # Update queue
        self.update_queue = queue.Queue()
        
        # Create UI
        self.create_ui()
        
        # Start trading thread
        self.trading_thread = None
        self.start_trading()
        
        # Start UI updates
        self.update_ui()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.logger.info("🚀 Multi-Token Dashboard initialized")
    
    def setup_logging(self):
        """Setup logging"""
        log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, f'multi_token_{datetime.now().strftime("%Y%m%d")}.log')
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            handlers=[
                logging.FileHandler(log_file, mode='a'),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger('Dashboard')
    
    def create_ui(self):
        """Create the UI"""
        # Colors
        self.bg_color = '#0a0a0a'
        self.fg_color = '#00ff00'
        self.error_color = '#ff4444'
        self.warning_color = '#ffaa00'
        
        # Main container
        main_frame = tk.Frame(self.root, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_label = tk.Label(main_frame, text="🚀 MULTI-TOKEN TRADING DASHBOARD", 
                              font=('Arial', 18, 'bold'), fg=self.fg_color, bg=self.bg_color)
        title_label.pack(pady=5)
        
        subtitle_label = tk.Label(main_frame, text="Trading 30 High-Volume Tokens with AI Optimization", 
                                 font=('Arial', 12), fg=self.fg_color, bg=self.bg_color)
        subtitle_label.pack(pady=2)
        
        # Create sections
        self.create_account_section(main_frame)
        self.create_opportunities_section(main_frame)
        self.create_tokens_section(main_frame)
        self.create_trades_section(main_frame)
        self.create_log_section(main_frame)
        self.create_control_section(main_frame)
    
    def create_account_section(self, parent):
        """Create account section"""
        account_frame = tk.LabelFrame(parent, text="💰 ACCOUNT BALANCE", 
                                    font=('Arial', 12, 'bold'), fg=self.fg_color, bg=self.bg_color)
        account_frame.pack(fill=tk.X, pady=5)
        
        account_grid = tk.Frame(account_frame, bg=self.bg_color)
        account_grid.pack(fill=tk.X, padx=5, pady=5)
        
        self.account_labels = {}
        account_items = [
            ("total", "Total Balance:", "$0.00"),
            ("available", "Available:", "$0.00"),
            ("trades", "Total Trades:", "0"),
            ("nominal", "Cycle Nominal:", "$0.00")
        ]
        
        for i, (key, label, default) in enumerate(account_items):
            row = i // 2
            col = (i % 4)
            
            tk.Label(account_grid, text=label, font=('Arial', 10), 
                    fg=self.fg_color, bg=self.bg_color).grid(row=row, column=col, sticky='w', padx=5)
            self.account_labels[key] = tk.Label(account_grid, text=default, font=('Arial', 10, 'bold'),
                                              fg=self.fg_color, bg=self.bg_color)
            self.account_labels[key].grid(row=row, column=col+1, sticky='w', padx=5)
    
    def create_opportunities_section(self, parent):
        """Create opportunities section"""
        opp_frame = tk.LabelFrame(parent, text="🎯 TOP TRADING OPPORTUNITIES", 
                                 font=('Arial', 12, 'bold'), fg=self.fg_color, bg=self.bg_color)
        opp_frame.pack(fill=tk.X, pady=5)
        
        # Create treeview for opportunities
        columns = ('Symbol', 'Direction', 'Score', 'Price', 'Change%', 'Volume', 'Reasoning')
        self.opp_tree = ttk.Treeview(opp_frame, columns=columns, show='headings', height=6)
        
        for col in columns:
            self.opp_tree.heading(col, text=col)
            width = 120 if col != 'Reasoning' else 300
            self.opp_tree.column(col, width=width)
        
        self.opp_tree.pack(fill=tk.X, padx=5, pady=5)
        
        # Style
        style = ttk.Style()
        style.configure("Treeview", background='#1a1a1a', foreground=self.fg_color, 
                       fieldbackground='#1a1a1a')
        style.configure("Treeview.Heading", background='#2a2a2a', foreground=self.fg_color)
    
    def create_tokens_section(self, parent):
        """Create tokens overview section"""
        tokens_frame = tk.LabelFrame(parent, text="📊 TOKEN OVERVIEW", 
                                   font=('Arial', 12, 'bold'), fg=self.fg_color, bg=self.bg_color)
        tokens_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Create treeview for all tokens
        columns = ('Symbol', 'Price', 'Change%', 'Volume', 'Spread%', 'Trades', 'PnL')
        self.tokens_tree = ttk.Treeview(tokens_frame, columns=columns, show='headings', height=10)
        
        for col in columns:
            self.tokens_tree.heading(col, text=col)
            self.tokens_tree.column(col, width=100)
        
        # Scrollbar
        token_scrollbar = ttk.Scrollbar(tokens_frame, orient=tk.VERTICAL, command=self.tokens_tree.yview)
        self.tokens_tree.configure(yscrollcommand=token_scrollbar.set)
        
        self.tokens_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        token_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def create_trades_section(self, parent):
        """Create recent trades section"""
        trades_frame = tk.LabelFrame(parent, text="💼 RECENT TRADES", 
                                    font=('Arial', 12, 'bold'), fg=self.fg_color, bg=self.bg_color)
        trades_frame.pack(fill=tk.X, pady=5)
        
        # Create treeview for trades
        columns = ('Time', 'Symbol', 'Side', 'Size', 'Price', 'Nominal')
        self.trades_tree = ttk.Treeview(trades_frame, columns=columns, show='headings', height=5)
        
        for col in columns:
            self.trades_tree.heading(col, text=col)
            self.trades_tree.column(col, width=100)
        
        self.trades_tree.pack(fill=tk.X, padx=5, pady=5)
    
    def create_log_section(self, parent):
        """Create log section"""
        log_frame = tk.LabelFrame(parent, text="📝 ACTIVITY LOG", 
                                font=('Arial', 12, 'bold'), fg=self.fg_color, bg=self.bg_color)
        log_frame.pack(fill=tk.X, pady=5)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, width=150, 
                                                 bg='#1a1a1a', fg=self.fg_color, 
                                                 font=('Courier', 9))
        self.log_text.pack(fill=tk.X, padx=5, pady=5)
    
    def create_control_section(self, parent):
        """Create control section"""
        control_frame = tk.Frame(parent, bg=self.bg_color)
        control_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = tk.Button(control_frame, text="🚀 START TRADING", 
                                     command=self.toggle_trading, font=('Arial', 12, 'bold'),
                                     bg='#00aa00', fg='white', padx=20, pady=10)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        tk.Button(control_frame, text="📊 REFRESH", command=self.manual_refresh,
                 font=('Arial', 10), bg='#0066cc', fg='white', padx=15, pady=10).pack(side=tk.LEFT, padx=5)
        
        tk.Button(control_frame, text="🗑️ CLEAR LOGS", command=self.clear_logs,
                 font=('Arial', 10), bg='#666666', fg='white', padx=15, pady=10).pack(side=tk.LEFT, padx=5)
        
        # Status indicator
        self.status_indicator = tk.Label(control_frame, text="● STOPPED", 
                                       font=('Arial', 12, 'bold'), fg=self.error_color, bg=self.bg_color)
        self.status_indicator.pack(side=tk.RIGHT, padx=20)
    
    def start_trading(self):
        """Start trading in separate thread"""
        if self.trading_thread is None or not self.trading_thread.is_alive():
            self.trader.running = True
            self.trading_thread = threading.Thread(target=self.trading_loop, daemon=True)
            self.trading_thread.start()
            self.logger.info("🚀 Multi-token trading started")
    
    def stop_trading(self):
        """Stop trading"""
        self.trader.running = False
        if self.trading_thread:
            self.trading_thread.join(timeout=5)
        self.logger.info("🛑 Multi-token trading stopped")
    
    def toggle_trading(self):
        """Toggle trading"""
        if self.trader.running:
            self.stop_trading()
            self.start_button.config(text="🚀 START TRADING", bg='#00aa00')
            self.status_indicator.config(text="● STOPPED", fg=self.error_color)
        else:
            self.start_trading()
            self.start_button.config(text="🛑 STOP TRADING", bg='#aa0000')
            self.status_indicator.config(text="● RUNNING", fg=self.fg_color)
    
    def trading_loop(self):
        """Main trading loop"""
        while self.trader.running:
            try:
                result = self.trader.run_trading_cycle()
                self.update_queue.put(("cycle_result", result))
                time.sleep(10)  # 10-second cycles for multi-token
            except Exception as e:
                self.logger.error(f"❌ Trading loop error: {e}")
                self.update_queue.put(("error", str(e)))
                time.sleep(10)
    
    def manual_refresh(self):
        """Manual refresh"""
        try:
            result = self.trader.run_trading_cycle()
            self.update_queue.put(("cycle_result", result))
        except Exception as e:
            self.logger.error(f"❌ Refresh error: {e}")
    
    def clear_logs(self):
        """Clear logs"""
        self.log_text.delete(1.0, tk.END)
    
    def update_ui(self):
        """Update UI"""
        try:
            # Process queue
            while not self.update_queue.empty():
                try:
                    update_type, data = self.update_queue.get_nowait()
                    
                    if update_type == "cycle_result":
                        self.handle_cycle_result(data)
                    elif update_type == "error":
                        self.log_message(f"❌ Error: {data}", self.error_color)
                        
                except queue.Empty:
                    break
            
            # Update account
            self.update_account_display()
            
            # Update tokens display
            self.update_tokens_display()
            
            # Update trades display
            self.update_trades_display()
            
        except Exception as e:
            self.logger.error(f"❌ UI update error: {e}")
        
        # Schedule next update
        self.root.after(2000, self.update_ui)  # Update every 2 seconds
    
    def handle_cycle_result(self, result):
        """Handle cycle result"""
        if result["success"]:
            self.log_message(f"✅ Cycle {result['cycle']}: {result['tokens_analyzed']} tokens, {result['trades_executed']} trades (${result['total_nominal']:.4f})")
            
            # Update opportunities
            self.update_opportunities_display(result.get("top_opportunities", []))
        else:
            self.log_message(f"❌ Cycle failed: {result.get('error', 'Unknown')}", self.error_color)
    
    def update_account_display(self):
        """Update account display"""
        account = self.trader.get_account_summary()
        
        self.account_labels["total"].config(text=f"${account['total_balance']:.2f}")
        self.account_labels["available"].config(text=f"${account['available_balance']:.2f}")
        self.account_labels["trades"].config(text=str(len(self.trader.trades)))
        
        # Calculate cycle nominal
        recent_trades = [t for t in self.trader.trades if time.time() - t.timestamp < 60]
        cycle_nominal = sum(t.nominal_value for t in recent_trades)
        self.account_labels["nominal"].config(text=f"${cycle_nominal:.4f}")
    
    def update_opportunities_display(self, opportunities):
        """Update opportunities display"""
        # Clear existing
        for item in self.opp_tree.get_children():
            self.opp_tree.delete(item)
        
        # Add opportunities
        for opp in opportunities:
            token = opp["token"]
            
            # Color based on direction
            direction_colors = {"BUY": "green", "SELL": "red", "BUY_DIP": "green", "SELL_RALLY": "red"}
            
            values = (
                token.symbol,
                opp["direction"],
                f"{opp['score']:.3f}",
                f"${token.price:.6f}",
                f"{token.change_24h:+.2f}%",
                f"${token.volume/1000000:.1f}M",
                opp["reasoning"][:50] + "..." if len(opp["reasoning"]) > 50 else opp["reasoning"]
            )
            
            self.opp_tree.insert('', tk.END, values=values)
    
    def update_tokens_display(self):
        """Update tokens display"""
        # Clear existing
        for item in self.tokens_tree.get_children():
            self.tokens_tree.delete(item)
        
        # Get latest token data
        if self.trader.token_data:
            latest_tokens = self.trader.token_data[-1]
            
            for token in latest_tokens:
                perf = self.trader.performance.get(token.symbol, {})
                
                values = (
                    token.symbol,
                    f"${token.price:.6f}",
                    f"{token.change_24h:+.2f}%",
                    f"${token.volume/1000000:.1f}M",
                    f"{token.spread_pct:.3f}%",
                    str(perf.get("trades", 0)),
                    f"${perf.get('total_pnl', 0):.4f}"
                )
                
                self.tokens_tree.insert('', tk.END, values=values)
    
    def update_trades_display(self):
        """Update trades display"""
        # Clear existing
        for item in self.trades_tree.get_children():
            self.trades_tree.delete(item)
        
        # Add recent trades
        recent_trades = list(self.trader.trades)[-20:]  # Last 20 trades
        for trade in reversed(recent_trades):
            time_str = datetime.fromtimestamp(trade.timestamp).strftime("%H:%M:%S")
            
            values = (
                time_str,
                trade.symbol,
                trade.side,
                f"{trade.size:.6f}",
                f"${trade.price:.6f}",
                f"${trade.nominal_value:.4f}"
            )
            
            self.trades_tree.insert('', tk.END, values=values)
    
    def log_message(self, message: str, color: str = None):
        """Add log message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        
        # Limit log size
        lines = self.log_text.get(1.0, tk.END).split('\n')
        if len(lines) > 50:
            self.log_text.delete(1.0, f"{len(lines)-50}.0")
    
    def on_closing(self):
        """Handle window close"""
        if messagebox.askokcancel("Quit", "Stop trading and quit?"):
            self.stop_trading()
            self.root.destroy()
    
    def run(self):
        """Run dashboard"""
        self.logger.info("🚀 Starting Multi-Token Trading Dashboard")
        self.root.mainloop()

def main():
    """Main entry point"""
    print("🚀 MULTI-TOKEN TRADING DASHBOARD")
    print("=" * 50)
    print("📊 Trading 30 High-Volume Tokens")
    print("🎯 AI-Powered Opportunity Detection")
    print("💰 Nominal Value: $0.01-$0.10 per trade")
    print("🔄 10-Second Trading Cycles")
    print("=" * 50)
    
    # Check environment variables
    if not os.getenv("GATE_API_KEY") or not os.getenv("GATE_API_SECRET"):
        print("⚠️  Running in DEMO mode - no API keys")
        print("   Set GATE_API_KEY and GATE_API_SECRET for live trading")
    
    # Create and run dashboard
    dashboard = MultiTokenDashboard()
    dashboard.run()

if __name__ == "__main__":
    main()
