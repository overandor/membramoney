#!/usr/bin/env python3
"""
MARINADE FINANCE LIQUID STAKING ANALYZER
Extracts and analyzes liquid staking data to find top performers
Identifies wallets with highest ROI over 90-day periods
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
from concurrent.futures import ThreadPoolExecutor, as_completed
import aiohttp
import websockets

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('marinade_analyzer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class StakingWallet:
    """Wallet participating in liquid staking"""
    address: str
    initial_balance: float
    current_balance: float
    staked_amount: float
    rewards_earned: float
    roi_percentage: float
    wallet_age_days: int
    first_seen: datetime
    last_seen: datetime
    transaction_count: int
    avg_staking_duration: float

@dataclass
class StakingPerformance:
    """Performance metrics for staking analysis"""
    wallet_address: str
    period_start: datetime
    period_end: datetime
    initial_value: float
    final_value: float
    roi_percentage: float
    rewards_earned: float
    staking_efficiency: float
    risk_score: float
    consistency_score: float

class MarinadeFinanceAnalyzer:
    """Analyzes Marinade Finance liquid staking data"""
    
    def __init__(self):
        self.base_url = "https://snapshots-api.marinade.finance"
        self.solana_rpc = "https://api.mainnet-beta.solana.com"
        
        # Database for analysis
        self.db_path = "marinade_staking_analysis.db"
        self.init_database()
        
        # Analysis parameters
        self.analysis_period_days = 90
        self.min_wallet_size = 1000  # Minimum SOL to analyze
        self.top_performers_count = 100
        
        logger.info("🔥 Marinade Finance Analyzer Initialized")
        logger.info(f"🌐 API Base URL: {self.base_url}")
        logger.info(f"📊 Analysis Period: {self.analysis_period_days} days")
        logger.info(f"💰 Min Wallet Size: {self.min_wallet_size} SOL")
    
    def init_database(self):
        """Initialize analysis database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staking_wallets (
                address TEXT PRIMARY KEY,
                initial_balance REAL DEFAULT 0,
                current_balance REAL DEFAULT 0,
                staked_amount REAL DEFAULT 0,
                rewards_earned REAL DEFAULT 0,
                roi_percentage REAL DEFAULT 0,
                wallet_age_days INTEGER DEFAULT 0,
                first_seen TEXT,
                last_seen TEXT,
                transaction_count INTEGER DEFAULT 0,
                avg_staking_duration REAL DEFAULT 0,
                last_updated TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staking_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                period_start TEXT NOT NULL,
                period_end TEXT NOT NULL,
                initial_value REAL DEFAULT 0,
                final_value REAL DEFAULT 0,
                roi_percentage REAL DEFAULT 0,
                rewards_earned REAL DEFAULT 0,
                staking_efficiency REAL DEFAULT 0,
                risk_score REAL DEFAULT 0,
                consistency_score REAL DEFAULT 0,
                analysis_date TEXT NOT NULL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS marinade_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                epoch INTEGER,
                total_staked REAL DEFAULT 0,
                total_wallets INTEGER DEFAULT 0,
                avg_apr REAL DEFAULT 0,
                timestamp TEXT NOT NULL,
                raw_data TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    async def fetch_marinade_snapshots(self, limit: int = 100) -> List[Dict]:
        """Fetch Marinade Finance snapshots"""
        try:
            url = f"{self.base_url}/snapshots"
            params = {"limit": limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"📊 Retrieved {len(data)} Marinade snapshots")
                        return data
                    else:
                        logger.error(f"❌ Failed to fetch snapshots: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ Snapshot fetch error: {e}")
            return []
    
    async def fetch_wallet_staking_data(self, wallet_address: str) -> Optional[Dict]:
        """Fetch specific wallet staking data"""
        try:
            url = f"{self.base_url}/wallet/{wallet_address}"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        logger.warning(f"⚠️  Wallet {wallet_address[:8]}... not found")
                        return None
                        
        except Exception as e:
            logger.error(f"❌ Wallet data fetch error: {e}")
            return None
    
    async def fetch_top_stakers(self, limit: int = 500) -> List[Dict]:
        """Fetch top stakers from Marinade"""
        try:
            url = f"{self.base_url}/top-stakers"
            params = {"limit": limit}
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"🏆 Retrieved {len(data)} top stakers")
                        return data
                    else:
                        logger.error(f"❌ Failed to fetch top stakers: {response.status}")
                        return []
                        
        except Exception as e:
            logger.error(f"❌ Top stakers fetch error: {e}")
            return []
    
    async def analyze_wallet_performance(self, wallet_address: str, days_back: int = 90) -> Optional[StakingPerformance]:
        """Analyze individual wallet performance over time period"""
        try:
            # Fetch wallet data
            wallet_data = await self.fetch_wallet_staking_data(wallet_address)
            if not wallet_data:
                return None
            
            # Calculate performance metrics
            current_time = datetime.now()
            period_start = current_time - timedelta(days=days_back)
            
            # Extract staking history
            staking_history = wallet_data.get('staking_history', [])
            
            # Filter data within analysis period
            period_data = [
                entry for entry in staking_history
                if datetime.fromisoformat(entry.get('timestamp', '')) >= period_start
            ]
            
            if not period_data:
                return None
            
            # Calculate metrics
            initial_value = period_data[0].get('total_staked', 0)
            final_value = wallet_data.get('current_staked', 0)
            rewards_earned = wallet_data.get('total_rewards', 0)
            
            # Calculate ROI
            roi_percentage = ((final_value - initial_value) / initial_value * 100) if initial_value > 0 else 0
            
            # Calculate staking efficiency (rewards per SOL staked per day)
            staking_efficiency = (rewards_earned / initial_value / days_back) if initial_value > 0 else 0
            
            # Calculate risk score (volatility in staking)
            staking_amounts = [entry.get('staked_amount', 0) for entry in period_data]
            risk_score = np.std(staking_amounts) / np.mean(staking_amounts) if staking_amounts else 0
            
            # Calculate consistency score (how consistently they stake)
            consistency_score = len(period_data) / days_back  # Days staked / total days
            
            performance = StakingPerformance(
                wallet_address=wallet_address,
                period_start=period_start,
                period_end=current_time,
                initial_value=initial_value,
                final_value=final_value,
                roi_percentage=roi_percentage,
                rewards_earned=rewards_earned,
                staking_efficiency=staking_efficiency,
                risk_score=risk_score,
                consistency_score=consistency_score
            )
            
            return performance
            
        except Exception as e:
            logger.error(f"❌ Performance analysis error for {wallet_address[:8]}...: {e}")
            return None
    
    async def scan_top_performers(self, wallet_count: int = 500) -> List[StakingPerformance]:
        """Scan top performing wallets"""
        logger.info(f"🔍 Scanning top {wallet_count} staking performers...")
        
        # Fetch top stakers
        top_stakers = await self.fetch_top_stakers(wallet_count)
        if not top_stakers:
            return []
        
        # Analyze each wallet
        performances = []
        semaphore = asyncio.Semaphore(10)  # Limit concurrent requests
        
        async def analyze_wallet(wallet_data):
            async with semaphore:
                address = wallet_data.get('address')
                if address:
                    performance = await self.analyze_wallet_performance(address)
                    if performance and performance.roi_percentage > 0:
                        return performance
            return None
        
        # Process wallets concurrently
        tasks = [analyze_wallet(wallet) for wallet in top_stakers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter valid results
        performances = [r for r in results if r is not None and isinstance(r, StakingPerformance)]
        
        # Sort by ROI
        performances.sort(key=lambda x: x.roi_percentage, reverse=True)
        
        logger.info(f"📈 Found {len(performers)} positive performers")
        return performances[:self.top_performers_count]
    
    def identify_anomalies(self, performances: List[StakingPerformance]) -> List[Dict]:
        """Identify potentially anomalous or profitable patterns"""
        anomalies = []
        
        if not performances:
            return anomalies
        
        # Calculate statistics
        roi_values = [p.roi_percentage for p in performances]
        mean_roi = np.mean(roi_values)
        std_roi = np.std(roi_values)
        
        # Identify outliers (ROI > 2 standard deviations above mean)
        for perf in performances:
            if perf.roi_percentage > mean_roi + 2 * std_roi:
                anomalies.append({
                    "wallet_address": perf.wallet_address,
                    "anomaly_type": "HIGH_ROI",
                    "roi_percentage": perf.roi_percentage,
                    "expected_roi": mean_roi,
                    "deviation": (perf.roi_percentage - mean_roi) / std_roi,
                    "staking_efficiency": perf.staking_efficiency,
                    "risk_score": perf.risk_score,
                    "explanation": f"ROI is {perf.roi_percentage:.2f}% vs expected {mean_roi:.2f}%"
                })
        
        # Identify high efficiency with low risk
        for perf in performances:
            if (perf.staking_efficiency > np.mean([p.staking_efficiency for p in performances]) * 1.5 
                and perf.risk_score < np.mean([p.risk_score for p in performances]) * 0.5):
                anomalies.append({
                    "wallet_address": perf.wallet_address,
                    "anomaly_type": "HIGH_EFFICIENCY_LOW_RISK",
                    "roi_percentage": perf.roi_percentage,
                    "staking_efficiency": perf.staking_efficiency,
                    "risk_score": perf.risk_score,
                    "explanation": "High staking efficiency with low volatility"
                })
        
        logger.info(f"🚨 Identified {len(anomalies)} anomalous performers")
        return anomalies
    
    def save_analysis_results(self, performances: List[StakingPerformance], anomalies: List[Dict]):
        """Save analysis results to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        analysis_date = datetime.now().isoformat()
        
        # Save performances
        for perf in performances:
            cursor.execute('''
                INSERT OR REPLACE INTO staking_performance 
                (wallet_address, period_start, period_end, initial_value, final_value, 
                 roi_percentage, rewards_earned, staking_efficiency, risk_score, 
                 consistency_score, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                perf.wallet_address,
                perf.period_start.isoformat(),
                perf.period_end.isoformat(),
                perf.initial_value,
                perf.final_value,
                perf.roi_percentage,
                perf.rewards_earned,
                perf.staking_efficiency,
                perf.risk_score,
                perf.consistency_score,
                analysis_date
            ))
        
        # Save anomalies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS staking_anomalies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                anomaly_type TEXT NOT NULL,
                roi_percentage REAL DEFAULT 0,
                expected_roi REAL DEFAULT 0,
                deviation REAL DEFAULT 0,
                staking_efficiency REAL DEFAULT 0,
                risk_score REAL DEFAULT 0,
                explanation TEXT,
                analysis_date TEXT NOT NULL
            )
        ''')
        
        for anomaly in anomalies:
            cursor.execute('''
                INSERT INTO staking_anomalies 
                (wallet_address, anomaly_type, roi_percentage, expected_roi, deviation,
                 staking_efficiency, risk_score, explanation, analysis_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                anomaly["wallet_address"],
                anomaly["anomaly_type"],
                anomaly["roi_percentage"],
                anomaly["expected_roi"],
                anomaly["deviation"],
                anomaly["staking_efficiency"],
                anomaly["risk_score"],
                anomaly["explanation"],
                analysis_date
            ))
        
        conn.commit()
        conn.close()
        
        logger.info(f"💾 Saved {len(performances)} performances and {len(anomalies)} anomalies")
    
    def generate_report(self, performances: List[StakingPerformance], anomalies: List[Dict]) -> str:
        """Generate analysis report"""
        report = f"""
# MARINADE FINANCE LIQUID STAKING ANALYSIS REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## SUMMARY
- Total Analyzed: {len(performances)} wallets
- Analysis Period: {self.analysis_period_days} days
- Positive ROI Wallets: {len([p for p in performances if p.roi_percentage > 0])}
- Anomalies Detected: {len(anomalies)}

## TOP 10 PERFORMERS
"""
        
        for i, perf in enumerate(performances[:10], 1):
            report += f"""
{i}. **{perf.wallet_address[:8]}...{perf.wallet_address[-8:]}**
   - ROI: {perf.roi_percentage:.2f}%
   - Rewards: {perf.rewards_earned:.4f} SOL
   - Efficiency: {perf.staking_efficiency:.6f} SOL/SOL/day
   - Risk Score: {perf.risk_score:.4f}
   - Consistency: {perf.consistency_score:.2%}
   - Explorer: https://explorer.solana.com/address/{perf.wallet_address}
"""
        
        report += "\n## ANOMALIES\n"
        
        for anomaly in anomalies[:10]:
            report += f"""
🚨 **{anomaly['anomaly_type']}** - {anomaly['wallet_address'][:8]}...{anomaly['wallet_address'][-8:]}
   - ROI: {anomaly['roi_percentage']:.2f}% (vs {anomaly['expected_roi']:.2f}% expected)
   - Deviation: {anomaly['deviation']:.2f}σ
   - Explanation: {anomaly['explanation']}
"""
        
        report += f"""
## INSIGHTS
- Average ROI: {np.mean([p.roi_percentage for p in performances]):.2f}%
- Top 1% ROI Threshold: {np.percentile([p.roi_percentage for p in performances], 99):.2f}%
- Most Efficient Wallet: {min(performances, key=lambda x: x.staking_efficiency).wallet_address[:8]}...
- Lowest Risk: {min(performances, key=lambda x: x.risk_score).wallet_address[:8]}...

## RECOMMENDATIONS
1. Monitor top performers for pattern replication
2. Investigate anomalies for potential strategies
3. Consider risk-adjusted returns over raw ROI
4. Track consistency for sustainable strategies
"""
        
        return report
    
    async def run_full_analysis(self) -> Dict:
        """Run complete analysis pipeline"""
        logger.info("🚀 Starting Marinade Finance Analysis...")
        
        start_time = time.time()
        
        try:
            # Step 1: Scan top performers
            performances = await self.scan_top_performers(500)
            
            if not performances:
                logger.warning("⚠️  No performers found")
                return {"success": False, "error": "No performers found"}
            
            # Step 2: Identify anomalies
            anomalies = self.identify_anomalies(performances)
            
            # Step 3: Save results
            self.save_analysis_results(performances, anomalies)
            
            # Step 4: Generate report
            report = self.generate_report(performances, anomalies)
            
            # Save report to file
            with open("marinade_analysis_report.md", "w") as f:
                f.write(report)
            
            analysis_time = time.time() - start_time
            
            results = {
                "success": True,
                "analysis_time": analysis_time,
                "total_wallets": len(performances),
                "positive_roi_wallets": len([p for p in performances if p.roi_percentage > 0]),
                "anomalies": len(anomalies),
                "top_performer": {
                    "address": performances[0].wallet_address if performances else None,
                    "roi": performances[0].roi_percentage if performances else 0,
                    "rewards": performances[0].rewards_earned if performances else 0
                },
                "report_file": "marinade_analysis_report.md",
                "database": self.db_path
            }
            
            logger.info(f"✅ Analysis completed in {analysis_time:.2f} seconds")
            logger.info(f"📊 Analyzed {len(performances)} wallets")
            logger.info(f"🚨 Found {len(anomalies)} anomalies")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Analysis failed: {e}")
            return {"success": False, "error": str(e)}

# Initialize analyzer
marinade_analyzer = MarinadeFinanceAnalyzer()

async def main():
    """Main analysis function"""
    results = await marinade_analyzer.run_full_analysis()
    
    if results["success"]:
        print("\n🎉 MARINADE FINANCE ANALYSIS COMPLETED!")
        print(f"📊 Analyzed: {results['total_wallets']} wallets")
        print(f"📈 Positive ROI: {results['positive_roi_wallets']} wallets")
        print(f"🚨 Anomalies: {results['anomalies']}")
        print(f"⏱️  Time: {results['analysis_time']:.2f} seconds")
        print(f"📄 Report: {results['report_file']}")
        print(f"💾 Database: {results['database']}")
        
        if results["top_performer"]["address"]:
            print(f"\n🏆 TOP PERFORMER:")
            print(f"   Address: {results['top_performer']['address']}")
            print(f"   ROI: {results['top_performer']['roi']:.2f}%")
            print(f"   Rewards: {results['top_performer']['rewards']:.4f} SOL")
    else:
        print(f"❌ Analysis failed: {results['error']}")

if __name__ == "__main__":
    asyncio.run(main())
