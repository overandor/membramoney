#!/usr/bin/env python3
"""
Example client for connecting to arbitrage opportunity streaming
"""

import asyncio
import websockets
import json
import aiohttp

async def websocket_client():
    """Connect to WebSocket for real-time opportunity streaming"""
    uri = "ws://localhost:8765"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("🔗 Connected to WebSocket server")
            
            # Listen for messages
            async for message in websocket:
                data = json.loads(message)
                
                if data["type"] == "connected":
                    print(f"✅ {data['message']}")
                elif data["type"] == "opportunity":
                    opp = data["data"]
                    print(f"\n🎯 NEW OPPORTUNITY:")
                    print(f"  Token: {opp['token']}")
                    print(f"  Buy Price: ${opp['buy_price']:.4f}")
                    print(f"  Sell Price: ${opp['sell_price']:.4f}")
                    print(f"  Spread: {opp['spread']*100:.2f}%")
                    print(f"  Z-Score: {opp['zscore']:.2f}")
                    print(f"  Liquidity: ${opp['liquidity']:,.0f}")
                    print(f"  Timestamp: {data['timestamp']}")
                    
    except Exception as e:
        print(f"❌ WebSocket error: {e}")

async def rest_api_client():
    """Example REST API calls"""
    base_url = "http://localhost:7860"
    
    async with aiohttp.ClientSession() as session:
        # Get API info
        async with session.get(f"{base_url}/") as resp:
            data = await resp.json()
            print(f"\n📡 API Info: {json.dumps(data, indent=2)}")
        
        # Get opportunities
        async with session.get(f"{base_url}/api/opportunities?limit=5") as resp:
            data = await resp.json()
            print(f"\n📊 Recent Opportunities: {data['total']}")
            for opp in data["opportunities"]:
                print(f"  - {opp['token']}: {opp['spread']*100:.2f}% spread")
        
        # Get metrics
        async with session.get(f"{base_url}/api/metrics") as resp:
            data = await resp.json()
            print(f"\n📈 Metrics:")
            print(f"  Win Rate: {data['win_rate']*100:.1f}%")
            print(f"  Avg Delay: {data['avg_delay']:.0f}s")
            print(f"  Verified: {data['verified']}")
        
        # Get rules
        async with session.get(f"{base_url}/api/rules") as resp:
            data = await resp.json()
            print(f"\n🤖 Trading Rules:")
            print(f"  Min Spread: {data['rules']['min_spread']*100:.2f}%")
            print(f"  Min Liquidity: ${data['rules']['min_liquidity']:,.0f}")
            print(f"  Trades Analyzed: {data['trades_analyzed']}")

async def main():
    """Run both WebSocket and REST API clients"""
    print("🚀 Starting Arbitrage Opportunity Client")
    print("=" * 50)
    
    # Run REST API calls first
    await rest_api_client()
    
    # Then connect to WebSocket for streaming
    print("\n" + "=" * 50)
    print("🔌 Connecting to WebSocket for real-time updates...")
    await websocket_client()

if __name__ == "__main__":
    asyncio.run(main())
