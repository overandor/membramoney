#!/usr/bin/env python3
import os
"""
Live Marinade wallet collection demo
"""

import asyncio
from marinade_scale_collector import MarinadeScaleCollector

async def run_live_collection():
    """Run live wallet collection"""
    
    print("🚀 Starting Live Marinade Wallet Collection")
    print("="*80)
    
    # Initialize collector
    collector = MarinadeScaleCollector()
    
    # Get current SOL price
    await collector.get_sol_price()
    
    # Collect wallets from the last 7 days (smaller demo)
    print("\n📡 Collecting wallets from last 7 days...")
    batch_id = await collector.collect_wallets_scale(days_back=7, batch_size_days=3)
    
    # Show results
    print("\n📊 Collection Results:")
    collector.print_collection_summary()
    
    # Export data
    exported_count = collector.export_wallet_data("marinade_live_collection.json")
    print(f"\n📁 Exported {exported_count} wallets to JSON file")
    
    # Show sample of collected wallets
    print("\n💼 Sample Wallets:")
    conn = collector.get_connection() if hasattr(collector, 'get_connection') else None
    
    if conn:
        import sqlite3
        conn = sqlite3.connect(collector.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT address, amount_sol, usd_value, roi_30d, days_active 
            FROM wallets 
            ORDER BY amount_sol DESC 
            LIMIT 5
        """)
        
        for row in cursor.fetchall():
            address, amount_sol, usd_value, roi_30d, days_active = row
            print(f"   {address[:10]}... | {amount_sol:.2f} SOL | ${usd_value:.2f} | ROI: {roi_30d:.2f}% | {days_active:.0f} days")
        
        conn.close()
    
    print(f"\n🎉 Live collection completed! Batch ID: {batch_id}")
    print("💡 Your database now contains real Marinade wallet data for analysis!")

if __name__ == "__main__":
    asyncio.run(run_live_collection())
