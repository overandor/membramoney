#!/usr/bin/env python3
import os
"""
MARINADE WALLET DATA ANALYZER
Comprehensive analysis of Marinade staking wallet data
"""

import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Tuple
import json

class MarinadeWalletAnalyzer:
    def __init__(self):
        self.wallets_df = None
        self.analysis_results = {}
        
    def parse_wallet_data(self, data_string: str) -> pd.DataFrame:
        """Parse the wallet data string into a DataFrame"""
        wallets = []
        
        for line in data_string.strip().split('\n'):
            if not line.strip():
                continue
                
            parts = line.split('\t')
            if len(parts) >= 10:
                wallet = {
                    'address': parts[0],
                    'amount_sol': float(parts[1]),
                    'usd_value': float(parts[2]),
                    'avg_balance': float(parts[3]),
                    'volatility': float(parts[4]),
                    'max_balance': float(parts[5]),
                    'days_active': float(parts[6]),
                    'roi_30d': float(parts[7]),
                    'efficiency': float(parts[8]),
                    'score': float(parts[9]) if parts[9] else 0.0
                }
                
                # Additional metrics if available
                if len(parts) > 10 and parts[10]:
                    wallet['additional_metric'] = float(parts[10])
                    
                wallets.append(wallet)
        
        self.wallets_df = pd.DataFrame(wallets)
        print(f"📊 Parsed {len(self.wallets_df)} wallets")
        return self.wallets_df
    
    def basic_statistics(self) -> Dict:
        """Calculate basic statistics"""
        if self.wallets_df is None:
            return {}
            
        stats = {
            'total_wallets': len(self.wallets_df),
            'total_sol_staked': self.wallets_df['amount_sol'].sum(),
            'total_usd_value': self.wallets_df['usd_value'].sum(),
            'avg_sol_per_wallet': self.wallets_df['amount_sol'].mean(),
            'avg_usd_per_wallet': self.wallets_df['usd_value'].mean(),
            'median_sol': self.wallets_df['amount_sol'].median(),
            'median_usd': self.wallets_df['usd_value'].mean(),
            'max_single_wallet': self.wallets_df['amount_sol'].max(),
            'min_wallet': self.wallets_df['amount_sol'].min(),
            'wallets_over_100_sol': len(self.wallets_df[self.wallets_df['amount_sol'] > 100]),
            'wallets_over_1000_sol': len(self.wallets_df[self.wallets_df['amount_sol'] > 1000]),
            'wallets_over_10000_sol': len(self.wallets_df[self.wallets_df['amount_sol'] > 10000])
        }
        
        return stats
    
    def performance_analysis(self) -> Dict:
        """Analyze wallet performance metrics"""
        if self.wallets_df is None:
            return {}
            
        perf = {
            'avg_roi_30d': self.wallets_df['roi_30d'].mean(),
            'median_roi_30d': self.wallets_df['roi_30d'].median(),
            'positive_roi_wallets': len(self.wallets_df[self.wallets_df['roi_30d'] > 0]),
            'negative_roi_wallets': len(self.wallets_df[self.wallets_df['roi_30d'] < 0]),
            'avg_efficiency': self.wallets_df['efficiency'].mean(),
            'avg_score': self.wallets_df['score'].mean(),
            'top_performers': len(self.wallets_df[self.wallets_df['roi_30d'] > 50]),
            'underperformers': len(self.wallets_df[self.wallets_df['roi_30d'] < -50])
        }
        
        return perf
    
    def risk_analysis(self) -> Dict:
        """Analyze risk metrics"""
        if self.wallets_df is None:
            return {}
            
        risk = {
            'avg_volatility': self.wallets_df['volatility'].mean(),
            'high_volatility_wallets': len(self.wallets_df[self.wallets_df['volatility'] > 50]),
            'low_volatility_wallets': len(self.wallets_df[self.wallets_df['volatility'] < 10]),
            'avg_days_active': self.wallets_df['days_active'].mean(),
            'veteran_wallets': len(self.wallets_df[self.wallets_df['days_active'] > 300]),
            'new_wallets': len(self.wallets_df[self.wallets_df['days_active'] < 30])
        }
        
        return risk
    
    def concentration_analysis(self) -> Dict:
        """Analyze concentration of wealth"""
        if self.wallets_df is None:
            return {}
            
        # Sort by amount
        sorted_df = self.wallets_df.sort_values('amount_sol', ascending=False)
        
        # Calculate concentration metrics
        total_sol = sorted_df['amount_sol'].sum()
        
        concentration = {
            'top_1_percent_share': sorted_df.head(int(len(sorted_df) * 0.01))['amount_sol'].sum() / total_sol * 100,
            'top_5_percent_share': sorted_df.head(int(len(sorted_df) * 0.05))['amount_sol'].sum() / total_sol * 100,
            'top_10_percent_share': sorted_df.head(int(len(sorted_df) * 0.1))['amount_sol'].sum() / total_sol * 100,
            'top_20_percent_share': sorted_df.head(int(len(sorted_df) * 0.2))['amount_sol'].sum() / total_sol * 100,
            'top_wallet_share': sorted_df.head(1)['amount_sol'].sum() / total_sol * 100,
            'gini_coefficient': self.calculate_gini(sorted_df['amount_sol'].values)
        }
        
        return concentration
    
    def calculate_gini(self, values: np.ndarray) -> float:
        """Calculate Gini coefficient for wealth inequality"""
        values = np.sort(values)
        n = len(values)
        index = np.arange(1, n + 1)
        gini = (2 * np.sum(index * values)) / (n * np.sum(values)) - (n + 1) / n
        return gini
    
    def identify_whales(self, threshold_sol: float = 1000) -> pd.DataFrame:
        """Identify whale wallets"""
        if self.wallets_df is None:
            return pd.DataFrame()
            
        whales = self.wallets_df[self.wallets_df['amount_sol'] > threshold_sol].copy()
        whales = whales.sort_values('amount_sol', ascending=False)
        
        # Add whale category
        whales['category'] = np.where(whales['amount_sol'] > 10000, 'MEGA WHALE',
                                     np.where(whales['amount_sol'] > 5000, 'LARGE WHALE', 'WHALE'))
        
        return whales
    
    def identify_high_performers(self, roi_threshold: float = 20) -> pd.DataFrame:
        """Identify high performing wallets"""
        if self.wallets_df is None:
            return pd.DataFrame()
            
        performers = self.wallets_df[self.wallets_df['roi_30d'] > roi_threshold].copy()
        performers = performers.sort_values('roi_30d', ascending=False)
        
        # Add performance category
        performers['category'] = np.where(performers['roi_30d'] > 100, 'EXCEPTIONAL',
                                        np.where(performers['roi_30d'] > 50, 'EXCELLENT', 'GOOD'))
        
        return performers
    
    def generate_wallet_report(self, address: str) -> Dict:
        """Generate detailed report for a specific wallet"""
        if self.wallets_df is None:
            return {}
            
        wallet = self.wallets_df[self.wallets_df['address'] == address]
        
        if wallet.empty:
            return {"error": "Wallet not found"}
        
        wallet_data = wallet.iloc[0]
        
        # Calculate percentiles
        sol_percentile = (self.wallets_df['amount_sol'] < wallet_data['amount_sol']).mean() * 100
        roi_percentile = (self.wallets_df['roi_30d'] < wallet_data['roi_30d']).mean() * 100
        efficiency_percentile = (self.wallets_df['efficiency'] < wallet_data['efficiency']).mean() * 100
        
        report = {
            'address': address,
            'amount_sol': wallet_data['amount_sol'],
            'usd_value': wallet_data['usd_value'],
            'roi_30d': wallet_data['roi_30d'],
            'efficiency': wallet_data['efficiency'],
            'score': wallet_data['score'],
            'days_active': wallet_data['days_active'],
            'volatility': wallet_data['volatility'],
            'rankings': {
                'sol_staked_percentile': sol_percentile,
                'roi_percentile': roi_percentile,
                'efficiency_percentile': efficiency_percentile
            },
            'classification': self.classify_wallet(wallet_data)
        }
        
        return report
    
    def classify_wallet(self, wallet_data) -> str:
        """Classify wallet type based on metrics"""
        sol = wallet_data['amount_sol']
        roi = wallet_data['roi_30d']
        days = wallet_data['days_active']
        
        if sol > 10000:
            return "🐋 MEGA WHALE"
        elif sol > 1000:
            return "🐳 WHALE"
        elif sol > 100:
            return "🐟 LARGE FISH"
        elif sol > 10:
            return "🐠 MEDIUM FISH"
        else:
            return "🐡 SMALL FISH"
    
    def export_analysis(self, filename: str = "marinade_analysis.json"):
        """Export complete analysis to JSON"""
        if self.wallets_df is None:
            print("❌ No data to export")
            return
            
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'basic_statistics': self.basic_statistics(),
            'performance_analysis': self.performance_analysis(),
            'risk_analysis': self.risk_analysis(),
            'concentration_analysis': self.concentration_analysis(),
            'top_wallets': self.identify_whales().head(20).to_dict('records'),
            'top_performers': self.identify_high_performers().head(20).to_dict('records')
        }
        
        with open(filename, 'w') as f:
            json.dump(analysis, f, indent=2, default=str)
        
        print(f"📁 Analysis exported to {filename}")
    
    def print_summary_report(self):
        """Print comprehensive summary report"""
        if self.wallets_df is None:
            print("❌ No data available")
            return
            
        print("\n" + "="*80)
        print("🌊 MARINADE STAKING WALLET ANALYSIS REPORT")
        print("="*80)
        
        # Basic Stats
        basic = self.basic_statistics()
        print(f"\n📊 BASIC STATISTICS:")
        print(f"   Total Wallets: {basic['total_wallets']:,}")
        print(f"   Total SOL Staked: {basic['total_sol_staked']:,.2f}")
        print(f"   Total USD Value: ${basic['total_usd_value']:,.2f}")
        print(f"   Average SOL per Wallet: {basic['avg_sol_per_wallet']:.2f}")
        print(f"   Median SOL: {basic['median_sol']:.2f}")
        print(f"   Largest Single Wallet: {basic['max_single_wallet']:,.2f} SOL")
        print(f"   Wallets > 100 SOL: {basic['wallets_over_100_sol']}")
        print(f"   Wallets > 1,000 SOL: {basic['wallets_over_1000_sol']}")
        print(f"   Wallets > 10,000 SOL: {basic['wallets_over_10000_sol']}")
        
        # Performance
        perf = self.performance_analysis()
        print(f"\n🚀 PERFORMANCE ANALYSIS:")
        print(f"   Average 30D ROI: {perf['avg_roi_30d']:.2f}%")
        print(f"   Median 30D ROI: {perf['median_roi_30d']:.2f}%")
        print(f"   Positive ROI Wallets: {perf['positive_roi_wallets']} ({perf['positive_roi_wallets']/basic['total_wallets']*100:.1f}%)")
        print(f"   Negative ROI Wallets: {perf['negative_roi_wallets']} ({perf['negative_roi_wallets']/basic['total_wallets']*100:.1f}%)")
        print(f"   Top Performers (>50% ROI): {perf['top_performers']}")
        
        # Risk Analysis
        risk = self.risk_analysis()
        print(f"\n⚠️  RISK ANALYSIS:")
        print(f"   Average Volatility: {risk['avg_volatility']:.2f}")
        print(f"   High Volatility Wallets (>50): {risk['high_volatility_wallets']}")
        print(f"   Average Days Active: {risk['avg_days_active']:.1f}")
        print(f"   Veteran Wallets (>300 days): {risk['veteran_wallets']}")
        print(f"   New Wallets (<30 days): {risk['new_wallets']}")
        
        # Concentration
        conc = self.concentration_analysis()
        print(f"\n🎯 CONCENTRATION ANALYSIS:")
        print(f"   Top 1% Share: {conc['top_1_percent_share']:.2f}%")
        print(f"   Top 5% Share: {conc['top_5_percent_share']:.2f}%")
        print(f"   Top 10% Share: {conc['top_10_percent_share']:.2f}%")
        print(f"   Top 20% Share: {conc['top_20_percent_share']:.2f}%")
        print(f"   Single Largest Wallet: {conc['top_wallet_share']:.2f}%")
        print(f"   Gini Coefficient: {conc['gini_coefficient']:.3f} (0=perfect equality, 1=perfect inequality)")
        
        # Top Wallets
        whales = self.identify_whales().head(10)
        print(f"\n🐋 TOP 10 WHALE WALLETS:")
        for _, whale in whales.iterrows():
            print(f"   {whale['address'][:8]}... | {whale['amount_sol']:,.2f} SOL | ${whale['usd_value']:,.2f} | {whale['category']}")
        
        # Top Performers
        performers = self.identify_high_performers().head(10)
        print(f"\n🌟 TOP 10 PERFORMING WALLETS:")
        for _, perf in performers.iterrows():
            print(f"   {perf['address'][:8]}... | ROI: {perf['roi_30d']:.2f}% | {perf['amount_sol']:.2f} SOL | {perf['category']}")
        
        print("\n" + "="*80)

