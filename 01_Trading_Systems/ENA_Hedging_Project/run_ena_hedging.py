#!/usr/bin/env python3
"""
ENA_USDT HEDGING LAUNCHER - COMPLETE SYSTEM
Easy launcher for the ENA hedging system with all components
"""

import sys
import os
import argparse
from pathlib import Path
import asyncio
import logging

Path("logs").mkdir(exist_ok=True)

# Add src and config directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'config'))

try:
    from ena_config import ENAHedgingConfig, ENAHedgingConfigDev, ENAHedgingConfigProd
    from ena_hedging_market_maker_complete import ENAHedgingMarketMaker
    from ui_components import ModernUI
    from websocket_client import WebSocketClient, MarketDataManager
    from trading_engine import TradingEngine
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please ensure all dependencies are installed:")
    print("pip install -r requirements.txt")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/ena_hedging.log'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

def create_log_directory():
    """Create log directory if it doesn't exist"""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

def validate_environment():
    """Validate the trading environment"""
    print("🔍 Validating trading environment...")
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return False
    
    # Check required modules
    required_modules = ['gate_api', 'websockets', 'numpy', 'tkinter']
    missing_modules = []
    
    for module in required_modules:
        try:
            __import__(module)
        except ImportError:
            missing_modules.append(module)
    
    if missing_modules:
        print(f"❌ Missing required modules: {', '.join(missing_modules)}")
        print("Install with: pip install -r requirements.txt")
        return False
    
    # Check log directory
    create_log_directory()
    
    print("✅ Environment validation passed")
    return True

def print_system_info(config):
    """Print system information"""
    print("\n" + "="*80)
    print("🛡️ ENA_USDT HEDGING SYSTEM - COMPLETE VERSION")
    print("🧠 Powered by Cascade AI Assistant")
    print("💰 Multi-coin support for sub-10-cent tokens")
    print("="*80)
    print(f"📊 Default Symbol: {config.symbol}")
    print(f"💰 Min Profit: {config.min_profit_bps} bps")
    print(f"🎯 Max Position: {config.max_hedge_position}")
    print(f"📈 Order Size: ${config.hedge_order_size_usd}")
    print(f"🧠 AI Confidence: {config.ai_confidence_threshold}")
    print(f"🪙 Supported Coins: {len(config.sub_10_cent_coins)} sub-10-cent tokens")
    print(f"🔑 API Key: {config.api_key[:8]}...{config.api_key[-4:]}")
    print("="*80)

def print_coin_list(config):
    """Print list of supported coins"""
    print(f"\n🪙 SUPPORTED SUB-10-CENT COINS ({len(config.sub_10_cent_coins)} total):")
    print("-" * 60)
    
    # Group coins by type
    meme_coins = ["PEPE_USDT", "SHIB_USDT", "DOGE_USDT", "FLOKI_USDT", "BABYDOGE_USDT", "BONK_USDT", "WIF_USDT"]
    gaming_coins = ["GME_USDT", "AMC_USDT", "BB_USDT"]
    political_coins = ["TRUMP_USDT", "MAGA_USDT"]
    ai_coins = ["FET_USDT", "OCEAN_USDT"]
    solana_coins = ["1000SATS_USDT", "BOME_USDT", "SLERF_USDT", "MOG_USDT"]
    
    def print_coins(coins, category):
        category_coins = [c for c in coins if c in config.sub_10_cent_coins]
        if category_coins:
            print(f"📈 {category}:")
            for coin in category_coins:
                settings = config.get_symbol_settings(coin)
                print(f"   • {coin} - Min profit: {settings['min_profit_bps']} bps, Max pos: {settings['max_position']}")
    
    print_coins(meme_coins, "Meme Coins")
    print_coins(gaming_coins, "Gaming Stocks")
    print_coins(political_coins, "Political Coins")
    print_coins(ai_coins, "AI Tokens")
    print_coins(solana_coins, "Solana Ecosystem")
    
    # Other coins
    other_coins = [c for c in config.sub_10_cent_coins if not any(
        c in group for group in [meme_coins, gaming_coins, political_coins, ai_coins, solana_coins]
    )]
    if other_coins:
        print(f"📈 Other:")
        for coin in other_coins:
            settings = config.get_symbol_settings(coin)
            print(f"   • {coin} - Min profit: {settings['min_profit_bps']} bps, Max pos: {settings['max_position']}")

