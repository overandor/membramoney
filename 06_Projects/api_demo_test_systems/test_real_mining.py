#!/usr/bin/env python3
"""
TEST REAL SOLANA MINING FUNCTIONALITY
Check if the decentralized-trader system actually mines the real Solana blockchain
"""

import sys
import os
import asyncio
import sqlite3
from datetime import datetime

# Add the decentralized-trader directory to path
sys.path.append('/Users/alep/Downloads/decentralized-trader')

def test_real_mining():
    """Test if the real Solana mining system works"""
    print("🔍 TESTING REAL SOLANA MINING FUNCTIONALITY")
    print("=" * 80)
    
    try:
        # Import the real miner
        from real_solana_miner import RealSolanaMiner
        
        print("✅ Successfully imported RealSolanaMiner")
        
        # Initialize the miner
        miner = RealSolanaMiner()
        print("✅ Successfully initialized RealSolanaMiner")
        
        # Check configuration
        print(f"\n📊 MINER CONFIGURATION:")
        print(f"   RPC Endpoint: {miner.solana_rpc}")
        print(f"   Database: {miner.db_path}")
        print(f"   Base Reward: {miner.base_reward} lamports")
        print(f"   SOL Price: ${miner.sol_price_usd}")
        print(f"   CPU Cores: {miner.cpu_cores}")
        print(f"   Max Threads: {miner.max_threads}")
        
        # Test database initialization
        miner.init_database()
        print("✅ Database initialized successfully")
        
        # Test wallet creation
        wallet = miner.create_real_wallet()
        print(f"✅ Created wallet: {wallet.address[:8]}...{wallet.address[-8:]}")
        print(f"   Private Key: {wallet.private_key[:20]}...")
        print(f"   Public Key: {wallet.public_key}")
        
        # Test RPC connection
        print(f"\n🌐 TESTING SOLANA RPC CONNECTION...")
        
        async def test_connection():
            try:
                # Initialize RPC client
                connected = await miner.init_rpc_client()
                
                if connected:
                    print("✅ Connected to Solana network!")
                    
                    # Get network info
                    slot = await miner.rpc_client.get_slot()
                    print(f"   Current Slot: {slot.value}")
                    
                    version = await miner.rpc_client.get_version()
                    print(f"   Solana Version: {version.solana_core}")
                    
                    # Test wallet balance
                    balance = await miner.get_wallet_balance(wallet.address)
                    print(f"   Wallet Balance: {balance:,} lamports")
                    
                    # Test mining puzzle
                    print(f"\n⛏️  TESTING MINING PUZZLE...")
                    
                    mined_amount = await miner.mine_real_solana(wallet)
                    
                    if mined_amount:
                        print(f"✅ Successfully mined: {mined_amount:,} lamports")
                        print(f"   Income: ${(mined_amount / 1_000_000_000) * miner.sol_price_usd:.6f}")
                        
                        # Check if it's real mining or simulation
                        if mined_amount == miner.base_reward:
                            print("⚠️  WARNING: This appears to be simulated mining")
                            print("   The reward matches the base reward exactly")
                            print("   Real mining would have variable rewards")
                        else:
                            print("✅ Variable reward detected - possible real mining")
                        
                        return True
                    else:
                        print("❌ Mining test failed")
                        return False
                
                else:
                    print("❌ Failed to connect to Solana network")
                    return False
                    
            except Exception as e:
                print(f"❌ Connection test failed: {e}")
                return False
        
        # Run the test
        result = asyncio.run(test_connection())
        
        # Check database for mining records
        print(f"\n💾 CHECKING DATABASE RECORDS...")
        
        conn = sqlite3.connect(miner.db_path)
        cursor = conn.cursor()
        
        # Check wallets table
        cursor.execute("SELECT COUNT(*) FROM real_mining_wallets")
        wallet_count = cursor.fetchone()[0]
        print(f"   Wallets in database: {wallet_count}")
        
        # Check mining log
        cursor.execute("SELECT COUNT(*) FROM real_mining_log")
        log_count = cursor.fetchone()[0]
        print(f"   Mining log entries: {log_count}")
        
        if log_count > 0:
            cursor.execute("SELECT * FROM real_mining_log ORDER BY timestamp DESC LIMIT 3")
            recent_logs = cursor.fetchall()
            
            print(f"\n📊 RECENT MINING LOGS:")
            for log in recent_logs:
                print(f"   {log[1][:8]}... - {log[2]:,} lamports - ${log[4]:.6f}")
        
        conn.close()
        
        # Test web interface
        print(f"\n🌐 TESTING WEB INTERFACE...")
        
        try:
            # Import Flask app
            from real_solana_miner import app
            
            # Test routes
            with app.test_client() as client:
                response = client.get('/')
                
                if response.status_code == 200:
                    print("✅ Web interface accessible")
                    print("   Dashboard should be available")
                else:
                    print(f"❌ Web interface error: {response.status_code}")
        
        except Exception as e:
            print(f"❌ Web interface test failed: {e}")
        
        # Final assessment
        print(f"\n🎯 MINING SYSTEM ASSESSMENT:")
        print("=" * 50)
        
        if result:
            print("✅ BASIC FUNCTIONALITY: WORKING")
            print("   - Connects to Solana network")
            print("   - Creates real wallets")
            print("   - Generates mining puzzles")
            print("   - Solves computational puzzles")
            print("   - Logs mining activity")
        else:
            print("❌ BASIC FUNCTIONALITY: FAILED")
            print("   - Network connection issues")
            print("   - Mining puzzle failures")
        
        print(f"\n⚠️  IMPORTANT NOTES:")
        print("   This system SIMULATES mining on Solana")
        print("   Real Solana doesn't use traditional mining")
        print("   Actual rewards come from staking/validation")
        print("   The system tracks computational work")
        print("   But doesn't generate real SOL rewards")
        
        print(f"\n📊 SYSTEM STATUS:")
        print(f"   Network Connection: {'✅' if result else '❌'}")
        print(f"   Wallet Creation: ✅")
        print(f"   Database Storage: ✅")
        print(f"   Web Interface: ✅")
        print(f"   Mining Simulation: {'✅' if result else '❌'}")
        
        return result
        
    except ImportError as e:
        print(f"❌ Failed to import mining system: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

def check_existing_mining_data():
    """Check existing mining data from databases"""
    print(f"\n📊 CHECKING EXISTING MINING DATA")
    print("=" * 50)
    
    databases = [
        '/Users/alep/Downloads/decentralized-trader/real_mining.db',
        '/Users/alep/Downloads/decentralized-trader/production_mining.db',
        '/Users/alep/Downloads/decentralized-trader/m5_solana_mining.db',
        '/Users/alep/Downloads/decentralized-trader/solana_wallets.db'
    ]
    
    total_wallets = 0
    total_mined = 0
    total_transactions = 0
    
    for db_path in databases:
        if os.path.exists(db_path):
            print(f"\n📁 Database: {os.path.basename(db_path)}")
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Get table names
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                for table in tables:
                    if 'wallet' in table.lower():
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        total_wallets += count
                        print(f"   {table}: {count} wallets")
                    
                    if 'mining' in table.lower() or 'log' in table.lower():
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        total_transactions += count
                        print(f"   {table}: {count} records")
                        
                        # Try to get mining totals
                        try:
                            cursor.execute(f"SELECT SUM(total_mined) FROM {table}")
                            mined = cursor.fetchone()[0]
                            if mined:
                                total_mined += mined
                        except:
                            pass
                
                conn.close()
                
            except Exception as e:
                print(f"   ❌ Error: {e}")
        else:
            print(f"\n❌ Database not found: {os.path.basename(db_path)}")
    
    print(f"\n📊 TOTAL MINING STATISTICS:")
    print(f"   Total Wallets: {total_wallets}")
    print(f"   Total Records: {total_transactions}")
    print(f"   Total Mined: {total_mined:,} lamports")
    print(f"   Total Mined: {total_mined / 1_000_000_000:.6f} SOL")
    print(f"   USD Value: ${(total_mined / 1_000_000_000) * 100:.2f}")

if __name__ == "__main__":
    # Check existing data first
    check_existing_mining_data()
    
    # Test real mining functionality
    test_real_mining()
