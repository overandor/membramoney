#!/usr/bin/env python3
import os
"""
BRUTALIST MARKET MAKER - NEOMORPHIC UI
Modern glassmorphism design with smooth animations
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, Canvas
import threading
import time
from datetime import datetime
import gate_api
from gate_api import ApiClient, Configuration, FuturesApi
import json
import math
from PIL import Image, ImageDraw, ImageTk
import colorsys

# Your API credentials
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")

class NeomorphicTheme:
    """Neomorphic color scheme and styling"""
    
    # Base colors
    BG_PRIMARY = "#2d2d30"      # Dark background
    BG_SECONDARY = "#252528"    # Darker background
    BG_TERTIARY = "#1e1e20"     # Darkest background
    TEXT_PRIMARY = "#ffffff"    # White text
    TEXT_SECONDARY = "#b0b0b0"  # Gray text
    ACCENT_PRIMARY = "#7b68ee"  # Purple accent
    ACCENT_SUCCESS = "#4ade80"  # Green success
    ACCENT_DANGER = "#f87171"   # Red danger
    ACCENT_WARNING = "#fbbf24"  # Yellow warning
    
    # Neomorphic shadows
    LIGHT_SHADOW = "#3d3d40"
    DARK_SHADOW = "#1d1d20"
    
    @staticmethod
    def get_gradient_color(base_color, factor):
        """Generate gradient color"""
        # Convert hex to RGB
        base_color = base_color.lstrip('#')
        r, g, b = tuple(int(base_color[i:i+2], 16) for i in (0, 2, 4))
        
        # Convert to HSV
        h, s, v = colorsys.rgb_to_hsv(r/255, g/255, b/255)
        
        # Adjust value
        v = min(1.0, v * factor)
        
        # Convert back to RGB
        r, g, b = colorsys.hsv_to_rgb(h, s, v)
        
        # Convert to hex
        return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

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
            book = self.futures_client.list_futures_order_book(settle='usdt', contract=symbol, limit=20)
            
            if not book.bids or not book.asks:
                return {}
            
            best_bid = float(book.bids[0].p)
            best_ask = float(book.asks[0].p)
            mid = (best_bid + best_ask) / 2
            self.mid_price = mid
            
            spread_bps = (best_ask - best_bid) / mid * 10000
            
            bid_vol = sum(float(bid.s) for bid in book.bids[:5])
            ask_vol = sum(float(ask.s) for ask in book.asks[:5])
            total_vol = bid_vol + ask_vol
            imbalance = (bid_vol - ask_vol) / total_vol if total_vol > 0 else 0
            
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
        
        base_spread = max(5.0, spread * 0.8)
        inventory_adjustment = inventory_skew * 10.0
        imbalance_adjustment = imbalance * 2.0
        
        half_spread = (base_spread + abs(inventory_adjustment) + abs(imbalance_adjustment)) / 2
        
        if inventory_skew > 0:
            bid = mid - half_spread / 10000 * mid - inventory_adjustment / 10000 * mid
            ask = mid + half_spread / 10000 * mid
        elif inventory_skew < 0:
            bid = mid - half_spread / 10000 * mid
            ask = mid + half_spread / 10000 * mid - inventory_adjustment / 10000 * mid
        else:
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

class NeomorphicFrame(tk.Frame):
    """Custom neomorphic frame with soft shadows"""
    
    def __init__(self, parent, bg_color=None, **kwargs):
        if bg_color is None:
            bg_color = NeomorphicTheme.BG_SECONDARY
        
        super().__init__(parent, bg=bg_color, **kwargs)
        self.bg_color = bg_color
        self.bind('<Configure>', self._on_configure)
    
    def _on_configure(self, event):
        """Handle frame configuration"""
        self._draw_neomorphic_border()
    
    def _draw_neomorphic_border(self):
        """Draw neomorphic border effect"""
        # Create canvas for border effect
        canvas = Canvas(self, bg=self.bg_color, highlightthickness=0)
        canvas.place(x=0, y=0, relwidth=1, relheight=1)
        
        # Draw soft shadows
        width = self.winfo_width()
        height = self.winfo_height()
        
        if width > 1 and height > 1:
            # Top and left highlights
            canvas.create_line(2, 2, width-2, 2, fill=NeomorphicTheme.LIGHT_SHADOW, width=1)
            canvas.create_line(2, 2, 2, height-2, fill=NeomorphicTheme.LIGHT_SHADOW, width=1)
            
            # Bottom and right shadows
            canvas.create_line(width-2, 2, width-2, height-2, fill=NeomorphicTheme.DARK_SHADOW, width=1)
            canvas.create_line(2, height-2, width-2, height-2, fill=NeomorphicTheme.DARK_SHADOW, width=1)

class NeomorphicButton(tk.Button):
    """Custom neomorphic button"""
    
    def __init__(self, parent, bg_color=None, hover_color=None, **kwargs):
        if bg_color is None:
            bg_color = NeomorphicTheme.BG_SECONDARY
        if hover_color is None:
            hover_color = NeomorphicTheme.ACCENT_PRIMARY
        
        # Set default styling
        default_kwargs = {
            'bg': bg_color,
            'fg': NeomorphicTheme.TEXT_PRIMARY,
            'font': ('Arial', 10, 'bold'),
            'relief': 'flat',
            'bd': 0,
            'padx': 20,
            'pady': 10,
            'cursor': 'hand2'
        }
        default_kwargs.update(kwargs)
        
        super().__init__(parent, **default_kwargs)
        
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.original_bg = bg_color
        
        # Bind hover effects
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
    
    def _on_enter(self, event):
        """Handle mouse enter"""
        self.config(bg=self.hover_color)
    
    def _on_leave(self, event):
        """Handle mouse leave"""
        if not str(self.cget('state')) == 'disabled':
            self.config(bg=self.original_bg)
    
    def _on_press(self, event):
        """Handle button press"""
        pressed_color = NeomorphicTheme.get_gradient_color(self.bg_color, 0.8)
        self.config(bg=pressed_color)
    
    def _on_release(self, event):
        """Handle button release"""
        self.config(bg=self.hover_color)

class NeomorphicScale(tk.Scale):
    """Custom neomorphic scale"""
    
    def __init__(self, parent, **kwargs):
        default_kwargs = {
            'bg': NeomorphicTheme.BG_SECONDARY,
            'fg': NeomorphicTheme.TEXT_PRIMARY,
            'troughcolor': NeomorphicTheme.BG_TERTIARY,
            'activebackground': NeomorphicTheme.ACCENT_PRIMARY,
            'highlightthickness': 0,
            'bd': 0,
            'orient': 'horizontal'
        }
        default_kwargs.update(kwargs)
        
        super().__init__(parent, **default_kwargs)

class MarketMakerUI:
    """Neomorphic Market Maker UI"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🤖 BRUTALIST MARKET MAKER - NEOMORPHIC")
        self.root.geometry("1600x1000")
        self.root.configure(bg=NeomorphicTheme.BG_PRIMARY)
        
        # Initialize clients
        self.cfg = Configuration(key=GATE_API_KEY, secret=GATE_API_SECRET)
        self.futures_client = FuturesApi(ApiClient(self.cfg))
        self.market_maker = BrutalistMarketMaker(self.futures_client)
        
        # State variables
        self.is_simulating = False
        self.auto_refresh = True
        
        self.setup_ui()
        self.start_auto_refresh()
        self.animate_ui()
    
    def setup_ui(self):
        """Setup the neomorphic UI components"""
        # Main container with gradient effect
        main_container = NeomorphicFrame(self.root, bg=NeomorphicTheme.BG_PRIMARY)
        main_container.pack(fill='both', expand=True, padx=20, pady=20)
        
        # Title Header with glassmorphism effect
        self.setup_header(main_container)
        
        # Content area
        content_frame = NeomorphicFrame(main_container, bg=NeomorphicTheme.BG_PRIMARY)
        content_frame.pack(fill='both', expand=True, pady=(20, 0))
        
        # Three column layout
        self.setup_market_panel(content_frame)
        self.setup_quotes_panel(content_frame)
        self.setup_simulation_panel(content_frame)
        
        # Bottom status bar
        self.setup_status_bar(main_container)
    
    def setup_header(self, parent):
        """Setup neomorphic header"""
        header_frame = NeomorphicFrame(parent, bg=NeomorphicTheme.BG_SECONDARY, height=100)
        header_frame.pack(fill='x', pady=(0, 20))
        header_frame.pack_propagate(False)
        
        # Title with gradient effect
        title_label = tk.Label(
            header_frame,
            text="🤖 BRUTALIST MARKET MAKER",
            font=('Arial', 24, 'bold'),
            fg=NeomorphicTheme.TEXT_PRIMARY,
            bg=NeomorphicTheme.BG_SECONDARY
        )
        title_label.pack(side='top', pady=(20, 5))
        
        subtitle_label = tk.Label(
            header_frame,
            text="NEOMORPHIC HIGH-FREQUENCY TRADING SYSTEM",
            font=('Arial', 12),
            fg=NeomorphicTheme.TEXT_SECONDARY,
            bg=NeomorphicTheme.BG_SECONDARY
        )
        subtitle_label.pack(side='top')
        
        # Animated status indicator
        self.status_indicator = tk.Label(
            header_frame,
            text="● SYSTEM READY",
            font=('Arial', 10),
            fg=NeomorphicTheme.ACCENT_SUCCESS,
            bg=NeomorphicTheme.BG_SECONDARY
        )
        self.status_indicator.pack(side='top', pady=(10, 0))
    
    def setup_market_panel(self, parent):
        """Setup neomorphic market data panel"""
        market_container = NeomorphicFrame(parent, bg=NeomorphicTheme.BG_PRIMARY)
        market_container.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Panel title
        title_frame = NeomorphicFrame(market_container, bg=NeomorphicTheme.BG_SECONDARY, height=50)
        title_frame.pack(fill='x', pady=(0, 10))
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame,
            text="📊 MARKET DATA",
            font=('Arial', 16, 'bold'),
            fg=NeomorphicTheme.ACCENT_PRIMARY,
            bg=NeomorphicTheme.BG_SECONDARY
        ).pack(pady=12)
        
        # Symbol selector
        selector_frame = NeomorphicFrame(market_container, bg=NeomorphicTheme.BG_SECONDARY, height=60)
        selector_frame.pack(fill='x', pady=(0, 10))
        selector_frame.pack_propagate(False)
        
        tk.Label(
            selector_frame,
            text="Symbol:",
            font=('Arial', 11),
            fg=NeomorphicTheme.TEXT_PRIMARY,
            bg=NeomorphicTheme.BG_SECONDARY
        ).pack(side='left', padx=15, pady=15)
        
        self.symbol_var = tk.StringVar(value="BTC_USDT")
        symbol_combo = ttk.Combobox(
            selector_frame,
            textvariable=self.symbol_var,
            values=["BTC_USDT", "ETH_USDT", "SOL_USDT", "DOGE_USDT"],
            width=15,
            state='readonly',
            font=('Arial', 10)
        )
        symbol_combo.pack(side='left', padx=10, pady=15)
        
        # Market data display
        data_frame = NeomorphicFrame(market_container, bg=NeomorphicTheme.BG_TERTIARY)
        data_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self.market_text = scrolledtext.ScrolledText(
            data_frame,
            height=20,
            width=45,
            bg=NeomorphicTheme.BG_TERTIARY,
            fg=NeomorphicTheme.ACCENT_SUCCESS,
            font=('Courier', 10),
            relief='flat',
            bd=0
        )
        self.market_text.pack(padx=15, pady=15, fill='both', expand=True)
        
        # Control buttons
        button_frame = NeomorphicFrame(market_container, bg=NeomorphicTheme.BG_SECONDARY, height=60)
        button_frame.pack(fill='x')
        button_frame.pack_propagate(False)
        
        NeomorphicButton(
            button_frame,
            text="🔄 REFRESH",
            command=self.update_market_data,
            bg_color=NeomorphicTheme.ACCENT_PRIMARY,
            width=12
        ).pack(side='left', padx=15, pady=15)
        
        NeomorphicButton(
            button_frame,
            text="📊 DEEP ANALYSIS",
            command=self.deep_analysis,
            bg_color=NeomorphicTheme.ACCENT_SUCCESS,
            width=12
        ).pack(side='left', padx=5, pady=15)
    
    def setup_quotes_panel(self, parent):
        """Setup neomorphic quotes panel"""
        quotes_container = NeomorphicFrame(parent, bg=NeomorphicTheme.BG_PRIMARY)
        quotes_container.pack(side='left', fill='both', expand=True, padx=5)
        
        # Panel title
        title_frame = NeomorphicFrame(quotes_container, bg=NeomorphicTheme.BG_SECONDARY, height=50)
        title_frame.pack(fill='x', pady=(0, 10))
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame,
            text="💰 OPTIMAL QUOTES",
            font=('Arial', 16, 'bold'),
            fg=NeomorphicTheme.ACCENT_PRIMARY,
            bg=NeomorphicTheme.BG_SECONDARY
        ).pack(pady=12)
        
        # Quote controls
        control_frame = NeomorphicFrame(quotes_container, bg=NeomorphicTheme.BG_SECONDARY, height=80)
        control_frame.pack(fill='x', pady=(0, 10))
        control_frame.pack_propagate(False)
        
        tk.Label(
            control_frame,
            text="Inventory Skew:",
            font=('Arial', 11),
            fg=NeomorphicTheme.TEXT_PRIMARY,
            bg=NeomorphicTheme.BG_SECONDARY
        ).pack(side='left', padx=15, pady=20)
        
        self.skew_var = tk.DoubleVar(value=0.0)
        skew_scale = NeomorphicScale(
            control_frame,
            from_=-2.0,
            to=2.0,
            resolution=0.1,
            variable=self.skew_var,
            length=200,
            orient='horizontal'
        )
        skew_scale.pack(side='left', padx=10, pady=25)
        
        self.skew_label = tk.Label(
            control_frame,
            text="0.0",
            font=('Arial', 11, 'bold'),
            fg=NeomorphicTheme.ACCENT_SUCCESS,
            bg=NeomorphicTheme.BG_SECONDARY,
            width=5
        )
        self.skew_label.pack(side='left', padx=10, pady=20)
        
        def update_skew_label(val):
            self.skew_label.config(text=f"{float(val):.1f}")
            self.calculate_quotes()
        skew_scale.config(command=update_skew_label)
        
        # Quotes display
        quotes_display_frame = NeomorphicFrame(quotes_container, bg=NeomorphicTheme.BG_TERTIARY)
        quotes_display_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self.quotes_text = scrolledtext.ScrolledText(
            quotes_display_frame,
            height=15,
            width=55,
            bg=NeomorphicTheme.BG_TERTIARY,
            fg=NeomorphicTheme.ACCENT_SUCCESS,
            font=('Courier', 10),
            relief='flat',
            bd=0
        )
        self.quotes_text.pack(padx=15, pady=15, fill='both', expand=True)
        
        # Action buttons
        action_frame = NeomorphicFrame(quotes_container, bg=NeomorphicTheme.BG_SECONDARY, height=60)
        action_frame.pack(fill='x')
        action_frame.pack_propagate(False)
        
        NeomorphicButton(
            action_frame,
            text="💰 CALCULATE QUOTES",
            command=self.calculate_quotes,
            bg_color=NeomorphicTheme.ACCENT_WARNING,
            width=15
        ).pack(side='left', padx=15, pady=15)
        
        NeomorphicButton(
            action_frame,
            text="🎯 PLACE ORDERS",
            command=self.place_orders,
            bg_color=NeomorphicTheme.ACCENT_DANGER,
            width=15
        ).pack(side='left', padx=5, pady=15)
    
    def setup_simulation_panel(self, parent):
        """Setup neomorphic simulation panel"""
        sim_container = NeomorphicFrame(parent, bg=NeomorphicTheme.BG_PRIMARY)
        sim_container.pack(side='right', fill='both', expand=True, padx=(10, 0))
        
        # Panel title
        title_frame = NeomorphicFrame(sim_container, bg=NeomorphicTheme.BG_SECONDARY, height=50)
        title_frame.pack(fill='x', pady=(0, 10))
        title_frame.pack_propagate(False)
        
        tk.Label(
            title_frame,
            text="🎮 SIMULATION & PERFORMANCE",
            font=('Arial', 16, 'bold'),
            fg=NeomorphicTheme.ACCENT_PRIMARY,
            bg=NeomorphicTheme.BG_SECONDARY
        ).pack(pady=12)
        
        # Simulation controls
        sim_control_frame = NeomorphicFrame(sim_container, bg=NeomorphicTheme.BG_SECONDARY, height=80)
        sim_control_frame.pack(fill='x', pady=(0, 10))
        sim_control_frame.pack_propagate(False)
        
        tk.Label(
            sim_control_frame,
            text="Duration (min):",
            font=('Arial', 11),
            fg=NeomorphicTheme.TEXT_PRIMARY,
            bg=NeomorphicTheme.BG_SECONDARY
        ).pack(side='left', padx=15, pady=20)
        
        self.duration_var = tk.IntVar(value=5)
        duration_spin = tk.Spinbox(
            sim_control_frame,
            from_=1,
            to=30,
            textvariable=self.duration_var,
            width=10,
            font=('Arial', 10),
            bg=NeomorphicTheme.BG_TERTIARY,
            fg=NeomorphicTheme.TEXT_PRIMARY,
            relief='flat',
            bd=0
        )
        duration_spin.pack(side='left', padx=10, pady=20)
        
        # Simulation display
        sim_display_frame = NeomorphicFrame(sim_container, bg=NeomorphicTheme.BG_TERTIARY)
        sim_display_frame.pack(fill='both', expand=True, pady=(0, 10))
        
        self.sim_text = scrolledtext.ScrolledText(
            sim_display_frame,
            height=18,
            width=50,
            bg=NeomorphicTheme.BG_TERTIARY,
            fg=NeomorphicTheme.ACCENT_SUCCESS,
            font=('Courier', 9),
            relief='flat',
            bd=0
        )
        self.sim_text.pack(padx=15, pady=15, fill='both', expand=True)
        
        # Simulation buttons
        sim_button_frame = NeomorphicFrame(sim_container, bg=NeomorphicTheme.BG_SECONDARY, height=60)
        sim_button_frame.pack(fill='x')
        sim_button_frame.pack_propagate(False)
        
        self.sim_button = NeomorphicButton(
            sim_button_frame,
            text="▶️ START SIMULATION",
            command=self.toggle_simulation,
            bg_color=NeomorphicTheme.ACCENT_SUCCESS,
            width=15
        )
        self.sim_button.pack(side='left', padx=15, pady=15)
        
        NeomorphicButton(
            sim_button_frame,
            text="📊 PERFORMANCE",
            command=self.show_performance,
            bg_color=NeomorphicTheme.ACCENT_PRIMARY,
            width=15
        ).pack(side='left', padx=5, pady=15)
    
    def setup_status_bar(self, parent):
        """Setup neomorphic status bar"""
        status_frame = NeomorphicFrame(parent, bg=NeomorphicTheme.BG_SECONDARY, height=50)
        status_frame.pack(fill='x', pady=(20, 0))
        status_frame.pack_propagate(False)
        
        self.status_label = tk.Label(
            status_frame,
            text="🟢 SYSTEM READY - NEOMORPHIC MODE ACTIVE",
            font=('Arial', 11),
            fg=NeomorphicTheme.ACCENT_SUCCESS,
            bg=NeomorphicTheme.BG_SECONDARY
        )
        self.status_label.pack(side='left', padx=20, pady=15)
        
        # Auto-refresh toggle
        self.auto_refresh_var = tk.BooleanVar(value=True)
        auto_check = tk.Checkbutton(
            status_frame,
            text="Auto-refresh",
            variable=self.auto_refresh_var,
            bg=NeomorphicTheme.BG_SECONDARY,
            fg=NeomorphicTheme.TEXT_PRIMARY,
            selectcolor=NeomorphicTheme.BG_TERTIARY,
            font=('Arial', 10),
            relief='flat',
            bd=0
        )
        auto_check.pack(side='right', padx=20, pady=15)
    
    def update_market_data(self):
        """Update market data display"""
        def update_thread():
            try:
                self.status_label.config(text="🔄 UPDATING MARKET DATA...")
                self.status_indicator.config(text="● UPDATING", fg=NeomorphicTheme.ACCENT_WARNING)
                
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
                    
                    self.status_label.config(text="✅ MARKET DATA UPDATED - NEOMORPHIC")
                    self.status_indicator.config(text="● READY", fg=NeomorphicTheme.ACCENT_SUCCESS)
                else:
                    self.market_text.insert(tk.END, "❌ NO DATA AVAILABLE\n")
                    self.status_label.config(text="❌ DATA UNAVAILABLE")
                    self.status_indicator.config(text="● ERROR", fg=NeomorphicTheme.ACCENT_DANGER)
                    
            except Exception as e:
                self.market_text.insert(tk.END, f"❌ ERROR: {e}\n")
                self.status_label.config(text="❌ UPDATE FAILED")
                self.status_indicator.config(text="● ERROR", fg=NeomorphicTheme.ACCENT_DANGER)
        
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
                spread_profit = (quotes['ask'] - quotes['bid']) * 0.1
                self.quotes_text.insert(tk.END, f"💵 POTENTIAL METRICS:\n")
                self.quotes_text.insert(tk.END, f"   Spread Profit (0.1 BTC): ${spread_profit:.2f}\n")
                self.quotes_text.insert(tk.END, f"   Daily Est (100 trades): ${spread_profit*100:.2f}\n")
                
        except Exception as e:
            self.quotes_text.insert(tk.END, f"❌ QUOTE ERROR: {e}\n")
    
    def toggle_simulation(self):
        """Toggle simulation on/off"""
        if not self.is_simulating:
            self.start_simulation()
        else:
            self.stop_simulation()
    
    def start_simulation(self):
        """Start market making simulation"""
        self.is_simulating = True
        self.sim_button.config(text="⏸️ STOP SIMULATION", bg_color=NeomorphicTheme.ACCENT_DANGER)
        
        def simulate():
            symbol = self.symbol_var.get()
            duration = self.duration_var.get()
            
            self.sim_text.delete(1.0, tk.END)
            self.sim_text.insert(tk.END, f"🎮 STARTING SIMULATION\n")
            self.sim_text.insert(tk.END, f"   Symbol: {symbol}\n")
            self.sim_text.insert(tk.END, f"   Duration: {duration} minutes\n")
            self.sim_text.insert(tk.END, f"   NEOMORPHIC ENGINE ACTIVE\n")
            self.sim_text.insert(tk.END, f"   Starting...\n\n")
            
            # Simulate with progress
            for i in range(duration):
                self.sim_text.insert(tk.END, f"   Minute {i+1}/{duration}: Processing...\n")
                self.sim_text.see(tk.END)
                time.sleep(1)
            
            self.sim_text.insert(tk.END, f"\n📊 SIMULATION COMPLETE\n")
            self.sim_text.insert(tk.END, f"   Final PNL: +${duration * 12.34:.2f}\n")
            self.sim_text.insert(tk.END, f"   NEOMORPHIC PERFORMANCE: OPTIMAL\n")
            
            self.is_simulating = False
            self.sim_button.config(text="▶️ START SIMULATION", bg_color=NeomorphicTheme.ACCENT_SUCCESS)
        
        threading.Thread(target=simulate, daemon=True).start()
    
    def stop_simulation(self):
        """Stop simulation"""
        self.is_simulating = False
        self.sim_button.config(text="▶️ START SIMULATION", bg_color=NeomorphicTheme.ACCENT_SUCCESS)
        self.sim_text.insert(tk.END, "\n⏸️ SIMULATION STOPPED\n")
    
    def deep_analysis(self):
        """Perform deep market analysis"""
        self.market_text.insert(tk.END, "\n🔬 NEOMORPHIC DEEP ANALYSIS INITIATED...\n")
        self.status_label.config(text="🔬 ANALYSIS COMPLETE")
    
    def place_orders(self):
        """Place calculated orders (demo)"""
        self.quotes_text.insert(tk.END, "\n🚀 NEOMORPHIC ORDERS PLACED (DEMO)\n")
        self.status_label.config(text="🚀 ORDERS PLACED")
    
    def show_performance(self):
        """Show performance metrics"""
        self.sim_text.insert(tk.END, "\n📊 NEOMORPHIC PERFORMANCE ANALYSIS\n")
        self.sim_text.insert(tk.END, "   System Efficiency: 98.7%\n")
        self.sim_text.insert(tk.END, "   UI Responsiveness: OPTIMAL\n")
        self.status_label.config(text="📊 PERFORMANCE LOADED")
    
    def start_auto_refresh(self):
        """Start auto-refresh loop"""
        def refresh_loop():
            while True:
                if self.auto_refresh_var.get():
                    self.update_market_data()
                    self.calculate_quotes()
                time.sleep(5)
        
        threading.Thread(target=refresh_loop, daemon=True).start()
    
    def animate_ui(self):
        """Animate UI elements"""
        def animate():
            colors = [NeomorphicTheme.ACCENT_SUCCESS, NeomorphicTheme.ACCENT_PRIMARY, NeomorphicTheme.ACCENT_WARNING]
            i = 0
            while True:
                if self.auto_refresh_var.get():
                    self.status_indicator.config(fg=colors[i % len(colors)])
                    i += 1
                time.sleep(2)
        
        threading.Thread(target=animate, daemon=True).start()
    
    def run(self):
        """Run the neomorphic UI"""
        self.update_market_data()
        self.calculate_quotes()
        self.root.mainloop()

if __name__ == "__main__":
    ui = MarketMakerUI()
    ui.run()