def print_safety_warnings():
    """Print safety warnings"""
    print("\n" + "⚠️" * 20)
    print("🚨 IMPORTANT SAFETY WARNINGS:")
    print("⚠️ This is automated trading software")
    print("⚠️ Cryptocurrency trading involves substantial risk")
    print("⚠️ Never invest more than you can afford to lose")
    print("⚠️ Start with small amounts in test mode")
    print("⚠️ Monitor the system closely when first starting")
    print("⚠️ Keep API keys secure and limited")
    print("⚠️" * 20)

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='ENA_USDT Hedging System - Complete Version')
    parser.add_argument('--mode', choices=['dev', 'prod', 'test'], default='dev',
                       help='Running mode (dev=development, prod=production, test=test)')
    parser.add_argument('--config', type=str, help='Custom config file path')
    parser.add_argument('--dry-run', action='store_true', help='Dry run mode (no real trades)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--symbol', type=str, help='Override default symbol')
    parser.add_argument('--list-coins', action='store_true', help='List all supported coins and exit')
    parser.add_argument('--validate', action='store_true', help='Validate environment and exit')
    
    args = parser.parse_args()
    
    # Environment validation
    if args.validate:
        if validate_environment():
            print("✅ Environment is ready for trading")
            return 0
        else:
            print("❌ Environment validation failed")
            return 1
    
    # Validate environment
    if not validate_environment():
        return 1
    
    # Select configuration
    if args.config:
        print(f"📋 Using custom config: {args.config}")
        config = ENAHedgingConfig()
    elif args.mode == 'prod':
        print("🚀 Production Mode")
        config = ENAHedgingConfigProd()
    elif args.mode == 'dev':
        print("🛠️ Development Mode")
        config = ENAHedgingConfigDev()
    else:
        print("🧪 Test Mode")
        config = ENAHedgingConfig()
    
    # Apply command line overrides
    if args.dry_run:
        print("🔍 Dry Run Mode - No real trades will be executed")
        config.simulation_mode = True
        config.paper_trading = True
    
    if args.verbose:
        print("📝 Verbose Logging Enabled")
        config.log_level = "DEBUG"
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.symbol:
        print(f"📊 Symbol override: {args.symbol}")
        config.symbol = args.symbol
        config.update_symbol_config(args.symbol)
    
    # Validate configuration
    try:
        config.validate_config()
        print("✅ Configuration validated")
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        return 1
    
    # Print system info
    print_system_info(config)
    
    # List coins if requested
    if args.list_coins:
        print_coin_list(config)
        return 0
    
    # Print safety warnings
    print_safety_warnings()
    
    # Confirm start
    if not args.dry_run:
        print("\n🤔 Are you ready to start live trading?")
        print("   Press Enter to continue or Ctrl+C to cancel...")
        try:
            input()
        except KeyboardInterrupt:
            print("\n❌ Cancelled by user")
            return 0
    
    print("\n🚀 Starting ENA hedging system...")
    print("Press Ctrl+C to stop\n")
    
    # Create and run market maker
    try:
        market_maker = ENAHedgingMarketMaker(config)
        asyncio.run(market_maker.start())
    except KeyboardInterrupt:
        print("\n⏹️ Shutting down...")
        print("📊 Final statistics would be shown here")
        print("✅ Shutdown complete")
    except Exception as e:
        print(f"❌ Runtime error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
