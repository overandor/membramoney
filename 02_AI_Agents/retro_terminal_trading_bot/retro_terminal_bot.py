#!/usr/bin/env python3
"""
RETRO 90s TERMINAL TRADING BOT
Brutalist computer aesthetic with collaborative colors
Real Gate.io account integration
"""

import asyncio
import aiohttp
import json
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, font
import threading
import time
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import logging
from dataclasses import dataclass, field
from enum import Enum
import random
import hashlib
import hmac
import base64
from urllib.parse import urlencode

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 90s TERMINAL COLOR PALETTE - Collaborating colors
class TerminalColors:
    # Classic terminal green matrix
    MATRIX_GREEN = '#00ff41'
    MATRIX_GREEN_DIM = '#00cc33'
    MATRIX_GREEN_DARK = '#008811'
    
    # Phosphor green variations
    PHOSPHOR_BRIGHT = '#33ff33'
    PHOSPHOR_MEDIUM = '#00ff00'
    PHOSPHOR_DIM = '#00cc00'
    
    # Amber terminal (classic 80s/90s)
    AMBER_BRIGHT = '#ffb000'
    AMBER_MEDIUM = '#ff8800'
    AMBER_DIM = '#cc6600'
    
    # Terminal backgrounds
    BLACK_MATRIX = '#000000'
    DARK_GREEN = '#001100'
    DARK_AMBER = '#1a0f00'
    
    # Accent colors
    CYAN_BRIGHT = '#00ffff'
    CYAN_DIM = '#00cccc'
    RED_ALERT = '#ff3333'
    YELLOW_WARNING = '#ffff00'

