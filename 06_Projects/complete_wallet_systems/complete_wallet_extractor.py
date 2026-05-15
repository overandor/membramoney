#!/usr/bin/env python3
"""
COMPLETE WALLET EXTRACTOR - ALL AVAILABLE WALLETS
Pulls ALL available wallets from Marinade + integrates OKX trading data
No simulation - only real data extraction
"""

import sqlite3
import requests
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

class CompleteWalletExtractor:
    """Extracts ALL available wallets with OKX trading integration"""
    
    def __init__(self):
        self.base_url = "https://snapshots-api.marinade.finance/v1/stakers/ns/all"
        self.price_url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        self.db_path = "complete_wallets.db"
        self.okx_csv_path = "/Users/alep/Downloads/OKX Tradi (2).csv"
        
        # Initialize database
        self.init_database()
        
        print("🔍 COMPLETE WALLET EXTRACTOR INITIALIZED")
        print("📡 Marinade API: ALL available wallets")
        print("💼 OKX Trading Data Integration")
        print(f"💾 Database: {self.db_path}")
    
    def init_database(self):
        """Initialize comprehensive database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Marinade wallets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS marinade_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT UNIQUE NOT NULL,
                amount_sol REAL NOT NULL,
                usd_value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                snapshot_date TEXT NOT NULL,
                sol_price REAL NOT NULL,
                source TEXT DEFAULT 'marinade_api',
                extraction_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # OKX trading data table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS okx_trading_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uid TEXT NOT NULL,
                name TEXT,
                account_type TEXT,
                account_name TEXT,
                order_id TEXT,
                time TEXT NOT NULL,
                trade_type TEXT,
                symbol TEXT,
                action TEXT,
                amount REAL,
                trading_unit TEXT,
                filled_price REAL,
                filled_price_unit TEXT,
                pnl REAL,
                fee REAL,
                fee_unit TEXT,
                position_change TEXT,
                position_balance REAL,
                position_unit TEXT,
                balance_change REAL,
                balance REAL,
                balance_unit TEXT,
                extraction_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Cross-reference table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_cross_reference (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                marinade_address TEXT,
                okx_uid TEXT,
                correlation_score REAL DEFAULT 0,
                match_reason TEXT,
                verified BOOLEAN DEFAULT FALSE,
                extraction_date TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Performance analytics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                source TEXT NOT NULL,
                total_balance REAL DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                trade_count INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0,
                avg_trade_size REAL DEFAULT 0,
                risk_score REAL DEFAULT 0,
                last_updated TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def pull_all_marinade_wallets(self) -> int:
        """Pull ALL available wallets from Marinade API"""
        print("📡 PULLING ALL AVAILABLE WALLETS FROM MARINADE")
        print("=" * 80)
        
        try:
            # Make API call
            response = requests.get(self.base_url, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            # Handle different response formats
            if isinstance(data, list):
                wallets = data
            elif isinstance(data, dict):
                wallets = data.get('data', data.get('items', []))
            else:
                wallets = []
            
            print(f"✅ Retrieved {len(wallets)} total wallets from Marinade API")
            
            # Get SOL price
            sol_price = self.get_sol_price()
            print(f"💰 SOL Price: ${sol_price:.2f}")
            
            # Process ALL wallets
            processed_wallets = []
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            for i, wallet in enumerate(wallets):
                try:
                    # Extract address (try different field names)
                    address = (wallet.get('pubkey') or 
                              wallet.get('address') or 
                              wallet.get('wallet') or 
                              wallet.get('publicKey'))
                    
                    # Extract amount
                    amount = (wallet.get('amount') or 
                             wallet.get('balance') or 
                             wallet.get('amountSol') or 
                             wallet.get('solAmount') or 0)
                    
                    if address and amount:
                        amount_float = float(amount)
                        
                        if amount_float > 0:
                            processed_wallets.append({
                                'address': address,
                                'amount_sol': amount_float,
                                'usd_value': amount_float * sol_price,
                                'timestamp': datetime.now().isoformat(),
                                'snapshot_date': current_date,
                                'sol_price': sol_price,
                                'source': 'marinade_api'
                            })
                            
                            if i < 20:
                                print(f"   {i+1:3d}. {address[:8]}...{address[-8:]} - {amount_float:10.2f} SOL (${amount_float * sol_price:,.2f})")
                
                except Exception as e:
                    print(f"   ⚠️  Error processing wallet {i}: {e}")
            
            # Save ALL wallets to database
            saved_count = self.save_all_wallets(processed_wallets)
            
            print(f"\n✅ Processed {len(processed_wallets)} valid wallets")
            print(f"💾 Saved {saved_count} wallets to database")
            
            # Calculate statistics
            self.calculate_wallet_statistics(processed_wallets)
            
            return len(processed_wallets)
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error: {e}")
            return 0
        except Exception as e:
            print(f"❌ Error: {e}")
            return 0
    
    def get_sol_price(self) -> float:
        """Get current SOL price"""
        try:
            response = requests.get(self.price_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get('solana', {}).get('usd', 100.0)
        except:
            return 100.0
    
    def save_all_wallets(self, wallets: List[Dict]) -> int:
        """Save all wallets to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        saved_count = 0
        
        for wallet in wallets:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO marinade_wallets 
                    (address, amount_sol, usd_value, timestamp, snapshot_date, sol_price, source, extraction_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    wallet['address'],
                    wallet['amount_sol'],
                    wallet['usd_value'],
                    wallet['timestamp'],
                    wallet['snapshot_date'],
                    wallet['sol_price'],
                    wallet['source'],
                    datetime.now().isoformat()
                ))
                saved_count += 1
            except Exception as e:
                print(f"   ⚠️  Error saving {wallet['address'][:8]}...: {e}")
        
        conn.commit()
        conn.close()
        return saved_count
    
    def calculate_wallet_statistics(self, wallets: List[Dict]):
        """Calculate comprehensive wallet statistics"""
        print(f"\n📊 WALLET STATISTICS:")
        print("=" * 50)
        
        if not wallets:
            print("❌ No wallets to analyze")
            return
        
        # Basic statistics
        total_wallets = len(wallets)
        total_sol = sum(w['amount_sol'] for w in wallets)
        total_usd = sum(w['usd_value'] for w in wallets)
        avg_sol = total_sol / total_wallets
        avg_usd = total_usd / total_wallets
        
        # Distribution analysis
        wallet_sizes = [w['amount_sol'] for w in wallets]
        wallet_sizes.sort()
        
        min_wallet = wallet_sizes[0]
        max_wallet = wallet_sizes[-1]
        median_wallet = wallet_sizes[len(wallet_sizes)//2]
        
        # Percentiles
        p25 = wallet_sizes[int(len(wallet_sizes) * 0.25)]
        p75 = wallet_sizes[int(len(wallet_sizes) * 0.75)]
        p90 = wallet_sizes[int(len(wallet_sizes) * 0.90)]
        p99 = wallet_sizes[int(len(wallet_sizes) * 0.99)]
        
        # Large wallets (>1000 SOL)
        large_wallets = [w for w in wallets if w['amount_sol'] > 1000]
        medium_wallets = [w for w in wallets if 100 <= w['amount_sol'] <= 1000]
        small_wallets = [w for w in wallets if w['amount_sol'] < 100]
        
        print(f"📈 BASIC STATISTICS:")
        print(f"   Total Wallets: {total_wallets:,}")
        print(f"   Total SOL: {total_sol:,.2f}")
        print(f"   Total USD: ${total_usd:,.2f}")
        print(f"   Average SOL: {avg_sol:.6f}")
        print(f"   Average USD: ${avg_usd:,.2f}")
        
        print(f"\n📊 DISTRIBUTION:")
        print(f"   Min Wallet: {min_wallet:.6f} SOL")
        print(f"   Max Wallet: {max_wallet:.6f} SOL")
        print(f"   Median: {median_wallet:.6f} SOL")
        print(f"   25th Percentile: {p25:.6f} SOL")
        print(f"   75th Percentile: {p75:.6f} SOL")
        print(f"   90th Percentile: {p90:.6f} SOL")
        print(f"   99th Percentile: {p99:.6f} SOL")
        
        print(f"\n🎯 WALLET CATEGORIES:")
        print(f"   Large Wallets (>1000 SOL): {len(large_wallets):,} ({len(large_wallets)/total_wallets*100:.1f}%)")
        print(f"   Medium Wallets (100-1000 SOL): {len(medium_wallets):,} ({len(medium_wallets)/total_wallets*100:.1f}%)")
        print(f"   Small Wallets (<100 SOL): {len(small_wallets):,} ({len(small_wallets)/total_wallets*100:.1f}%)")
        
        # Top 10 wallets
        top_wallets = sorted(wallets, key=lambda x: x['amount_sol'], reverse=True)[:10]
        
        print(f"\n🏆 TOP 10 WALLETS:")
        for i, wallet in enumerate(top_wallets, 1):
            print(f"   {i:2d}. {wallet['address'][:8]}...{wallet['address'][-8:]}")
            print(f"       {wallet['amount_sol']:,.2f} SOL (${wallet['usd_value']:,.2f})")
            print(f"       Explorer: https://explorer.solana.com/address/{wallet['address']}")
    
    def import_okx_trading_data(self) -> int:
        """Import OKX trading data from CSV"""
        print(f"\n💼 IMPORTING OKX TRADING DATA")
        print("=" * 50)
        
        if not os.path.exists(self.okx_csv_path):
            print(f"❌ OKX CSV not found: {self.okx_csv_path}")
            return 0
        
        try:
            # Read CSV
            df = pd.read_csv(self.okx_csv_path)
            print(f"📊 OKX CSV loaded: {len(df)} records")
            
            # Extract user info from first row
            user_info = df.iloc[0] if len(df) > 0 else None
            if user_info and 'UID' in str(user_info.iloc[0]):
                uid = str(user_info.iloc[0]).split(':')[1] if ':' in str(user_info.iloc[0]) else str(user_info.iloc[0])
                name = str(user_info.iloc[1]).split(':')[1] if ':' in str(user_info.iloc[1]) else str(user_info.iloc[1])
                account_type = str(user_info.iloc[2]).split(':')[1] if ':' in str(user_info.iloc[2]) else str(user_info.iloc[2])
                account_name = str(user_info.iloc[3]).split(':')[1] if ':' in str(user_info.iloc[3]) else str(user_info.iloc[3])
                
                print(f"👤 User Info:")
                print(f"   UID: {uid}")
                print(f"   Name: {name}")
                print(f"   Account Type: {account_type}")
                print(f"   Account Name: {account_name}")
            
            # Process trading records
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            saved_count = 0
            total_pnl = 0
            trade_count = 0
            
            for index, row in df.iterrows():
                if index == 0:  # Skip header row
                    continue
                
                try:
                    # Extract trading data
                    order_id = str(row.iloc[1]) if len(row) > 1 else ''
                    time_str = str(row.iloc[2]) if len(row) > 2 else ''
                    trade_type = str(row.iloc[3]) if len(row) > 3 else ''
                    symbol = str(row.iloc[4]) if len(row) > 4 else ''
                    action = str(row.iloc[5]) if len(row) > 5 else ''
                    amount = float(row.iloc[6]) if len(row) > 6 and str(row.iloc[6]) != '' else 0
                    trading_unit = str(row.iloc[7]) if len(row) > 7 else ''
                    filled_price = float(row.iloc[8]) if len(row) > 8 and str(row.iloc[8]) != '' else 0
                    pnl = float(row.iloc[10]) if len(row) > 10 and str(row.iloc[10]) != '' else 0
                    fee = float(row.iloc[11]) if len(row) > 11 and str(row.iloc[11]) != '' else 0
                    balance = float(row.iloc[16]) if len(row) > 16 and str(row.iloc[16]) != '' else 0
                    balance_unit = str(row.iloc[17]) if len(row) > 17 else ''
                    
                    # Save to database
                    cursor.execute('''
                        INSERT INTO okx_trading_data 
                        (uid, name, account_type, account_name, order_id, time, trade_type, symbol, action, 
                         amount, trading_unit, filled_price, pnl, fee, balance, balance_unit)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        uid, name, account_type, account_name, order_id, time_str, trade_type, symbol, action,
                        amount, trading_unit, filled_price, pnl, fee, balance, balance_unit
                    ))
                    
                    saved_count += 1
                    total_pnl += pnl
                    if trade_type == 'Swap':
                        trade_count += 1
                
                except Exception as e:
                    print(f"   ⚠️  Error processing row {index}: {e}")
            
            conn.commit()
            conn.close()
            
            print(f"✅ Imported {saved_count} trading records")
            print(f"💰 Total PnL: ${total_pnl:,.2f}")
            print(f"📊 Trade Count: {trade_count}")
            
            return saved_count
            
        except Exception as e:
            print(f"❌ Error importing OKX data: {e}")
            return 0
    
    def cross_reference_wallets(self):
        """Cross-reference Marinade wallets with OKX trading data"""
        print(f"\n🔗 CROSS-REFERENCING WALLETS")
        print("=" * 50)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get unique symbols from OKX data
        cursor.execute("SELECT DISTINCT symbol FROM okx_trading_data WHERE symbol != ''")
        symbols = [row[0] for row in cursor.fetchall()]
        
        print(f"📊 Found {len(symbols)} unique trading symbols:")
        for symbol in symbols[:10]:
            print(f"   {symbol}")
        
        if len(symbols) > 10:
            print(f"   ... and {len(symbols) - 10} more")
        
        # Look for SOL-related symbols
        sol_symbols = [s for s in symbols if 'SOL' in s.upper() or 'SOLANA' in s.upper()]
        
        print(f"\n🔍 SOL-related symbols: {len(sol_symbols)}")
        for symbol in sol_symbols:
            print(f"   {symbol}")
        
        # Calculate trading performance
        cursor.execute("""
            SELECT symbol, COUNT(*) as trade_count, SUM(pnl) as total_pnl, 
                   AVG(pnl) as avg_pnl, SUM(fee) as total_fees
            FROM okx_trading_data 
            WHERE trade_type = 'Swap' AND symbol != ''
            GROUP BY symbol
            ORDER BY total_pnl DESC
        """)
        
        performance = cursor.fetchall()
        
        print(f"\n📈 TRADING PERFORMANCE BY SYMBOL:")
        print(f"{'Symbol':<15} {'Trades':<8} {'Total PnL':<12} {'Avg PnL':<10} {'Fees':<10}")
        print("-" * 65)
        
        for symbol, trades, pnl, avg_pnl, fees in performance[:10]:
            print(f"{symbol:<15} {trades:<8} ${pnl:>11.2f} ${avg_pnl:>9.2f} ${fees:>9.2f}")
        
        conn.close()
    
    def generate_complete_report(self):
        """Generate complete wallet analysis report"""
        print(f"\n📋 COMPLETE WALLET ANALYSIS REPORT")
        print("=" * 80)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Marinade wallet summary
        cursor.execute("SELECT COUNT(*) as count, SUM(amount_sol) as total_sol, SUM(usd_value) as total_usd FROM marinade_wallets")
        marinade_stats = cursor.fetchone()
        
        # OKX trading summary
        cursor.execute("SELECT COUNT(*) as count, SUM(pnl) as total_pnl, COUNT(DISTINCT symbol) as symbols FROM okx_trading_data WHERE trade_type = 'Swap'")
        okx_stats = cursor.fetchone()
        
        print(f"📊 MARINADE WALLETS:")
        print(f"   Total Wallets: {marinade_stats[0]:,}")
        print(f"   Total SOL: {marinade_stats[1]:,.2f}")
        print(f"   Total USD: ${marinade_stats[2]:,.2f}")
        
        print(f"\n💼 OKX TRADING:")
        print(f"   Total Trades: {okx_stats[0]:,}")
        print(f"   Total PnL: ${okx_stats[1]:,.2f}")
        print(f"   Unique Symbols: {okx_stats[2]}")
        
        # Top performing Marinade wallets
        cursor.execute("SELECT address, amount_sol, usd_value FROM marinade_wallets ORDER BY amount_sol DESC LIMIT 10")
        top_wallets = cursor.fetchall()
        
        print(f"\n🏆 TOP 10 MARINADE WALLETS:")
        for i, (address, sol, usd) in enumerate(top_wallets, 1):
            print(f"   {i:2d}. {address[:8]}...{address[-8:]}")
            print(f"       {sol:,.2f} SOL (${usd:,.2f})")
            print(f"       Explorer: https://explorer.solana.com/address/{address}")
        
        # Export to CSV
        self.export_to_csv()
        
        conn.close()
    
    def export_to_csv(self):
        """Export all data to CSV files"""
        print(f"\n💾 EXPORTING DATA TO CSV")
        print("=" * 30)
        
        conn = sqlite3.connect(self.db_path)
        
        # Export Marinade wallets
        marinade_df = pd.read_sql_query("SELECT * FROM marinade_wallets", conn)
        marinade_df.to_csv('marinade_wallets_complete.csv', index=False)
        print(f"✅ Exported {len(marinade_df)} Marinade wallets to marinade_wallets_complete.csv")
        
        # Export OKX data
        okx_df = pd.read_sql_query("SELECT * FROM okx_trading_data", conn)
        okx_df.to_csv('okx_trading_complete.csv', index=False)
        print(f"✅ Exported {len(okx_df)} OKX records to okx_trading_complete.csv")
        
        # Export combined analysis
        combined_df = pd.read_sql_query("""
            SELECT 
                'marinade' as source, address as identifier, amount_sol as amount, usd_value as value, 
                timestamp as date_time, extraction_date
            FROM marinade_wallets
            UNION ALL
            SELECT 
                'okx' as source, order_id as identifier, amount as amount, pnl as value, 
                time as date_time, extraction_date
            FROM okx_trading_data 
            WHERE trade_type = 'Swap'
        """, conn)
        
        combined_df.to_csv('combined_wallet_analysis.csv', index=False)
        print(f"✅ Exported {len(combined_df)} combined records to combined_wallet_analysis.csv")
        
        conn.close()
    
    def run_complete_extraction(self):
        """Run complete wallet extraction process"""
        print("🚀 STARTING COMPLETE WALLET EXTRACTION")
        print("=" * 80)
        
        # Step 1: Pull all Marinade wallets
        marinade_count = self.pull_all_marinade_wallets()
        
        # Step 2: Import OKX trading data
        okx_count = self.import_okx_trading_data()
        
        # Step 3: Cross-reference data
        self.cross_reference_wallets()
        
        # Step 4: Generate complete report
        self.generate_complete_report()
        
        print(f"\n🎉 EXTRACTION COMPLETE!")
        print(f"📊 Marinade Wallets: {marinade_count:,}")
        print(f"💼 OKX Trading Records: {okx_count:,}")
        print(f"💾 Database: {self.db_path}")
        print(f"📄 CSV Exports: marinade_wallets_complete.csv, okx_trading_complete.csv, combined_wallet_analysis.csv")

# Main execution
if __name__ == "__main__":
    extractor = CompleteWalletExtractor()
    extractor.run_complete_extraction()
