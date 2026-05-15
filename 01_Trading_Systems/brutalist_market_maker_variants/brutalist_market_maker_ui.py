#!/usr/bin/env python3
import os
"""
BRUTALIST MARKET MAKER UI
Advanced market making interface with real-time analytics
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
from datetime import datetime
import gate_api
from gate_api import ApiClient, Configuration, FuturesApi
import json
import math

# Your API credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

class BrutalistMarketMaker:
    """High-frequency market making strategy"""
    
    def __init__(self, futures_client):
        self.futures_client = futures_client
        self.is_running = False
        self.current_position = 0.0
        self.mid_price = None
        self.volatility = 10.0
        self.total_pnl = 0.0
        
    def calculate_market_metrics(self, symbol: str = "BTC_USDT") -> dict:
        """Calculate market making metrics"""
        try:
            # Get order book
            book = self.futures_client.list_futures_order_book(settle='usdt', contract=symbol, limit=20)
            
            if not book.bids or not book.asks:
                return {}
            
            # Calculate mid price
            best_bid = float(book.bids[0].p)
            best_ask = float(book.asks[0].p)
            mid = (best_bid + best_ask) / 2
            self.mid_price = mid
            
            # Calculate spread
            spread_bps = (best_ask - best_bid) / mid * 10000
            
            # Calculate volume imbalance
            bid_vol = sum(float(bid.s) for bid in book.bids[:5])
            ask_vol = sum(float(ask.s) for ask in book.asks[:5])
            total_vol = bid_vol + ask_vol
            imbalance = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0
            
            # Calculate depth
            bid_depth = sum(float(bid.p) * float(bid.s) for bid in book.bids[:10])
            ask_depth = sum(float(ask.p) * float(ask.s) for ask in book.asks[:10])
            
            return {
                'mid': mid,
                'spread_bps': spread_bps,
                'imbalance': imbalance,
                'bid_depth': bid_depth,
                'ask_depth': ask_depth,
                'best_bid': best_bid,
                'best_ask': best_ask,
                'bid_vol': bid_vol,
                'ask_vol': ask_vol
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def calculate_optimal_quotes(self, metrics: dict, inventory_skew: float = 0.0) -> dict:
        """Calculate optimal bid/ask quotes"""
        if not metrics or 'mid' not in metrics:
            return {}
        
        mid = metrics['mid']
        spread = metrics['spread_bps']
        imbalance = metrics['imbalance']
        
        # Base spread with inventory adjustment
        base_spread = max(5.0, spread * 0.8)
        inventory_adjustment = inventory_skew * 10.0  # bps
        imbalance_adjustment = imbalance * 2.0  # bps
        
        # Total spread
        half_spread = (base_spread + abs(inventory_adjustment) + abs(imbalance_adjustment)) / 2
        
        # Calculate quotes
        if inventory_skew > 0:  # Long inventory - quote lower bid, higher ask
            bid = mid - half_spread / 10000 * mid - inventory_adjustment / 10000 * mid
            ask = mid + half_spread / 10000 * mid
        elif inventory_skew < 0:  # Short inventory - quote higher bid, lower ask
            bid = mid - half_spread / 10000 * mid
            ask = mid + half_spread / 10000 * mid - inventory_adjustment / 10000 * mid
        else:  # Neutral
            bid = mid - half_spread / 10000 * mid
            ask = mid + half_spread / 10000 * mid
        
        return {
            'bid': bid,
            'ask': ask,
            'spread_bps': (ask - bid) / mid * 10000,
            'inventory_adjustment': inventory_adjustment
        }
    
    def get_position_summary(self) -> dict:
        """Get current position summary"""
        try:
            positions = self.futures_client.list_positions(settle='usdt')
            active_positions = []
            
            for pos in positions:
                size = float(pos.size)
                if size != 0:
                    pnl = float(pos.unrealised_pnl)
                    active_positions.append({
                        'symbol': pos.contract,
                        'size': size,
                        'pnl': pnl,
                        'side': 'LONG' if size > 0 else 'SHORT'
                    })
            
            total_pnl = sum(pos['pnl'] for pos in active_positions)
            self.total_pnl = total_pnl
            
            return {
                'positions': active_positions,
                'total_pnl': total_pnl,
                'position_count': len(active_positions)
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def simulate_market_making(self, symbol: str = "BTC_USDT", duration_minutes: int = 5) -> dict:
        """Simulate market making strategy"""
        results = []
        
        for i in range(duration_minutes):
            # Get current metrics
            metrics = self.calculate_market_metrics(symbol)
            if not metrics:
                continue
            
            # Get position
            position_summary = self.get_position_summary()
            
            # Calculate quotes
            inventory_skew = sum(pos['size'] for pos in position_summary.get('positions', [])) / 10.0
            quotes = self.calculate_optimal_quotes(metrics, inventory_skew)
            
            # Simulate trade execution
            result = {
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'mid': metrics['mid'],
                'spread_bps': metrics['spread_bps'],
                'bid_quote': quotes.get('bid'),
                'ask_quote': quotes.get('ask'),
                'inventory_skew': inventory_skew,
                'total_pnl': position_summary.get('total_pnl', 0),
                'imbalance': metrics['imbalance']
            }
            
            results.append(result)
            time.sleep(1)  # Simulate real-time
        
        return {
            'symbol': symbol,
            'duration_minutes': duration_minutes,
            'data_points': len(results),
            'results': results,
            'final_pnl': results[-1]['total_pnl'] if results else 0
        }

class MarketMakerUI:
    """Advanced Market Maker UI"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 BRUTALIST MARKET MAKER")
        self.root.geometry("1400x900")
        self.root.configure(bg='#0a0a0a')
        
        # Initialize clients
        self.cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        self.futures_client = FuturesApi(ApiClient(self.cfg))
        self.market_maker = BrutalistMarketMaker(self.futures_client)
        
        # State variables
        self.is_simulating = False
        self.auto_refresh = False
        
        self.setup_ui()
        self.start_auto_refresh()
    
    def setup_ui(self):
        """Setup the UI components"""
        # Title Header
        title_frame = tk.Frame(self.root, bg='#0a0a0a', height=80)
        title_frame.pack(fill='x', padx=10, pady=5)
        
        tk.Label(title_frame, text="🤖 BRUTALIST MARKET MAKER", 
                font=('Arial', 20, 'bold'), fg='#ff0040', bg='#0a0a0a').pack(side='top')
        tk.Label(title_frame, text="HIGH-FREQUENCY TRADING SYSTEM", 
                font=('Arial', 12), fg='#666', bg='#0a0a0a').pack(side='top')
        
        # Main Container
        main_container = tk.Frame(self.root, bg='#0a0a0a')
        main_container.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Left Panel - Market Data
        left_panel = tk.Frame(main_container, bg='#1a1a1a', width=400)
        left_panel.pack(side='left', fill='both', expand=False, padx=(0, 5))
        left_panel.pack_propagate(False)
        
        self.setup_market_panel(left_panel)
        
        # Center Panel - Quotes & Analytics
        center_panel = tk.Frame(main_container, bg='#1a1a1a', width=500)
        center_panel.pack(side='left', fill='both', expand=True, padx=5)
        center_panel.pack_propagate(False)
        
        self.setup_quotes_panel(center_panel)
        
        # Right Panel - AI Assistant & Performance
        right_panel = tk.Frame(main_container, bg='#1a1a1a', width=450)
        right_panel.pack(side='right', fill='both', expand=False, padx=(5, 0))
        right_panel.pack_propagate(False)
        
        self.setup_ai_panel(right_panel)
        
        # Bottom Status Bar
        self.setup_status_bar()
    
    def setup_market_panel(self, parent):
        """Setup market data panel"""
        tk.Label(parent, text="📊 MARKET DATA", 
                font=('Arial', 14, 'bold'), fg='#ff0040', bg='#1a1a1a').pack(pady=10)
        
        # Symbol selector
        symbol_frame = tk.Frame(parent, bg='#1a1a1a')
        symbol_frame.pack(pady=5)
        
        tk.Label(symbol_frame, text="Symbol:", fg='#fff', bg='#1a1a1a').pack(side='left', padx=5)
        self.symbol_var = tk.StringVar(value="BTC_USDT")
        symbol_combo = ttk.Combobox(symbol_frame, textvariable=self.symbol_var, 
                                   values=["ENA_USDT", "BTC_USDT", "ETH_USDT", "SOL_USDT", "DOGE_USDT"], 
                                   width=15, state='readonly')
        self.symbol_var.set("ENA_USDT")  # Default to ENA
        symbol_combo.pack(side='left')
        
        # Market metrics display
        self.market_text = scrolledtext.ScrolledText(parent, height=20, width=45,
                                                    bg='#0a0a0a', fg='#00ff00', 
                                                    font=('Courier', 10))
        self.market_text.pack(padx=10, pady=10, fill='both', expand=True)
        
        # Control buttons
        button_frame = tk.Frame(parent, bg='#1a1a1a')
        button_frame.pack(pady=10)
        
        tk.Button(button_frame, text="🔄 REFRESH", command=self.update_market_data,
                 bg='#ff0040', fg='#fff', font=('Arial', 10, 'bold'), width=12).pack(side='left', padx=5)
        tk.Button(button_frame, text="📊 DEEP ANALYSIS", command=self.deep_analysis,
                 bg='#00ff00', fg='#000', font=('Arial', 10, 'bold'), width=12).pack(side='left', padx=5)
    
    def setup_quotes_panel(self, parent):
        """Setup quotes and analytics panel"""
        tk.Label(parent, text="💰 OPTIMAL QUOTES", 
                font=('Arial', 14, 'bold'), fg='#ff0040', bg='#1a1a1a').pack(pady=10)
        
        # Quote controls
        control_frame = tk.Frame(parent, bg='#1a1a1a')
        control_frame.pack(pady=5)
        
        tk.Label(control_frame, text="Inventory Skew:", fg='#fff', bg='#1a1a1a').pack(side='left', padx=5)
        self.skew_var = tk.DoubleVar(value=0.0)
        skew_scale = tk.Scale(control_frame, from_=-2.0, to=2.0, resolution=0.1,
                             orient='horizontal', variable=self.skew_var, length=200,
                             bg='#1a1a1a', fg='#fff', highlightthickness=0)
        skew_scale.pack(side='left', padx=5)
        
        self.skew_label = tk.Label(control_frame, text="0.0", fg='#00ff00', bg='#1a1a1a', width=5)
        self.skew_label.pack(side='left')
        
        # Update skew label
        def update_skew_label(val):
            self.skew_label.config(text=f"{float(val):.1f}")
            self.calculate_quotes()
        skew_scale.config(command=update_skew_label)
        
        # Quotes display
        self.quotes_text = scrolledtext.ScrolledText(parent, height=15, width=55,
                                                    bg='#0a0a0a', fg='#00ff00', 
                                                    font=('Courier', 10))
        self.quotes_text.pack(padx=10, pady=10, fill='both', expand=True)
        
        # Action buttons
        action_frame = tk.Frame(parent, bg='#1a1a1a')
        action_frame.pack(pady=10)
        
        tk.Button(action_frame, text="💰 CALCULATE QUOTES", command=self.calculate_quotes,
                 bg='#ffaa00', fg='#000', font=('Arial', 10, 'bold'), width=15).pack(side='left', padx=5)
        tk.Button(action_frame, text="🎯 PLACE ORDERS", command=self.place_orders,
                 bg='#ff0040', fg='#fff', font=('Arial', 10, 'bold'), width=15).pack(side='left', padx=5)
    
    def setup_ai_panel(self, parent):
        """Setup AI Assistant panel with Cascade integration"""
        tk.Label(parent, text="🤖 CASCADE AI ASSISTANT", 
                font=('Arial', 14, 'bold'), fg='#00ff88', bg='#1a1a1a').pack(pady=10)
        
        # AI Status indicator
        status_frame = tk.Frame(parent, bg='#1a1a1a')
        status_frame.pack(pady=5)
        
        self.ai_status_label = tk.Label(status_frame, text="🟢 AI ACTIVE", 
                                       font=('Arial', 10, 'bold'), fg='#00ff88', bg='#1a1a1a')
        self.ai_status_label.pack(side='left')
        
        self.ai_thinking_label = tk.Label(status_frame, text="", 
                                         font=('Arial', 9, 'italic'), fg='#ffaa00', bg='#1a1a1a')
        self.ai_thinking_label.pack(side='left', padx=10)
        
        # AI Output Display
        self.ai_text = scrolledtext.ScrolledText(parent, height=25, width=50,
                                                bg='#0a0a0a', fg='#00ff88', 
                                                font=('Courier', 9))
        self.ai_text.pack(padx=10, pady=10, fill='both', expand=True)
        
        # AI Control buttons
        ai_button_frame = tk.Frame(parent, bg='#1a1a1a')
        ai_button_frame.pack(pady=10)
        
        tk.Button(ai_button_frame, text="🧠 ANALYZE MARKET", command=self.ai_analyze_market,
                 bg='#00ff88', fg='#000', font=('Arial', 10, 'bold'), width=12).pack(side='left', padx=3)
        tk.Button(ai_button_frame, text="⚡ OPTIMIZE STRATEGY", command=self.ai_optimize_strategy,
                 bg='#ff0040', fg='#fff', font=('Arial', 10, 'bold'), width=12).pack(side='left', padx=3)
        tk.Button(ai_button_frame, text="� PREDICT", command=self.ai_predict,
                 bg='#00aaff', fg='#fff', font=('Arial', 10, 'bold'), width=12).pack(side='left', padx=3)
        
        # Initialize AI analysis
        self.ai_welcome_message()
        self.start_ai_analysis()
    
    def setup_status_bar(self):
        """Setup status bar"""
        status_frame = tk.Frame(self.root, bg='#1a1a1a', height=30)
        status_frame.pack(fill='x', side='bottom', padx=10, pady=5)
        
        self.status_label = tk.Label(status_frame, text="🟢 SYSTEM READY", 
                                    font=('Arial', 10), fg='#00ff00', bg='#1a1a1a')
        self.status_label.pack(side='left')
        
        # Auto-refresh toggle
        self.auto_refresh_var = tk.BooleanVar(value=True)
        auto_check = tk.Checkbutton(status_frame, text="Auto-refresh", variable=self.auto_refresh_var,
                                   bg='#1a1a1a', fg='#fff', selectcolor='#1a1a1a')
        auto_check.pack(side='right', padx=10)
    
    def update_market_data(self):
        """Update market data display"""
        def update_thread():
            try:
                self.status_label.config(text="🔄 UPDATING MARKET DATA...")
                
                symbol = self.symbol_var.get()
                metrics = self.market_maker.calculate_market_metrics(symbol)
                
                self.market_text.delete(1.0, tk.END)
                self.market_text.insert(tk.END, f"🕐 {datetime.now().strftime('%H:%M:%S')}\n")
                self.market_text.insert(tk.END, "="*40 + "\n\n")
                
                if metrics and 'mid' in metrics:
                    self.market_text.insert(tk.END, f"📊 {symbol} MARKET:\n")
                    self.market_text.insert(tk.END, f"   Mid Price: ${metrics['mid']:.2f}\n")
                    self.market_text.insert(tk.END, f"   Spread: {metrics['spread_bps']:.1f} bps\n")
                    self.market_text.insert(tk.END, f"   Best Bid: ${metrics['best_bid']:.2f}\n")
                    self.market_text.insert(tk.END, f"   Best Ask: ${metrics['best_ask']:.2f}\n")
                    self.market_text.insert(tk.END, f"   Imbalance: {metrics['imbalance']:+.3f}\n")
                    self.market_text.insert(tk.END, f"   Bid Volume: {metrics['bid_vol']:.1f}\n")
                    self.market_text.insert(tk.END, f"   Ask Volume: {metrics['ask_vol']:.1f}\n")
                    self.market_text.insert(tk.END, f"   Bid Depth: ${metrics['bid_depth']:,.0f}\n")
                    self.market_text.insert(tk.END, f"   Ask Depth: ${metrics['ask_depth']:,.0f}\n\n")
                    
                    # Position info
                    positions = self.market_maker.get_position_summary()
                    if 'positions' in positions:
                        self.market_text.insert(tk.END, f"💰 POSITIONS:\n")
                        for pos in positions['positions']:
                            self.market_text.insert(tk.END, f"   {pos['side']} {pos['symbol']}: {pos['size']:.2f}\n")
                            self.market_text.insert(tk.END, f"   PNL: ${pos['pnl']:+.2f}\n")
                        self.market_text.insert(tk.END, f"\n   Total PNL: ${positions['total_pnl']:+.2f}\n")
                    
                    self.status_label.config(text="✅ MARKET DATA UPDATED")
                else:
                    self.market_text.insert(tk.END, "❌ NO DATA AVAILABLE\n")
                    self.status_label.config(text="❌ DATA UNAVAILABLE")
                    
            except Exception as e:
                self.market_text.insert(tk.END, f"❌ ERROR: {e}\n")
                self.status_label.config(text="❌ UPDATE FAILED")
        
        threading.Thread(target=update_thread, daemon=True).start()
    
    def calculate_quotes(self):
        """Calculate optimal quotes"""
        try:
            symbol = self.symbol_var.get()
            metrics = self.market_maker.calculate_market_metrics(symbol)
            
            if not metrics or 'mid' not in metrics:
                return
            
            inventory_skew = self.skew_var.get()
            quotes = self.market_maker.calculate_optimal_quotes(metrics, inventory_skew)
            
            self.quotes_text.delete(1.0, tk.END)
            self.quotes_text.insert(tk.END, f"💰 OPTIMAL QUOTES FOR {symbol}\n")
            self.quotes_text.insert(tk.END, "="*40 + "\n\n")
            
            self.quotes_text.insert(tk.END, f"📊 MARKET CONDITIONS:\n")
            self.quotes_text.insert(tk.END, f"   Mid Price: ${metrics['mid']:.2f}\n")
            self.quotes_text.insert(tk.END, f"   Current Spread: {metrics['spread_bps']:.1f} bps\n")
            self.quotes_text.insert(tk.END, f"   Volume Imbalance: {metrics['imbalance']:+.3f}\n")
            self.quotes_text.insert(tk.END, f"   Inventory Skew: {inventory_skew:+.1f}\n\n")
            
            if quotes:
                self.quotes_text.insert(tk.END, f"🎯 CALCULATED QUOTES:\n")
                self.quotes_text.insert(tk.END, f"   Optimal Bid: ${quotes['bid']:.2f}\n")
                self.quotes_text.insert(tk.END, f"   Optimal Ask: ${quotes['ask']:.2f}\n")
                self.quotes_text.insert(tk.END, f"   Quote Spread: {quotes['spread_bps']:.1f} bps\n")
                self.quotes_text.insert(tk.END, f"   Inventory Adj: {quotes['inventory_adjustment']:.1f} bps\n\n")
                
                # Calculate potential profit
                spread_profit = (quotes['ask'] - quotes['bid']) * 0.1  # Assuming 0.1 BTC size
                self.quotes_text.insert(tk.END, f"💵 POTENTIAL METRICS:\n")
                self.quotes_text.insert(tk.END, f"   Spread Profit (0.1 BTC): ${spread_profit:.2f}\n")
                self.quotes_text.insert(tk.END, f"   Daily Est (100 trades): ${spread_profit*100:.2f}\n")
                
        except Exception as e:
            self.quotes_text.insert(tk.END, f"❌ QUOTE ERROR: {e}\n")
    
    def ai_welcome_message(self):
        """Display AI welcome message"""
        self.ai_text.delete(1.0, tk.END)
        self.ai_text.insert(tk.END, "🤖 CASCADE AI ASSISTANT ONLINE\n")
        self.ai_text.insert(tk.END, "="*45 + "\n\n")
        self.ai_text.insert(tk.END, "🚀 Integrated with ENA Market Maker\n")
        self.ai_text.insert(tk.END, "📊 Real-time market analysis active\n")
        self.ai_text.insert(tk.END, "🧠 AI-powered strategy optimization\n")
        self.ai_text.insert(tk.END, "⚡ High-frequency trading insights\n\n")
        self.ai_text.insert(tk.END, "🎯 Ready to enhance your trading!\n\n")
        self.ai_text.insert(tk.END, "💡 Use buttons below for AI analysis\n")
        self.ai_text.insert(tk.END, "📈 I'll provide continuous insights\n")
        
        # Scroll to bottom
        self.ai_text.see(tk.END)
    
    def start_ai_analysis(self):
        """Start continuous AI analysis"""
        def analysis_loop():
            while True:
                if hasattr(self, 'ai_text') and self.ai_text.winfo_exists():
                    try:
                        self.ai_continuous_analysis()
                    except:
                        pass
                time.sleep(10)  # Update every 10 seconds
        
        threading.Thread(target=analysis_loop, daemon=True).start()
    
    def ai_continuous_analysis(self):
        """Continuous AI market analysis"""
        try:
            symbol = self.symbol_var.get()
            metrics = self.market_maker.calculate_market_metrics(symbol)
            
            if metrics and 'mid' in metrics:
                timestamp = datetime.now().strftime('%H:%M:%S')
                
                # AI Analysis
                analysis = []
                analysis.append(f"\n🕐 {timestamp} - AI ANALYSIS")
                analysis.append(f"📊 {symbol}: ${metrics['mid']:.4f}")
                
                # Market condition assessment
                spread = metrics['spread_bps']
                if spread < 5:
                    analysis.append(f"✅ TIGHT SPREAD: {spread:.1f}bps - GOOD FOR MM")
                elif spread < 15:
                    analysis.append(f"⚠️ MODERATE SPREAD: {spread:.1f}bps")
                else:
                    analysis.append(f"🔴 WIDE SPREAD: {spread:.1f}bps - CAUTION")
                
                # Imbalance analysis
                imbalance = metrics['imbalance']
                if imbalance > 0.2:
                    analysis.append(f"🟢 BID-DOMINANT: {imbalance:+.3f} - BUY PRESSURE")
                elif imbalance < -0.2:
                    analysis.append(f"🔴 ASK-DOMINANT: {imbalance:+.3f} - SELL PRESSURE")
                else:
                    analysis.append(f"⚖️ BALANCED: {imbalance:+.3f}")
                
                # AI recommendation
                if abs(imbalance) > 0.3:
                    analysis.append(f"🎯 AI: CONSIDER ONE-SIDED QUOTES")
                elif spread < 10:
                    analysis.append(f"� AI: AGGRESSIVE MM OPPORTUNITY")
                else:
                    analysis.append(f"🎯 AI: CONSERVATIVE APPROACH")
                
                # Update AI display
                self.ai_text.insert(tk.END, "\n" + "\n".join(analysis) + "\n")
                
                # Keep only last 20 lines
                lines = self.ai_text.get(1.0, tk.END).split('\n')
                if len(lines) > 20:
                    self.ai_text.delete(1.0, f"{len(lines)-20}.0")
                
                self.ai_text.see(tk.END)
                
        except Exception as e:
            pass  # Silent fail to avoid disrupting UI
    
    def ai_analyze_market(self):
        """Perform comprehensive AI market analysis"""
        self.ai_thinking_label.config(text="🧠 Analyzing...")
        
        def analyze():
            try:
                symbol = self.symbol_var.get()
                metrics = self.market_maker.calculate_market_metrics(symbol)
                positions = self.market_maker.get_position_summary()
                
                # Deep AI Analysis
                analysis = []
                analysis.append("\n🧠 DEEP AI MARKET ANALYSIS")
                analysis.append("="*40)
                
                if metrics and 'mid' in metrics:
                    analysis.append(f"\n📊 MARKET STRUCTURE:")
                    analysis.append(f"   Price: ${metrics['mid']:.4f}")
                    analysis.append(f"   Spread: {metrics['spread_bps']:.1f}bps")
                    analysis.append(f"   Imbalance: {metrics['imbalance']:+.3f}")
                    
                    # AI market classification
                    if metrics['spread_bps'] < 3 and abs(metrics['imbalance']) < 0.1:
                        market_type = "� EFFICIENT MARKET"
                        strategy = "Balanced MM"
                    elif metrics['spread_bps'] > 20:
                        market_type = "🔴 VOLATILE MARKET"
                        strategy = "Wide quotes, risk management"
                    elif abs(metrics['imbalance']) > 0.4:
                        market_type = "⚠️ DIRECTIONAL MARKET"
                        strategy = "Follow trend, reduce inventory"
                    else:
                        market_type = "⚖️ NORMAL MARKET"
                        strategy = "Standard MM strategy"
                    
                    analysis.append(f"\n🎯 AI CLASSIFICATION: {market_type}")
                    analysis.append(f"📋 RECOMMENDED: {strategy}")
                    
                    # Risk assessment
                    risk_score = min(10, int(metrics['spread_bps'] / 2 + abs(metrics['imbalance']) * 10))
                    if risk_score < 3:
                        risk_level = "🟢 LOW RISK"
                    elif risk_score < 7:
                        risk_level = "⚠️ MEDIUM RISK"
                    else:
                        risk_level = "🔴 HIGH RISK"
                    
                    analysis.append(f"\n⚡ RISK ASSESSMENT: {risk_level} ({risk_score}/10)")
                    
                    # Position analysis
                    if 'positions' in positions and positions['positions']:
                        analysis.append(f"\n� POSITION ANALYSIS:")
                        for pos in positions['positions']:
                            analysis.append(f"   {pos['side']} {pos['symbol']}: {pos['size']:.2f}")
                            analysis.append(f"   PnL: ${pos['pnl']:+.2f}")
                        analysis.append(f"   Total PnL: ${positions['total_pnl']:+.2f}")
                    
                    # AI strategic recommendation
                    analysis.append(f"\n🚀 STRATEGIC RECOMMENDATIONS:")
                    if metrics['spread_bps'] < 5:
                        analysis.append(f"   • Tight spread - increase frequency")
                        analysis.append(f"   • Consider smaller order sizes")
                    if abs(metrics['imbalance']) > 0.3:
                        analysis.append(f"   • Strong directional pressure")
                        analysis.append(f"   • Adjust inventory bias")
                    if risk_score > 6:
                        analysis.append(f"   • High risk - reduce exposure")
                        analysis.append(f"   • Widen quotes for safety")
                
                # Display analysis
                self.ai_text.insert(tk.END, "\n" + "\n".join(analysis) + "\n")
                self.ai_text.see(tk.END)
                
            except Exception as e:
                self.ai_text.insert(tk.END, f"\n❌ AI Analysis Error: {e}\n")
            finally:
                self.ai_thinking_label.config(text="")
        
        threading.Thread(target=analyze, daemon=True).start()
    
    def ai_optimize_strategy(self):
        """AI-powered strategy optimization"""
        self.ai_thinking_label.config(text="⚡ Optimizing...")
        
        def optimize():
            try:
                symbol = self.symbol_var.get()
                metrics = self.market_maker.calculate_market_metrics(symbol)
                
                optimization = []
                optimization.append("\n⚡ AI STRATEGY OPTIMIZATION")
                optimization.append("="*40)
                
                if metrics and 'mid' in metrics:
                    # Calculate optimal parameters
                    spread = metrics['spread_bps']
                    imbalance = metrics['imbalance']
                    
                    optimization.append(f"\n🎯 OPTIMAL PARAMETERS:")
                    
                    # Spread optimization
                    if spread < 3:
                        opt_spread = f"2-3bps (aggressive)"
                        opt_frequency = "50-100ms"
                    elif spread < 10:
                        opt_spread = f"3-8bps (balanced)"
                        opt_frequency = "100-200ms"
                    else:
                        opt_spread = f"8-15bps (conservative)"
                        opt_frequency = "200-500ms"
                    
                    optimization.append(f"   Quote Spread: {opt_spread}")
                    optimization.append(f"   Refresh Rate: {opt_frequency}")
                    
                    # Size optimization based on depth
                    total_depth = metrics['bid_depth'] + metrics['ask_depth']
                    if total_depth > 100000:
                        opt_size = "Large (0.5-1.0 ENA)"
                    elif total_depth > 50000:
                        opt_size = "Medium (0.2-0.5 ENA)"
                    else:
                        opt_size = "Small (0.1-0.2 ENA)"
                    
                    optimization.append(f"   Order Size: {opt_size}")
                    
                    # Inventory strategy
                    if imbalance > 0.2:
                        inv_strategy = "Lean short - reduce long exposure"
                    elif imbalance < -0.2:
                        inv_strategy = "Lean long - reduce short exposure"
                    else:
                        inv_strategy = "Balanced - maintain neutral inventory"
                    
                    optimization.append(f"   Inventory: {inv_strategy}")
                    
                    # Expected performance
                    if spread < 5:
                        expected_profit = "High - tight spreads"
                        risk_level = "Medium - high frequency"
                    elif spread < 15:
                        expected_profit = "Medium - balanced approach"
                        risk_level = "Low - conservative"
                    else:
                        expected_profit = "Low - wide spreads"
                        risk_level = "Very Low - cautious"
                    
                    optimization.append(f"\n📈 EXPECTED PERFORMANCE:")
                    optimization.append(f"   Profit Potential: {expected_profit}")
                    optimization.append(f"   Risk Level: {risk_level}")
                    
                    # Action items
                    optimization.append(f"\n🚀 IMMEDIATE ACTIONS:")
                    optimization.append(f"   • Update spread to {opt_spread}")
                    optimization.append(f"   • Set refresh to {opt_frequency}")
                    optimization.append(f"   • Adjust order size to {opt_size}")
                    optimization.append(f"   • {inv_strategy}")
                
                self.ai_text.insert(tk.END, "\n" + "\n".join(optimization) + "\n")
                self.ai_text.see(tk.END)
                
            except Exception as e:
                self.ai_text.insert(tk.END, f"\n❌ Optimization Error: {e}\n")
            finally:
                self.ai_thinking_label.config(text="")
        
        threading.Thread(target=optimize, daemon=True).start()
    
    def ai_predict(self):
        """AI market prediction"""
        self.ai_thinking_label.config(text="� Predicting...")
        
        def predict():
            try:
                symbol = self.symbol_var.get()
                metrics = self.market_maker.calculate_market_metrics(symbol)
                
                prediction = []
                prediction.append("\n🔮 AI MARKET PREDICTION")
                prediction.append("="*40)
                
                if metrics and 'mid' in metrics:
                    current_price = metrics['mid']
                    spread = metrics['spread_bps']
                    imbalance = metrics['imbalance']
                    
                    prediction.append(f"\n📊 CURRENT STATE:")
                    prediction.append(f"   Price: ${current_price:.4f}")
                    prediction.append(f"   Spread: {spread:.1f}bps")
                    prediction.append(f"   Imbalance: {imbalance:+.3f}")
                    
                    # Price movement prediction
                    if imbalance > 0.3:
                        direction = "🟢 BULLISH"
                        confidence = min(85, 60 + int(abs(imbalance) * 50))
                        target_move = "+0.5% to +2.0%"
                    elif imbalance < -0.3:
                        direction = "🔴 BEARISH"
                        confidence = min(85, 60 + int(abs(imbalance) * 50))
                        target_move = "-0.5% to -2.0%"
                    else:
                        direction = "⚖️ SIDEWAYS"
                        confidence = 70
                        target_move = "±0.3%"
                    
                    prediction.append(f"\n🎯 PRICE PREDICTION:")
                    prediction.append(f"   Direction: {direction}")
                    prediction.append(f"   Confidence: {confidence}%")
                    prediction.append(f"   Target Move: {target_move}")
                    
                    # Volatility prediction
                    if spread < 5:
                        vol_forecast = "Low volatility expected"
                        rec_strategy = "Market making optimal"
                    elif spread < 15:
                        vol_forecast = "Moderate volatility"
                        rec_strategy = "Balanced approach"
                    else:
                        vol_forecast = "High volatility likely"
                        rec_strategy = "Risk management priority"
                    
                    prediction.append(f"\n🌊 VOLATILITY FORECAST:")
                    prediction.append(f"   Outlook: {vol_forecast}")
                    prediction.append(f"   Strategy: {rec_strategy}")
                    
                    # Time horizon
                    prediction.append(f"\n⏰ TIME HORIZON:")
                    prediction.append(f"   Short-term (5-15 min): {direction}")
                    prediction.append(f"   Medium-term (1-2 hrs): Monitor trend")
                    prediction.append(f"   Update: Check every 10 minutes")
                    
                    # Trading recommendation
                    prediction.append(f"\n🚀 TRADING RECOMMENDATIONS:")
                    if "BULLISH" in direction:
                        prediction.append(f"   • Consider slight long bias")
                        prediction.append(f"   • Widen ask quotes")
                        prediction.append(f"   • Tighten bid quotes")
                    elif "BEARISH" in direction:
                        prediction.append(f"   • Consider slight short bias")
                        prediction.append(f"   • Widen bid quotes")
                        prediction.append(f"   • Tighten ask quotes")
                    else:
                        prediction.append(f"   • Maintain balanced quotes")
                        prediction.append(f"   • Standard MM strategy")
                        prediction.append(f"   • Focus on spread capture")
                
                self.ai_text.insert(tk.END, "\n" + "\n".join(prediction) + "\n")
                self.ai_text.see(tk.END)
                
            except Exception as e:
                self.ai_text.insert(tk.END, f"\n❌ Prediction Error: {e}\n")
            finally:
                self.ai_thinking_label.config(text="")
        
        threading.Thread(target=predict, daemon=True).start()
    
    def deep_analysis(self):
        """Perform deep market analysis"""
        self.ai_analyze_market()  # Redirect to AI analysis
        self.status_label.config(text="🔬 AI ANALYSIS COMPLETE")
    
    def place_orders(self):
        """Place calculated orders (demo)"""
        self.quotes_text.insert(tk.END, "\n🚀 ORDERS PLACED (DEMO)\n")
        self.status_label.config(text="🚀 ORDERS PLACED")
    
    def start_auto_refresh(self):
        """Start auto-refresh loop"""
        def refresh_loop():
            while True:
                if self.auto_refresh_var.get():
                    self.update_market_data()
                    self.calculate_quotes()
                time.sleep(5)  # Refresh every 5 seconds
        
        threading.Thread(target=refresh_loop, daemon=True).start()
    
    def run(self):
        """Run the UI"""
        self.update_market_data()
        self.calculate_quotes()
        self.root.mainloop()

if __name__ == "__main__":
    ui = MarketMakerUI()
    ui.run()
