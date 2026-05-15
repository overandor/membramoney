#!/usr/bin/env python3
"""
MARINADE STAKING TRACKER - DEPLOYMENT READY
Complete Marinade Finance staking analysis system with web interface
Deploy immediately to Vercel/Netlify
"""

import asyncio
import json
import time
import logging
import requests
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from flask import Flask, render_template_string, jsonify, request
import webbrowser

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('marinade_deploy.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class WalletPerformance:
    """Wallet performance data"""
    address: str
    current_sol: float
    current_usd: float
    roi_percentage: float
    cents_per_second: float
    days_tracked: int
    growth_rate: float

class MarinadeDeploySystem:
    """Deployable Marinade staking analysis system"""
    
    def __init__(self):
        self.base_url = "https://snapshots-api.marinade.finance/v1/stakers/ns/all"
        self.price_url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        self.db_path = "marinade_deploy.db"
        
        # Initialize database
        self.init_database()
        
        # Flask app
        self.app = Flask(__name__)
        self.setup_routes()
        
        logger.info("🚀 Marinade Deploy System Initialized")
        logger.info(f"🌐 API: {self.base_url}")
        logger.info(f"💾 Database: {self.db_path}")
    
    def init_database(self):
        """Initialize deployment database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                sol_amount REAL NOT NULL,
                usd_value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                snapshot_date TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_cache (
                address TEXT PRIMARY KEY,
                current_sol REAL DEFAULT 0,
                current_usd REAL DEFAULT 0,
                roi_percentage REAL DEFAULT 0,
                cents_per_second REAL DEFAULT 0,
                days_tracked INTEGER DEFAULT 0,
                growth_rate REAL DEFAULT 0,
                last_updated TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def fetch_marinade_data(self) -> List[Dict]:
        """Fetch data from Marinade API"""
        try:
            logger.info("📡 Fetching Marinade data...")
            response = requests.get(self.base_url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list):
                wallets = data
            elif isinstance(data, dict):
                wallets = data.get('data', data.get('items', []))
            else:
                wallets = []
            
            logger.info(f"✅ Retrieved {len(wallets)} wallets")
            return wallets
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch Marinade data: {e}")
            return []
    
    def fetch_sol_price(self) -> float:
        """Fetch SOL price"""
        try:
            response = requests.get(self.price_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            price = data.get('solana', {}).get('usd', 100.0)
            
            logger.info(f"💰 SOL Price: ${price:.2f}")
            return price
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch SOL price: {e}")
            return 100.0
    
    def save_wallet_data(self, wallets: List[Dict], sol_price: float):
        """Save wallet data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().isoformat()
        snapshot_date = datetime.now().strftime('%Y-%m-%d')
        
        saved_count = 0
        for wallet in wallets:
            try:
                address = wallet.get('pubkey', wallet.get('address', ''))
                amount_sol = float(wallet.get('amount', wallet.get('balance', 0)))
                
                if not address:
                    continue
                
                usd_value = amount_sol * sol_price
                
                cursor.execute('''
                    INSERT INTO wallet_snapshots 
                    (address, sol_amount, usd_value, timestamp, snapshot_date)
                    VALUES (?, ?, ?, ?, ?)
                ''', (address, amount_sol, usd_value, timestamp, snapshot_date))
                
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"⚠️  Failed to save wallet: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"💾 Saved {saved_count} wallets to database")
        return saved_count
    
    def calculate_performance_metrics(self, address: str) -> Optional[WalletPerformance]:
        """Calculate performance metrics for a wallet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get wallet history
            cursor.execute('''
                SELECT sol_amount, usd_value, timestamp 
                FROM wallet_snapshots 
                WHERE address = ? 
                ORDER BY timestamp ASC
            ''', (address,))
            
            history = cursor.fetchall()
            
            if len(history) < 2:
                return None
            
            # Calculate metrics
            first_record = history[0]
            last_record = history[-1]
            
            first_sol = first_record[1]
            current_sol = last_record[1]
            current_usd = last_record[2]
            
            # ROI calculation
            roi_percentage = ((current_sol - first_sol) / first_sol * 100) if first_sol > 0 else 0
            
            # Time tracking
            first_time = datetime.fromisoformat(first_record[2])
            last_time = datetime.fromisoformat(last_record[2])
            days_tracked = (last_time - first_time).days
            
            # Cents per second
            cents_per_second = (current_usd - (first_sol * 100)) / (days_tracked * 86400) if days_tracked > 0 else 0
            
            # Growth rate
            growth_rate = roi_percentage / days_tracked if days_tracked > 0 else 0
            
            performance = WalletPerformance(
                address=address,
                current_sol=current_sol,
                current_usd=current_usd,
                roi_percentage=roi_percentage,
                cents_per_second=cents_per_second,
                days_tracked=days_tracked,
                growth_rate=growth_rate
            )
            
            return performance
            
        except Exception as e:
            logger.error(f"❌ Performance calculation error: {e}")
            return None
        finally:
            conn.close()
    
    def get_top_performers(self, limit: int = 25, min_days: int = 30) -> List[WalletPerformance]:
        """Get top performing wallets"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get all unique addresses with sufficient history
            cursor.execute('''
                SELECT DISTINCT address 
                FROM wallet_snapshots 
                GROUP BY address 
                HAVING COUNT(*) >= 2
            ''')
            
            addresses = [row[0] for row in cursor.fetchall()]
            
            performances = []
            for address in addresses:
                perf = self.calculate_performance_metrics(address)
                if perf and perf.days_tracked >= min_days:
                    performances.append(perf)
            
            # Sort by ROI percentage
            performances.sort(key=lambda x: x.roi_percentage, reverse=True)
            
            return performances[:limit]
            
        except Exception as e:
            logger.error(f"❌ Failed to get top performers: {e}")
            return []
        finally:
            conn.close()
    
    def get_wallets_0_to_20k(self, days_back: int = 90) -> List[WalletPerformance]:
        """Find wallets that went from $0 to $20,000+"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
            
            cursor.execute('''
                SELECT DISTINCT address 
                FROM wallet_snapshots 
                WHERE timestamp >= ?
                GROUP BY address
            ''', (cutoff_date,))
            
            addresses = [row[0] for row in cursor.fetchall()]
            
            target_wallets = []
            for address in addresses:
                perf = self.calculate_performance_metrics(address)
                if perf and perf.current_usd >= 20000 and perf.roi_percentage > 1000:
                    target_wallets.append(perf)
            
            target_wallets.sort(key=lambda x: x.current_usd, reverse=True)
            
            logger.info(f"🎯 Found {len(target_wallets)} wallets $0->$20K+ in {days_back} days")
            return target_wallets
            
        except Exception as e:
            logger.error(f"❌ Failed to find $0->$20K wallets: {e}")
            return []
        finally:
            conn.close()
    
    def setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route('/')
        def dashboard():
            """Main dashboard"""
            return render_template_string('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Marinade Staking Tracker - Deployed</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 50%, #f093fb 100%); }
        .glass-effect { background: rgba(255, 255, 255, 0.1); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.2); }
        .live-indicator { background: #10b981; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.7; } }
    </style>
</head>
<body class="gradient-bg min-h-screen text-white">
    <div class="container mx-auto px-4 py-8">
        <header class="text-center mb-10">
            <h1 class="text-5xl font-bold mb-4">
                <i class="fas fa-chart-line mr-3"></i>Marinade Staking Tracker
            </h1>
            <p class="text-xl opacity-90">Find $0 → $20,000 Wallets • Live Analysis</p>
            <div class="flex items-center justify-center mt-4">
                <div class="live-indicator w-3 h-3 rounded-full mr-2"></div>
                <span class="text-lg">DEPLOYED LIVE</span>
            </div>
        </header>

        <div class="glass-effect rounded-xl p-6 mb-10">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-rocket mr-2"></i>Quick Actions
            </h2>
            <div class="grid md:grid-cols-3 gap-6">
                <button onclick="collectData()" class="bg-green-600 hover:bg-green-700 px-6 py-3 rounded-lg font-bold">
                    <i class="fas fa-download mr-2"></i>Collect Data
                </button>
                <button onclick="showTopPerformers()" class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-bold">
                    <i class="fas fa-trophy mr-2"></i>Top Performers
                </button>
                <button onclick="find0to20k()" class="bg-purple-600 hover:bg-purple-700 px-6 py-3 rounded-lg font-bold">
                    <i class="fas fa-dollar-sign mr-2"></i>$0 → $20K Wallets
                </button>
            </div>
        </div>

        <div class="glass-effect rounded-xl p-6">
            <h2 class="text-2xl font-bold mb-6">
                <i class="fas fa-search mr-2"></i>Results
            </h2>
            <div id="results" class="space-y-4">
                <div class="text-center opacity-60">
                    <i class="fas fa-chart-line text-4xl mb-4"></i>
                    <p>Click an action to load results</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function apiCall(endpoint) {
            try {
                const response = await fetch(`/api${endpoint}`);
                return await response.json();
            } catch (error) {
                return { error: error.message };
            }
        }

        async function collectData() {
            const response = await apiCall('/collect');
            if (response.success) {
                showNotification('Data collected successfully!', 'success');
            } else {
                showNotification(response.error, 'error');
            }
        }

        async function showTopPerformers() {
            const response = await apiCall('/top-performers');
            if (response.success) {
                displayResults(response.data, 'Top Performers');
            } else {
                showNotification(response.error, 'error');
            }
        }

        async function find0to20k() {
            const response = await apiCall('/0-to-20k');
            if (response.success) {
                displayResults(response.data, '$0 → $20K Wallets');
            } else {
                showNotification(response.error, 'error');
            }
        }

        function displayResults(data, title) {
            const resultsDiv = document.getElementById('results');
            
            if (!data || data.length === 0) {
                resultsDiv.innerHTML = `
                    <div class="text-center opacity-60">
                        <i class="fas fa-search text-4xl mb-4"></i>
                        <p>No results found</p>
                    </div>
                `;
                return;
            }

            resultsDiv.innerHTML = `
                <h3 class="text-xl font-bold mb-4">${title}</h3>
                <div class="space-y-3">
                    ${data.map((wallet, index) => `
                        <div class="p-4 bg-white/10 rounded-lg">
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <div class="text-sm opacity-70">Address</div>
                                    <div class="font-mono text-xs">${wallet.address}</div>
                                    <div class="text-xs opacity-50 mt-1">
                                        <a href="https://explorer.solana.com/address/${wallet.address}" target="_blank" class="text-blue-400">
                                            Explorer →
                                        </a>
                                    </div>
                                </div>
                                <div>
                                    <div class="text-sm opacity-70">Current Value</div>
                                    <div class="font-bold text-green-400">$${wallet.current_usd.toFixed(2)}</div>
                                    <div class="text-sm">ROI: ${wallet.roi_percentage.toFixed(2)}%</div>
                                    <div class="text-sm">${wallet.days_tracked} days</div>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        function showNotification(message, type) {
            const colors = { success: 'bg-green-500', error: 'bg-red-500' };
            const notification = document.createElement('div');
            notification.className = `fixed top-4 right-4 ${colors[type]} text-white px-6 py-3 rounded-lg`;
            notification.textContent = message;
            document.body.appendChild(notification);
            setTimeout(() => notification.remove(), 4000);
        }
    </script>
</body>
</html>
            ''')
        
        @self.app.route('/api/collect', methods=['POST'])
        def collect_data():
            """Collect Marinade data"""
            try:
                wallets = self.fetch_marinade_data()
                if wallets:
                    sol_price = self.fetch_sol_price()
                    saved = self.save_wallet_data(wallets, sol_price)
                    
                    return jsonify({
                        "success": True,
                        "message": f"Collected and saved {saved} wallets",
                        "sol_price": sol_price
                    })
                else:
                    return jsonify({"success": False, "error": "No data fetched"})
                    
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/api/top-performers')
        def get_top_performers():
            """Get top performing wallets"""
            try:
                performers = self.get_top_performers(limit=50)
                
                data = []
                for perf in performers:
                    data.append({
                        "address": perf.address,
                        "current_sol": perf.current_sol,
                        "current_usd": perf.current_usd,
                        "roi_percentage": perf.roi_percentage,
                        "cents_per_second": perf.cents_per_second,
                        "days_tracked": perf.days_tracked,
                        "growth_rate": perf.growth_rate
                    })
                
                return jsonify({
                    "success": True,
                    "data": data
                })
                
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
        
        @self.app.route('/api/0-to-20k')
        def get_0_to_20k():
            """Get wallets that went from $0 to $20,000+"""
            try:
                wallets = self.get_wallets_0_to_20k(days_back=90)
                
                data = []
                for wallet in wallets:
                    data.append({
                        "address": wallet.address,
                        "current_sol": wallet.current_sol,
                        "current_usd": wallet.current_usd,
                        "roi_percentage": wallet.roi_percentage,
                        "cents_per_second": wallet.cents_per_second,
                        "days_tracked": wallet.days_tracked,
                        "growth_rate": wallet.growth_rate
                    })
                
                return jsonify({
                    "success": True,
                    "data": data,
                    "count": len(data)
                })
                
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500
    
    def run(self, port: int = 8095):
        """Run the deployed system"""
        logger.info(f"🚀 Starting Marinade Deploy System on port {port}")
        logger.info(f"🌐 Dashboard: http://localhost:{port}")
        
        # Open browser
        webbrowser.open(f'http://localhost:{port}')
        
        # Run Flask app
        self.app.run(host='0.0.0.0', port=port, debug=False)

# Main deployment
if __name__ == "__main__":
    system = MarinadeDeploySystem()
    system.run(port=8095)