def main():
    """Main function to analyze the provided wallet data"""
    
    # Your wallet data
    wallet_data = """8h5CyobUGigqr8Ns3oX8gXD3wk2si5JucBoqi6FAX1k9	258.96531815856	30703.60261862112	11756.260458715877	100.04560709032744	876.4790744466837	75.0	-32.97091717750791	0.1141448894869346	4.783629205492605	
G76imCPLo9PTu2ypRvjnFQ8P4n43BeKagEbebuRa9zPY	256.59953062848	25292.0784610896	9756.63473317454	115.49555734391102	1013.4548921901048	74.0	-49.36140662211383	0.1139622081199113	4.157759345168743	5.333333333333333
Ccb8CM8s7gNgp3rcMamBcSrv5ftjYU5mNU2XYKRfuzy1	41.9365278384	2101.2175601913605	4910.470986745211	64.81628094232744	572.6922501561037	76.0	-11.542127697740186	0.1131782050912334		
9jeP3f1mKanTpJYuqwY3EjasUAjC7Rei44aRaJoaELNu	1216.85396817504	60094.13610719088	4838.483801578609	28.944896652621665	243.13969381203648	75.0	-1.837126772156883	0.119046364658985	23.89745829280871	8.5
DGpGRkvzY1gEX1VrPEPTzj3Dw7k1LuBqC8sUcS8MNeYg	2591.2151845632	68035.16650615056	2525.608514162023	28.73840750035806	252.42574591537067	75.0	-1.551687602725292	0.1138489554468545	26.49035422201413	7.0
4phZ1xEgcSAEezKa7DzB2AfmiQGei9qfXGea65ETNfUe	260.08733108592	6505.789165312321	2401.386414382148	7.924762026448696	44.27298311523352	68.0	-7.432791552815192	0.1789976972146232	5.907002954869993	1.375
ENDA9v65gmYJfyCK8xqtiDpuQc9DxvDD67JFwxjvek2M	1875.14014262016	43786.14197730096	2235.0863747238623	118.02508378871448	1044.2387168474556	75.0	-85.9095681528761	0.1130250026976885	2.634956381863044	5.0
CtcaGNAQd7jsYQMvP2osV2ZtnUPEpPZPkVWiWZtVpdsD	79.98461438448	1758.46421023728	2098.503079335328	24.83231840394439	215.0547642882001	75.0	-31.526423519690777	0.1154697431890697	493.09302556115193	1.5
AyxnmzjBJYoaMv1YV55CvNBBENKnxNuSyBx9aFDUxBot	272.10646479744	5916.64417915056	2074.3857440340475	25.367895310880733	222.9907364462533	64.0	-8.756990616470524	0.1137621038217212	13.437141816527278	1.6666666666666667
CNbJfAUQv3miNfNHqR78teTTynEmFmLrfRr8e4DoC5oU	271.1877878736	4683.24717041712	1626.938815032472	18.98619710172231	166.42448458933808	73.0	-5.882453265181911	0.1140829556935197	283.5709389203201	1.5"""
    
    # Initialize analyzer
    analyzer = MarinadeWalletAnalyzer()
    
    # Parse data
    analyzer.parse_wallet_data(wallet_data)
    
    # Generate comprehensive report
    analyzer.print_summary_report()
    
    # Export analysis
    analyzer.export_analysis()
    
    # Example: Analyze specific wallet
    if not analyzer.wallets_df.empty:
        sample_wallet = analyzer.wallets_df.iloc[0]['address']
        wallet_report = analyzer.generate_wallet_report(sample_wallet)
        print(f"\n🔍 DETAILED WALLET REPORT: {sample_wallet[:8]}...")
        print(json.dumps(wallet_report, indent=2, default=str))

if __name__ == "__main__":
    main()
