#!/usr/bin/env python3
import os
"""
COMPLETE GATE.IO BALANCE CHECKER + HEDGING SCANNER
Shows ALL balances + UI + 0-10 cent coin hedging
"""

import gate_api
from gate_api import ApiClient, Configuration, SpotApi, MarginApi, FuturesApi
import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
from datetime import datetime
from typing import List, Dict
import asyncio
import json
import math
import logging

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
        
    def calculate_market_metrics(self, symbol: str = "BTC_USDT") -> Dict:
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
    
    def calculate_optimal_quotes(self, metrics: Dict, inventory_skew: float = 0.0) -> Dict:
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
    
    def get_position_summary(self) -> Dict:
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
    
    def simulate_market_making(self, symbol: str = "BTC_USDT", duration_minutes: int = 5) -> Dict:
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

class HedgingScanner:
    """Scanner for 0-10 cent coins with hedging analysis"""
    
    def __init__(self, client):
        self.client = client
        self.micro_caps = []
        self.hedging_opportunities = []
    
    def scan_micro_caps(self) -> List[Dict]:
        """Scan for 0-10 cent coins"""
        try:
            tickers = self.client.list_tickers()
            micro_caps = []
            
            for ticker in tickers:
                if not ticker.currency_pair.endswith('_USDT'):
                    continue
                
                price = float(ticker.last)
                volume = float(ticker.base_volume)
                change = float(ticker.change_percentage)
                
                # 0-10 cent range
                if 0.0001 <= price <= 0.10 and volume >= 1000:
                    micro_caps.append({
                        'symbol': ticker.currency_pair.replace('_USDT', ''),
                        'pair': ticker.currency_pair,
                        'price': price,
                        'volume': volume,
                        'change': change,
                        'high_24h': float(ticker.high_24h),
                        'low_24h': float(ticker.low_24h)
                    })
            
            # Sort by volume (highest first)
            micro_caps.sort(key=lambda x: x['volume'], reverse=True)
            self.micro_caps = micro_caps
            return micro_caps
            
        except Exception as e:
            print(f"❌ Micro-cap scan error: {e}")
            return []
    
    def analyze_hedging_opportunities(self) -> List[Dict]:
        """Analyze hedging opportunities for micro-caps"""
        opportunities = []
        
        for coin in self.micro_caps[:50]:  # Analyze top 50
            price = coin['price']
            change = coin['change']
            volume = coin['volume']
            high_24h = coin['high_24h']
            low_24h = coin['low_24h']
            
            # Calculate volatility
            if low_24h > 0:
                volatility = (high_24h - low_24h) / low_24h * 100
            else:
                volatility = 0
            
            # Hedging signals
            signal = "HOLD"
            reason = ""
            confidence = 0
            
            # Strong dump - potential bounce
            if change < -15.0 and volume > 10000:
                signal = "BUY_HEDGE"
                reason = "Strong dump with high volume - bounce potential"
                confidence = 8
            elif change < -10.0 and volatility > 20:
                signal = "BUY_HEDGE"
                reason = "High volatility dump - hedging opportunity"
                confidence = 7
            
            # Strong pump - potential short
            elif change > 20.0 and volume < 5000:
                signal = "SELL_HEDGE"
                reason = "Weak pump - likely to reverse"
                confidence = 7
            elif change > 15.0 and volatility > 25:
                signal = "SELL_HEDGE"
                reason = "Volatile pump - short opportunity"
                confidence = 6
            
            # Calculate risk/reward
            risk_reward = 0
            if signal != "HOLD":
                if signal == "BUY_HEDGE":
                    potential_upside = high_24h - price
                    potential_downside = price - low_24h
                    if potential_downside > 0:
                        risk_reward = potential_upside / potential_downside
                elif signal == "SELL_HEDGE":
                    potential_downside = price - low_24h
                    potential_upside = high_24h - price
                    if potential_upside > 0:
                        risk_reward = potential_downside / potential_upside
            
            if signal != "HOLD":
                opportunities.append({
                    'symbol': coin['symbol'],
                    'signal': signal,
                    'reason': reason,
                    'confidence': confidence,
                    'price': price,
                    'change': change,
                    'volume': volume,
                    'volatility': volatility,
                    'risk_reward': risk_reward,
                    'high_24h': high_24h,
                    'low_24h': low_24h
                })
        
        # Sort by confidence and risk/reward
        opportunities.sort(key=lambda x: (x['confidence'], x['risk_reward']), reverse=True)
        self.hedging_opportunities = opportunities[:20]  # Top 20
        return self.hedging_opportunities

