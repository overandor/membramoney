#!/usr/bin/env python3
import os
"""
Test script to verify Marinade API parsing works correctly
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timedelta

async def test_marinade_api():
    """Test the Marinade API with correct date parameters"""
    
    base_url = "https://snapshots-api.marinade.finance/v1/stakers/ns/all"
    
    # Test with recent dates
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    start_str = start_date.strftime('%Y-%m-%d')
    end_str = end_date.strftime('%Y-%m-%d')
    
    api_url = f"{base_url}?startDate={start_str}&endDate={end_str}"
    
    print(f"📡 Testing API call: {api_url}")
    
    try:
        # Add compression handling
        headers = {
            'Accept-Encoding': 'gzip, deflate',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(api_url) as response:
                print(f"📊 Response status: {response.status}")
                print(f"📊 Content-Type: {response.headers.get('Content-Type')}")
                print(f"📊 Content-Encoding: {response.headers.get('Content-Encoding')}")
                
                if response.status == 200:
                    data = await response.json()
                    
                    print(f"📋 Data type: {type(data)}")
                    print(f"📋 Total wallets: {len(data)}")
                    
                    # Show first few wallet entries
                    wallet_count = 0
                    for wallet_address, snapshots in data.items():
                        if wallet_count < 3:
                            print(f"\n💼 Wallet {wallet_count + 1}: {wallet_address}")
                            print(f"   Snapshots: {len(snapshots)}")
                            
                            if snapshots:
                                latest = snapshots[-1]
                                print(f"   Latest amount: {latest.get('amount', 0)} SOL")
                                print(f"   Latest date: {latest.get('createdAt', 'N/A')}")
                                
                                # Show first and last for ROI calculation
                                if len(snapshots) > 1:
                                    first = snapshots[0]
                                    print(f"   First amount: {first.get('amount', 0)} SOL")
                                    print(f"   First date: {first.get('createdAt', 'N/A')}")
                                    
                                    # Calculate ROI
                                    first_amount = float(first.get('amount', 0))
                                    latest_amount = float(latest.get('amount', 0))
                                    if first_amount > 0:
                                        roi = ((latest_amount - first_amount) / first_amount) * 100
                                        print(f"   ROI: {roi:.2f}%")
                        
                        wallet_count += 1
                        if wallet_count >= 3:
                            break
                    
                    print(f"\n✅ Successfully parsed {len(data)} wallets")
                    return True
                else:
                    error_text = await response.text()
                    print(f"❌ API error: {error_text}")
                    return False
                    
    except Exception as e:
        print(f"❌ Failed to test API: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_marinade_api())
