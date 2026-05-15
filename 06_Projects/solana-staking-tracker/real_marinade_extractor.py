#!/usr/bin/env python3
"""
REAL MARINADE WALLET EXTRACTOR
Pulls actual data from Marinade Finance endpoint - no simulation
"""

import requests
import sqlite3
import json
from datetime import datetime
import pandas as pd

def pull_real_marinade_data():
    print("🔗 PULLING REAL DATA FROM MARINADE FINANCE")
    print("=" * 80)
    
    # Marinade Finance API endpoint
    url = "https://snapshots-api.marinade.finance/v1/stakers/ns/all"
    
    try:
        print(f"📡 Connecting to: {url}")
        
        # Make real API call
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        print(f"✅ Connected! Retrieved data type: {type(data)}")
        
        # Handle different response formats
        if isinstance(data, list):
            wallets = data
            print(f"📊 Direct list format: {len(wallets)} wallets")
        elif isinstance(data, dict):
            wallets = data.get('data', data.get('items', []))
            print(f"📊 Dict format: {len(wallets)} wallets")
        else:
            wallets = []
            print(f"❌ Unexpected format: {type(data)}")
        
        if not wallets:
            print("❌ No wallet data found")
            return
        
        print(f"📈 Processing {len(wallets)} real wallets...")
        
        # Process real wallet data
        real_wallets = []
        
        for i, wallet in enumerate(wallets[:100]):  # Process first 100
            try:
                # Extract address (try different field names)
                address = (wallet.get('pubkey') or 
                          wallet.get('address') or 
                          wallet.get('wallet') or 
                          wallet.get('publicKey'))
                
                # Extract amount (try different field names)
                amount = (wallet.get('amount') or 
                         wallet.get('balance') or 
                         wallet.get('amountSol') or 
                         wallet.get('solAmount') or 0)
                
                if address and amount:
                    amount_float = float(amount)
                    
                    if amount_float > 0:  # Only include wallets with balance
                        real_wallets.append({
                            'address': address,
                            'amount_sol': amount_float,
                            'created_at': wallet.get('createdAt', datetime.now().isoformat()),
                            'source': 'marinade_api',
                            'timestamp': datetime.now().isoformat()
                        })
                        
                        if i < 10:  # Show first 10
                            print(f"   {i+1}. {address[:8]}...{address[-8:]} - {amount_float:.6f} SOL")
                
            except Exception as e:
                print(f"   ⚠️  Error processing wallet {i}: {e}")
        
        print(f"\n✅ Processed {len(real_wallets)} valid wallets")
        
        # Get SOL price
        try:
            price_url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            price_response = requests.get(price_url, timeout=10)
            price_data = price_response.json()
            sol_price = price_data.get('solana', {}).get('usd', 100.0)
            print(f"💰 SOL Price: ${sol_price:.2f}")
        except:
            sol_price = 100.0
            print(f"💰 SOL Price: ${sol_price:.2f} (default)")
        
        # Calculate USD values and analysis
        for wallet in real_wallets:
            wallet['usd_value'] = wallet['amount_sol'] * sol_price
        
        # Sort by USD value
        real_wallets.sort(key=lambda x: x['usd_value'], reverse=True)
        
        print(f"\n🏆 TOP 20 REAL WALLETS BY USD VALUE:")
        print("=" * 80)
        
        for i, wallet in enumerate(real_wallets[:20], 1):
            print(f"{i:2d}. {wallet['address']}")
            print(f"     SOL: {wallet['amount_sol']:.6f}")
            print(f"     USD: ${wallet['usd_value']:,.2f}")
            print(f"     Explorer: https://explorer.solana.com/address/{wallet['address']}")
            print()
        
        # Find high-value wallets ($1,000+)
        high_value = [w for w in real_wallets if w['usd_value'] >= 1000]
        
        print(f"💰 HIGH VALUE WALLETS ($1,000+): {len(high_value)} wallets")
        print("=" * 50)
        
        for i, wallet in enumerate(high_value[:10], 1):
            print(f"{i}. {wallet['address'][:8]}...{wallet['address'][-8:]} - ${wallet['usd_value']:,.2f}")
        
        # Save to database
        save_to_database(real_wallets, sol_price)
        
        # Create pandas analysis
        create_pandas_analysis(real_wallets)
        
        return real_wallets
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return []
    except Exception as e:
        print(f"❌ Error: {e}")
        return []

