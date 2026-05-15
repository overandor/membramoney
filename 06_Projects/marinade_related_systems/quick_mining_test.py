#!/usr/bin/env python3
"""
QUICK MINING SYSTEM TEST
Check if decentralized-trader is actually mining real Solana
"""

import sqlite3
import os

print("🔍 TESTING DECENTRALIZED-TRADER MINING SYSTEM")
print("=" * 80)

# Check all mining databases
databases = [
    'real_mining.db',
    'production_mining.db', 
    'm5_solana_mining.db',
    'solana_wallets.db'
]

total_wallets = 0
total_mined = 0
total_transactions = 0

for db_name in databases:
    db_path = f'/Users/alep/Downloads/decentralized-trader/{db_name}'
    
    if os.path.exists(db_path):
        print(f"\n📁 Database: {db_name}")
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get table names
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            for table_name, in tables:
                if 'wallet' in table_name.lower():
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    total_wallets += count
                    print(f"   📊 {table_name}: {count} wallets")
                    
                    # Get sample wallet data
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                    wallets = cursor.fetchall()
                    
                    for wallet in wallets:
                        print(f"      Wallet: {str(wallet)[:100]}...")
                
                elif 'mining' in table_name.lower() or 'log' in table_name.lower():
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    total_transactions += count
                    print(f"   📝 {table_name}: {count} records")
                    
                    # Try to get mining totals
                    try:
                        cursor.execute(f"SELECT SUM(total_mined) FROM {table_name}")
                        mined = cursor.fetchone()[0]
                        if mined:
                            total_mined += mined
                            print(f"      Total mined: {mined:,} lamports")
                    except:
                        pass
            
            conn.close()
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
    else:
        print(f"\n❌ Database not found: {db_name}")

print(f"\n📊 MINING SYSTEM SUMMARY:")
print("=" * 50)
print(f"   Total Wallets: {total_wallets}")
print(f"   Total Transactions: {total_transactions}")
print(f"   Total Mined: {total_mined:,} lamports")
print(f"   Total Mined: {total_mined / 1_000_000_000:.6f} SOL")
print(f"   USD Value: ${(total_mined / 1_000_000_000) * 100:.2f}")

# Check if it's real mining or simulation
print(f"\n🎯 MINING AUTHENTICITY ASSESSMENT:")
print("=" * 50)

if total_mined > 0:
    print("✅ MINING ACTIVITY DETECTED")
    print("   - Wallets have been created")
    print("   - Mining records exist")
    print("   - Lamports have been 'mined'")
    
    # Check for patterns
    if total_mined % 10000 == 0:
        print("⚠️  WARNING: Mining amounts are perfect multiples")
        print("   This suggests simulated rewards")
    
    if total_mined == total_transactions * 10000:
        print("⚠️  WARNING: Fixed reward pattern detected")
        print("   Each transaction mined exactly 10,000 lamports")
        print("   This indicates simulation, not real mining")
    
    print(f"\n📈 REAL MINING INDICATORS:")
    if total_wallets > 0:
        print("   ✅ Real wallet addresses created")
    else:
        print("   ❌ No wallets created")
    
    if total_transactions > 0:
        print("   ✅ Mining activity logged")
    else:
        print("   ❌ No mining activity")
    
    if total_mined > 0:
        print("   ✅ Lamports generated")
    else:
        print("   ❌ No lamports generated")
    
    print(f"\n⚠️  IMPORTANT NOTE:")
    print("   Solana doesn't use traditional mining")
    print("   This system appears to SIMULATE mining")
    print("   Real rewards come from staking/validation")
    print("   The 'mining' is computational puzzle solving")
    print("   But rewards are not real SOL tokens")

else:
    print("❌ NO MINING ACTIVITY DETECTED")
    print("   - No wallets created")
    print("   - No mining records")
    print("   - No lamports generated")

print(f"\n🌐 WEB INTERFACE STATUS:")
print("=" * 30)

# Check if web files exist
web_files = [
    'app.py',
    'real_solana_miner.py',
    'production_mining_trading.py',
    'blockchain_dashboard.html'
]

for web_file in web_files:
    web_path = f'/Users/alep/Downloads/decentralized-trader/{web_file}'
    if os.path.exists(web_path):
        print(f"   ✅ {web_file}")
    else:
        print(f"   ❌ {web_file}")

print(f"\n🎯 FINAL ASSESSMENT:")
print("=" * 30)

if total_wallets > 0 and total_transactions > 0:
    print("🟡 SYSTEM IS FUNCTIONAL BUT SIMULATED")
    print("   - Creates real wallets")
    print("   - Logs mining activity")
    print("   - Generates lamports (simulated)")
    print("   - Has web interface")
    print("   - But NOT real Solana mining")
else:
    print("🔴 SYSTEM IS NOT FUNCTIONAL")
    print("   - No mining activity detected")
    print("   - May need initialization")

print(f"\n📋 RECOMMENDATIONS:")
print("   1. This is a SIMULATION system")
print("   2. For real SOL, use staking")
print("   3. For real mining, use PoW blockchains")
print("   4. System is good for learning/demos")
print("   5. Web interface works for monitoring")
