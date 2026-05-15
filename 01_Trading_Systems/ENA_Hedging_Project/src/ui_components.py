#!/usr/bin/env python3
"""
UI COMPONENTS FOR ENA HEDGING SYSTEM
Modern, responsive UI components
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from datetime import datetime
from collections import deque
import threading

class ModernFrame(tk.Frame):
    """Modern frame with dark theme"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', '#1a1a1a')
        super().__init__(parent, **kwargs)

class ModernLabel(tk.Label):
    """Modern label with dark theme"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', '#1a1a1a')
        kwargs.setdefault('fg', '#00ff88')
        kwargs.setdefault('font', ('Courier', 10))
        super().__init__(parent, **kwargs)

class ModernButton(tk.Button):
    """Modern button with hover effects"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', '#2a2a2a')
        kwargs.setdefault('fg', '#ffffff')
        kwargs.setdefault('font', ('Arial', 10, 'bold'))
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('bd', 0)
        kwargs.setdefault('padx', 20)
        kwargs.setdefault('pady', 10)
        
        super().__init__(parent, **kwargs)
        
        # Bind hover effects
        self.bind('<Enter>', self.on_enter)
        self.bind('<Leave>', self.on_leave)
        
        self.original_bg = self['bg']
        self.hover_bg = '#3a3a3a'
    
    def on_enter(self, event):
        self.configure(bg=self.hover_bg)
    
    def on_leave(self, event):
        self.configure(bg=self.original_bg)

class SuccessButton(ModernButton):
    """Green success button"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', '#00ff00')
        kwargs.setdefault('fg', '#000000')
        kwargs.setdefault('hover_bg', '#00cc00')
        super().__init__(parent, **kwargs)

class DangerButton(ModernButton):
    """Red danger button"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', '#ff4444')
        kwargs.setdefault('fg', '#ffffff')
        kwargs.setdefault('hover_bg', '#cc0000')
        super().__init__(parent, **kwargs)

class WarningButton(ModernButton):
    """Orange warning button"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', '#ff8800')
        kwargs.setdefault('fg', '#ffffff')
        kwargs.setdefault('hover_bg', '#cc6600')
        super().__init__(parent, **kwargs)

class InfoButton(ModernButton):
    """Blue info button"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', '#0088ff')
        kwargs.setdefault('fg', '#ffffff')
        kwargs.setdefault('hover_bg', '#0066cc')
        super().__init__(parent, **kwargs)

class ModernLogText(scrolledtext.ScrolledText):
    """Modern log text with dark theme"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('bg', '#0a0a0a')
        kwargs.setdefault('fg', '#00ff88')
        kwargs.setdefault('font', ('Courier', 9))
        kwargs.setdefault('insertbackground', '#00ff88')
        kwargs.setdefault('selectbackground', '#004400')
        kwargs.setdefault('selectforeground', '#00ff88')
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('bd', 0)
        
        super().__init__(parent, **kwargs)
        
        # Configure tags for different message types
        self.tag_configure('INFO', foreground='#00ff88')
        self.tag_configure('SUCCESS', foreground='#00ff00')
        self.tag_configure('WARNING', foreground='#ffaa00')
        self.tag_configure('ERROR', foreground='#ff4444')
        self.tag_configure('AI', foreground='#ff00ff')
        self.tag_configure('HEDGE', foreground='#00ffff')
        self.tag_configure('PROFIT', foreground='#00ff00')
        self.tag_configure('LOSS', foreground='#ff4444')
    
    def add_message(self, message, msg_type='INFO'):
        """Add a message with appropriate coloring"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        formatted_message = f"[{timestamp}] {message}\n"
        
        self.insert(tk.END, formatted_message, msg_type)
        self.see(tk.END)
        
        # Limit log size
        lines = self.get(1.0, tk.END).split('\n')
        if len(lines) > 1000:
            self.delete(1.0, f"{len(lines)-1000}.0")

