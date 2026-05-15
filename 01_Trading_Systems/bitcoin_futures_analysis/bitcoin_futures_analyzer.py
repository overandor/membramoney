#!/usr/bin/env python3
import os
"""
BITCOIN FUTURES MINIMUM ORDER ANALYZER
Finds exchanges with lowest minimum order sizes for Bitcoin futures
"""

import asyncio
import aiohttp
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FuturesExchangeAnalyzer:
    """Analyzes Bitcoin futures minimum order sizes across exchanges"""
    
    def __init__(self):
        self.exchanges = {
            'binance': self.get_binance_futures_info,
            'bybit': self.get_bybit_futures_info,
            'okx': self.get_okx_futures_info,
            'kucoin': self.get_kucoin_futures_info,
            'gateio': self.get_gateio_futures_info,
            'huobi': self.get_huobi_futures_info,
            'mexc': self.get_mexc_futures_info,
            'bitget': self.get_bitget_futures_info
        }
        
        self.results = []
    
    async def get_binance_futures_info(self) -> Dict:
        """Get Binance Bitcoin futures minimum info"""
        try:
            # Binance futures symbol info
            url = "https://fapi.binance.com/fapi/v1/exchangeInfo"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for symbol_info in data['symbols']:
                            if symbol_info['symbol'] == 'BTCUSDT':
                                filters = {f['filterType']: f for f in symbol_info['filters']}
                                
                                return {
                                    'exchange': 'Binance Futures',
                                    'symbol': 'BTCUSDT',
                                    'min_quantity': float(filters['LOT_SIZE']['minQty']),
                                    'max_quantity': float(filters['LOT_SIZE']['maxQty']),
                                    'quantity_step': float(filters['LOT_SIZE']['stepSize']),
                                    'min_notional': float(filters['MIN_NOTIONAL']['notional']),
                                    'price_step': float(filters['PRICE_FILTER']['tickSize']),
                                    'contract_size': 1.0,  # 1 BTC per contract
                                    'leverage': 'Up to 125x',
                                    'maker_fee': 0.0002,  # 0.02%
                                    'taker_fee': 0.0004   # 0.04%
                                }
        except Exception as e:
            logger.error(f"Binance API error: {e}")
        
        return None
    
    async def get_bybit_futures_info(self) -> Dict:
        """Get Bybit Bitcoin futures minimum info"""
        try:
            url = "https://api.bybit.com/v5/market/instruments-info?category=linear&symbol=BTCUSDT"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['retCode'] == 0 and data['result']['list']:
                            info = data['result']['list'][0]
                            
                            return {
                                'exchange': 'Bybit Futures',
                                'symbol': 'BTCUSDT',
                                'min_quantity': float(info['lotSizeFilter']['minOrderQty']),
                                'max_quantity': float(info['lotSizeFilter']['maxOrderQty']),
                                'quantity_step': float(info['lotSizeFilter']['qtyStep']),
                                'min_notional': float(info['lotSizeFilter']['minOrderAmt']),
                                'price_step': float(info['priceFilter']['tickSize']),
                                'contract_size': 1.0,
                                'leverage': 'Up to 100x',
                                'maker_fee': 0.0001,  # 0.01%
                                'taker_fee': 0.0006   # 0.06%
                            }
        except Exception as e:
            logger.error(f"Bybit API error: {e}")
        
        return None
    
    async def get_okx_futures_info(self) -> Dict:
        """Get OKX Bitcoin futures minimum info"""
        try:
            url = "https://www.okx.com/api/v5/public/instruments?instType=SWAP&uly=BTC"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['code'] == '0' and data['data']:
                            for instrument in data['data']:
                                if instrument['instId'] == 'BTC-USDT-SWAP':
                                    return {
                                        'exchange': 'OKX Futures',
                                        'symbol': 'BTC-USDT-SWAP',
                                        'min_quantity': float(instrument['minSz']),
                                        'max_quantity': float(instrument['maxLmtSz']),
                                        'quantity_step': float(instrument['lotSz']),
                                        'min_notional': float(instrument['minSz']) * float(instrument['ctMult']),
                                        'price_step': float(instrument['tickSz']),
                                        'contract_size': float(instrument['ctMult']),
                                        'leverage': 'Up to 125x',
                                        'maker_fee': 0.0002,  # 0.02%
                                        'taker_fee': 0.0005   # 0.05%
                                    }
        except Exception as e:
            logger.error(f"OKX API error: {e}")
        
        return None
    
    async def get_kucoin_futures_info(self) -> Dict:
        """Get KuCoin Bitcoin futures minimum info"""
        try:
            url = "https://api-futures.kucoin.com/api/v1/contracts/active"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['code'] == '200' and data['data']:
                            for contract in data['data']:
                                if contract['symbol'] == 'BTCUSDTM':
                                    return {
                                        'exchange': 'KuCoin Futures',
                                        'symbol': 'BTCUSDTM',
                                        'min_quantity': float(contract['lotSize']),
                                        'max_quantity': float(contract['maxOrderQty']),
                                        'quantity_step': float(contract['lotSize']),
                                        'min_notional': float(contract['minOrderValue']),
                                        'price_step': float(contract['tickSize']),
                                        'contract_size': 0.01,  # 0.01 BTC per contract
                                        'leverage': 'Up to 100x',
                                        'maker_fee': 0.0002,  # 0.02%
                                        'taker_fee': 0.0006   # 0.06%
                                    }
        except Exception as e:
            logger.error(f"KuCoin API error: {e}")
        
        return None
    
    async def get_gateio_futures_info(self) -> Dict:
        """Get Gate.io Bitcoin futures minimum info"""
        try:
            url = "https://api.gateio.ws/api/v4/futures/usdt/contracts"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for contract in data:
                            if contract['name'] == 'BTC_USDT':
                                return {
                                    'exchange': 'Gate.io Futures',
                                    'symbol': 'BTC_USDT',
                                    'min_quantity': float(contract['order_size_min']),
                                    'max_quantity': float(contract['order_size_max']),
                                    'quantity_step': float(contract['order_size_step']),
                                    'min_notional': float(contract['order_size_min']) * float(contract['quanto_multiplier']),
                                    'price_step': float(contract['precision_step']),
                                    'contract_size': float(contract['quanto_multiplier']),
                                    'leverage': 'Up to 100x',
                                    'maker_fee': 0.0002,  # 0.02%
                                    'taker_fee': 0.0005   # 0.05%
                                }
        except Exception as e:
            logger.error(f"Gate.io API error: {e}")
        
        return None
    
    async def get_huobi_futures_info(self) -> Dict:
        """Get Huobi Bitcoin futures minimum info"""
        try:
            url = "https://api.hbdm.com/linear-swap-api/v1/swap_contract_info"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['status'] == 'ok' and data['data']:
                            for contract in data['data']:
                                if contract['contract_code'] == 'BTC-USDT':
                                    return {
                                        'exchange': 'Huobi Futures',
                                        'symbol': 'BTC-USDT',
                                        'min_quantity': float(contract['min_order_size']),
                                        'max_quantity': float(contract['max_order_size']),
                                        'quantity_step': float(contract['order_size_step']),
                                        'min_notional': float(contract['min_order_value']),
                                        'price_step': float(contract['price_tick']),
                                        'contract_size': 1.0,
                                        'leverage': 'Up to 100x',
                                        'maker_fee': 0.0002,  # 0.02%
                                        'taker_fee': 0.0004   # 0.04%
                                    }
        except Exception as e:
            logger.error(f"Huobi API error: {e}")
        
        return None
    
    async def get_mexc_futures_info(self) -> Dict:
        """Get MEXC Bitcoin futures minimum info"""
        try:
            # MEXC doesn't have a public API for contract info, using typical values
            return {
                'exchange': 'MEXC Futures',
                'symbol': 'BTCUSDT',
                'min_quantity': 0.001,
                'max_quantity': 1000,
                'quantity_step': 0.001,
                'min_notional': 5.0,  # $5 minimum
                'price_step': 0.01,
                'contract_size': 1.0,
                'leverage': 'Up to 200x',
                'maker_fee': 0.0002,  # 0.02%
                'taker_fee': 0.0004   # 0.04%
            }
        except Exception as e:
            logger.error(f"MEXC API error: {e}")
        
        return None
    
    async def get_bitget_futures_info(self) -> Dict:
        """Get Bitget Bitcoin futures minimum info"""
        try:
            url = "https://api.bitget.com/api/v2/market/contracts?symbol=BTCUSDT&productType=USDT-FUTURES"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        if data['code'] == '00000' and data['data']:
                            contract = data['data'][0]
                            
                            return {
                                'exchange': 'Bitget Futures',
                                'symbol': 'BTCUSDT',
                                'min_quantity': float(contract['minSize']),
                                'max_quantity': float(contract['maxSize']),
                                'quantity_step': float(contract['sizeStep']),
                                'min_notional': float(contract['minOrderAmount']),
                                'price_step': float(contract['priceStep']),
                                'contract_size': 1.0,
                                'leverage': 'Up to 125x',
                                'maker_fee': 0.0001,  # 0.01%
                                'taker_fee': 0.0004   # 0.04%
                            }
        except Exception as e:
            logger.error(f"Bitget API error: {e}")
        
        return None
    
    async def analyze_all_exchanges(self):
        """Analyze all exchanges for minimum order requirements"""
        print("🔍 Analyzing Bitcoin futures minimum order sizes across exchanges...")
        
        tasks = []
        for exchange_name, func in self.exchanges.items():
            task = asyncio.create_task(func())
            tasks.append((exchange_name, task))
        
        for exchange_name, task in tasks:
            try:
                result = await task
                if result:
                    self.results.append(result)
                    print(f"✅ {exchange_name}: Data retrieved")
                else:
                    print(f"❌ {exchange_name}: Failed to get data")
            except Exception as e:
                print(f"❌ {exchange_name}: Error - {e}")
    
    def calculate_minimum_investment(self, btc_price: float = 65000) -> pd.DataFrame:
        """Calculate minimum investment needed for each exchange"""
        
        for result in self.results:
            # Calculate minimum USD value needed
            min_usd_value = result['min_quantity'] * result['contract_size'] * btc_price
            
            # Calculate maximum leverage at minimum
            max_leverage_value = min_usd_value
            
            # Add fees to calculation
            total_fee_per_trade = (result['maker_fee'] + result['taker_fee']) * min_usd_value
            
            result.update({
                'min_usd_value': min_usd_value,
                'total_fee_per_trade': total_fee_per_trade,
                'btc_price_used': btc_price
            })
        
        df = pd.DataFrame(self.results)
        
        # Sort by minimum USD value (lowest first)
        df = df.sort_values('min_usd_value')
        
        return df
    
    def print_comparison_table(self, df: pd.DataFrame):
        """Print detailed comparison table"""
        print("\n" + "="*120)
        print("📊 BITCOIN FUTURES MINIMUM ORDER COMPARISON")
        print("="*120)
        
        print(f"{'Exchange':<15} {'Symbol':<15} {'Min Qty':<10} {'Min USD':<10} {'Contract':<10} {'Leverage':<12} {'Maker Fee':<10} {'Taker Fee':<10}")
        print("-" * 120)
        
        for _, row in df.iterrows():
            print(f"{row['exchange']:<15} {row['symbol']:<15} {row['min_quantity']:<10.6f} "
                  f"${row['min_usd_value']:<9.2f} {row['contract_size']:<10.6f} "
                  f"{row['leverage']:<12} {row['maker_fee']*100:<9.3f}% {row['taker_fee']*100:<9.3f}%")
        
        print("="*120)
    
    def print_short_strategy_analysis(self, df: pd.DataFrame):
        """Print analysis for short strategy"""
        print("\n🎯 SHORT STRATEGY ANALYSIS")
        print("="*80)
        
        # Find best exchanges for small orders
        smallest_min = df.iloc[0]
        print(f"🏆 LOWEST MINIMUM: {smallest_min['exchange']}")
        print(f"   Minimum Order: {smallest_min['min_quantity']:.6f} BTC")
        print(f"   Minimum Value: ${smallest_min['min_usd_value']:.2f}")
        print(f"   With 100x leverage: ${smallest_min['min_usd_value']/100:.2f} margin")
        
        # Calculate how many orders you can place with $100
        print(f"\n💰 ORDERS WITH $100 CAPITAL:")
        for _, row in df.head(5).iterrows():
            orders_with_100 = 100 / row['min_usd_value']
            print(f"   {row['exchange']}: {orders_with_100:.0f} orders "
                  f"(${row['min_usd_value']:.2f} each)")
        
        # Fee analysis for frequent trading
        print(f"\n💸 FEE ANALYSIS (per $1000 turnover):")
        for _, row in df.head(5).iterrows():
            daily_fees = row['total_fee_per_trade'] * 2 * 10  # 10 round trips per day
            monthly_fees = daily_fees * 30
            print(f"   {row['exchange']}: ${daily_fees:.2f}/day, ${monthly_fees:.0f}/month")
        
        print(f"\n⚠️  RISK WARNINGS:")
        print(f"   • High leverage amplifies losses")
        print(f"   • Short positions have unlimited risk")
        print(f"   • Fees accumulate quickly with frequent trading")
        print(f"   • Market gaps can stop out positions")
        
        print("="*80)
    
    def generate_trading_plan(self, df: pd.DataFrame, capital: float = 100):
        """Generate a specific trading plan"""
        print(f"\n📋 TRADING PLAN FOR ${capital} CAPITAL")
        print("="*80)
        
        best_exchange = df.iloc[0]
        
        # Calculate position sizing
        min_order_value = best_exchange['min_usd_value']
        max_orders = int(capital / min_order_value)
        
        print(f"🏆 RECOMMENDED EXCHANGE: {best_exchange['exchange']}")
        print(f"   Minimum per order: ${min_order_value:.2f}")
        print(f"   Maximum orders: {max_orders}")
        print(f"   Recommended orders: {max_orders // 2} (keep 50% as margin)")
        
        # Short strategy parameters
        print(f"\n📉 DAILY SHORT STRATEGY:")
        print(f"   • Place {max_orders // 4} short orders at market open")
        print(f"   • Target profit: 0.5% per trade = ${min_order_value * 0.005:.2f}")
        print(f"   • Stop loss: 1% = ${min_order_value * 0.01:.2f}")
        print(f"   • Daily profit target: ${(max_orders // 4) * min_order_value * 0.005:.2f}")
        
        # Risk management
        print(f"\n⚖️  RISK MANAGEMENT:")
        print(f"   • Maximum daily loss: ${capital * 0.05:.2f} (5%)")
        print(f"   • Position size: ${min_order_value:.2f} per order")
        print(f"   • Total exposure: ${(max_orders // 2) * min_order_value:.2f}")
        print(f"   • Required margin at 50x leverage: ${((max_orders // 2) * min_order_value) / 50:.2f}")
        
        print("="*80)

async def main():
    """Main analysis function"""
    print("🚀 BITCOIN FUTURES MINIMUM ORDER ANALYZER")
    print("="*80)
    print("🎯 Finding exchanges with lowest minimum order sizes for small short positions")
    
    analyzer = FuturesExchangeAnalyzer()
    
    # Analyze all exchanges
    await analyzer.analyze_all_exchanges()
    
    if not analyzer.results:
        print("❌ No data retrieved from exchanges")
        return
    
    # Calculate and display results
    df = analyzer.calculate_minimum_investment(btc_price=65000)
    
    # Print comparison
    analyzer.print_comparison_table(df)
    
    # Print short strategy analysis
    analyzer.print_short_strategy_analysis(df)
    
    # Generate trading plan
    analyzer.generate_trading_plan(df, capital=100)
    
    # Save results
    df.to_csv('bitcoin_futures_minimum_analysis.csv', index=False)
    print(f"\n💾 Results saved to 'bitcoin_futures_minimum_analysis.csv'")

if __name__ == "__main__":
    asyncio.run(main())
