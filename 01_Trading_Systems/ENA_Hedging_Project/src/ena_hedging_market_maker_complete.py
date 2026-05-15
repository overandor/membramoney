#!/usr/bin/env python3
"""
ENA_USDT HEDGING MARKET MAKER - COMPLETE SYSTEM
Intelligent hedging strategy with Cascade AI integration
Multi-coin support for sub-10-cent tokens

Author: Cascade AI Assistant
"""

import asyncio
import websockets
import json
import time
import math
import logging
import threading
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from collections import deque
import gate_api
from gate_api import ApiClient, Configuration, FuturesApi
import numpy as np
import sys
import os

# Add config path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'config'))
from ena_config import ENAHedgingConfig, ENAHedgingConfigDev, ENAHedgingConfigProd

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

class CascadeAIAssistant:
    """Cascade AI Assistant - Intelligent Trading Decision Maker"""
    
    def __init__(self, config, ui):
        self.config = config
        self.ui = ui
        self.market_analysis = {}
        self.hedge_opportunities = []
        self.risk_assessment = {}
        self.last_analysis_time = 0
        
    def analyze_market_conditions(self, bids, asks, mid_price, position, balance, symbol):
        """Cascade AI market analysis for intelligent decisions"""
        current_time = time.time()
        
        if not bids or not asks:
            return {'action': 'WAIT', 'reason': 'No market data'}
        
        # Market structure analysis
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        spread_bps = (best_ask - best_bid) / mid_price * 10000
        
        # Volume and liquidity analysis
        bid_volume = sum(float(bid[1]) for bid in bids[:5])
        ask_volume = sum(float(ask[1]) for ask in asks[:5])
        total_volume = bid_volume + ask_volume
        volume_imbalance = (bid_volume - ask_volume) / total_volume if total_volume > 0 else 0
        
        # Price momentum analysis
        price_pressure = volume_imbalance * 0.5
        spread_pressure = max(0, (spread_bps - 5) / 20)
        
        # Position risk analysis
        position_risk = abs(position) / self.config.max_hedge_position if self.config.max_hedge_position > 0 else 0
        balance_risk = max(0, (10 - balance) / 10)
        
        # Symbol-specific adjustments for sub-10-cent coins
        if symbol in self.config.sub_10_cent_coins:
            # More aggressive for low-price coins
            spread_pressure *= 0.7  # Less penalty for wider spreads
            opportunity_multiplier = 1.3  # Higher opportunity score
        else:
            opportunity_multiplier = 1.0
        
        # Cascade AI Decision Logic
        decision = self._make_trading_decision(
            spread_bps, volume_imbalance, position_risk, balance_risk,
            price_pressure, spread_pressure, mid_price, position, opportunity_multiplier
        )
        
        # Update analysis cache
        self.market_analysis = {
            'symbol': symbol,
            'spread_bps': spread_bps,
            'volume_imbalance': volume_imbalance,
            'total_volume': total_volume,
            'price_pressure': price_pressure,
            'spread_pressure': spread_pressure,
            'position_risk': position_risk,
            'balance_risk': balance_risk,
            'decision': decision,
            'timestamp': current_time
        }
        
        return decision
    
    def _make_trading_decision(self, spread_bps, volume_imbalance, position_risk, 
                              balance_risk, price_pressure, spread_pressure, mid_price, position, opportunity_multiplier=1.0):
        """Cascade AI core decision making logic"""
        
        # Risk assessment
        overall_risk = (position_risk * 0.4 + balance_risk * 0.3 + 
                       max(0, spread_pressure) * 0.2 + abs(volume_imbalance) * 0.1)
        
        # Opportunity scoring
        opportunity_score = 0
        
        # Spread opportunity
        if spread_bps > 3:
            opportunity_score += min(spread_bps / 10, 0.4) * opportunity_multiplier
        
        # Volume imbalance opportunity
        if abs(volume_imbalance) > 0.2:
            opportunity_score += min(abs(volume_imbalance) * 0.5, 0.3) * opportunity_multiplier
        
        # Price pressure opportunity
        if abs(price_pressure) > 0.1:
            opportunity_score += min(abs(price_pressure) * 0.3, 0.3) * opportunity_multiplier
        
        # Cascade AI Decision Tree
        if overall_risk > 0.8:
            return {
                'action': 'REDUCE',
                'reason': f'High risk detected ({overall_risk:.2f}) - reducing exposure',
                'confidence': 0.9,
                'risk_level': 'HIGH'
            }
        
        elif opportunity_score > 0.6 and spread_bps > self.config.min_profit_bps * 2:
            return {
                'action': 'HEDGE_AGGRESSIVE',
                'reason': f'High opportunity ({opportunity_score:.2f}) - aggressive hedging',
                'confidence': min(0.95, 0.7 + opportunity_score * 0.25),
                'opportunity_score': opportunity_score,
                'risk_level': 'MEDIUM'
            }
        
        elif opportunity_score > 0.3 and spread_bps > self.config.min_profit_bps:
            return {
                'action': 'HEDGE_CONSERVATIVE',
                'reason': f'Moderate opportunity ({opportunity_score:.2f}) - conservative hedging',
                'confidence': 0.6 + opportunity_score * 0.2,
                'opportunity_score': opportunity_score,
                'risk_level': 'LOW'
            }
        
        elif position_risk > 0.6:
            return {
                'action': 'WAIT',
                'reason': f'Position risk too high ({position_risk:.2f}) - waiting',
                'confidence': 0.8,
                'risk_level': 'MEDIUM'
            }
        
        else:
            return {
                'action': 'MONITOR',
                'reason': f'Market conditions neutral - monitoring',
                'confidence': 0.5,
                'opportunity_score': opportunity_score,
                'risk_level': 'LOW'
            }
    
    def get_hedge_recommendations(self, decision, bids, asks, mid_price, symbol):
        """Get specific hedge recommendations based on AI decision"""
        if decision['action'] not in ['HEDGE_AGGRESSIVE', 'HEDGE_CONSERVATIVE']:
            return []
        
        recommendations = []
        
        # Calculate optimal hedge sizes
        available_balance = 5.56
        base_size_usd = self.config.hedge_order_size_usd
        
        # Symbol-specific adjustments
        if symbol in self.config.sub_10_cent_coins:
            size_multiplier = 1.5  # Larger size for low-price coins
            price_improvement = 0.00001  # Smaller improvement for low prices
        else:
            size_multiplier = 1.0
            price_improvement = self.config.hedge_price_improvement
        
        if decision['action'] == 'HEDGE_AGGRESSIVE':
            size_multiplier *= 1.5
            price_improvement *= 2
        
        # Calculate hedge size
        hedge_usd = min(base_size_usd * size_multiplier, available_balance * 0.3)
        hedge_size = hedge_usd / mid_price
        
        # Get best prices
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        
        # Calculate improved prices
        buy_price = best_bid + price_improvement
        sell_price = best_ask - price_improvement
        
        # Ensure minimum profit
        expected_spread_bps = (sell_price - buy_price) / mid_price * 10000
        if expected_spread_bps < self.config.min_profit_bps:
            half_spread = self.config.min_profit_bps / 2 / 10000 * mid_price
            buy_price = mid_price - half_spread
            sell_price = mid_price + half_spread
        
        recommendations.append({
            'action': 'PLACE_HEDGE_PAIR',
            'buy_price': buy_price,
            'sell_price': sell_price,
            'size': hedge_size,
            'expected_profit_bps': expected_spread_bps,
            'confidence': decision['confidence'],
            'reason': decision['reason']
        })
        
        return recommendations
    
    def log_ai_decision(self, decision, symbol):
        """Log AI decision with detailed reasoning"""
        risk_emoji = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}
        action_emoji = {
            'HEDGE_AGGRESSIVE': '🚀',
            'HEDGE_CONSERVATIVE': '🛡️',
            'WAIT': '⏳',
            'MONITOR': '👁️',
            'REDUCE': '⚠️'
        }
        
        emoji = action_emoji.get(decision['action'], '🤖')
        risk_emoji = risk_emoji.get(decision.get('risk_level', 'LOW'), '🟢')
        
        self.ui.add_log(f"🧠 CASCADE AI DECISION ({symbol}):")
        self.ui.add_log(f"   {emoji} Action: {decision['action']}")
        self.ui.add_log(f"   📊 Reason: {decision['reason']}")
        self.ui.add_log(f"   🎯 Confidence: {decision['confidence']:.2f}")
        self.ui.add_log(f"   {risk_emoji} Risk Level: {decision.get('risk_level', 'LOW')}")
        
        if 'opportunity_score' in decision:
            self.ui.add_log(f"   💎 Opportunity Score: {decision['opportunity_score']:.3f}")