class RetroTerminalUI:
    """90s Brutalist Terminal UI"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("TERMINAL://GATE.IO_TRADING_SYSTEM")
        self.root.geometry("1600x1000")
        self.root.configure(bg=TerminalColors.BLACK_MATRIX)
        
        # Brutalist 90s styling
        self.root.overrideredirect(False)
        self.setup_terminal_fonts()
        
        # Initialize bot
        self.bot = None
        self.running = False
        
        # Create retro terminal interface
        self.create_terminal_interface()
        
        # Start terminal effects
        self.start_terminal_effects()
        
        # Initialize bot in background
        threading.Thread(target=self.initialize_system, daemon=True).start()
        
        # Start update loop
        self.update_terminal()
    
    def setup_terminal_fonts(self):
        """Setup 90s terminal fonts"""
        # Classic terminal fonts
        self.terminal_font = font.Font(family="Courier New", size=10, weight="bold")
        self.header_font = font.Font(family="Courier New", size=14, weight="bold")
        self.small_font = font.Font(family="Courier New", size=8)
        self.large_font = font.Font(family="Courier New", size=16, weight="bold")
    
    def create_terminal_interface(self):
        """Create brutalist terminal interface"""
        # Main terminal frame
        self.terminal_frame = tk.Frame(self.root, bg=TerminalColors.BLACK_MATRIX, relief=tk.SOLID, bd=3)
        self.terminal_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Terminal header
        self.create_terminal_header()
        
        # Main content area
        self.create_main_terminal()
        
        # Status bar
        self.create_status_bar()
        
        # Control panel
        self.create_control_panel()
    
    def create_terminal_header(self):
        """Create terminal header with system info"""
        header_frame = tk.Frame(self.terminal_frame, bg=TerminalColors.MATRIX_GREEN_DARK, relief=tk.RAISED, bd=2)
        header_frame.pack(fill=tk.X, padx=2, pady=2)
        
        # System title
        title_label = tk.Label(header_frame, 
                              text="[SYSTEM://GATE.IO_TRADING_TERMINAL_v2.0]",
                              font=self.large_font,
                              fg=TerminalColors.MATRIX_GREEN,
                              bg=TerminalColors.MATRIX_GREEN_DARK)
        title_label.pack(pady=5)
        
        # System info bar
        info_frame = tk.Frame(header_frame, bg=TerminalColors.BLACK_MATRIX)
        info_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.system_time_label = tk.Label(info_frame, 
                                         text="TIME: --:--:--",
                                         font=self.terminal_font,
                                         fg=TerminalColors.PHOSPHOR_BRIGHT,
                                         bg=TerminalColors.BLACK_MATRIX)
        self.system_time_label.pack(side=tk.LEFT, padx=10)
        
        self.connection_status_label = tk.Label(info_frame, 
                                               text="[STATUS: INITIALIZING...]",
                                               font=self.terminal_font,
                                               fg=TerminalColors.AMBER_BRIGHT,
                                               bg=TerminalColors.BLACK_MATRIX)
        self.connection_status_label.pack(side=tk.LEFT, padx=10)
        
        self.account_balance_label = tk.Label(info_frame, 
                                            text="BALANCE: $--.--",
                                            font=self.terminal_font,
                                            fg=TerminalColors.CYAN_BRIGHT,
                                            bg=TerminalColors.BLACK_MATRIX)
        self.account_balance_label.pack(side=tk.RIGHT, padx=10)
    
    def create_main_terminal(self):
        """Create main terminal display area"""
        main_frame = tk.Frame(self.terminal_frame, bg=TerminalColors.BLACK_MATRIX)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        
        # Left panel - Account & Positions
        left_panel = tk.Frame(main_frame, bg=TerminalColors.DARK_GREEN, relief=tk.SUNKEN, bd=3)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(2, 1), pady=2)
        
        # Account section
        self.create_account_section(left_panel)
        
        # Positions section
        self.create_positions_section(left_panel)
        
        # Center panel - Market & Contracts
        center_panel = tk.Frame(main_frame, bg=TerminalColors.DARK_GREEN, relief=tk.SUNKEN, bd=3)
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=1, pady=2)
        
        # Market scanner
        self.create_market_section(center_panel)
        
        # Contracts section
        self.create_contracts_section(center_panel)
        
        # Right panel - Terminal Log
        right_panel = tk.Frame(main_frame, bg=TerminalColors.DARK_GREEN, relief=tk.SUNKEN, bd=3)
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(1, 2), pady=2)
        
        # Terminal log
        self.create_terminal_log(right_panel)
        
        # System monitor
        self.create_system_monitor(right_panel)
    
    def create_account_section(self, parent):
        """Create account information section"""
        account_frame = tk.Frame(parent, bg=TerminalColors.BLACK_MATRIX, relief=tk.GROOVE, bd=2)
        account_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(account_frame, text=">>> ACCOUNT_BALANCE <<<",
                font=self.header_font,
                fg=TerminalColors.PHOSPHOR_BRIGHT,
                bg=TerminalColors.BLACK_MATRIX).pack(pady=5)
        
        # Account tree with terminal styling
        self.account_tree = ttk.Treeview(account_frame, 
                                       columns=('currency', 'available', 'frozen', 'total'),
                                       show='tree headings',
                                       height=8)
        
        # Configure terminal style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('Terminal.Treeview', 
                       background=TerminalColors.BLACK_MATRIX,
                       foreground=TerminalColors.PHOSPHOR_MEDIUM,
                       fieldbackground=TerminalColors.BLACK_MATRIX,
                       borderwidth=0,
                       font=self.terminal_font)
        style.configure('Terminal.Treeview.Heading',
                       background=TerminalColors.MATRIX_GREEN_DARK,
                       foreground=TerminalColors.PHOSPHOR_BRIGHT,
                       font=self.terminal_font)
        
        self.account_tree.configure(style='Terminal.Treeview')
        
        self.account_tree.heading('#0', text='ACCOUNT')
        self.account_tree.heading('currency', text='CURR')
        self.account_tree.heading('available', text='AVAIL')
        self.account_tree.heading('frozen', text='FROZ')
        self.account_tree.heading('total', text='TOTAL')
        
        self.account_tree.column('#0', width=100)
        self.account_tree.column('currency', width=80)
        self.account_tree.column('available', width=100)
        self.account_tree.column('frozen', width=80)
        self.account_tree.column('total', width=80)
        
        self.account_tree.pack(padx=5, pady=5)
    
    def create_positions_section(self, parent):
        """Create positions section"""
        positions_frame = tk.Frame(parent, bg=TerminalColors.BLACK_MATRIX, relief=tk.GROOVE, bd=2)
        positions_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(positions_frame, text=">>> ACTIVE_POSITIONS <<<",
                font=self.header_font,
                fg=TerminalColors.PHOSPHOR_BRIGHT,
                bg=TerminalColors.BLACK_MATRIX).pack(pady=5)
        
        self.positions_tree = ttk.Treeview(positions_frame,
                                         columns=('symbol', 'type', 'side', 'size', 'pnl', 'margin'),
                                         show='tree headings',
                                         height=10)
        self.positions_tree.configure(style='Terminal.Treeview')
        
        self.positions_tree.heading('#0', text='ID')
        self.positions_tree.heading('symbol', text='SYMBOL')
        self.positions_tree.heading('type', text='TYPE')
        self.positions_tree.heading('side', text='SIDE')
        self.positions_tree.heading('size', text='SIZE')
        self.positions_tree.heading('pnl', text='PNL')
        self.positions_tree.heading('margin', text='MARGIN')
        
        self.positions_tree.column('#0', width=40)
        self.positions_tree.column('symbol', width=80)
        self.positions_tree.column('type', width=60)
        self.positions_tree.column('side', width=50)
        self.positions_tree.column('size', width=80)
        self.positions_tree.column('pnl', width=80)
        self.positions_tree.column('margin', width=70)
        
        self.positions_tree.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
    
    def create_market_section(self, parent):
        """Create market scanner section"""
        market_frame = tk.Frame(parent, bg=TerminalColors.BLACK_MATRIX, relief=tk.GROOVE, bd=2)
        market_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(market_frame, text=">>> MARKET_SCANNER <<<",
                font=self.header_font,
                fg=TerminalColors.CYAN_BRIGHT,
                bg=TerminalColors.BLACK_MATRIX).pack(pady=5)
        
        # Market status
        self.market_status_label = tk.Label(market_frame,
                                          text="[SCANNER: OFFLINE]",
                                          font=self.terminal_font,
                                          fg=TerminalColors.AMBER_MEDIUM,
                                          bg=TerminalColors.BLACK_MATRIX)
        self.market_status_label.pack()
        
        # Scanner results
        self.scanner_text = tk.Text(market_frame, height=8, width=50,
                                   bg=TerminalColors.BLACK_MATRIX,
                                   fg=TerminalColors.PHOSPHOR_MEDIUM,
                                   font=self.small_font,
                                   relief=tk.FLAT,
                                   bd=0)
        self.scanner_text.pack(padx=5, pady=5)
    
    def create_contracts_section(self, parent):
        """Create contracts section"""
        contracts_frame = tk.Frame(parent, bg=TerminalColors.BLACK_MATRIX, relief=tk.GROOVE, bd=2)
        contracts_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(contracts_frame, text=">>> MICRO_CONTRACTS <<<",
                font=self.header_font,
                fg=TerminalColors.CYAN_BRIGHT,
                bg=TerminalColors.BLACK_MATRIX).pack(pady=5)
        
        self.contracts_tree = ttk.Treeview(contracts_frame,
                                         columns=('symbol', 'type', 'price', 'nominal', 'volume'),
                                         show='tree headings',
                                         height=12)
        self.contracts_tree.configure(style='Terminal.Treeview')
        
        self.contracts_tree.heading('#0', text='ID')
        self.contracts_tree.heading('symbol', text='SYMBOL')
        self.contracts_tree.heading('type', text='TYPE')
        self.contracts_tree.heading('price', text='PRICE')
        self.contracts_tree.heading('nominal', text='NOMINAL')
        self.contracts_tree.heading('volume', text='VOLUME')
        
        self.contracts_tree.column('#0', width=40)
        self.contracts_tree.column('symbol', width=80)
        self.contracts_tree.column('type', width=60)
        self.contracts_tree.column('price', width=80)
        self.contracts_tree.column('nominal', width=80)
        self.contracts_tree.column('volume', width=70)
        
        self.contracts_tree.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
    
    def create_terminal_log(self, parent):
        """Create terminal log section"""
        log_frame = tk.Frame(parent, bg=TerminalColors.BLACK_MATRIX, relief=tk.GROOVE, bd=2)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        tk.Label(log_frame, text=">>> TERMINAL_LOG <<<",
                font=self.header_font,
                fg=TerminalColors.AMBER_BRIGHT,
                bg=TerminalColors.BLACK_MATRIX).pack(pady=5)
        
        self.terminal_log = scrolledtext.ScrolledText(log_frame, height=15, width=50,
                                                    bg=TerminalColors.BLACK_MATRIX,
                                                    fg=TerminalColors.PHOSPHOR_MEDIUM,
                                                    font=self.terminal_font,
                                                    relief=tk.FLAT,
                                                    bd=0,
                                                    insertbackground=TerminalColors.PHOSPHOR_BRIGHT)
        self.terminal_log.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        # Initial boot sequence
        self.boot_sequence()
    
    def create_system_monitor(self, parent):
        """Create system monitor section"""
        monitor_frame = tk.Frame(parent, bg=TerminalColors.BLACK_MATRIX, relief=tk.GROOVE, bd=2)
        monitor_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(monitor_frame, text=">>> SYSTEM_MONITOR <<<",
                font=self.header_font,
                fg=TerminalColors.CYAN_BRIGHT,
                bg=TerminalColors.BLACK_MATRIX).pack(pady=5)
        
        # System stats
        self.trades_label = tk.Label(monitor_frame, text="TRADES: 000",
                                    font=self.terminal_font,
                                    fg=TerminalColors.PHOSPHOR_MEDIUM,
                                    bg=TerminalColors.BLACK_MATRIX)
        self.trades_label.pack()
        
        self.pnl_label = tk.Label(monitor_frame, text="PNL: $0.0000",
                                 font=self.terminal_font,
                                 fg=TerminalColors.PHOSPHOR_MEDIUM,
                                 bg=TerminalColors.BLACK_MATRIX)
        self.pnl_label.pack()
        
        self.winrate_label = tk.Label(monitor_frame, text="WIN_RATE: 00.0%",
                                     font=self.terminal_font,
                                     fg=TerminalColors.PHOSPHOR_MEDIUM,
                                     bg=TerminalColors.BLACK_MATRIX)
        self.winrate_label.pack()
        
        self.positions_count_label = tk.Label(monitor_frame, text="POSITIONS: 0/10",
                                             font=self.terminal_font,
                                             fg=TerminalColors.PHOSPHOR_MEDIUM,
                                             bg=TerminalColors.BLACK_MATRIX)
        self.positions_count_label.pack()
    
    def create_status_bar(self):
        """Create terminal status bar"""
        status_frame = tk.Frame(self.terminal_frame, bg=TerminalColors.MATRIX_GREEN_DARK, relief=tk.RAISED, bd=2)
        status_frame.pack(fill=tk.X, padx=2, pady=2)
        
        self.status_label = tk.Label(status_frame,
                                   text="[SYSTEM READY - AWAITING COMMANDS...]",
                                   font=self.terminal_font,
                                   fg=TerminalColors.PHOSPHOR_BRIGHT,
                                   bg=TerminalColors.MATRIX_GREEN_DARK)
        self.status_label.pack(pady=5)
    
    def create_control_panel(self):
        """Create brutalist control panel"""
        control_frame = tk.Frame(self.terminal_frame, bg=TerminalColors.BLACK_MATRIX, relief=tk.RAISED, bd=3)
        control_frame.pack(fill=tk.X, padx=2, pady=2)
        
        # Brutalist button styling
        button_style = {
            'font': self.terminal_font,
            'relief': tk.RAISED,
            'bd': 3,
            'width': 20,
            'height': 2
        }
        
        self.start_button = tk.Button(control_frame,
                                    text="[START_TRADING]",
                                    command=self.start_trading,
                                    bg=TerminalColors.MATRIX_GREEN_DARK,
                                    fg=TerminalColors.PHOSPHOR_BRIGHT,
                                    activebackground=TerminalColors.MATRIX_GREEN,
                                    **button_style)
        self.start_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.stop_button = tk.Button(control_frame,
                                   text="[STOP_TRADING]",
                                   command=self.stop_trading,
                                   bg=TerminalColors.BLACK_MATRIX,
                                   fg=TerminalColors.RED_ALERT,
                                   state=tk.DISABLED,
                                   activebackground=TerminalColors.MATRIX_GREEN_DARK,
                                   **button_style)
        self.stop_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.scan_button = tk.Button(control_frame,
                                   text="[SCAN_MARKET]",
                                   command=self.scan_market,
                                   bg=TerminalColors.DARK_AMBER,
                                   fg=TerminalColors.AMBER_BRIGHT,
                                   activebackground=TerminalColors.AMBER_MEDIUM,
                                   **button_style)
        self.scan_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.shuffle_button = tk.Button(control_frame,
                                      text="[SHUFFLE_FUNDS]",
                                      command=self.shuffle_funds,
                                      bg=TerminalColors.BLACK_MATRIX,
                                      fg=TerminalColors.CYAN_BRIGHT,
                                      activebackground=TerminalColors.MATRIX_GREEN_DARK,
                                      **button_style)
        self.shuffle_button.pack(side=tk.LEFT, padx=5, pady=5)
        
        self.emergency_button = tk.Button(control_frame,
                                        text="[EMERGENCY_STOP]",
                                        command=self.emergency_stop,
                                        bg=TerminalColors.RED_ALERT,
                                        fg=TerminalColors.BLACK_MATRIX,
                                        activebackground=TerminalColors.AMBER_MEDIUM,
                                        **button_style)
        self.emergency_button.pack(side=tk.RIGHT, padx=5, pady=5)
    
    def boot_sequence(self):
        """Display terminal boot sequence"""
        boot_messages = [
            ">>> TERMINAL BOOT SEQUENCE INITIATED...",
            ">>> LOADING GATE.IO API MODULES...",
            ">>> ESTABLISHING SECURE CONNECTION...",
            ">>> AUTHENTICATING API CREDENTIALS...",
            ">>> INITIALIZING TRADING ENGINE...",
            ">>> CALIBRATING MICRO-CAP SCANNERS...",
            ">>> SYSTEM READY - AWAITING COMMANDS..."
        ]
        
        for message in boot_messages:
            self.terminal_log.insert(tk.END, f"{message}\n")
            self.terminal_log.see(tk.END)
            self.root.update()
            time.sleep(0.3)
    
    def log_terminal(self, message, color=TerminalColors.PHOSPHOR_MEDIUM):
        """Log message to terminal with color"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Add colored tag
        tag_name = f"color_{int(time.time())}"
        self.terminal_log.tag_configure(tag_name, foreground=color)
        
        self.terminal_log.insert(tk.END, f"[{timestamp}] {message}\n", tag_name)
        self.terminal_log.see(tk.END)
    
    def start_terminal_effects(self):
        """Start terminal visual effects"""
        self.update_system_time()
        self.cursor_blink()
    
    def update_system_time(self):
        """Update system time display"""
        current_time = datetime.now().strftime("%H:%M:%S")
        self.system_time_label.config(text=f"TIME: {current_time}")
        self.root.after(1000, self.update_system_time)
    
    def cursor_blink(self):
        """Create terminal cursor blink effect"""
        if hasattr(self, 'connection_status_label'):
            current_text = self.connection_status_label.cget("text")
            if current_text.endswith("█"):
                self.connection_status_label.config(text=current_text[:-1])
            else:
                self.connection_status_label.config(text=current_text + "█")
        self.root.after(500, self.cursor_blink)
    
    def initialize_system(self):
        """Initialize trading system"""
        try:
            # Import and initialize bot
            from advanced_gateio_bot import AdvancedGateioBot
            self.bot = AdvancedGateioBot()
            
            # Initialize account
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.bot.initialize_account())
            
            # Update UI with real data
            self.root.after(0, self.update_account_display)
            self.log_terminal(f"ACCOUNT CONNECTED - BALANCE: ${self.bot.total_usdt_balance:.2f}", 
                            TerminalColors.CYAN_BRIGHT)
            self.connection_status_label.config(text="[STATUS: CONNECTED]")
            
        except Exception as e:
            self.log_terminal(f"INITIALIZATION ERROR: {e}", TerminalColors.RED_ALERT)
            self.connection_status_label.config(text="[STATUS: ERROR]")
    
    def update_account_display(self):
        """Update account display with real data"""
        if not self.bot:
            return
        
        # Clear existing items
        for item in self.account_tree.get_children():
            self.account_tree.delete(item)
        
        # Add account balances
        for key, balance in self.bot.account_balances.items():
            self.account_tree.insert('', 'end', text=key,
                                    values=(balance.currency,
                                           f"{balance.available:.4f}",
                                           f"{balance.frozen:.4f}",
                                           f"{balance.total:.4f}"))
        
        # Update balance display
        self.account_balance_label.config(text=f"BALANCE: ${self.bot.total_usdt_balance:.2f}")
    
    def start_trading(self):
        """Start trading with terminal feedback"""
        if not self.bot:
            self.log_terminal("ERROR: SYSTEM NOT INITIALIZED", TerminalColors.RED_ALERT)
            return
        
        self.running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        
        self.log_terminal(">>> TRADING SYSTEM ACTIVATED <<<", TerminalColors.MATRIX_GREEN)
        self.status_label.config(text="[TRADING ACTIVE - MONITORING MARKETS...]")
        
        # Start trading loop
        threading.Thread(target=self.trading_loop, daemon=True).start()
    
    def stop_trading(self):
        """Stop trading"""
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log_terminal(">>> TRADING SYSTEM DEACTIVATED <<<", TerminalColors.AMBER_BRIGHT)
        self.status_label.config(text="[TRADING STOPPED - SYSTEM IDLE]")
    
    def emergency_stop(self):
        """Emergency stop all operations"""
        self.running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        
        self.log_terminal("!!! EMERGENCY STOP ACTIVATED !!!", TerminalColors.RED_ALERT)
        self.status_label.config(text="[EMERGENCY STOP - ALL SYSTEMS HALTED]")
    
    def scan_market(self):
        """Manual market scan"""
        if not self.bot:
            self.log_terminal("ERROR: SYSTEM NOT INITIALIZED", TerminalColors.RED_ALERT)
            return
        
        self.log_terminal(">>> INITIATING MARKET SCAN <<<", TerminalColors.CYAN_BRIGHT)
        threading.Thread(target=self.market_scan_loop, daemon=True).start()
    
    def shuffle_funds(self):
        """Shuffle funds between accounts"""
        if not self.bot:
            self.log_terminal("ERROR: SYSTEM NOT INITIALIZED", TerminalColors.RED_ALERT)
            return
        
        self.log_terminal(">>> INITIATING FUND SHUFFLE <<<", TerminalColors.AMBER_BRIGHT)
        threading.Thread(target=self.fund_shuffle_loop, daemon=True).start()
    
    def trading_loop(self):
        """Main trading loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.trading_cycle())
    
    async def trading_cycle(self):
        """Trading cycle"""
        while self.running:
            try:
                if self.bot:
                    await self.bot.run_trading_cycle()
                    self.root.after(0, self.update_positions_display)
                await asyncio.sleep(30)
            except Exception as e:
                self.log_terminal(f"TRADING ERROR: {e}", TerminalColors.RED_ALERT)
                await asyncio.sleep(10)
    
    def market_scan_loop(self):
        """Market scan loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.scan_cycle())
    
    async def scan_cycle(self):
        """Scan cycle"""
        try:
            if self.bot:
                opportunities = await self.bot.get_micro_cap_opportunities()
                self.root.after(0, lambda: self.update_scanner_display(opportunities))
        except Exception as e:
            self.log_terminal(f"SCAN ERROR: {e}", TerminalColors.RED_ALERT)
    
    def fund_shuffle_loop(self):
        """Fund shuffle loop"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.shuffle_cycle())
    
    async def shuffle_cycle(self):
        """Shuffle cycle"""
        try:
            if self.bot:
                await self.bot.optimize_fund_allocation()
                self.log_terminal("FUND SHUFFLE COMPLETED", TerminalColors.CYAN_BRIGHT)
        except Exception as e:
            self.log_terminal(f"SHUFFLE ERROR: {e}", TerminalColors.RED_ALERT)
    
    def update_positions_display(self):
        """Update positions display"""
        if not self.bot:
            return
        
        # Clear existing items
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)
        
        # Add active positions
        for i, position in enumerate(self.bot.active_positions):
            pnl_color = TerminalColors.MATRIX_GREEN if position.unrealized_pnl > 0 else TerminalColors.RED_ALERT
            
            self.positions_tree.insert('', 'end', iid=i, text=f"#{i+1}",
                                      values=(position.symbol,
                                             position.contract_type.value,
                                             position.side,
                                             f"{position.size:.6f}",
                                             f"${position.unrealized_pnl:.4f}",
                                             f"${position.margin_used:.4f}"))
        
        # Update system monitor
        self.trades_label.config(text=f"TRADES: {self.bot.total_trades:03d}")
        self.pnl_label.config(text=f"PNL: ${self.bot.total_pnl:.4f}")
        win_rate = (self.bot.successful_trades / max(1, self.bot.total_trades)) * 100
        self.winrate_label.config(text=f"WIN_RATE: {win_rate:05.1f}%")
        self.positions_count_label.config(text=f"POSITIONS: {len(self.bot.active_positions)}/10")
    
    def update_scanner_display(self, opportunities):
        """Update scanner display"""
        self.scanner_text.delete(1.0, tk.END)
        
        if opportunities:
            self.scanner_text.insert(tk.END, f"FOUND {len(opportunities)} OPPORTUNITIES:\n")
            self.scanner_text.insert(tk.END, "-" * 40 + "\n")
            
            for i, contract in enumerate(opportunities[:10]):
                self.scanner_text.insert(tk.END, f"{i+1}. {contract.symbol}\n")
                self.scanner_text.insert(tk.END, f"   TYPE: {contract.contract_type.value}\n")
                self.scanner_text.insert(tk.END, f"   PRICE: ${contract.last_price:.6f}\n")
                self.scanner_text.insert(tk.END, f"   NOMINAL: ${contract.nominal_value:.6f}\n")
                self.scanner_text.insert(tk.END, "-" * 40 + "\n")
        else:
            self.scanner_text.insert(tk.END, "NO OPPORTUNITIES DETECTED\n")
            self.scanner_text.insert(tk.END, "SCANNING FOR PUMP SIGNALS...\n")
    
    def update_terminal(self):
        """Update terminal display"""
        if self.running and self.bot:
            self.update_positions_display()
            self.update_account_display()
        
        # Schedule next update
        self.root.after(3000, self.update_terminal)
    
    def run(self):
        """Run the terminal"""
        self.root.mainloop()

def main():
    """Main function"""
    print(">>> INITIALIZING RETRO TERMINAL TRADING SYSTEM...")
    print(">>> 90s BRUTALIST AESTHETIC LOADING...")
    print(">>> MATRIX GREEN TERMINAL ACTIVE...")
    
    terminal = RetroTerminalUI()
    terminal.run()

if __name__ == "__main__":
    main()
