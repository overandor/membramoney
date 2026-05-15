#!/usr/bin/env python3
import os
"""
MARINADE SCALE WALLET COLLECTOR & TRACKER
Handles large-scale wallet data collection and analysis
"""

import asyncio
import aiohttp
import pandas as pd
import numpy as np
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time
import logging
from dataclasses import dataclass
import requests

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class WalletMetrics:
    """Data class for wallet metrics"""
    address: str
    amount_sol: float
    usd_value: float
    avg_balance: float
    volatility: float
    max_balance: float
    days_active: float
    roi_30d: float
    efficiency: float
    score: float
    last_updated: str

class MarinadeScaleCollector:
    """Large-scale Marinade wallet collector and tracker"""
    
    def __init__(self, db_path: str = "marinade_scale.db"):
        self.db_path = db_path
        self.base_url = "https://snapshots-api.marinade.finance/v1/stakers/ns/all"
        self.price_url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
        self.session = None
        self.sol_price = 100.0  # Default price
        
        # Initialize database
        self.init_database()
        
        logger.info("🌊 Marinade Scale Collector initialized")
    
    def init_database(self):
        """Initialize scalable database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Main wallets table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallets (
                address TEXT PRIMARY KEY,
                amount_sol REAL,
                usd_value REAL,
                avg_balance REAL,
                volatility REAL,
                max_balance REAL,
                days_active REAL,
                roi_30d REAL,
                efficiency REAL,
                score REAL,
                last_updated TEXT,
                snapshot_date TEXT,
                collection_batch TEXT
            )
        ''')
        
        # Historical snapshots
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT,
                amount_sol REAL,
                usd_value REAL,
                timestamp TEXT,
                snapshot_date TEXT,
                batch_id TEXT
            )
        ''')
        
        # Collection metadata
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collection_metadata (
                batch_id TEXT PRIMARY KEY,
                start_time TEXT,
                end_time TEXT,
                wallets_collected INTEGER,
                total_sol REAL,
                total_usd REAL,
                api_calls INTEGER,
                status TEXT
            )
        ''')
        
        # Performance tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wallet_performance (
                address TEXT PRIMARY KEY,
                roi_7d REAL,
                roi_30d REAL,
                roi_90d REAL,
                volatility_score REAL,
                efficiency_score REAL,
                risk_level TEXT,
                last_calculated TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def get_sol_price(self) -> float:
        """Get current SOL price"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.price_url, timeout=10) as response:
                    data = await response.json()
                    price = data.get('solana', {}).get('usd', 100.0)
                    self.sol_price = price
                    logger.info(f"💰 SOL Price: ${price:.2f}")
                    return price
        except Exception as e:
            logger.error(f"❌ Failed to get SOL price: {e}")
            return self.sol_price
    
    async def fetch_wallet_batch(self, start_date: str, end_date: str, batch_id: str) -> Dict:
        """Fetch a batch of wallets from Marinade API"""
        try:
            # Construct API URL with date parameters
            api_url = f"{self.base_url}?startDate={start_date}&endDate={end_date}"
            logger.info(f"📡 Fetching wallets: {api_url}")
            
            # Add compression handling
            headers = {
                'Accept-Encoding': 'gzip, deflate',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            async with aiohttp.ClientSession(headers=headers, timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # The API returns a dict where keys are wallet addresses
                        if isinstance(data, dict):
                            wallets = data
                        else:
                            logger.warning(f"⚠️  Unexpected response format: {type(data)}")
                            wallets = {}
                        
                        logger.info(f"✅ Retrieved {len(wallets)} wallets for batch {batch_id}")
                        return wallets
                    else:
                        logger.error(f"❌ API error {response.status}: {await response.text()}")
                        return {}
        
        except Exception as e:
            logger.error(f"❌ Failed to fetch batch {batch_id}: {e}")
            return {}
    
    def parse_wallet_data(self, raw_wallets: Dict, batch_id: str) -> List[WalletMetrics]:
        """Parse raw wallet data into structured format"""
        parsed_wallets = []
        current_time = datetime.now().isoformat()
        
        # The API returns a dict where keys are wallet addresses
        for wallet_address, snapshots in raw_wallets.items():
            try:
                if not snapshots or len(snapshots) == 0:
                    continue
                
                # Get the latest snapshot
                latest_snapshot = snapshots[-1]
                
                # Extract data from latest snapshot
                amount_sol = float(latest_snapshot.get('amount', 0))
                
                # Calculate USD value
                usd_value = amount_sol * self.sol_price
                
                # Calculate additional metrics from historical data
                amounts = [float(snap.get('amount', 0)) for snap in snapshots]
                avg_balance = np.mean(amounts) if amounts else amount_sol
                max_balance = np.max(amounts) if amounts else amount_sol
                min_balance = np.min(amounts) if amounts else amount_sol
                
                # Calculate volatility (standard deviation)
                volatility = np.std(amounts) if len(amounts) > 1 else 0
                
                # Calculate days active from first to last snapshot
                if len(snapshots) > 1:
                    first_time = datetime.fromisoformat(snapshots[0].get('createdAt', '').replace('Z', '+00:00'))
                    last_time = datetime.fromisoformat(latest_snapshot.get('createdAt', '').replace('Z', '+00:00'))
                    days_active = (last_time - first_time).days
                else:
                    days_active = 1
                
                # Calculate 30-day ROI if we have enough data
                roi_30d = 0
                if len(snapshots) > 1:
                    # Simple ROI calculation: (current - first) / first * 100
                    first_amount = float(snapshots[0].get('amount', 0))
                    if first_amount > 0:
                        roi_30d = ((amount_sol - first_amount) / first_amount) * 100
                
                # Calculate efficiency (balance per day active)
                efficiency = amount_sol / days_active if days_active > 0 else 0
                
                # Calculate a simple score based on balance and efficiency
                score = (amount_sol * 0.7) + (efficiency * 0.3)
                
                wallet_metrics = WalletMetrics(
                    address=wallet_address,
                    amount_sol=amount_sol,
                    usd_value=usd_value,
                    avg_balance=avg_balance,
                    volatility=volatility,
                    max_balance=max_balance,
                    days_active=days_active,
                    roi_30d=roi_30d,
                    efficiency=efficiency,
                    score=score,
                    last_updated=current_time
                )
                
                parsed_wallets.append(wallet_metrics)
                
            except Exception as e:
                logger.warning(f"⚠️  Failed to parse wallet {wallet_address}: {e}")
                continue
        
        logger.info(f"📊 Parsed {len(parsed_wallets)} wallets in batch {batch_id}")
        return parsed_wallets
    
    def save_wallet_batch(self, wallets: List[WalletMetrics], batch_id: str):
        """Save wallet batch to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        current_date = datetime.now().strftime('%Y-%m-%d')
        saved_count = 0
        
        for wallet in wallets:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO wallets 
                    (address, amount_sol, usd_value, avg_balance, volatility, 
                     max_balance, days_active, roi_30d, efficiency, score, 
                     last_updated, snapshot_date, collection_batch)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    wallet.address, wallet.amount_sol, wallet.usd_value,
                    wallet.avg_balance, wallet.volatility, wallet.max_balance,
                    wallet.days_active, wallet.roi_30d, wallet.efficiency,
                    wallet.score, wallet.last_updated, current_date, batch_id
                ))
                
                # Also save to historical snapshots
                cursor.execute('''
                    INSERT INTO wallet_snapshots 
                    (address, amount_sol, usd_value, timestamp, snapshot_date, batch_id)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    wallet.address, wallet.amount_sol, wallet.usd_value,
                    wallet.last_updated, current_date, batch_id
                ))
                
                saved_count += 1
                
            except Exception as e:
                logger.warning(f"⚠️  Failed to save wallet {wallet.address}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"💾 Saved {saved_count} wallets from batch {batch_id}")
        return saved_count
    
    def update_collection_metadata(self, batch_id: str, status: str, **kwargs):
        """Update collection metadata"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO collection_metadata 
            (batch_id, start_time, end_time, wallets_collected, total_sol, 
             total_usd, api_calls, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            batch_id,
            kwargs.get('start_time', datetime.now().isoformat()),
            kwargs.get('end_time', datetime.now().isoformat()),
            kwargs.get('wallets_collected', 0),
            kwargs.get('total_sol', 0),
            kwargs.get('total_usd', 0),
            kwargs.get('api_calls', 0),
            status
        ))
        
        conn.commit()
        conn.close()
    
    async def collect_wallets_scale(self, days_back: int = 30, batch_size_days: int = 7) -> str:
        """Collect wallets at scale with batching"""
        logger.info("🚀 Starting large-scale wallet collection")
        
        # Get current SOL price
        await self.get_sol_price()
        
        # Generate date ranges
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        batch_id = f"scale_collection_{int(time.time())}"
        start_time = datetime.now().isoformat()
        
        # Initialize metadata
        self.update_collection_metadata(batch_id, "started", start_time=start_time)
        
        total_wallets = 0
        total_sol = 0
        total_usd = 0
        api_calls = 0
        
        # Collect in batches
        current_start = start_date
        batch_num = 1
        
        while current_start < end_date:
            current_end = min(current_start + timedelta(days=batch_size_days), end_date)
            
            start_str = current_start.strftime('%Y-%m-%d')
            end_str = current_end.strftime('%Y-%m-%d')
            
            logger.info(f"📦 Processing batch {batch_num}: {start_str} to {end_str}")
            
            # Fetch batch
            raw_wallets = await self.fetch_wallet_batch(start_str, end_str, f"{batch_id}_batch_{batch_num}")
            api_calls += 1
            
            if raw_wallets:
                # Parse and save
                parsed_wallets = self.parse_wallet_data(raw_wallets, f"{batch_id}_batch_{batch_num}")
                saved_count = self.save_wallet_batch(parsed_wallets, f"{batch_id}_batch_{batch_num}")
                
                # Update totals
                batch_sol = sum(w.amount_sol for w in parsed_wallets)
                batch_usd = sum(w.usd_value for w in parsed_wallets)
                
                total_wallets += saved_count
                total_sol += batch_sol
                total_usd += batch_usd
                
                logger.info(f"✅ Batch {batch_num} complete: {saved_count} wallets, {batch_sol:.2f} SOL")
            
            # Move to next batch
            current_start = current_end
            batch_num += 1
            
            # Rate limiting
            await asyncio.sleep(1)
        
        # Update final metadata
        end_time = datetime.now().isoformat()
        self.update_collection_metadata(
            batch_id, "completed",
            start_time=start_time,
            end_time=end_time,
            wallets_collected=total_wallets,
            total_sol=total_sol,
            total_usd=total_usd,
            api_calls=api_calls
        )
        
        logger.info(f"🎉 Scale collection complete: {total_wallets} wallets collected")
        return batch_id
    
    def load_wallets_from_sample(self, sample_data: str) -> int:
        """Load wallets from sample data (like the one you provided)"""
        logger.info("📊 Loading wallets from sample data")
        
        wallets = []
        current_time = datetime.now().isoformat()
        batch_id = f"sample_load_{int(time.time())}"
        
        for line in sample_data.strip().split('\n'):
            if not line.strip():
                continue
                
            parts = line.split('\t')
            if len(parts) >= 10:
                try:
                    wallet = WalletMetrics(
                        address=parts[0],
                        amount_sol=float(parts[1]),
                        usd_value=float(parts[2]),
                        avg_balance=float(parts[3]),
                        volatility=float(parts[4]),
                        max_balance=float(parts[5]),
                        days_active=float(parts[6]),
                        roi_30d=float(parts[7]),
                        efficiency=float(parts[8]),
                        score=float(parts[9]) if parts[9] else 0.0,
                        last_updated=current_time
                    )
                    wallets.append(wallet)
                except Exception as e:
                    logger.warning(f"⚠️  Failed to parse wallet line: {e}")
        
        if wallets:
            saved_count = self.save_wallet_batch(wallets, batch_id)
            self.update_collection_metadata(
                batch_id, "completed",
                start_time=current_time,
                end_time=current_time,
                wallets_collected=saved_count,
                total_sol=sum(w.amount_sol for w in wallets),
                total_usd=sum(w.usd_value for w in wallets),
                api_calls=0
            )
            
            logger.info(f"✅ Loaded {saved_count} wallets from sample data")
            return saved_count
        
        return 0
    
    def get_collection_stats(self) -> Dict:
        """Get collection statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Wallet counts
        cursor.execute("SELECT COUNT(*) FROM wallets")
        total_wallets = cursor.fetchone()[0]
        
        # SOL totals
        cursor.execute("SELECT SUM(amount_sol), SUM(usd_value) FROM wallets")
        total_sol, total_usd = cursor.fetchone()
        
        # Collection batches
        cursor.execute("SELECT COUNT(DISTINCT collection_batch) FROM wallets WHERE collection_batch IS NOT NULL")
        batch_count = cursor.fetchone()[0]
        
        # Recent collections
        cursor.execute("""
            SELECT batch_id, wallets_collected, total_sol, status, start_time 
            FROM collection_metadata 
            ORDER BY start_time DESC 
            LIMIT 5
        """)
        recent_batches = cursor.fetchall()
        
        conn.close()
        
        return {
            'total_wallets': total_wallets or 0,
            'total_sol': total_sol or 0,
            'total_usd': total_usd or 0,
            'batch_count': batch_count or 0,
            'recent_batches': recent_batches
        }
    
    def export_wallet_data(self, filename: str = "marinade_wallets_export.json", limit: Optional[int] = None):
        """Export wallet data to JSON"""
        conn = sqlite3.connect(self.db_path)
        
        query = "SELECT * FROM wallets ORDER BY amount_sol DESC"
        if limit:
            query += f" LIMIT {limit}"
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        # Convert to JSON
        data = df.to_dict('records')
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"📁 Exported {len(data)} wallets to {filename}")
        return len(data)
    
    def print_collection_summary(self):
        """Print collection summary"""
        stats = self.get_collection_stats()
        
        print("\n" + "="*80)
        print("🌊 MARINADE SCALE COLLECTION SUMMARY")
        print("="*80)
        print(f"📊 Total Wallets: {stats['total_wallets']:,}")
        print(f"💰 Total SOL: {stats['total_sol']:,.2f}")
        print(f"💵 Total USD Value: ${stats['total_usd']:,.2f}")
        print(f"📦 Collection Batches: {stats['batch_count']}")
        
        if stats['recent_batches']:
            print(f"\n📈 Recent Collections:")
            for batch in stats['recent_batches']:
                print(f"   {batch[0]}: {batch[1]} wallets, {batch[2]:.2f} SOL - {batch[3]}")
        
        print("="*80)

async def main():
    """Main function for scale collection"""
    collector = MarinadeScaleCollector()
    
    # Your sample data
    sample_data = """8h5CyobUGigqr8Ns3oX8gXD3wk2si5JucBoqi6FAX1k9	258.96531815856	30703.60261862112	11756.260458715877	100.04560709032744	876.4790744466837	75.0	-32.97091717750791	0.1141448894869346	4.783629205492605	
G76imCPLo9PTu2ypRvjnFQ8P4n43BeKagEbebuRa9zPY	256.59953062848	25292.0784610896	9756.63473317454	115.49555734391102	1013.4548921901048	74.0	-49.36140662211383	0.1139622081199113	4.157759345168743	5.333333333333333
Ccb8CM8s7gNgp3rcMamBcSrv5ftjYU5mNU2XYKRfuzy1	41.9365278384	2101.2175601913605	4910.470986745211	64.81628094232744	572.6922501561037	76.0	-11.542127697740186	0.1131782050912334		
9jeP3f1mKanTpJYuqwY3EjasUAjC7Rei44aRaJoaELNu	1216.85396817504	60094.13610719088	4838.483801578609	28.944896652621665	243.13969381203648	75.0	-1.837126772156883	0.119046364658985	23.89745829280871	8.5
DGpGRkvzY1gEX1VrPEPTzj3Dw7k1LuBqC8sUcS8MNeYg	2591.2151845632	68035.16650615056	2525.608514162023	28.73840750035806	252.42574591537067	75.0	-1.551687602725292	0.1138489554468545	26.49035422201413	7.0
4phZ1xEgcSAEezKa7DzB2AfmiQGei9qfXGea65ETNfUe	260.08733108592	6505.789165312321	2401.386414382148	7.924762026448696	44.27298311523352	68.0	-7.432791552815192	0.1789976972146232	5.907002954869993	1.375
ENDA9v65gmYJfyCK8xqtiDpuQc9DxvDD67JFwxjvek2M	1875.14014262016	43786.14197730096	2235.0863747238623	118.02508378871448	1044.2387168474556	75.0	-85.9095681528761	0.1130250026976885	2.634956381863044	5.0
CtcaGNAQd7jsYQMvP2osV2ZtnUPEpPZPkVWiWZtVpdsD	79.98461438448	1758.46421023728	2098.503079335328	24.83231840394439	215.0547642882001	75.0	-31.526423519690777	0.1154697431890697	493.09302556115193	1.5
AyxnmzjBJYoaMv1YV55CvNBBENKnxNuSyBx9aFDUxBot	272.10646479744	5916.64417915056	2074.3857440340475	25.367895310880733	222.9907364462533	64.0	-8.756990616470524	0.1137621038217212	13.437141816527278	1.6666666666666667
CNbJfAUQv3miNfNHqR78teTTynEmFmLrfRr8e4DoC5oU	271.1877878736	4683.24717041712	1626.938815032472	18.98619710172231	166.42448458933808	73.0	-5.882453265181911	0.1140829556935197	283.5709389203201	1.5"""
    
    print("🚀 Starting Marinade Scale Collection Demo")
    print("📊 Loading sample wallet data...")
    
    # Load sample data
    loaded_count = collector.load_wallets_from_sample(sample_data)
    print(f"✅ Loaded {loaded_count} wallets from sample")
    
    # Show current stats
    collector.print_collection_summary()
    
    # Option to collect from API
    print("\n📡 Option: Collect from live Marinade API?")
    print("   This will fetch wallets from the last 30 days in batches")
    
    # Uncomment to run live collection
    # batch_id = await collector.collect_wallets_scale(days_back=30, batch_size_days=7)
    # print(f"🎉 Live collection completed: {batch_id}")
    
    # Export data
    collector.export_wallet_data("marinade_scale_export.json")
    
    print("\n💡 Next steps:")
    print("   1. Add your 12,000 wallet sample using load_wallets_from_sample()")
    print("   2. Run live collection with collect_wallets_scale()")
    print("   3. Export data for further analysis")
    print("   4. Track wallets over time with historical snapshots")

if __name__ == "__main__":
    asyncio.run(main())
