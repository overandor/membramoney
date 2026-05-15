#!/usr/bin/env python3
"""
Gate.io Micro Coins Scanner - All-in-One
Lists all coins $0-$0.10 with auto-scanning, copy-paste, and CLI options
No API key required - uses public market data

Usage:
    python gate_micro_coins_scanner.py              # GUI mode
    python gate_micro_coins_scanner.py --cli        # CLI mode
    python gate_micro_coins_scanner.py --export     # Export to JSON
"""

import requests
import tkinter as tk
from tkinter import ttk
from threading import Thread
import json
import time
import argparse
import sys
from datetime import datetime


class GateMicroCoinsScanner:
    def __init__(self, root=None):
        self.root = root
        self.coins = []
        self.filtered_coins = []
        self.previous_filtered = set()
        
        # Auto-refresh settings
        self.auto_refresh = False
        self.scan_interval = 5  # seconds
        self.scan_thread = None
        self.stop_scan = False
        
        if self.root:
            self.build_ui()
            self.fetch_coins_async()
    
    def build_ui(self):
        if not self.root:
            return
            
        self.root.title("🪙 Gate.io Micro Coins Scanner ($0-$0.10)")
        self.root.geometry("900x750")
        self.root.configure(bg="#1a1a2e")
        
        # Header
        header = tk.Frame(self.root, bg="#16213e", height=60)
        header.pack(fill=tk.X, padx=10, pady=10)
        header.pack_propagate(False)
        
        tk.Label(header, text="🪙 Gate.io Micro Coins Scanner", 
                font=("Helvetica", 20, "bold"), 
                bg="#16213e", fg="#00d4ff").pack(pady=10)
        
        # Controls
        controls = tk.Frame(self.root, bg="#1a1a2e")
        controls.pack(fill=tk.X, padx=10, pady=5)
        
        # Price range slider
        tk.Label(controls, text="Max Price: $", 
                font=("Helvetica", 12), 
                bg="#1a1a2e", fg="#fff").pack(side=tk.LEFT, padx=5)
        
        self.price_var = tk.DoubleVar(value=0.10)
        self.price_slider = ttk.Scale(controls, from_=0.01, to=1.0, 
                                      variable=self.price_var, 
                                      orient=tk.HORIZONTAL, length=200,
                                      command=self.on_slider_change)
        self.price_slider.pack(side=tk.LEFT, padx=5)
        
        self.price_label = tk.Label(controls, text="$0.10", 
                                   font=("Helvetica", 12, "bold"),
                                   bg="#1a1a2e", fg="#00ff88")
        self.price_label.pack(side=tk.LEFT, padx=5)
        
        # Min volume filter
        tk.Label(controls, text="Min Volume (24h): $", 
                font=("Helvetica", 12), 
                bg="#1a1a2e", fg="#fff").pack(side=tk.LEFT, padx=(20, 5))
        
        self.volume_var = tk.StringVar(value="1000")
        tk.Entry(controls, textvariable=self.volume_var, width=10,
                font=("Helvetica", 11), bg="#0f3460", fg="#fff",
                insertbackground="#fff").pack(side=tk.LEFT, padx=5)
        
        # Auto-refresh controls
        tk.Label(controls, text="|  Auto-Scan:", 
                font=("Helvetica", 11, "bold"), 
                bg="#1a1a2e", fg="#00ff88").pack(side=tk.LEFT, padx=(15, 5))
        
        self.auto_refresh_var = tk.BooleanVar(value=False)
        self.auto_refresh_check = tk.Checkbutton(controls, variable=self.auto_refresh_var,
                                               command=self.toggle_auto_refresh,
                                               font=("Helvetica", 11),
                                               bg="#1a1a2e", fg="#fff",
                                               selectcolor="#0f3460",
                                               activebackground="#1a1a2e")
        self.auto_refresh_check.pack(side=tk.LEFT, padx=5)
        
        tk.Label(controls, text="Interval (s):", 
                font=("Helvetica", 11), 
                bg="#1a1a2e", fg="#fff").pack(side=tk.LEFT, padx=5)
        
        self.interval_var = tk.IntVar(value=5)
        tk.Spinbox(controls, from_=2, to=60, width=5,
                 textvariable=self.interval_var,
                 font=("Helvetica", 11),
                 bg="#0f3460", fg="#fff",
                 buttonbackground="#00d4ff").pack(side=tk.LEFT, padx=5)
        
        # Refresh button
        self.refresh_btn = tk.Button(controls, text="🔄 Refresh", 
                                    command=self.fetch_coins_async,
                                    font=("Helvetica", 11, "bold"),
                                    bg="#e94560", fg="#fff",
                                    activebackground="#ff6b6b",
                                    relief=tk.FLAT, padx=15, pady=5)
        self.refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        # Search
        search_frame = tk.Frame(self.root, bg="#1a1a2e")
        search_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(search_frame, text="🔍 Search: ", 
                font=("Helvetica", 12), 
                bg="#1a1a2e", fg="#fff").pack(side=tk.LEFT)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', lambda *args: self.filter_coins())
        tk.Entry(search_frame, textvariable=self.search_var, width=30,
                font=("Helvetica", 11), bg="#0f3460", fg="#fff",
                insertbackground="#fff").pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Stats
        self.stats_label = tk.Label(self.root, text="⏳ Loading...", 
                                   font=("Helvetica", 11),
                                   bg="#1a1a2e", fg="#aaa")
        self.stats_label.pack(pady=5)
        
        # Results area
        results_frame = tk.Frame(self.root, bg="#1a1a2e")
        results_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Treeview for coins
        columns = ("symbol", "price", "change_24h", "volume", "copy")
        self.tree = ttk.Treeview(results_frame, columns=columns, 
                                show="headings", height=20)
        
        self.tree.heading("symbol", text="💎 Symbol")
        self.tree.heading("price", text="💰 Price")
        self.tree.heading("change_24h", text="📊 24h Change")
        self.tree.heading("volume", text="📈 Volume (24h)")
        self.tree.heading("copy", text="📋 Copy")
        
        self.tree.column("symbol", width=120, anchor=tk.CENTER)
        self.tree.column("price", width=100, anchor=tk.CENTER)
        self.tree.column("change_24h", width=100, anchor=tk.CENTER)
        self.tree.column("volume", width=150, anchor=tk.CENTER)
        self.tree.column("copy", width=80, anchor=tk.CENTER)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, 
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Click handler
        self.tree.bind("<Double-1>", self.on_double_click)
        
        # Copy all buttons
        btn_frame = tk.Frame(self.root, bg="#1a1a2e")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Button(btn_frame, text="📋 Copy All Symbols", 
                 command=self.copy_all_symbols,
                 font=("Helvetica", 11, "bold"),
                 bg="#00d4ff", fg="#1a1a2e",
                 activebackground="#00ffff",
                 relief=tk.FLAT, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📋 Copy JSON", 
                 command=self.copy_json,
                 font=("Helvetica", 11, "bold"),
                 bg="#e94560", fg="#fff",
                 activebackground="#ff6b6b",
                 relief=tk.FLAT, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="📋 Copy Python List", 
                 command=self.copy_python_list,
                 font=("Helvetica", 11, "bold"),
                 bg="#0f3460", fg="#fff",
                 activebackground="#1a4a7a",
                 relief=tk.FLAT, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        tk.Button(btn_frame, text="💾 Export to File", 
                 command=self.export_to_file,
                 font=("Helvetica", 11, "bold"),
                 bg="#00ff88", fg="#1a1a2e",
                 activebackground="#00ffaa",
                 relief=tk.FLAT, padx=15, pady=8).pack(side=tk.LEFT, padx=5)
        
        # Status bar
        self.status = tk.Label(self.root, text="Ready", 
                              font=("Helvetica", 10),
                              bg="#0f3460", fg="#fff", anchor=tk.W)
        self.status.pack(fill=tk.X, side=tk.BOTTOM)
    
    def fetch_coins_async(self):
        if self.root:
            self.refresh_btn.config(state=tk.DISABLED, text="⏳ Loading...")
            self.status.config(text="Fetching market data from Gate.io...")
            Thread(target=self.fetch_coins, daemon=True).start()
        else:
            self.fetch_coins()
    
    def fetch_coins(self):
        try:
            # Gate.io public API - no auth needed
            response = requests.get(
                "https://api.gateio.ws/api/v4/spot/tickers",
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
            self.coins = []
            for ticker in data:
                try:
                    symbol = ticker.get("currency_pair", "")
                    if not symbol.endswith("_USDT"):
                        continue
                    
                    price = float(ticker.get("last", 0))
                    volume = float(ticker.get("quote_volume", 0))
                    change = float(ticker.get("change_percentage", 0))
                    
                    # Get base currency
                    base = symbol.replace("_USDT", "")
                    
                    self.coins.append({
                        "symbol": base,
                        "full_symbol": symbol,
                        "price": price,
                        "volume": volume,
                        "change_24h": change
                    })
                except (ValueError, TypeError):
                    continue
            
            if self.root:
                self.root.after(0, self.on_coins_loaded)
            
        except Exception as e:
            if self.root:
                self.root.after(0, lambda: self.show_error(str(e)))
            else:
                print(f"Error: {e}")
    
    def on_coins_loaded(self):
        self.refresh_btn.config(state=tk.NORMAL, text="🔄 Refresh")
        self.filter_coins()
        self.status.config(text=f"✅ Loaded {len(self.coins)} coins from Gate.io")
    
    def show_error(self, msg):
        self.refresh_btn.config(state=tk.NORMAL, text="🔄 Refresh")
        self.status.config(text=f"❌ Error: {msg}")
    
    def toggle_auto_refresh(self):
        """Toggle auto-refresh scanning on/off"""
        self.auto_refresh = self.auto_refresh_var.get()
        if self.auto_refresh:
            self.stop_scan = False
            self.scan_interval = self.interval_var.get()
            self.status.config(text=f"🔄 Auto-scan started (every {self.scan_interval}s)")
            Thread(target=self.auto_scan_loop, daemon=True).start()
        else:
            self.stop_scan = True
            self.status.config(text="⏸️ Auto-scan stopped")
    
    def auto_scan_loop(self):
        """Background loop for auto-refreshing coin data"""
        while not self.stop_scan:
            time.sleep(self.scan_interval)
            if not self.stop_scan:
                self.root.after(0, self.fetch_coins_async)
    
    def filter_coins(self, max_price=0.10, min_volume=1000, search=""):
        if self.root:
            max_price = self.price_var.get()
            min_volume = float(self.volume_var.get() or 0)
            search = self.search_var.get().lower()
        
        self.filtered_coins = []
        for coin in self.coins:
            if coin["price"] > max_price:
                continue
            if coin["volume"] < min_volume:
                continue
            if search and search not in coin["symbol"].lower():
                continue
            self.filtered_coins.append(coin)
        
        # Sort by volume
        self.filtered_coins.sort(key=lambda x: x["volume"], reverse=True)
        
        # Detect changes for auto-scan
        current_symbols = {c["symbol"] for c in self.filtered_coins}
        if self.auto_refresh and current_symbols != self.previous_filtered:
            added = current_symbols - self.previous_filtered
            removed = self.previous_filtered - current_symbols
            if added:
                self.status.config(text=f"🆕 New coins entered range: {', '.join(list(added)[:3])}")
            elif removed:
                self.status.config(text=f"⬇️ Coins left range: {', '.join(list(removed)[:3])}")
        
        self.previous_filtered = current_symbols
        
        if self.root:
            self.update_display()
            scan_indicator = " 🔄 Scanning..." if self.auto_refresh else ""
            self.stats_label.config(
                text=f"📊 Showing {len(self.filtered_coins)} coins | "
                     f"Price: $0 - ${max_price:.2f} | "
                     f"Min Volume: ${min_volume:,.0f}{scan_indicator}"
            )
    
    def update_display(self):
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        # Add coins
        for coin in self.filtered_coins:
            change_color = "🟢" if coin["change_24h"] >= 0 else "🔴"
            self.tree.insert("", tk.END, values=(
                coin["symbol"],
                f"${coin['price']:.6f}",
                f"{change_color} {coin['change_24h']:+.2f}%",
                f"${coin['volume']:,.0f}",
                "📋 Click"
            ))
    
    def on_slider_change(self, value):
        self.price_label.config(text=f"${float(value):.2f}")
        self.filter_coins()
    
    def on_double_click(self, event):
        item = self.tree.selection()[0]
        values = self.tree.item(item, "values")
        if values:
            symbol = values[0]
            self.copy_to_clipboard(symbol)
            self.status.config(text=f"✅ Copied: {symbol}")
    
    def copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
    
    def copy_all_symbols(self):
        if not self.filtered_coins:
            return
        symbols = ", ".join([c["symbol"] for c in self.filtered_coins])
        self.copy_to_clipboard(symbols)
        self.status.config(text=f"✅ Copied {len(self.filtered_coins)} symbols to clipboard")
    
    def copy_json(self):
        if not self.filtered_coins:
            return
        json_str = json.dumps(self.filtered_coins, indent=2)
        self.copy_to_clipboard(json_str)
        self.status.config(text="✅ Copied JSON to clipboard")
    
    def copy_python_list(self):
        if not self.filtered_coins:
            return
        symbols = [c["symbol"] for c in self.filtered_coins]
        py_list = f"SYMBOLS = {symbols}"
        self.copy_to_clipboard(py_list)
        self.status.config(text="✅ Copied Python list to clipboard")
    
    def export_to_file(self):
        if not self.filtered_coins:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"/Users/alep/Downloads/micro_coins_{timestamp}.json"
        
        export_data = {
            "timestamp": timestamp,
            "max_price": self.price_var.get(),
            "min_volume": float(self.volume_var.get() or 0),
            "count": len(self.filtered_coins),
            "coins": self.filtered_coins
        }
        
        with open(filename, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        self.status.config(text=f"✅ Exported to {filename}")
    
    def cli_output(self, max_price=0.10, min_volume=1000, limit=50, export=False):
        """Output in CLI mode"""
        self.fetch_coins()
        self.filter_coins(max_price, min_volume)
        
        print("=" * 70)
        print("🪙 GATE.IO MICRO COINS SCANNER")
        print("=" * 70)
        print(f"Price Range: $0 - ${max_price}")
        print(f"Min Volume: ${min_volume:,.0f}")
        print(f"Found: {len(self.filtered_coins)} coins")
        print("=" * 70)
        print()
        
        for coin in self.filtered_coins[:limit]:
            change_symbol = "🟢" if coin["change_24h"] >= 0 else "🔴"
            print(f"  {coin['symbol']:12} ${coin['price']:8.6f}  {change_symbol} {coin['change_24h']:+6.2f}%  Vol: ${coin['volume']:12,.0f}")
        
        print()
        print("=" * 70)
        print("COPY-PASTE LIST (comma-separated):")
        print("=" * 70)
        symbols_list = [c["symbol"] for c in self.filtered_coins]
        print(", ".join(symbols_list[:limit]))
        
        if export:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"/Users/alep/Downloads/micro_coins_{timestamp}.json"
            export_data = {
                "timestamp": timestamp,
                "max_price": max_price,
                "min_volume": min_volume,
                "count": len(self.filtered_coins),
                "coins": self.filtered_coins
            }
            with open(filename, 'w') as f:
                json.dump(export_data, f, indent=2)
            print()
            print(f"✅ Exported to {filename}")


def main():
    parser = argparse.ArgumentParser(description="Gate.io Micro Coins Scanner")
    parser.add_argument("--cli", action="store_true", help="Run in CLI mode")
    parser.add_argument("--export", action="store_true", help="Export to JSON file")
    parser.add_argument("--max-price", type=float, default=0.10, help="Maximum price (default: 0.10)")
    parser.add_argument("--min-volume", type=float, default=1000, help="Minimum volume (default: 1000)")
    parser.add_argument("--limit", type=int, default=50, help="Number of coins to display (default: 50)")
    
    args = parser.parse_args()
    
    if args.cli:
        # CLI mode
        scanner = GateMicroCoinsScanner(root=None)
        scanner.cli_output(
            max_price=args.max_price,
            min_volume=args.min_volume,
            limit=args.limit,
            export=args.export
        )
    else:
        # GUI mode
        root = tk.Tk()
        
        # Style
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", 
                       background="#16213e", 
                       foreground="#fff",
                       fieldbackground="#16213e",
                       rowheight=25)
        style.configure("Treeview.Heading", 
                       background="#0f3460", 
                       foreground="#fff",
                       font=("Helvetica", 11, "bold"))
        style.map("Treeview", 
                  background=[('selected', '#e94560')],
                  foreground=[('selected', '#fff')])
        
        app = GateMicroCoinsScanner(root)
        root.mainloop()


if __name__ == "__main__":
    main()
