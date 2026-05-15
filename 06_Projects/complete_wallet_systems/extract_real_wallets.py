#!/usr/bin/env python3
import os
"""
REAL WALLET EXTRACTOR - ACTUAL SOLANA ADDRESSES
Extract and analyze real Solana wallet addresses from all databases
"""

import sqlite3
import json

def extract_real_wallets():
    print("🔍 REAL SOLANA WALLET EXTRACTION:")
    print("=" * 80)
    
    databases = [
        'solana_wallets.db',
        'marinade_deploy.db', 
        'decentralized-trader/solana_wallets.db',
        'decentralized-trader/blockchain_wallets.db',
        'decentralized-trader/production_mining.db',
        'decentralized-trader/m5_solana_mining.db'
    ]
    
    all_wallets = []
    
    for db_path in databases:
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            print(f"\n📁 Analyzing: {db_path}")
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                if 'wallet' in table.lower() or 'address' in table.lower():
                    try:
                        # Get table structure
                        cursor.execute(f"PRAGMA table_info({table})")
                        columns = [col[1] for col in cursor.fetchall()]
                        
                        # Look for address columns
                        address_columns = []
                        for col in columns:
                            if any(word in col.lower() for word in ['address', 'pubkey', 'wallet', 'public_key']):
                                address_columns.append(col)
                        
                        if address_columns:
                            # Get sample data
                            cursor.execute(f"SELECT * FROM {table} LIMIT 5")
                            rows = cursor.fetchall()
                            
                            if rows:
                                print(f"   📊 Table: {table} ({len(rows)} records)")
                                print(f"   🔍 Address columns: {address_columns}")
                                
                                for i, row in enumerate(rows, 1):
                                    row_dict = dict(zip(columns, row))
                                    
                                    # Extract wallet addresses
                                    for col in address_columns:
                                        address = row_dict.get(col, '')
                                        if address and len(address) > 20:  # Valid Solana address
                                            all_wallets.append({
                                                'database': db_path,
                                                'table': table,
                                                'column': col,
                                                'address': address,
                                                'data': row_dict
                                            })
                                            
                                            print(f"     {i}. {address[:8]}...{address[-8:]} (from {col})")
                                            
                                            # Show additional info
                                            if 'balance' in row_dict:
                                                print(f"        Balance: {row_dict['balance']}")
                                            if 'sol_amount' in row_dict:
                                                print(f"        SOL: {row_dict['sol_amount']}")
                                            if 'created_at' in row_dict:
                                                print(f"        Created: {row_dict['created_at']}")
                                            
                                            print(f"        Explorer: https://explorer.solana.com/address/{address}")
                    
                    except Exception as e:
                        print(f"   ❌ Error reading {table}: {e}")
            
            conn.close()
            
        except Exception as e:
            print(f"❌ Error with {db_path}: {e}")
    
    # Summary
    print(f"\n📊 SUMMARY:")
    print(f"   Total real wallets found: {len(all_wallets)}")
    
    if all_wallets:
        print(f"\n🎯 UNIQUE WALLET ADDRESSES:")
        print("=" * 80)
        
        unique_wallets = {}
        for wallet in all_wallets:
            address = wallet['address']
            if address not in unique_wallets:
                unique_wallets[address] = wallet
        
        for i, (address, wallet) in enumerate(unique_wallets.items(), 1):
            print(f"{i}. {address[:8]}...{address[-8:]}")
            print(f"   Source: {wallet['database']} -> {wallet['table']}")
            print(f"   Explorer: https://explorer.solana.com/address/{address}")
            
            # Show wallet data
            data = wallet['data']
            if 'balance_lamports' in data:
                balance_sol = data['balance_lamports'] / 1_000_000_000
                print(f"   Balance: {balance_sol:.6f} SOL")
            if 'total_mined' in data:
                mined_sol = data['total_mined'] / 1_000_000_000
                print(f"   Mined: {mined_sol:.6f} SOL")
            if 'created_at' in data:
                print(f"   Created: {data['created_at']}")
            
            print()
        
        # Save to file
        with open('real_wallets.json', 'w') as f:
            json.dump([{
                'address': w['address'],
                'database': w['database'],
                'table': w['table'],
                'data': w['data']
            } for w in all_wallets], f, indent=2, default=str)
        
        print(f"💾 Saved {len(all_wallets)} wallet records to real_wallets.json")
    
    else:
        print("❌ No real wallet addresses found!")
        print("🔄 Attempting to create sample wallets...")
        
        # Create sample real wallets
        create_sample_wallets()

def create_sample_wallets():
    """Create sample real Solana wallets"""
    try:
        from solders.keypair import Keypair
        
        print("\n🔧 Creating sample real wallets...")
        
        sample_wallets = []
        for i in range(5):
            keypair = Keypair()
            address = str(keypair.pubkey())
            private_key = keypair.to_base58_string()
            
            wallet_data = {
                'address': address,
                'private_key': private_key,
                'balance_lamports': 0,
                'created_at': '2024-01-01T00:00:00Z',
                'source': 'sample_generation'
            }
            
            sample_wallets.append(wallet_data)
            print(f"   {i+1}. {address[:8]}...{address[-8:]}")
            print(f"      Explorer: https://explorer.solana.com/address/{address}")
        
        # Save to database
        conn = sqlite3.connect('real_wallets_sample.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sample_wallets (
                address TEXT PRIMARY KEY,
                private_key TEXT NOT NULL,
                balance_lamports INTEGER DEFAULT 0,
                created_at TEXT,
                source TEXT
            )
        ''')
        
        for wallet in sample_wallets:
            cursor.execute('''
                INSERT INTO sample_wallets 
                (address, private_key, balance_lamports, created_at, source)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                wallet['address'],
                wallet['private_key'],
                wallet['balance_lamports'],
                wallet['created_at'],
                wallet['source']
            ))
        
        conn.commit()
        conn.close()
        
        print(f"💾 Created {len(sample_wallets)} sample wallets in real_wallets_sample.db")
        
    except ImportError:
        print("❌ solders not available - cannot create real wallets")
    except Exception as e:
        print(f"❌ Error creating sample wallets: {e}")

if __name__ == "__main__":
    extract_real_wallets()
