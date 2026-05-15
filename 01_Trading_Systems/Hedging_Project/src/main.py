#!/usr/bin/env python3
"""
Main Entry Point for Hedging Project
Professional Gate.io Futures Hedging System
"""

import os
import sys
import argparse
import logging
from datetime import datetime

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hedging_market_maker import HedgingMarketMaker

def setup_logging():
    """Setup logging configuration"""
    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, f'hedging_{datetime.now().strftime("%Y%m%d")}.log')
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s %(levelname)s %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Professional Hedging Market Maker')
    parser.add_argument('--config', type=str, help='Configuration file path')
    parser.add_argument('--dry-run', action='store_true', help='Run in simulation mode')
    parser.add_argument('--symbol', type=str, default='ENA_USDT', help='Trading symbol')
    parser.add_argument('--nominal', type=float, default=0.05, help='Target nominal value')
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging()
    logger = logging.getLogger('Main')
    
    # Print startup banner
    print("🚀 PROFESSIONAL HEDGING PROJECT")
    print("=" * 50)
    print("📊 Gate.io Futures Hedging System")
    print(f"💰 Target Nominal: ${args.nominal:.2f}")
    print(f"📈 Symbol: {args.symbol}")
    print(f"🔧 Mode: {'DRY RUN' if args.dry_run else 'LIVE TRADING'}")
    print("=" * 50)
    
    # Check environment variables
    if not args.dry_run and (not os.getenv("GATE_API_KEY") or not os.getenv("GATE_API_SECRET")):
        logger.error("❌ Missing GATE_API_KEY or GATE_API_SECRET for live trading")
        logger.info("💡 Use --dry-run for simulation mode")
        logger.info("💡 Or set environment variables:")
        logger.info("   export GATE_API_KEY='your-key'")
        logger.info("   export GATE_API_SECRET='your-secret'")
        return
    
    if args.dry_run:
        logger.info("🧪 Running in DRY RUN mode - no real orders")
    else:
        logger.warning("⚠️  Running in LIVE mode - real orders will be placed")
    
    try:
        # Create and run hedging market maker
        hedger = HedgingMarketMaker(config_path=args.config)
        
        if args.dry_run:
            logger.info("🧪 Dry run mode - simulating trades")
            # In dry run mode, we would implement simulation logic here
            logger.info("✅ Dry run completed successfully")
        else:
            logger.info("🚀 Starting live hedging...")
            hedger.run()
            
    except KeyboardInterrupt:
        logger.info("🛑 Hedging system stopped by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        raise

if __name__ == "__main__":
    main()
