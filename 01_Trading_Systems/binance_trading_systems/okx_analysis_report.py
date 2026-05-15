#!/usr/bin/env python3
import os
"""
OKX TRADING ANALYSIS REPORT
Analyze OKX trading data for automation viability
"""

import pandas as pd
import sqlite3
from datetime import datetime
import json

def analyze_okx_trading():
    """Analyze OKX trading data and automation viability"""
    
    print("📊 OKX TRADING ANALYSIS REPORT")
    print("=" * 50)
    
    # Load OKX data
    try:
        df = pd.read_csv("/Users/alep/Downloads/OKX Tradi (2).csv")
        print(f"📁 Loaded {len(df)} trading records")
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return
    
    # Extract user info
    if len(df) > 0:
        user_row = df.iloc[0]
        uid = str(user_row.iloc[0]).split(':')[1] if ':' in str(user_row.iloc[0]) else 'Unknown'
        name = str(user_row.iloc[1]).split(':')[1] if ':' in str(user_row.iloc[1]) else 'Unknown'
        
        print(f"👤 TRADER PROFILE:")
        print(f"   UID: {uid}")
        print(f"   Name: {name}")
    
    # Analyze trading patterns
    print(f"\n📈 TRADING PATTERNS:")
    
    # Remove header row
    trades_df = df.iloc[1:].copy()
    
    # Count trade types
    trade_types = trades_df.iloc[:, 3].value_counts()
    print(f"   Trade Types: {dict(trade_types)}")
    
    # Analyze symbols
    symbols = trades_df.iloc[:, 4].value_counts()
    print(f"   Top Symbols: {dict(symbols.head(5))}")
    
    # Extract PnL data
    pnl_data = []
    for idx, row in trades_df.iterrows():
        try:
            pnl = float(row.iloc[10]) if len(row) > 10 and str(row.iloc[10]) != '' else 0
            symbol = str(row.iloc[4]) if len(row) > 4 else ''
            if pnl != 0 and symbol:
                pnl_data.append({'symbol': symbol, 'pnl': pnl})
        except:
            continue
    
    # Calculate performance
    if pnl_data:
        pnl_df = pd.DataFrame(pnl_data)
        symbol_performance = pnl_df.groupby('symbol').agg({
            'pnl': ['sum', 'count', 'mean']
        }).round(2)
        
        print(f"\n💰 PERFORMANCE BY SYMBOL:")
        for symbol in symbol_performance.index:
            total_pnl = symbol_performance.loc[symbol, ('pnl', 'sum')]
            trades = symbol_performance.loc[symbol, ('pnl', 'count')]
            avg_pnl = symbol_performance.loc[symbol, ('pnl', 'mean')]
            print(f"   {symbol}: ${total_pnl:,.2f} ({trades} trades, avg ${avg_pnl:.2f})")
    
    # Automation viability assessment
    print(f"\n🤖 AUTOMATION VIABILITY:")
    print("=" * 30)
    
    # Check data consistency
    consistent_timestamps = trades_df.iloc[:, 2].notna().sum()
    consistent_symbols = trades_df.iloc[:, 4].notna().sum()
    consistent_pnl = len([x for x in trades_df.iloc[:, 10] if str(x) != '' and str(x) != '0'])
    
    print(f"✅ DATA QUALITY:")
    print(f"   Consistent timestamps: {consistent_timestamps}/{len(trades_df)} ({consistent_timestamps/len(trades_df)*100:.1f}%)")
    print(f"   Consistent symbols: {consistent_symbols}/{len(trades_df)} ({consistent_symbols/len(trades_df)*100:.1f}%)")
    print(f"   PnL data available: {consistent_pnl}/{len(trades_df)} ({consistent_pnl/len(trades_df)*100:.1f}%)")
    
    # Automation potential
    print(f"\n🎯 AUTOMATION POTENTIAL:")
    
    if consistent_timestamps > len(trades_df) * 0.8:
        print("   ✅ Timestamps - HIGH automation potential")
    else:
        print("   ❌ Timestamps - LOW automation potential")
    
    if consistent_symbols > len(trades_df) * 0.8:
        print("   ✅ Symbol data - HIGH automation potential")
    else:
        print("   ❌ Symbol data - LOW automation potential")
    
    if consistent_pnl > len(trades_df) * 0.5:
        print("   ✅ P&L tracking - MEDIUM automation potential")
    else:
        print("   ❌ P&L tracking - LOW automation potential")
    
    # Pattern detection
    print(f"\n🔍 PATTERN DETECTION:")
    
    # Time-based patterns
    try:
        trades_df['datetime'] = pd.to_datetime(trades_df.iloc[:, 2])
        hourly_volume = trades_df.groupby(trades_df['datetime'].dt.hour).size()
        peak_hour = hourly_volume.idxmax()
        print(f"   Peak trading hour: {peak_hour}:00")
    except:
        print("   ⚠️  Time pattern analysis failed")
    
    # Symbol concentration
    if len(symbols) > 0:
        top_symbol = symbols.index[0]
        top_symbol_pct = symbols.iloc[0] / len(trades_df) * 100
        print(f"   Most traded symbol: {top_symbol} ({top_symbol_pct:.1f}% of trades)")
    
    # Fee analysis
    try:
        fees = []
        for idx, row in trades_df.iterrows():
            try:
                fee = float(row.iloc[11]) if len(row) > 11 and str(row.iloc[11]) != '' else 0
                if fee != 0:
                    fees.append(fee)
            except:
                continue
        
        if fees:
            total_fees = sum(fees)
            avg_fee = total_fees / len(fees)
            print(f"   Total fees: ${total_fees:,.4f}")
            print(f"   Average fee: ${avg_fee:.6f}")
    except:
        print("   ⚠️  Fee analysis failed")
    
    # Final assessment
    print(f"\n📋 FINAL ASSESSMENT:")
    print("=" * 20)
    
    data_quality_score = (consistent_timestamps + consistent_symbols + consistent_pnl) / (len(trades_df) * 3) * 100
    
    if data_quality_score > 80:
        viability = "HIGH"
        recommendation = "Excellent for automation - implement trading bot"
    elif data_quality_score > 60:
        viability = "MEDIUM"
        recommendation = "Good for automation - needs data cleaning"
    else:
        viability = "LOW"
        recommendation = "Poor for automation - requires better data"
    
    print(f"   Data Quality Score: {data_quality_score:.1f}%")
    print(f"   Automation Viability: {viability}")
    print(f"   Recommendation: {recommendation}")
    
    # Save analysis
    analysis_results = {
        'trader_uid': uid if 'uid' in locals() else 'Unknown',
        'total_records': len(df),
        'trade_types': dict(trade_types),
        'symbol_performance': symbol_performance.to_dict() if 'symbol_performance' in locals() else {},
        'data_quality_score': data_quality_score,
        'automation_viability': viability,
        'recommendation': recommendation,
        'analysis_date': datetime.now().isoformat()
    }
    
    with open('okx_analysis_report.json', 'w') as f:
        json.dump(analysis_results, f, indent=2)
    
    print(f"\n💾 Analysis saved to okx_analysis_report.json")

if __name__ == "__main__":
    analyze_okx_trading()