class TradingStats:
    """Statistics tracking for hedging"""
    
    def __init__(self):
        # Basic trading stats
        self.total_trades = 0
        self.total_volume = 0.0
        self.total_pnl = 0.0
        self.fees_paid = 0.0
        self.orders_placed = 0
        self.orders_filled = 0
        self.orders_cancelled = 0
        
        # Balance tracking
        self.available_balance = 0.0
        self.total_balance = 0.0
        self.unrealized_pnl = 0.0
        self.margin_used = 0.0
        self.margin_free = 0.0
        
        # Hedging statistics
        self.hedge_orders_placed = 0
        self.hedge_orders_filled = 0
        self.hedge_profit_trades = 0
        self.hedge_loss_trades = 0
        self.hedge_total_pnl = 0.0
        self.hedge_fees_paid = 0.0
        self.active_hedges = []
        
        # Performance tracking
        self.tps_history = deque(maxlen=100)
        self.pnl_history = deque(maxlen=1000)
        self.start_time = time.time()
        self.last_tps_calc = time.time()
        self.orders_this_second = 0
        self.current_tps = 0.0

class MarketMakerUI:
    """Modern UI for the hedging system"""
    
    def __init__(self, config, stats):
        self.config = config
        self.stats = stats
        self.root = None
        self.running = False
        self.log_queue = deque(maxlen=500)
        
    def create_ui(self):
        """Create the main UI"""
        self.root = tk.Tk()
        self.root.title(f"🛡️ {self.config.symbol} Hedging - Cascade AI")
        self.root.geometry("1400x900")
        self.root.configure(bg='#0a0a0a')
        
        # Style configuration
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure styles
        style.configure('Title.TLabel', background='#0a0a0a', foreground='#ff0040', font=('Arial', 16, 'bold'))
        style.configure('Stats.TLabel', background='#0a0a0a', foreground='#00ff88', font=('Courier', 10))
        style.configure('Dark.TFrame', background='#1a1a1a')
        
        # Main container
        main_container = tk.Frame(self.root, bg='#0a0a0a')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title_label = ttk.Label(main_container, text=f"🛡️ {self.config.symbol} HEDGING SYSTEM", style='Title.TLabel')
        title_label.pack(pady=10)
        
        # Top panel - Stats
        top_panel = tk.Frame(main_container, bg='#1a1a1a', height=150)
        top_panel.pack(fill='x', pady=(0, 10))
        top_panel.pack_propagate(False)
        
        # Stats labels
        self.setup_stats_panel(top_panel)
        
        # Middle panel - Controls and info
        middle_panel = tk.Frame(main_container, bg='#0a0a0a')
        middle_panel.pack(fill='both', expand=True)
        
        # Left panel - Controls
        left_panel = tk.Frame(middle_panel, bg='#1a1a1a', width=400)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)
        
        self.setup_control_panel(left_panel)
        
        # Right panel - Log
        right_panel = tk.Frame(middle_panel, bg='#1a1a1a')
        right_panel.pack(side='right', fill='both', expand=True)
        
        self.setup_log_panel(right_panel)
        
        # Status bar
        self.setup_status_bar()
        
        self.running = True
        
    def setup_stats_panel(self, parent):
        """Setup statistics display panel"""
        # Balance frame
        balance_frame = tk.Frame(parent, bg='#1a1a1a')
        balance_frame.pack(fill='x', padx=10, pady=5)
        
        self.balance_label = ttk.Label(balance_frame, text="Balance: $0.00", style='Stats.TLabel')
        self.balance_label.pack(side='left', padx=10)
        
        self.pnl_label = ttk.Label(balance_frame, text="PnL: $0.00", style='Stats.TLabel')
        self.pnl_label.pack(side='left', padx=10)
        
        # Trading frame
        trading_frame = tk.Frame(parent, bg='#1a1a1a')
        trading_frame.pack(fill='x', padx=10, pady=5)
        
        self.orders_label = ttk.Label(trading_frame, text="Orders: 0", style='Stats.TLabel')
        self.orders_label.pack(side='left', padx=10)
        
        self.tps_label = ttk.Label(trading_frame, text="TPS: 0.00", style='Stats.TLabel')
        self.tps_label.pack(side='left', padx=10)
        
        # Hedging frame
        hedge_frame = tk.Frame(parent, bg='#1a1a1a')
        hedge_frame.pack(fill='x', padx=10, pady=5)
        
        self.hedge_orders_label = ttk.Label(hedge_frame, text="Hedge Orders: 0", style='Stats.TLabel')
        self.hedge_orders_label.pack(side='left', padx=10)
        
        self.hedge_pnl_label = ttk.Label(hedge_frame, text="Hedge PnL: $0.00", style='Stats.TLabel')
        self.hedge_pnl_label.pack(side='left', padx=10)
    
    def setup_control_panel(self, parent):
        """Setup control panel"""
        # Title
        title = ttk.Label(parent, text="🎮 CONTROL PANEL", style='Title.TLabel')
        title.pack(pady=10)
        
        # Symbol selection
        symbol_frame = tk.Frame(parent, bg='#1a1a1a')
        symbol_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(symbol_frame, text="Symbol:", foreground='white', background='#1a1a1a').pack(side='left', padx=5)
        
        self.symbol_var = tk.StringVar(value=self.config.symbol)
        symbols = [self.config.symbol] + self.config.sub_10_cent_coins
        symbol_combo = ttk.Combobox(symbol_frame, textvariable=self.symbol_var, values=symbols, width=15, state='readonly')
        symbol_combo.pack(side='left')
        
        # Control buttons
        button_frame = tk.Frame(parent, bg='#1a1a1a')
        button_frame.pack(fill='x', padx=10, pady=20)
        
        self.start_button = tk.Button(button_frame, text="🚀 START HEDGING", command=self.start_trading,
                                     bg='#00ff00', fg='#000', font=('Arial', 12, 'bold'), width=18, height=2)
        self.start_button.pack(pady=5)
        
        self.stop_button = tk.Button(button_frame, text="⏹️ STOP HEDGING", command=self.stop_trading,
                                    bg='#ff0000', fg='#fff', font=('Arial', 12, 'bold'), width=18, height=2, state='disabled')
        self.stop_button.pack(pady=5)
        
        # Info frame
        info_frame = tk.Frame(parent, bg='#1a1a1a')
        info_frame.pack(fill='x', padx=10, pady=20)
        
        ttk.Label(info_frame, text="📊 SYSTEM INFO", style='Title.TLabel').pack()
        
        info_text = f"""
Min Profit: {self.config.min_profit_bps} bps
Max Position: {self.config.max_hedge_position} {self.config.symbol.split('_')[0]}
Order Size: ${self.config.hedge_order_size_usd}
AI Confidence: {self.config.ai_confidence_threshold}
        """.strip()
        
        info_label = ttk.Label(info_frame, text=info_text, style='Stats.TLabel', justify='left')
        info_label.pack(padx=10, pady=10)
    
    def setup_log_panel(self, parent):
        """Setup log panel"""
        # Title
        title = ttk.Label(parent, text="📝 ACTIVITY LOG", style='Title.TLabel')
        title.pack(pady=10)
        
        # Log text
        self.log_text = scrolledtext.ScrolledText(parent, height=25, width=80,
                                                  bg='#0a0a0a', fg='#00ff88', 
                                                  font=('Courier', 9))
        self.log_text.pack(padx=10, pady=10, fill='both', expand=True)
        
        # Clear button
        clear_button = tk.Button(parent, text="🗑️ CLEAR LOG", command=self.clear_log,
                                bg='#ff6b6b', fg='#fff', font=('Arial', 10, 'bold'))
        clear_button.pack(pady=5)
    
    def setup_status_bar(self):
        """Setup status bar"""
        status_frame = tk.Frame(self.root, bg='#1a1a1a', height=30)
        status_frame.pack(fill='x', side='bottom')
        status_frame.pack_propagate(False)
        
        self.status_label = ttk.Label(status_frame, text="🟢 READY", style='Stats.TLabel')
        self.status_label.pack(side='left', padx=10, pady=5)
        
        self.time_label = ttk.Label(status_frame, text="", style='Stats.TLabel')
        self.time_label.pack(side='right', padx=10, pady=5)
    
    def add_log(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.log_queue.append(log_entry)
        
        if self.log_text:
            self.log_text.insert(tk.END, log_entry + "\n")
            self.log_text.see(tk.END)
            
            # Limit log size
            lines = self.log_text.get(1.0, tk.END).split('\n')
            if len(lines) > 1000:
                self.log_text.delete(1.0, f"{len(lines)-1000}.0")
    
    def clear_log(self):
        """Clear the log"""
        if self.log_text:
            self.log_text.delete(1.0, tk.END)
    
    def update_ui(self):
        """Update UI elements"""
        if not self.running:
            return
        
        # Update stats
        self.balance_label.configure(text=f"Balance: ${self.stats.total_balance:.2f}")
        self.pnl_label.configure(text=f"PnL: ${self.stats.total_pnl:.4f}")
        self.orders_label.configure(text=f"Orders: {self.stats.orders_placed}")
        self.tps_label.configure(text=f"TPS: {self.stats.current_tps:.2f}")
        
        # Update hedging stats
        self.hedge_orders_label.configure(text=f"Hedge Orders: {self.stats.hedge_orders_filled}")
        hedge_pnl_color = '#00ff88' if self.stats.hedge_total_pnl >= 0 else '#ff6b6b'
        self.hedge_pnl_label.configure(text=f"Hedge PnL: ${self.stats.hedge_total_pnl:.4f}", foreground=hedge_pnl_color)
        
        # Update time
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.time_label.configure(text=current_time)
        
        # Schedule next update
        if self.root:
            self.root.after(100, self.update_ui)
    
    def start_trading(self):
        """Start trading"""
        self.start_button.config(state='disabled')
        self.stop_button.config(state='normal')
        self.status_label.configure(text="🟢 HEDGING ACTIVE")
        self.add_log("🚀 Hedging started")
        
        # Update symbol in config
        self.config.symbol = self.symbol_var.get()
        self.add_log(f"📊 Trading {self.config.symbol}")
    
    def stop_trading(self):
        """Stop trading"""
        self.start_button.config(state='normal')
        self.stop_button.config(state='disabled')
        self.status_label.configure(text="🔴 STOPPED")
        self.add_log("⏹️ Hedging stopped")
    
    def run(self):
        """Run the UI"""
        self.update_ui()
        self.root.mainloop()
    
    def close(self):
        """Close the UI"""
        self.running = False
        if self.root:
            self.root.quit()

class ENAHedgingMarketMaker:
    """Main ENA hedging market maker with Cascade AI"""
    
    def __init__(self, config: ENAHedgingConfig):
        self.config = config
        self.stats = TradingStats()
        self.ui = MarketMakerUI(config, self.stats)
        
        # Trading state
        self._running = False
        self._trading = False
        self.position = 0.0
        self.mid = 0.0
        self.bids = []
        self.asks = []
        
        # AI Assistant
        self.cascade_ai = CascadeAIAssistant(config, self.ui)
        
        # Initialize API
        cfg = Configuration(key=config.api_key, secret=config.api_secret)
        self.api = FuturesApi(ApiClient(cfg))
        
        # WebSocket
        self.ws = None
        self.ws_task = None
    
    async def get_balance(self):
        """Get account balance"""
        try:
            account = self.api.get_futures_account(settle='usdt')
            self.stats.available_balance = float(account.available)
            self.stats.total_balance = float(account.total)
            self.stats.unrealized_pnl = float(account.unrealised_pnl)
            self.ui.add_log(f"💰 Balance: ${self.stats.total_balance:.2f}")
        except Exception as e:
            self.ui.add_log(f"❌ Balance error: {e}")
    
    async def get_positions(self):
        """Get current positions"""
        try:
            positions = self.api.list_futures_positions(settle='usdt')
            for pos in positions:
                if pos.contract == self.config.symbol and float(pos.size) != 0:
                    self.position = float(pos.size)
                    self.ui.add_log(f"📊 Position: {self.position:+.6f} {self.config.symbol.split('_')[0]}")
                    break
        except Exception as e:
            self.ui.add_log(f"❌ Position error: {e}")
    
    async def place_hedge_order(self, side: str, price: float, size: float):
        """Place a hedge order"""
        try:
            order = gate_api.FuturesOrder(
                contract=self.config.symbol,
                size=size,
                price=price,
                side=side,
                type='limit',
                time_in_force='post_only',
                client_order_id=f"hedge_{int(time.time() * 1000)}"
            )
            
            result = self.api.create_futures_order(settle='usdt', order=order)
            self.stats.hedge_orders_placed += 1
            
            hedge_info = {
                'order_id': result.id,
                'side': side,
                'price': price,
                'size': size,
                'timestamp': time.time(),
                'status': 'active'
            }
            self.stats.active_hedges.append(hedge_info)
            
            self.ui.add_log(f"🛡️ HEDGE PLACED: {side.upper()} {size:.6f} @ ${price:.6f}")
            return result.id
            
        except Exception as e:
            self.ui.add_log(f"❌ Hedge order failed: {e}")
            return None
    
    async def check_hedge_profitability(self):
        """Check and close profitable hedges"""
        if not self.bids or not self.asks:
            return
        
        current_bid = float(self.bids[0][0])
        current_ask = float(self.asks[0][0])
        current_time = time.time()
        
        for hedge in self.stats.active_hedges[:]:
            if hedge['status'] != 'active':
                continue
            
            hedge_price = hedge['price']
            hedge_side = hedge['side']
            hedge_size = hedge['size']
            hedge_age = current_time - hedge['timestamp']
            
            # Calculate profit
            if hedge_side == 'buy':
                profit_per_unit = current_bid - hedge_price
                total_profit = profit_per_unit * hedge_size
                profit_bps = profit_per_unit / hedge_price * 10000
                close_price = current_bid
            else:
                profit_per_unit = hedge_price - current_ask
                total_profit = profit_per_unit * hedge_size
                profit_bps = profit_per_unit / hedge_price * 10000
                close_price = current_ask
            
            # Check profit threshold
            min_profit = self.config.min_profit_bps / 10000 * hedge_price * hedge_size
            
            if profit_bps >= self.config.market_sell_threshold or total_profit > min_profit:
                await self.close_hedge_position(hedge, total_profit, close_price, f"PROFITABLE ({profit_bps:.1f} bps)")
            elif hedge_age > self.config.max_hedge_age_seconds:
                await self.close_hedge_position(hedge, total_profit, close_price, f"AGED ({hedge_age:.0f}s)")
    
    async def close_hedge_position(self, hedge, profit, close_price, reason):
        """Close a hedge position"""
        try:
            close_side = 'sell' if hedge['side'] == 'buy' else 'buy'
            
            close_order = gate_api.FuturesOrder(
                contract=self.config.symbol,
                size=hedge['size'],
                side=close_side,
                type='market',
                client_order_id=f"close_hedge_{int(time.time() * 1000)}"
            )
            
            result = self.api.create_futures_order(settle='usdt', order=close_order)
            
            # Update statistics
            self.stats.hedge_orders_filled += 2
            self.stats.hedge_total_pnl += profit
            self.stats.total_pnl += profit
            
            if profit > 0:
                self.stats.hedge_profit_trades += 1
            else:
                self.stats.hedge_loss_trades += 1
            
            # Mark as closed
            hedge['status'] = 'closed'
            hedge['profit'] = profit
            
            profit_color = "+" if profit >= 0 else ""
            self.ui.add_log(f"💰 HEDGE CLOSED ({reason}): ${profit_color}{profit:.4f}")
            
        except Exception as e:
            self.ui.add_log(f"❌ Failed to close hedge: {e}")
    
    async def cascade_ai_hedging_strategy(self):
        """Cascade AI-driven hedging strategy"""
        if not self.bids or not self.asks:
            return
        
        # AI analysis
        ai_decision = self.cascade_ai.analyze_market_conditions(
            self.bids, self.asks, self.mid, self.position, 
            self.stats.available_balance, self.config.symbol
        )
        
        # Log AI decision
        self.cascade_ai.log_ai_decision(ai_decision, self.config.symbol)
        
        # Get recommendations
        recommendations = self.cascade_ai.get_hedge_recommendations(
            ai_decision, self.bids, self.asks, self.mid, self.config.symbol
        )
        
        # Execute recommendations
        for rec in recommendations:
            if rec['action'] == 'PLACE_HEDGE_PAIR':
                current_hedge_size = sum(h['size'] for h in self.stats.active_hedges if h['status'] == 'active')
                
                if current_hedge_size < self.config.max_hedge_position:
                    # Place hedge pair
                    buy_result = await self.place_hedge_order('buy', rec['buy_price'], rec['size'])
                    await asyncio.sleep(0.1)
                    sell_result = await self.place_hedge_order('sell', rec['sell_price'], rec['size'])
                    
                    if buy_result and sell_result:
                        self.ui.add_log(f"🧠 AI HEDGE EXECUTED:")
                        self.ui.add_log(f"   🎯 Confidence: {rec['confidence']:.2f}")
                        self.ui.add_log(f"   💰 Expected Profit: {rec['expected_profit_bps']:.1f} bps")
    
    async def connect_websocket(self):
        """Connect to WebSocket for real-time data"""
        try:
            self.ws = await websockets.connect(self.config.ws_url)
            self.ui.add_log("✅ WebSocket connected")
            
            # Subscribe to order book
            subscribe_msg = {
                "time": int(time.time()),
                "channel": "futures.order_book",
                "event": "subscribe",
                "payload": [
                    self.config.symbol,
                    5,  # Level
                    0   # Interval
                ]
            }
            await self.ws.send(json.dumps(subscribe_msg))
            
            return True
        except Exception as e:
            self.ui.add_log(f"❌ WebSocket error: {e}")
            return False
    
    async def process_messages(self):
        """Process WebSocket messages"""
        try:
            async for message in self.ws:
                data = json.loads(message)
                
                if data.get('channel') == 'futures.order_book' and data.get('event') == 'update':
                    # Update order book
                    bids = data.get('result', {}).get('bids', [])
                    asks = data.get('result', {}).get('asks', [])
                    
                    if bids and asks:
                        self.bids = bids
                        self.asks = asks
                        self.mid = (float(bids[0][0]) + float(asks[0][0])) / 2
                        
        except Exception as e:
            self.ui.add_log(f"❌ Message processing error: {e}")
    
    async def trading_loop(self):
        """Main trading loop"""
        balance_update_counter = 0
        hedge_counter = 0
        
        while self._running:
            try:
                # Update balance every 30 seconds
                balance_update_counter += 1
                if balance_update_counter >= 300:
                    await self.get_balance()
                    await self.get_positions()
                    balance_update_counter = 0
                
                # Check if trading is enabled
                if not self._trading:
                    await asyncio.sleep(1)
                    continue
                
                # Hedging strategy
                if self.config.hedging_mode:
                    hedge_counter += 1
                    
                    # Check profitability every 2 seconds
                    if hedge_counter % 20 == 0:
                        await self.check_hedge_profitability()
                    
                    # AI hedging every 5 seconds
                    if hedge_counter % 50 == 0:
                        await self.cascade_ai_hedging_strategy()
                
                await asyncio.sleep(0.1)
                
            except Exception as e:
                self.ui.add_log(f"❌ Trading loop error: {e}")
                await asyncio.sleep(1)
    
    async def start(self):
        """Start the market maker"""
        self._running = True
        
        # Create UI
        self.ui.create_ui()
        
        # Initial data fetch
        await self.get_balance()
        await self.get_positions()
        
        # Connect WebSocket
        if not await self.connect_websocket():
            self.ui.add_log("❌ Failed to connect WebSocket")
            return
        
        # Start tasks
        tasks = [
            asyncio.create_task(self.process_messages()),
            asyncio.create_task(self.trading_loop()),
            asyncio.create_task(asyncio.to_thread(self.ui.run))
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.ui.add_log(f"❌ Runtime error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the market maker"""
        self._running = False
        self._trading = False
        
        if self.ws:
            await self.ws.close()
        
        self.ui.add_log("⏹️ System stopped")
        self.ui.close()

def main():
    """Main entry point"""
    print("🛡️ ENA_USDT HEDGING SYSTEM")
    print("🧠 Powered by Cascade AI Assistant")
    print("💰 Multi-coin support for sub-10-cent tokens")
    print("=" * 60)
    
    # Load configuration
    config = ENAHedgingConfig()
    
    try:
        config.validate_config()
        print("✅ Configuration validated")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return 1
    
    print(f"📊 Symbol: {config.symbol}")
    print(f"💰 Min Profit: {config.min_profit_bps} bps")
    print(f"🎯 Max Position: {config.max_hedge_position}")
    print(f"📈 Order Size: ${config.hedge_order_size_usd}")
    print(f"🪙 Sub-10-cent coins: {', '.join(config.sub_10_cent_coins)}")
    print("=" * 60)
    
    # Create and run market maker
    market_maker = ENAHedgingMarketMaker(config)
    
    try:
        asyncio.run(market_maker.start())
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down...")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