class GateioBalanceUI:
    """UI for Gate.io Balance Checker with Hedging Scanner"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🚀 Gate.io Balance + Hedging Scanner")
        self.root.geometry("1200x800")
        self.root.configure(bg='#1a1a1a')
        
        # Initialize client
        self.cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        self.spot_client = SpotApi(ApiClient(self.cfg))
        self.futures_client = FuturesApi(ApiClient(self.cfg))
        self.scanner = HedgingScanner(self.spot_client)
        self.market_maker = BrutalistMarketMaker(self.futures_client)
        
        self.setup_ui()
        self.update_data()
    
    def setup_ui(self):
        """Setup the UI components"""
        # Title
        title_frame = tk.Frame(self.root, bg='#1a1a1a')
        title_frame.pack(pady=10)
        
        tk.Label(title_frame, text="🚀 GATE.IO BALANCE + HEDGING SCANNER", 
                font=('Arial', 16, 'bold'), fg='#00ff41', bg='#1a1a1a').pack()
        tk.Label(title_frame, text="0-10 Cent Coin Analysis", 
                font=('Arial', 12), fg='#888', bg='#1a1a1a').pack()
        
        # Main container
        main_frame = tk.Frame(self.root, bg='#1a1a1a')
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Left panel - Balances
        left_frame = tk.Frame(main_frame, bg='#2a2a2a', width=400)
        left_frame.pack(side='left', fill='both', expand=False, padx=(0, 5))
        left_frame.pack_propagate(False)
        
        tk.Label(left_frame, text="💰 ACCOUNT BALANCES", 
                font=('Arial', 12, 'bold'), fg='#00ff41', bg='#2a2a2a').pack(pady=5)
        
        self.balance_text = scrolledtext.ScrolledText(left_frame, height=15, width=45,
                                                      bg='#1a1a1a', fg='#fff', font=('Courier', 9))
        self.balance_text.pack(padx=5, pady=5)
        
        # Right panel - Hedging Scanner + Market Maker
        right_frame = tk.Frame(main_frame, bg='#2a2a2a')
        right_frame.pack(side='right', fill='both', expand=True)
        
        # Tab control
        tab_control = ttk.Notebook(right_frame)
        tab_control.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Hedging Tab
        hedge_tab = tk.Frame(tab_control, bg='#2a2a2a')
        tab_control.add(hedge_tab, text='🎯 Hedging Scanner')
        
        tk.Label(hedge_tab, text="🎯 HEDGING OPPORTUNITIES (0-10¢)", 
                font=('Arial', 12, 'bold'), fg='#00ff41', bg='#2a2a2a').pack(pady=5)
        
        # Hedging control buttons
        hedge_button_frame = tk.Frame(hedge_tab, bg='#2a2a2a')
        hedge_button_frame.pack(pady=5)
        
        tk.Button(hedge_button_frame, text="� SCAN MICRO-CAPS", command=self.scan_micro_caps,
                 bg='#ff6b35', fg='#fff', font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        tk.Button(hedge_button_frame, text="🎯 ANALYZE HEDGING", command=self.analyze_hedging,
                 bg='#4ecdc4', fg='#fff', font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        
        # Hedging results
        self.hedging_text = scrolledtext.ScrolledText(hedge_tab, height=20, width=80,
                                                      bg='#1a1a1a', fg='#fff', font=('Courier', 9))
        self.hedging_text.pack(padx=5, pady=5, fill='both', expand=True)
        
        # Market Maker Tab
        mm_tab = tk.Frame(tab_control, bg='#2a2a2a')
        tab_control.add(mm_tab, text='🤖 Market Maker')
        
        tk.Label(mm_tab, text="🤖 BRUTALIST MARKET MAKER", 
                font=('Arial', 12, 'bold'), fg='#00ff41', bg='#2a2a2a').pack(pady=5)
        
        # MM control buttons
        mm_button_frame = tk.Frame(mm_tab, bg='#2a2a2a')
        mm_button_frame.pack(pady=5)
        
        tk.Button(mm_button_frame, text="📊 MARKET METRICS", command=self.show_market_metrics,
                 bg='#9b59b6', fg='#fff', font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        tk.Button(mm_button_frame, text="� OPTIMAL QUOTES", command=self.show_optimal_quotes,
                 bg='#e74c3c', fg='#fff', font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        tk.Button(mm_button_frame, text="� SIMULATE MM", command=self.simulate_market_making,
                 bg='#f39c12', fg='#fff', font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        
        # Market maker results
        self.mm_text = scrolledtext.ScrolledText(mm_tab, height=20, width=80,
                                                 bg='#1a1a1a', fg='#fff', font=('Courier', 9))
        self.mm_text.pack(padx=5, pady=5, fill='both', expand=True)
        
        # Main control buttons
        button_frame = tk.Frame(right_frame, bg='#2a2a2a')
        button_frame.pack(pady=5)
        
        tk.Button(button_frame, text="🔄 REFRESH", command=self.update_data,
                 bg='#00ff41', fg='#1a1a1a', font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        
        # Status bar
        self.status_label = tk.Label(self.root, text="Ready", 
                                    font=('Arial', 10), fg='#00ff41', bg='#1a1a1a')
        self.status_label.pack(side='bottom', pady=5)
    
    def update_data(self):
        """Update balance data"""
        def update_thread():
            try:
                self.status_label.config(text="🔄 Updating balances...")
                
                # Clear and update balance text
                self.balance_text.delete(1.0, tk.END)
                self.balance_text.insert(tk.END, f"🕐 {datetime.now().strftime('%H:%M:%S')}\n")
                self.balance_text.insert(tk.END, "="*40 + "\n\n")
                
                # Spot balances
                self.balance_text.insert(tk.END, "📊 SPOT ACCOUNT:\n")
                balances = self.spot_client.list_spot_accounts()
                total_usdt = 0.0
                
                for balance in balances:
                    available = float(balance.available)
                    if available > 0:
                        self.balance_text.insert(tk.END, f"  🪙 {balance.currency}: {available:.6f}\n")
                        
                        if balance.currency != 'USDT' and available > 0:
                            try:
                                ticker = self.spot_client.list_tickers(currency_pair=f"{balance.currency}_USDT")[0]
                                price = float(ticker.last)
                                usdt_value = available * price
                                total_usdt += usdt_value
                                self.balance_text.insert(tk.END, f"     💵 ${usdt_value:.6f} @ ${price:.6f}\n")
                            except:
                                pass
                        elif balance.currency == 'USDT':
                            total_usdt += available
                
                self.balance_text.insert(tk.END, f"\n💰 Total Spot: ${total_usdt:.6f}\n\n")
                
                # Futures positions
                self.balance_text.insert(tk.END, "📊 FUTURES POSITIONS:\n")
                try:
                    positions = self.futures_client.list_positions(settle='usdt')
                    active_positions = [p for p in positions if float(p.size) != 0]
                    
                    if active_positions:
                        total_pnl = 0.0
                        for pos in active_positions[:10]:
                            size = float(pos.size)
                            pnl = float(pos.unrealised_pnl)
                            total_pnl += pnl
                            
                            direction = "🔴 SHORT" if size < 0 else "🟢 LONG"
                            self.balance_text.insert(tk.END, f"  {direction} {pos.contract:<10} PNL: ${pnl:+.2f}\n")
                        
                        self.balance_text.insert(tk.END, f"\n💰 Total PNL: ${total_pnl:+.2f}\n")
                    else:
                        self.balance_text.insert(tk.END, "  No active positions\n")
                except Exception as e:
                    self.balance_text.insert(tk.END, f"  Error: {e}\n")
                
                self.status_label.config(text="✅ Balances updated")
                
            except Exception as e:
                self.balance_text.insert(tk.END, f"❌ Error: {e}\n")
                self.status_label.config(text="❌ Update failed")
        
        threading.Thread(target=update_thread, daemon=True).start()
    
    def scan_micro_caps(self):
        """Scan for micro-cap coins"""
        def scan_thread():
            try:
                self.status_label.config(text="🔍 Scanning micro-caps...")
                self.hedging_text.delete(1.0, tk.END)
                self.hedging_text.insert(tk.END, f"🔍 SCANNING 0-10 CENT COINS\n")
                self.hedging_text.insert(tk.END, "="*50 + "\n\n")
                
                micro_caps = self.scanner.scan_micro_caps()
                
                if micro_caps:
                    self.hedging_text.insert(tk.END, f"📊 Found {len(micro_caps)} micro-cap coins:\n\n")
                    
                    for i, coin in enumerate(micro_caps[:30]):  # Show top 30
                        price = coin['price']
                        change = coin['change']
                        volume = coin['volume']
                        
                        color = "📈" if change > 0 else "📉"
                        self.hedging_text.insert(tk.END, 
                            f"{i+1:2d}. {coin['symbol']:<8} ${price:.6f} {color}{change:+6.2f}% Vol:{volume:>8.0f}\n")
                    
                    self.status_label.config(text=f"✅ Found {len(micro_caps)} micro-caps")
                else:
                    self.hedging_text.insert(tk.END, "❌ No micro-cap coins found\n")
                    self.status_label.config(text="❌ No coins found")
                    
            except Exception as e:
                self.hedging_text.insert(tk.END, f"❌ Scan error: {e}\n")
                self.status_label.config(text="❌ Scan failed")
        
        threading.Thread(target=scan_thread, daemon=True).start()
    
    def analyze_hedging(self):
        """Analyze hedging opportunities"""
        def analyze_thread():
            try:
                self.status_label.config(text="🎯 Analyzing hedging opportunities...")
                self.hedging_text.delete(1.0, tk.END)
                self.hedging_text.insert(tk.END, f"🎯 HEDGING OPPORTUNITY ANALYSIS\n")
                self.hedging_text.insert(tk.END, "="*50 + "\n\n")
                
                # First scan micro-caps if not done
                if not self.scanner.micro_caps:
                    self.hedging_text.insert(tk.END, "🔍 Scanning micro-caps first...\n")
                    self.scanner.scan_micro_caps()
                
                # Analyze opportunities
                opportunities = self.scanner.analyze_hedging_opportunities()
                
                if opportunities:
                    self.hedging_text.insert(tk.END, f"🎯 Found {len(opportunities)} hedging opportunities:\n\n")
                    
                    for i, opp in enumerate(opportunities):
                        signal_emoji = "🟢" if opp['signal'] == "BUY_HEDGE" else "🔴"
                        self.hedging_text.insert(tk.END, 
                            f"{i+1:2d}. {signal_emoji} {opp['symbol']:<8} {opp['signal']:<10}\n")
                        self.hedging_text.insert(tk.END, f"     💰 Price: ${opp['price']:.6f} ({opp['change']:+.2f}%)\n")
                        self.hedging_text.insert(tk.END, f"     📊 Volatility: {opp['volatility']:.1f}% | Risk/Reward: {opp['risk_reward']:.2f}\n")
                        self.hedging_text.insert(tk.END, f"     🎯 Confidence: {opp['confidence']}/10\n")
                        self.hedging_text.insert(tk.END, f"     💡 Reason: {opp['reason']}\n")
                        self.hedging_text.insert(tk.END, f"     📈 Range: ${opp['low_24h']:.6f} - ${opp['high_24h']:.6f}\n")
                        self.hedging_text.insert(tk.END, "-"*50 + "\n")
                    
                    self.status_label.config(text=f"✅ Found {len(opportunities)} opportunities")
                else:
                    self.hedging_text.insert(tk.END, "❌ No hedging opportunities found\n")
                    self.status_label.config(text="❌ No opportunities")
                    
            except Exception as e:
                self.hedging_text.insert(tk.END, f"❌ Analysis error: {e}\n")
                self.status_label.config(text="❌ Analysis failed")
        
        threading.Thread(target=analyze_thread, daemon=True).start()
    
    def show_market_metrics(self):
        """Show market making metrics"""
        def metrics_thread():
            try:
                self.status_label.config(text="📊 Calculating market metrics...")
                self.mm_text.delete(1.0, tk.END)
                self.mm_text.insert(tk.END, f"📊 MARKET MAKING METRICS\n")
                self.mm_text.insert(tk.END, "="*50 + "\n\n")
                
                # Get metrics for BTC_USDT
                metrics = self.market_maker.calculate_market_metrics("BTC_USDT")
                
                if metrics and 'mid' in metrics:
                    self.mm_text.insert(tk.END, f"🔍 BTC_USDT MARKET:\n")
                    self.mm_text.insert(tk.END, f"   Mid Price: ${metrics['mid']:.2f}\n")
                    self.mm_text.insert(tk.END, f"   Spread: {metrics['spread_bps']:.1f} bps\n")
                    self.mm_text.insert(tk.END, f"   Best Bid: ${metrics['best_bid']:.2f}\n")
                    self.mm_text.insert(tk.END, f"   Best Ask: ${metrics['best_ask']:.2f}\n")
                    self.mm_text.insert(tk.END, f"   Imbalance: {metrics['imbalance']:+.3f}\n")
                    self.mm_text.insert(tk.END, f"   Bid Volume: {metrics['bid_vol']:.1f}\n")
                    self.mm_text.insert(tk.END, f"   Ask Volume: {metrics['ask_vol']:.1f}\n")
                    self.mm_text.insert(tk.END, f"   Bid Depth: ${metrics['bid_depth']:,.0f}\n")
                    self.mm_text.insert(tk.END, f"   Ask Depth: ${metrics['ask_depth']:,.0f}\n\n")
                    
                    # Get position summary
                    positions = self.market_maker.get_position_summary()
                    if 'positions' in positions:
                        self.mm_text.insert(tk.END, f"💰 CURRENT POSITIONS:\n")
                        for pos in positions['positions']:
                            self.mm_text.insert(tk.END, f"   {pos['side']} {pos['symbol']}: {pos['size']:.2f} (PNL: ${pos['pnl']:+.2f})\n")
                        self.mm_text.insert(tk.END, f"\n   Total PNL: ${positions['total_pnl']:+.2f}\n")
                        self.mm_text.insert(tk.END, f"   Position Count: {positions['position_count']}\n")
                    
                    self.status_label.config(text="✅ Market metrics updated")
                else:
                    self.mm_text.insert(tk.END, "❌ Could not get market metrics\n")
                    self.status_label.config(text="❌ Metrics failed")
                    
            except Exception as e:
                self.mm_text.insert(tk.END, f"❌ Metrics error: {e}\n")
                self.status_label.config(text="❌ Metrics error")
        
        threading.Thread(target=metrics_thread, daemon=True).start()
    
    def show_optimal_quotes(self):
        """Show optimal market making quotes"""
        def quotes_thread():
            try:
                self.status_label.config(text="💰 Calculating optimal quotes...")
                self.mm_text.delete(1.0, tk.END)
                self.mm_text.insert(tk.END, f"💰 OPTIMAL MARKET MAKING QUOTES\n")
                self.mm_text.insert(tk.END, "="*50 + "\n\n")
                
                # Get current metrics
                metrics = self.market_maker.calculate_market_metrics("BTC_USDT")
                if not metrics or 'mid' not in metrics:
                    self.mm_text.insert(tk.END, "❌ Could not get market data\n")
                    return
                
                # Get position for inventory skew
                positions = self.market_maker.get_position_summary()
                inventory_skew = sum(pos['size'] for pos in positions.get('positions', [])) / 10.0
                
                self.mm_text.insert(tk.END, f"📊 MARKET CONDITIONS:\n")
                self.mm_text.insert(tk.END, f"   Mid Price: ${metrics['mid']:.2f}\n")
                self.mm_text.insert(tk.END, f"   Current Spread: {metrics['spread_bps']:.1f} bps\n")
                self.mm_text.insert(tk.END, f"   Volume Imbalance: {metrics['imbalance']:+.3f}\n")
                self.mm_text.insert(tk.END, f"   Inventory Skew: {inventory_skew:+.3f}\n\n")
                
                # Calculate quotes for different scenarios
                scenarios = [
                    ("Neutral", 0.0),
                    ("Long Inventory", 0.5),
                    ("Short Inventory", -0.5),
                    ("Very Long", 1.0),
                    ("Very Short", -1.0)
                ]
                
                self.mm_text.insert(tk.END, f"🎯 OPTIMAL QUOTES BY SCENARIO:\n\n")
                
                for scenario_name, skew in scenarios:
                    quotes = self.market_maker.calculate_optimal_quotes(metrics, skew)
                    if quotes:
                        spread = quotes['spread_bps']
                        bid = quotes['bid']
                        ask = quotes['ask']
                        
                        self.mm_text.insert(tk.END, f"   {scenario_name}:\n")
                        self.mm_text.insert(tk.END, f"     Bid: ${bid:.2f}\n")
                        self.mm_text.insert(tk.END, f"     Ask: ${ask:.2f}\n")
                        self.mm_text.insert(tk.END, f"     Spread: {spread:.1f} bps\n")
                        self.mm_text.insert(tk.END, f"     Inventory Adj: {quotes['inventory_adjustment']:.1f} bps\n\n")
                
                self.status_label.config(text="✅ Optimal quotes calculated")
                
            except Exception as e:
                self.mm_text.insert(tk.END, f"❌ Quotes error: {e}\n")
                self.status_label.config(text="❌ Quotes failed")
        
        threading.Thread(target=quotes_thread, daemon=True).start()
    
    def simulate_market_making(self):
        """Simulate market making strategy"""
        def simulate_thread():
            try:
                self.status_label.config(text="🎮 Simulating market making...")
                self.mm_text.delete(1.0, tk.END)
                self.mm_text.insert(tk.END, f"🎮 MARKET MAKING SIMULATION\n")
                self.mm_text.insert(tk.END, "="*50 + "\n\n")
                
                self.mm_text.insert(tk.END, "🔄 Running 60-second simulation...\n")
                self.mm_text.insert(tk.END, "   Analyzing market conditions\n")
                self.mm_text.insert(tk.END, "   Calculating optimal quotes\n")
                self.mm_text.insert(tk.END, "   Tracking position changes\n\n")
                
                # Run simulation
                results = self.market_maker.simulate_market_making("BTC_USDT", duration_minutes=1)
                
                if results and results['results']:
                    self.mm_text.insert(tk.END, f"📊 SIMULATION RESULTS:\n")
                    self.mm_text.insert(tk.END, f"   Symbol: {results['symbol']}\n")
                    self.mm_text.insert(tk.END, f"   Duration: {results['duration_minutes']} minutes\n")
                    self.mm_text.insert(tk.END, f"   Data Points: {results['data_points']}\n")
                    self.mm_text.insert(tk.END, f"   Final PNL: ${results['final_pnl']:+.2f}\n\n")
                    
                    # Show sample data points
                    self.mm_text.insert(tk.END, f"📈 SAMPLE DATA POINTS:\n")
                    for i, point in enumerate(results['results'][:10]):
                        self.mm_text.insert(tk.END, f"   {point['timestamp']}: Mid=${point['mid']:.2f}, ")
                        self.mm_text.insert(tk.END, f"Spread={point['spread_bps']:.1f}bps, ")
                        self.mm_text.insert(tk.END, f"PNL=${point['total_pnl']:+.2f}\n")
                    
                    if len(results['results']) > 10:
                        self.mm_text.insert(tk.END, f"   ... and {len(results['results']) - 10} more points\n")
                    
                    # Calculate statistics
                    spreads = [p['spread_bps'] for p in results['results']]
                    avg_spread = sum(spreads) / len(spreads) if spreads else 0
                    
                    self.mm_text.insert(tk.END, f"\n📊 SIMULATION STATISTICS:\n")
                    self.mm_text.insert(tk.END, f"   Average Spread: {avg_spread:.1f} bps\n")
                    self.mm_text.insert(tk.END, f"   Min Spread: {min(spreads):.1f} bps\n")
                    self.mm_text.insert(tk.END, f"   Max Spread: {max(spreads):.1f} bps\n")
                    
                    self.status_label.config(text="✅ Simulation complete")
                else:
                    self.mm_text.insert(tk.END, "❌ Simulation failed - no data\n")
                    self.status_label.config(text="❌ Simulation failed")
                    
            except Exception as e:
                self.mm_text.insert(tk.END, f"❌ Simulation error: {e}\n")
                self.status_label.config(text="❌ Simulation error")
        
        threading.Thread(target=simulate_thread, daemon=True).start()
    
    def run(self):
        """Run the UI"""
        self.root.mainloop()

def print_separator(title):
    print(f"\n{'='*60}")
    print(f"🔍 {title}")
    print(f"{'='*60}")

def check_spot_balances():
    """Check spot account balances"""
    try:
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = SpotApi(ApiClient(cfg))
        
        print("📊 SPOT ACCOUNT BALANCES:")
        balances = client.list_spot_accounts()
        
        total_usdt_value = 0.0
        has_balance = False
        
        for balance in balances:
            available = float(balance.available)
            total = float(balance.available)  # Using available as total
            
            if total > 0:
                has_balance = True
                print(f"  🪙 {balance.currency:<8} {available:>12.6f} (Available: {available:.6f})")
                
                # Calculate USDT value if not USDT
                if balance.currency != 'USDT' and available > 0:
                    try:
                        ticker = client.list_tickers(currency_pair=f"{balance.currency}_USDT")[0]
                        price = float(ticker.last)
                        usdt_value = available * price
                        total_usdt_value += usdt_value
                        print(f"     💵 Value: ${usdt_value:.6f} @ ${price:.6f}")
                    except:
                        print(f"     💵 Value: Unknown price")
                elif balance.currency == 'USDT':
                    total_usdt_value += available
        
        if not has_balance:
            print("  ❌ No balances found")
        
        print(f"\n💰 Total Spot Value: ${total_usdt_value:.6f}")
        return total_usdt_value
        
    except Exception as e:
        print(f"❌ Spot balance error: {e}")
        return 0.0

def check_margin_balances():
    """Check margin account balances"""
    try:
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = MarginApi(ApiClient(cfg))
        
        print("📊 MARGIN ACCOUNT BALANCES:")
        balances = client.list_margin_accounts()
        
        if balances:
            total_usdt_value = 0.0
            for balance in balances:
                print(f"  🪙 {balance.currency:<8} {float(balance.available):>12.6f}")
                if balance.currency == 'USDT':
                    total_usdt_value += float(balance.available)
            
            print(f"\n💰 Total Margin USDT: ${total_usdt_value:.6f}")
            return total_usdt_value
        else:
            print("  ❌ No margin balances found")
            return 0.0
            
    except Exception as e:
        print(f"❌ Margin balance error: {e}")
        return 0.0

def check_futures_balances():
    """Check futures account balances"""
    try:
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = FuturesApi(ApiClient(cfg))
        
        print("📊 FUTURES ACCOUNT BALANCES:")
        
        # Get futures account summary
        try:
            accounts = client.list_futures_accounts(settle='usdt')
            if accounts:
                for account in accounts:
                    print(f"  💰 Account: {account.mode}")
                    print(f"     Total: ${float(account.total):.6f}")
                    print(f"     Available: ${float(account.available):.6f}")
                    print(f"     Unrealized PNL: ${float(account.unrealised_pnl):.6f}")
                    print(f"     Margin: ${float(account.margin):.6f}")
                    return float(account.total)
            else:
                print("  ❌ No futures accounts found")
        except Exception as e:
            print(f"  ⚠️ Futures account summary error: {e}")
        
        # Try alternative method - get positions
        try:
            positions = client.list_positions(settle='usdt')
            if positions:
                print(f"  📈 Active Positions: {len(positions)}")
                total_unrealized = 0.0
                
                for pos in positions:
                    if float(pos.size) != 0:
                        print(f"     {pos.contract:<15} Size: {pos.size:>10} PNL: ${float(pos.unrealised_pnl):>8.2f}")
                        total_unrealized += float(pos.unrealised_pnl)
                
                print(f"  💰 Total Unrealized PNL: ${total_unrealized:.2f}")
            
        except Exception as e:
            print(f"  ⚠️ Positions error: {e}")
        
        return 0.0
        
    except Exception as e:
        print(f"❌ Futures balance error: {e}")
        return 0.0

def check_deposit_history():
    """Check recent deposit history"""
    try:
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = SpotApi(ApiClient(cfg))
        
        print("📊 RECENT DEPOSITS:")
        deposits = client.list_deposits(limit=10)
        
        if deposits:
            for deposit in deposits[:5]:  # Show last 5
                status = "✅" if deposit.status == 'DONE' else "⏳"
                print(f"  {status} {deposit.currency} {float(deposit.amount):.6f} - {deposit.created_at[:10]}")
        else:
            print("  ❌ No deposit history found")
            
    except Exception as e:
        print(f"❌ Deposit history error: {e}")

def check_trading_status():
    """Check overall trading status"""
    try:
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = SpotApi(ApiClient(cfg))
        
        print("📊 TRADING STATUS:")
        
        # Check open orders
        try:
            orders = client.list_orders(status='open')
            print(f"  📋 Open Orders: {len(orders)}")
            for order in orders[:3]:  # Show first 3
                print(f"     {order.currency_pair} {order.side} {order.amount} @ {order.price}")
        except:
            print("  📋 Open Orders: Error checking")
        
        # Check recent trades
        try:
            trades = client.list_my_trades(limit=10)
            print(f"  📈 Recent Trades: {len(trades)}")
        except:
            print("  📈 Recent Trades: Error checking")
            
    except Exception as e:
        print(f"❌ Trading status error: {e}")

def main():
    """Main function - launch UI or terminal mode"""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--terminal':
        # Terminal mode (original functionality)
        print("🚀 COMPLETE GATE.IO BALANCE CHECKER - TERMINAL MODE")
        print("="*60)
        print(f"🔑 API Key: {GATE_API_KEY[:10]}...")
        print(f"🔑 API Secret: {GATE_API_SECRET[:10]}...")
        
        # Original terminal functions...
        cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        client = SpotApi(ApiClient(cfg))
        scanner = HedgingScanner(client)
        
        print_separator("SPOT ACCOUNT")
        spot_value = check_spot_balances()
        
        print_separator("MARGIN ACCOUNT") 
        margin_value = check_margin_balances()
        
        print_separator("FUTURES ACCOUNT")
        futures_value = check_futures_balances()
        
        print_separator("0-10 CENT COIN SCAN")
        micro_caps = scanner.scan_micro_caps()
        if micro_caps:
            print(f"📊 Found {len(micro_caps)} micro-cap coins:")
            for i, coin in enumerate(micro_caps[:15]):
                print(f"  {i+1:2d}. {coin['symbol']:<8} ${coin['price']:.6f} ({coin['change']:+6.2f}%) Vol:{coin['volume']:>8.0f}")
        
        print_separator("HEDGING OPPORTUNITIES")
        opportunities = scanner.analyze_hedging_opportunities()
        if opportunities:
            print(f"🎯 Found {len(opportunities)} hedging opportunities:")
            for i, opp in enumerate(opportunities[:10]):
                signal_emoji = "🟢" if opp['signal'] == "BUY_HEDGE" else "🔴"
                print(f"  {i+1}. {signal_emoji} {opp['symbol']:<8} {opp['signal']:<10} - {opp['reason']}")
        
        print_separator("TOTAL SUMMARY")
        total_value = spot_value + margin_value + futures_value
        print(f"💰 Total Account Value: ${total_value:.6f}")
        print(f"   Spot: ${spot_value:.6f}")
        print(f"   Margin: ${margin_value:.6f}")
        print(f"   Futures: ${futures_value:.6f}")
        
        print(f"\n✅ Balance check complete!")
        print(f"🕐 Checked at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
    else:
        # Default: Launch UI
        print("🚀 Launching Gate.io Balance + Hedging Scanner UI...")
        ui = GateioBalanceUI()
        ui.run()

if __name__ == "__main__":
    from datetime import datetime
    main()
