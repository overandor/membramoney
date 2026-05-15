#!/usr/bin/env python3
import os
"""
MARINADE WALLET ANALYSIS DASHBOARD
Visualization and reporting for collected wallet data
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import sqlite3
import numpy as np
from datetime import datetime
import json

# Set style for better plots
plt.style.use('seaborn-v0_8')
sns.set_palette("husl")

class MarinadeDashboard:
    """Dashboard for visualizing Marinade wallet data"""
    
    def __init__(self, db_path: str = "marinade_scale.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        
    def load_wallet_data(self):
        """Load wallet data from database"""
        query = """
        SELECT address, amount_sol, usd_value, avg_balance, volatility,
               max_balance, days_active, roi_30d, efficiency, score,
               last_updated, collection_batch
        FROM wallets 
        WHERE amount_sol > 0
        ORDER BY amount_sol DESC
        """
        return pd.read_sql_query(query, self.conn)
    
    def create_wallet_distribution_chart(self, df):
        """Create wallet distribution visualization"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('🌊 MARINADE WALLET DISTRIBUTION ANALYSIS', fontsize=16, fontweight='bold')
        
        # 1. SOL Amount Distribution
        axes[0,0].hist(df['amount_sol'], bins=50, alpha=0.7, color='skyblue', edgecolor='black')
        axes[0,0].set_title('SOL Amount Distribution')
        axes[0,0].set_xlabel('SOL Amount')
        axes[0,0].set_ylabel('Number of Wallets')
        axes[0,0].axvline(df['amount_sol'].mean(), color='red', linestyle='--', label=f'Mean: {df["amount_sol"].mean():.2f}')
        axes[0,0].legend()
        
        # 2. USD Value Distribution
        axes[0,1].hist(df['usd_value'], bins=50, alpha=0.7, color='lightgreen', edgecolor='black')
        axes[0,1].set_title('USD Value Distribution')
        axes[0,1].set_xlabel('USD Value ($)')
        axes[0,1].set_ylabel('Number of Wallets')
        axes[0,1].axvline(df['usd_value'].mean(), color='red', linestyle='--', label=f'Mean: ${df["usd_value"].mean():,.2f}')
        axes[0,1].legend()
        
        # 3. ROI Distribution
        roi_data = df[df['roi_30d'].abs() < 100]  # Filter extreme values
        axes[1,0].hist(roi_data['roi_30d'], bins=30, alpha=0.7, color='orange', edgecolor='black')
        axes[1,0].set_title('30-Day ROI Distribution')
        axes[1,0].set_xlabel('ROI (%)')
        axes[1,0].set_ylabel('Number of Wallets')
        axes[1,0].axvline(0, color='black', linestyle='-', alpha=0.5)
        axes[1,0].axvline(roi_data['roi_30d'].mean(), color='red', linestyle='--', label=f'Mean: {roi_data["roi_30d"].mean():.2f}%')
        axes[1,0].legend()
        
        # 4. Days Active Distribution
        axes[1,1].hist(df['days_active'], bins=20, alpha=0.7, color='purple', edgecolor='black')
        axes[1,1].set_title('Days Active Distribution')
        axes[1,1].set_xlabel('Days Active')
        axes[1,1].set_ylabel('Number of Wallets')
        axes[1,1].axvline(df['days_active'].mean(), color='red', linestyle='--', label=f'Mean: {df["days_active"].mean():.1f} days')
        axes[1,1].legend()
        
        plt.tight_layout()
        plt.savefig('marinade_wallet_distribution.png', dpi=300, bbox_inches='tight')
        plt.show()
        
    def create_top_wallets_chart(self, df):
        """Create top wallets visualization"""
        fig, axes = plt.subplots(1, 2, figsize=(16, 8))
        fig.suptitle('🐋 TOP MARINADE WHALES', fontsize=16, fontweight='bold')
        
        # Top 20 wallets by SOL
        top_20 = df.head(20)
        
        # Bar chart of top 20
        bars1 = axes[0].barh(range(len(top_20)), top_20['amount_sol'], color='gold', alpha=0.8)
        axes[0].set_yticks(range(len(top_20)))
        axes[0].set_yticklabels([f"{addr[:8]}..." for addr in top_20['address']])
        axes[0].set_xlabel('SOL Amount')
        axes[0].set_title('Top 20 Wallets by SOL Amount')
        axes[0].grid(axis='x', alpha=0.3)
        
        # Add value labels on bars
        for i, bar in enumerate(bars1):
            width = bar.get_width()
            axes[0].text(width + width*0.01, bar.get_y() + bar.get_height()/2, 
                        f'{width:.1f}', ha='left', va='center', fontsize=9)
        
        # Pie chart of concentration
        top_5 = df.head(5)
        top_5_total = top_5['amount_sol'].sum()
        rest_total = df['amount_sol'].sum() - top_5_total
        
        sizes = [top_5_total, rest_total]
        labels = ['Top 5 Wallets', 'All Other Wallets']
        colors = ['gold', 'lightgray']
        
        axes[1].pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%', startangle=90)
        axes[1].set_title('Wealth Concentration: Top 5 vs Rest')
        
        plt.tight_layout()
        plt.savefig('marinade_top_whales.png', dpi=300, bbox_inches='tight')
        plt.show()
        
    def create_performance_analysis(self, df):
        """Create performance analysis charts"""
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('📈 MARINADE PERFORMANCE ANALYSIS', fontsize=16, fontweight='bold')
        
        # 1. ROI vs SOL Amount scatter
        valid_data = df[(df['roi_30d'].abs() < 50) & (df['amount_sol'] < 10000)]
        axes[0,0].scatter(valid_data['amount_sol'], valid_data['roi_30d'], 
                         alpha=0.6, s=20, c=valid_data['days_active'], cmap='viridis')
        axes[0,0].set_xlabel('SOL Amount')
        axes[0,0].set_ylabel('30-Day ROI (%)')
        axes[0,0].set_title('ROI vs SOL Amount (colored by days active)')
        axes[0,0].axhline(y=0, color='red', linestyle='--', alpha=0.5)
        axes[0,0].grid(True, alpha=0.3)
        
        # 2. Volatility vs Balance
        axes[0,1].scatter(df['avg_balance'], df['volatility'], 
                         alpha=0.6, s=15, color='coral')
        axes[0,1].set_xlabel('Average Balance (SOL)')
        axes[0,1].set_ylabel('Volatility')
        axes[0,1].set_title('Volatility vs Average Balance')
        axes[0,1].grid(True, alpha=0.3)
        
        # 3. Performance Categories
        def categorize_performance(roi):
            if roi > 10:
                return 'Excellent (>10%)'
            elif roi > 0:
                return 'Positive (0-10%)'
            elif roi > -10:
                return 'Small Loss (-10-0%)'
            else:
                return 'Big Loss (<-10%)'
        
        df['perf_category'] = df['roi_30d'].apply(categorize_performance)
        perf_counts = df['perf_category'].value_counts()
        
        colors = ['green', 'lightgreen', 'orange', 'red']
        axes[1,0].bar(perf_counts.index, perf_counts.values, color=colors, alpha=0.7)
        axes[1,0].set_title('Performance Categories')
        axes[1,0].set_ylabel('Number of Wallets')
        axes[1,0].tick_params(axis='x', rotation=45)
        
        # 4. Efficiency Score Distribution
        axes[1,1].hist(df['efficiency'], bins=30, alpha=0.7, color='teal', edgecolor='black')
        axes[1,1].set_title('Efficiency Score Distribution')
        axes[1,1].set_xlabel('Efficiency (SOL/day)')
        axes[1,1].set_ylabel('Number of Wallets')
        axes[1,1].axvline(df['efficiency'].mean(), color='red', linestyle='--', 
                         label=f'Mean: {df["efficiency"].mean():.2f}')
        axes[1,1].legend()
        
        plt.tight_layout()
        plt.savefig('marinade_performance_analysis.png', dpi=300, bbox_inches='tight')
        plt.show()
        
    def create_summary_statistics(self, df):
        """Create summary statistics report"""
        stats = {
            'total_wallets': len(df),
            'total_sol': df['amount_sol'].sum(),
            'total_usd': df['usd_value'].sum(),
            'avg_sol': df['amount_sol'].mean(),
            'median_sol': df['amount_sol'].median(),
            'avg_roi': df['roi_30d'].mean(),
            'median_roi': df['roi_30d'].median(),
            'positive_roi_wallets': len(df[df['roi_30d'] > 0]),
            'negative_roi_wallets': len(df[df['roi_30d'] < 0]),
            'avg_days_active': df['days_active'].mean(),
            'avg_volatility': df['volatility'].mean(),
            'whales_1000_plus': len(df[df['amount_sol'] >= 1000]),
            'whales_100_plus': len(df[df['amount_sol'] >= 100]),
            'top_10_percent_share': df.head(int(len(df) * 0.1))['amount_sol'].sum() / df['amount_sol'].sum() * 100
        }
        
        # Calculate Gini coefficient for wealth inequality
        sorted_amounts = np.sort(df['amount_sol'].values)
        n = len(sorted_amounts)
        index = np.arange(1, n + 1)
        gini = (np.sum((2 * index - n - 1) * sorted_amounts)) / (n * np.sum(sorted_amounts))
        stats['gini_coefficient'] = gini
        
        return stats
    
    def print_detailed_report(self, df):
        """Print detailed analysis report"""
        stats = self.create_summary_statistics(df)
        
        print("\n" + "="*80)
        print("🌊 MARINADE WALLET ANALYSIS DASHBOARD REPORT")
        print("="*80)
        
        print(f"\n📊 BASIC STATISTICS:")
        print(f"   Total Wallets Analyzed: {stats['total_wallets']:,}")
        print(f"   Total SOL Staked: {stats['total_sol']:,.2f}")
        print(f"   Total USD Value: ${stats['total_usd']:,.2f}")
        print(f"   Average SOL per Wallet: {stats['avg_sol']:.2f}")
        print(f"   Median SOL per Wallet: {stats['median_sol']:.2f}")
        
        print(f"\n🚀 PERFORMANCE METRICS:")
        print(f"   Average 30D ROI: {stats['avg_roi']:.2f}%")
        print(f"   Median 30D ROI: {stats['median_roi']:.2f}%")
        print(f"   Positive ROI Wallets: {stats['positive_roi_wallets']:,} ({stats['positive_roi_wallets']/stats['total_wallets']*100:.1f}%)")
        print(f"   Negative ROI Wallets: {stats['negative_roi_wallets']:,} ({stats['negative_roi_wallets']/stats['total_wallets']*100:.1f}%)")
        
        print(f"\n🎯 WEALTH CONCENTRATION:")
        print(f"   Wallets with 100+ SOL: {stats['whales_100_plus']:,}")
        print(f"   Wallets with 1000+ SOL: {stats['whales_1000_plus']:,}")
        print(f"   Top 10% Control: {stats['top_10_percent_share']:.1f}% of total SOL")
        print(f"   Gini Coefficient: {stats['gini_coefficient']:.3f} (0=perfect equality, 1=perfect inequality)")
        
        print(f"\n⚠️ RISK ANALYSIS:")
        print(f"   Average Days Active: {stats['avg_days_active']:.1f}")
        print(f"   Average Volatility: {stats['avg_volatility']:.2f}")
        
        print(f"\n🐋 TOP 5 WHALES:")
        top_5 = df.head(5)
        for i, (_, wallet) in enumerate(top_5.iterrows(), 1):
            print(f"   {i}. {wallet['address'][:10]}... | {wallet['amount_sol']:.2f} SOL | ${wallet['usd_value']:,.2f} | ROI: {wallet['roi_30d']:.2f}%")
        
        print("="*80)
        
    def generate_full_dashboard(self):
        """Generate complete dashboard with all visualizations"""
        print("🎨 Generating Marinade Wallet Analysis Dashboard...")
        
        # Load data
        df = self.load_wallet_data()
        print(f"📊 Loaded {len(df)} wallets for analysis")
        
        # Generate visualizations
        print("📈 Creating distribution charts...")
        self.create_wallet_distribution_chart(df)
        
        print("🐋 Creating whale analysis...")
        self.create_top_wallets_chart(df)
        
        print("📊 Creating performance analysis...")
        self.create_performance_analysis(df)
        
        # Print detailed report
        print("\n📋 Generating detailed report...")
        self.print_detailed_report(df)
        
        print(f"\n✅ Dashboard complete! Check the generated PNG files:")
        print("   - marinade_wallet_distribution.png")
        print("   - marinade_top_whales.png") 
        print("   - marinade_performance_analysis.png")
        
        self.conn.close()

def main():
    """Main function to run dashboard"""
    dashboard = MarinadeDashboard()
    dashboard.generate_full_dashboard()

if __name__ == "__main__":
    main()