def save_to_database(wallets, sol_price):
    """Save real wallet data to database"""
    print(f"\n💾 Saving to database...")
    
    conn = sqlite3.connect('real_marinade_wallets.db')
    cursor = conn.cursor()
    
    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS marinade_wallets (
            address TEXT PRIMARY KEY,
            amount_sol REAL NOT NULL,
            usd_value REAL NOT NULL,
            created_at TEXT,
            source TEXT,
            timestamp TEXT,
            sol_price REAL
        )
    ''')
    
    # Insert wallets
    saved_count = 0
    for wallet in wallets:
        try:
            cursor.execute('''
                INSERT OR REPLACE INTO marinade_wallets 
                (address, amount_sol, usd_value, created_at, source, timestamp, sol_price)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                wallet['address'],
                wallet['amount_sol'],
                wallet['usd_value'],
                wallet['created_at'],
                wallet['source'],
                wallet['timestamp'],
                sol_price
            ))
            saved_count += 1
        except Exception as e:
            print(f"   ⚠️  Error saving {wallet['address'][:8]}...: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Saved {saved_count} wallets to real_marinade_wallets.db")

def create_pandas_analysis(wallets):
    """Create pandas analysis of real wallets"""
    print(f"\n📊 PANDAS ANALYSIS:")
    print("=" * 50)
    
    # Create DataFrame
    df = pd.DataFrame(wallets)
    
    print(f"📈 DataFrame shape: {df.shape}")
    print(f"📊 Columns: {list(df.columns)}")
    
    # Statistics
    print(f"\n📊 WALLET STATISTICS:")
    print(f"   Total wallets: {len(df)}")
    print(f"   Total SOL: {df['amount_sol'].sum():.2f}")
    print(f"   Total USD: ${df['usd_value'].sum():,.2f}")
    print(f"   Average SOL: {df['amount_sol'].mean():.6f}")
    print(f"   Average USD: ${df['usd_value'].mean():,.2f}")
    print(f"   Max SOL: {df['amount_sol'].max():.6f}")
    print(f"   Max USD: ${df['usd_value'].max():,.2f}")
    print(f"   Min SOL: {df['amount_sol'].min():.6f}")
    print(f"   Min USD: ${df['usd_value'].min():,.2f}")
    
    # Distribution
    print(f"\n📊 VALUE DISTRIBUTION:")
    bins = [0, 10, 100, 1000, 10000, float('inf')]
    labels = ['<10 SOL', '10-100 SOL', '100-1000 SOL', '1000-10000 SOL', '>10000 SOL']
    
    df['value_category'] = pd.cut(df['amount_sol'], bins=bins, labels=labels, right=False)
    distribution = df['value_category'].value_counts().sort_index()
    
    for category, count in distribution.items():
        print(f"   {category}: {count} wallets")
    
    # Top 10
    print(f"\n🏆 TOP 10 WALLETS:")
    top_10 = df.nlargest(10, 'usd_value')
    
    for i, (_, row) in enumerate(top_10.iterrows(), 1):
        print(f"   {i}. {row['address'][:8]}...{row['address'][-8:]} - ${row['usd_value']:,.2f}")
    
    # Save analysis
    df.to_csv('marinade_wallets_analysis.csv', index=False)
    print(f"\n💾 Analysis saved to marinade_wallets_analysis.csv")

if __name__ == "__main__":
    wallets = pull_real_marinade_data()
    
    if wallets:
        print(f"\n🎉 SUCCESS! Retrieved {len(wallets)} real wallets from Marinade Finance")
        print(f"🔗 All wallets are real Solana addresses from actual API")
        print(f"📊 Data saved to real_marinade_wallets.db")
        print(f"📈 Analysis saved to marinade_wallets_analysis.csv")
    else:
        print(f"\n❌ Failed to retrieve wallet data")