class StatusBar(ModernFrame):
    """Modern status bar"""
    
    def __init__(self, parent, **kwargs):
        kwargs.setdefault('height', 30)
        super().__init__(parent, **kwargs)
        self.pack_propagate(False)
        
        # Status label
        self.status_label = ModernLabel(self, text="🟢 READY")
        self.status_label.pack(side='left', padx=10, pady=5)
        
        # Time label
        self.time_label = ModernLabel(self, text="")
        self.time_label.pack(side='right', padx=10, pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(self, mode='indeterminate', length=200)
        self.progress.pack(side='left', padx=20, pady=5)
        
        self.update_time()
    
    def update_time(self):
        """Update time display"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.time_label.configure(text=current_time)
        self.after(1000, self.update_time)
    
    def set_status(self, status, color='#00ff88'):
        """Set status with color"""
        self.status_label.configure(text=status, fg=color)
    
    def start_progress(self):
        """Start progress animation"""
        self.progress.start(10)
    
    def stop_progress(self):
        """Stop progress animation"""
        self.progress.stop()

class StatsPanel(ModernFrame):
    """Statistics display panel"""
    
    def __init__(self, parent, stats, **kwargs):
        super().__init__(parent, **kwargs)
        self.stats = stats
        
        # Create stat labels
        self.create_stat_labels()
    
    def create_stat_labels(self):
        """Create statistics labels"""
        # Balance frame
        balance_frame = ModernFrame(self)
        balance_frame.pack(fill='x', padx=10, pady=5)
        
        self.balance_label = ModernLabel(balance_frame, text="Balance: $0.00")
        self.balance_label.pack(side='left', padx=10)
        
        self.pnl_label = ModernLabel(balance_frame, text="PnL: $0.00")
        self.pnl_label.pack(side='left', padx=10)
        
        # Trading frame
        trading_frame = ModernFrame(self)
        trading_frame.pack(fill='x', padx=10, pady=5)
        
        self.orders_label = ModernLabel(trading_frame, text="Orders: 0")
        self.orders_label.pack(side='left', padx=10)
        
        self.tps_label = ModernLabel(trading_frame, text="TPS: 0.00")
        self.tps_label.pack(side='left', padx=10)
        
        # Hedging frame
        hedge_frame = ModernFrame(self)
        hedge_frame.pack(fill='x', padx=10, pady=5)
        
        self.hedge_orders_label = ModernLabel(hedge_frame, text="Hedge Orders: 0")
        self.hedge_orders_label.pack(side='left', padx=10)
        
        self.hedge_pnl_label = ModernLabel(hedge_frame, text="Hedge PnL: $0.00")
        self.hedge_pnl_label.pack(side='left', padx=10)
    
    def update_stats(self):
        """Update statistics display"""
        # Update basic stats
        self.balance_label.configure(text=f"Balance: ${self.stats.total_balance:.2f}")
        self.pnl_label.configure(text=f"PnL: ${self.stats.total_pnl:.4f}")
        self.orders_label.configure(text=f"Orders: {self.stats.orders_placed}")
        self.tps_label.configure(text=f"TPS: {self.stats.current_tps:.2f}")
        
        # Update hedging stats
        self.hedge_orders_label.configure(text=f"Hedge Orders: {self.stats.hedge_orders_filled}")
        
        # Color code PnL
        pnl_color = '#00ff00' if self.stats.hedge_total_pnl >= 0 else '#ff4444'
        self.hedge_pnl_label.configure(
            text=f"Hedge PnL: ${self.stats.hedge_total_pnl:.4f}",
            fg=pnl_color
        )

class ControlPanel(ModernFrame):
    """Control panel with buttons and settings"""
    
    def __init__(self, parent, config, **kwargs):
        super().__init__(parent, **kwargs)
        self.config = config
        self.on_start_callback = None
        self.on_stop_callback = None
        
        self.create_controls()
    
    def create_controls(self):
        """Create control elements"""
        # Title
        title = ModernLabel(self, text="🎮 CONTROL PANEL", 
                           font=('Arial', 14, 'bold'), fg='#ff0040')
        title.pack(pady=10)
        
        # Symbol selection
        symbol_frame = ModernFrame(self)
        symbol_frame.pack(fill='x', padx=10, pady=5)
        
        ModernLabel(symbol_frame, text="Symbol:").pack(side='left', padx=5)
        
        self.symbol_var = tk.StringVar(value=self.config.symbol)
        symbols = [self.config.symbol] + self.config.sub_10_cent_coins
        symbol_combo = ttk.Combobox(symbol_frame, textvariable=self.symbol_var, 
                                   values=symbols, width=15, state='readonly')
        symbol_combo.pack(side='left')
        
        # Control buttons
        button_frame = ModernFrame(self)
        button_frame.pack(fill='x', padx=10, pady=20)
        
        self.start_button = SuccessButton(button_frame, text="🚀 START HEDGING",
                                         command=self.start_trading, width=18)
        self.start_button.pack(pady=5)
        
        self.stop_button = DangerButton(button_frame, text="⏹️ STOP HEDGING",
                                       command=self.stop_trading, width=18, state='disabled')
        self.stop_button.pack(pady=5)
        
        # Quick actions
        quick_frame = ModernFrame(self)
        quick_frame.pack(fill='x', padx=10, pady=10)
        
        ModernLabel(quick_frame, text="⚡ QUICK ACTIONS", 
                   font=('Arial', 12, 'bold'), fg='#ff8800').pack(pady=5)
        
        InfoButton(quick_frame, text="📊 REFRESH DATA", 
                  command=self.refresh_data, width=15).pack(side='left', padx=5)
        
        WarningButton(quick_frame, text="🛑 EMERGENCY STOP", 
                     command=self.emergency_stop, width=15).pack(side='left', padx=5)
        
        # Info display
        self.create_info_display()
    
    def create_info_display(self):
        """Create information display"""
        info_frame = ModernFrame(self)
        info_frame.pack(fill='x', padx=10, pady=20)
        
        ModernLabel(info_frame, text="📊 SYSTEM INFO", 
                   font=('Arial', 12, 'bold'), fg='#0088ff').pack()
        
        info_text = f"""
Min Profit: {self.config.min_profit_bps} bps
Max Position: {self.config.max_hedge_position}
Order Size: ${self.config.hedge_order_size_usd}
AI Confidence: {self.config.ai_confidence_threshold}
        """.strip()
        
        info_label = ModernLabel(info_frame, text=info_text, justify='left')
        info_label.pack(padx=10, pady=10)
    
    def start_trading(self):
        """Start trading"""
        self.start_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        
        # Update symbol in config
        self.config.symbol = self.symbol_var.get()
        self.config.update_symbol_config(self.config.symbol)
        
        if self.on_start_callback:
            self.on_start_callback()
    
    def stop_trading(self):
        """Stop trading"""
        self.start_button.configure(state='normal')
        self.stop_button.configure(state='disabled')
        
        if self.on_stop_callback:
            self.on_stop_callback()
    
    def refresh_data(self):
        """Refresh data"""
        if hasattr(self, 'on_refresh_callback'):
            self.on_refresh_callback()
    
    def emergency_stop(self):
        """Emergency stop"""
        result = messagebox.askyesno("Emergency Stop", 
                                     "Are you sure you want to emergency stop all trading?")
        if result:
            self.stop_trading()
            if hasattr(self, 'on_emergency_stop_callback'):
                self.on_emergency_stop_callback()

class LogPanel(ModernFrame):
    """Log display panel"""
    
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.create_log_display()
    
    def create_log_display(self):
        """Create log display"""
        # Title
        title = ModernLabel(self, text="📝 ACTIVITY LOG", 
                           font=('Arial', 14, 'bold'), fg='#ff0040')
        title.pack(pady=10)
        
        # Log text
        self.log_text = ModernLogText(self, height=25, width=80)
        self.log_text.pack(padx=10, pady=10, fill='both', expand=True)
        
        # Control buttons
        control_frame = ModernFrame(self)
        control_frame.pack(fill='x', padx=10, pady=5)
        
        DangerButton(control_frame, text="🗑️ CLEAR LOG", 
                    command=self.clear_log, width=12).pack(side='left', padx=5)
        
        InfoButton(control_frame, text="📄 EXPORT LOG", 
                  command=self.export_log, width=12).pack(side='left', padx=5)
        
        WarningButton(control_frame, text="🔍 FILTER", 
                     command=self.filter_log, width=12).pack(side='left', padx=5)
    
    def add_log(self, message, msg_type='INFO'):
        """Add log message"""
        if self.log_text:
            self.log_text.add_message(message, msg_type)
    
    def clear_log(self):
        """Clear the log"""
        if self.log_text:
            self.log_text.delete(1.0, tk.END)
    
    def export_log(self):
        """Export log to file"""
        from tkinter import filedialog
        import datetime
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"hedge_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if filename and self.log_text:
            with open(filename, 'w') as f:
                f.write(self.log_text.get(1.0, tk.END))
            messagebox.showinfo("Export Complete", f"Log exported to {filename}")
    
    def filter_log(self):
        """Filter log messages"""
        # This could open a dialog to filter by message type
        messagebox.showinfo("Filter", "Log filtering feature coming soon!")

class ModernUI:
    """Main modern UI manager"""
    
    def __init__(self, config, stats):
        self.config = config
        self.stats = stats
        self.root = None
        self.running = False
        
        # UI components
        self.stats_panel = None
        self.control_panel = None
        self.log_panel = None
        self.status_bar = None
    
    def create_ui(self):
        """Create the main UI"""
        self.root = tk.Tk()
        self.root.title(f"🛡️ {self.config.symbol} Hedging - Cascade AI")
        self.root.geometry("1400x900")
        self.root.configure(bg='#0a0a0a')
        
        # Configure styles
        self.configure_styles()
        
        # Create main container
        main_container = ModernFrame(self.root, bg='#0a0a0a')
        main_container.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Title
        title = ModernLabel(main_container, text=f"🛡️ {self.config.symbol} HEDGING SYSTEM",
                           font=('Arial', 18, 'bold'), fg='#ff0040')
        title.pack(pady=10)
        
        # Top panel - Stats
        self.stats_panel = StatsPanel(main_container, self.stats)
        self.stats_panel.pack(fill='x', pady=(0, 10))
        
        # Middle panel - Controls and log
        middle_container = ModernFrame(main_container, bg='#0a0a0a')
        middle_container.pack(fill='both', expand=True)
        
        # Left panel - Controls
        self.control_panel = ControlPanel(middle_container, self.config)
        self.control_panel.pack(side='left', fill='y', padx=(0, 10))
        
        # Right panel - Log
        self.log_panel = LogPanel(middle_container)
        self.log_panel.pack(side='right', fill='both', expand=True)
        
        # Status bar
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(fill='x', side='bottom')
        
        # Set callbacks
        self.control_panel.on_start_callback = self.on_start_trading
        self.control_panel.on_stop_callback = self.on_stop_trading
        self.control_panel.on_refresh_callback = self.on_refresh_data
        self.control_panel.on_emergency_stop_callback = self.on_emergency_stop
        
        self.running = True
    
    def configure_styles(self):
        """Configure ttk styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure combobox
        style.configure('TCombobox', 
                       fieldbackground='#2a2a2a',
                       background='#2a2a2a',
                       foreground='#ffffff',
                       borderwidth=0,
                       relief='flat')
        
        # Configure progress bar
        style.configure('TProgressbar',
                       background='#00ff88',
                       troughcolor='#2a2a2a',
                       borderwidth=0,
                       relief='flat')
    
    def update_ui(self):
        """Update UI elements"""
        if not self.running:
            return
        
        # Update stats
        if self.stats_panel:
            self.stats_panel.update_stats()
        
        # Schedule next update
        if self.root:
            self.root.after(100, self.update_ui)
    
    def add_log(self, message, msg_type='INFO'):
        """Add log message"""
        if self.log_panel:
            self.log_panel.add_log(message, msg_type)
    
    def set_status(self, status, color='#00ff88'):
        """Set status bar"""
        if self.status_bar:
            self.status_bar.set_status(status, color)
    
    def start_progress(self):
        """Start progress animation"""
        if self.status_bar:
            self.status_bar.start_progress()
    
    def stop_progress(self):
        """Stop progress animation"""
        if self.status_bar:
            self.status_bar.stop_progress()
    
    def on_start_trading(self):
        """Handle start trading"""
        self.set_status("🟢 HEDGING ACTIVE", '#00ff00')
        self.add_log("🚀 Hedging started", 'SUCCESS')
        self.add_log(f"📊 Trading {self.config.symbol}", 'INFO')
    
    def on_stop_trading(self):
        """Handle stop trading"""
        self.set_status("🔴 STOPPED", '#ff4444')
        self.add_log("⏹️ Hedging stopped", 'WARNING')
    
    def on_refresh_data(self):
        """Handle refresh data"""
        self.add_log("📊 Refreshing data...", 'INFO')
        self.start_progress()
        # Progress would be stopped when data is refreshed
    
    def on_emergency_stop(self):
        """Handle emergency stop"""
        self.set_status("🔴 EMERGENCY STOP", '#ff0000')
        self.add_log("🛑 EMERGENCY STOP ACTIVATED", 'ERROR')
    
    def run(self):
        """Run the UI"""
        self.update_ui()
        self.root.mainloop()
    
    def close(self):
        """Close the UI"""
        self.running = False
        if self.root:
            self.root.quit()
