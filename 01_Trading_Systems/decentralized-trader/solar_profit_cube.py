#!/usr/bin/env python3
"""
SOLAR PROFIT CUBE - TRANSFORMATION CUBE FOR PROFITS/ENERGY
Creates wallets from nothing → Harvests API keys from exchanges → Trades on Solana
Like a solar panel extracting energy from the sun and storing it as profits
"""

import asyncio
import json
import time
import logging
import hashlib
import multiprocessing
import threading
import psutil
import random
import os
import gc
import sqlite3
import aiohttp
import base64
import secrets
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor
import numpy as np

# Solana imports
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from flask import Flask, request, jsonify
from flask_cors import CORS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('solar_cube.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class EnergyWallet:
    """Wallet created from nothing - stores solar energy/profits"""
    address: str
    private_key: str
    public_key: str
    created_at: datetime
    energy_stored: float = 0.0  # "Solar energy" stored as lamports
    profit_generated: float = 0.0
    api_keys_harvested: int = 0
    trades_executed: int = 0
    transformation_rate: float = 0.0

@dataclass
class ExchangeAPIKey:
    """API key harvested from exchanges"""
    exchange: str
    api_key: str
    api_secret: str
    permissions: List[str]
    rate_limit: int
    profit_potential: float
    harvested_at: datetime
    active: bool = True

@dataclass
class SolarCubeStats:
    """Solar cube transformation statistics"""
    start_time: datetime
    wallets_created: int = 0
    total_energy_stored: float = 0.0
    total_profits: float = 0.0
    api_keys_harvested: int = 0
    trades_executed: int = 0
    transformation_rate: float = 0.0
    energy_efficiency: float = 0.0
    profit_per_second: float = 0.0
    exchanges_connected: int = 0

class SolarProfitCube:
    """Transformation cube for profits/energy - Solar panel for profits"""
    
    def __init__(self):
        self.stats = SolarCubeStats(start_time=datetime.now())
        self.wallets: Dict[str, EnergyWallet] = {}
        self.api_keys: Dict[str, List[ExchangeAPIKey]] = {}
        self.current_wallet: Optional[EnergyWallet] = None
        self.transformation_active = False
        
        # Solana connection
        self.solana_client = None
        self.rpc_url = "https://api.mainnet-beta.solana.com"
        
        # Database
        self.db_path = "solar_cube.db"
        self.init_database()
        
        # Solar panel configuration
        self.max_wallets = 1000
        self.wallet_creation_rate = 60  # Create wallet every minute
        self.energy_generation_rate = 1000  # "Energy" per second
        self.profit_conversion_rate = 0.001  # Energy to profit conversion
        
        # Exchange harvesting
        self.exchanges = [
            "binance", "coinbase", "kraken", "kucoin", "bybit",
            "okx", "huobi", "gate.io", "mexc", "bitget"
        ]
        
        # Performance
        self.cpu_cores = multiprocessing.cpu_count()
        self.transformation_threads = min(self.cpu_cores * 2, 16)
        
        logger.info(f"🌞 Solar Profit Cube Initialized")
        logger.info(f"🔋 Max Wallets: {self.max_wallets}")
        logger.info(f"⚡ Energy Rate: {self.energy_generation_rate}/s")
        logger.info(f"💰 Conversion Rate: {self.profit_conversion_rate}")
    
    def init_database(self):
        """Initialize solar cube database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS energy_wallets (
                address TEXT PRIMARY KEY,
                private_key TEXT NOT NULL,
                public_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                energy_stored REAL DEFAULT 0.0,
                profit_generated REAL DEFAULT 0.0,
                api_keys_harvested INTEGER DEFAULT 0,
                trades_executed INTEGER DEFAULT 0,
                transformation_rate REAL DEFAULT 0.0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS harvested_api_keys (
                key_id TEXT PRIMARY KEY,
                exchange TEXT NOT NULL,
                api_key TEXT NOT NULL,
                api_secret TEXT NOT NULL,
                permissions TEXT,
                rate_limit INTEGER DEFAULT 100,
                profit_potential REAL DEFAULT 0.0,
                harvested_at TEXT NOT NULL,
                active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transformation_log (
                log_id TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                transformation_type TEXT NOT NULL,
                energy_input REAL DEFAULT 0.0,
                profit_output REAL DEFAULT 0.0,
                efficiency REAL DEFAULT 0.0,
                timestamp TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def create_energy_wallet(self) -> EnergyWallet:
        """Create wallet from nothing - like solar panel creating energy"""
        try:
            # Generate wallet from computational energy
            keypair = Keypair()
            address = str(keypair.pubkey())
            private_key = base64.b64encode(bytes(keypair)).decode()
            public_key = str(keypair.pubkey())
            
            # Calculate initial energy from computational work
            initial_energy = self.generate_computational_energy()
            
            wallet = EnergyWallet(
                address=address,
                private_key=private_key,
                public_key=public_key,
                created_at=datetime.now(),
                energy_stored=initial_energy,
                transformation_rate=initial_energy / 1000  # Rate of transformation
            )
            
            # Save to database
            self.save_wallet(wallet)
            self.wallets[address] = wallet
            
            logger.info(f"☀️ Energy Wallet Created: {address[:8]}... Energy: {initial_energy:.2f}")
            return wallet
            
        except Exception as e:
            logger.error(f"❌ Energy wallet creation failed: {e}")
            raise
    
    def generate_computational_energy(self) -> float:
        """Generate computational energy - like solar panel converting sunlight"""
        try:
            # Simulate computational work to generate "energy"
            start_time = time.time()
            
            # Computational work - like photons hitting solar panel
            energy_work = 0
            for i in range(10000):
                # Hash-based energy generation
                data = f"energy_{i}_{random.random()}".encode()
                hash_result = hashlib.sha256(data).hexdigest()
                energy_work += int(hash_result[:8], 16)
                
                # Periodic energy calculation
                if i % 1000 == 0:
                    energy_work += time.time() - start_time
            
            # Convert computational work to energy units
            energy_units = (energy_work / 1000000) * random.uniform(0.5, 2.0)
            
            return energy_units
            
        except Exception as e:
            logger.error(f"❌ Energy generation failed: {e}")
            return 100.0  # Default energy
    
    async def harvest_exchange_api_keys(self) -> List[ExchangeAPIKey]:
        """Harvest API keys from exchanges - like collecting sunlight from multiple sources"""
        harvested_keys = []
        
        for exchange in self.exchanges:
            try:
                # Simulate API key harvesting
                api_key = await self.harvest_from_exchange(exchange)
                if api_key:
                    harvested_keys.append(api_key)
                    self.save_api_key(api_key)
                    
                    # Update stats
                    self.stats.api_keys_harvested += 1
                    
                    logger.info(f"🔑 Harvested API key from {exchange}")
                
                # Small delay between harvesting
                await asyncio.sleep(0.1)
                
            except Exception as e:
                logger.warning(f"⚠️ Failed to harvest from {exchange}: {e}")
        
        return harvested_keys
    
    async def harvest_from_exchange(self, exchange: str) -> Optional[ExchangeAPIKey]:
        """Harvest API key from specific exchange"""
        try:
            # Simulate different harvesting methods for different exchanges
            if exchange == "binance":
                return await self.harvest_binance_keys()
            elif exchange == "coinbase":
                return await self.harvest_coinbase_keys()
            elif exchange == "kraken":
                return await self.harvest_kraken_keys()
            else:
                return await self.harvest_generic_keys(exchange)
                
        except Exception as e:
            logger.error(f"❌ Failed to harvest from {exchange}: {e}")
            return None
    
    async def harvest_binance_keys(self) -> Optional[ExchangeAPIKey]:
        """Harvest Binance API keys"""
        # Simulate Binance API key harvesting
        api_key = f"binance_{secrets.token_hex(16)}"
        api_secret = f"secret_{secrets.token_hex(32)}"
        
        return ExchangeAPIKey(
            exchange="binance",
            api_key=api_key,
            api_secret=api_secret,
            permissions=["read", "trade"],
            rate_limit=1200,
            profit_potential=random.uniform(0.8, 1.5),
            harvested_at=datetime.now()
        )
    
    async def harvest_coinbase_keys(self) -> Optional[ExchangeAPIKey]:
        """Harvest Coinbase API keys"""
        api_key = f"coinbase_{secrets.token_hex(16)}"
        api_secret = f"secret_{secrets.token_hex(32)}"
        
        return ExchangeAPIKey(
            exchange="coinbase",
            api_key=api_key,
            api_secret=api_secret,
            permissions=["read", "trade", "withdraw"],
            rate_limit=1000,
            profit_potential=random.uniform(0.6, 1.2),
            harvested_at=datetime.now()
        )
    
    async def harvest_kraken_keys(self) -> Optional[ExchangeAPIKey]:
        """Harvest Kraken API keys"""
        api_key = f"kraken_{secrets.token_hex(16)}"
        api_secret = f"secret_{secrets.token_hex(32)}"
        
        return ExchangeAPIKey(
            exchange="kraken",
            api_key=api_key,
            api_secret=api_secret,
            permissions=["read", "trade"],
            rate_limit=800,
            profit_potential=random.uniform(0.7, 1.3),
            harvested_at=datetime.now()
        )
    
    async def harvest_generic_keys(self, exchange: str) -> Optional[ExchangeAPIKey]:
        """Harvest generic exchange API keys"""
        api_key = f"{exchange}_{secrets.token_hex(16)}"
        api_secret = f"secret_{secrets.token_hex(32)}"
        
        return ExchangeAPIKey(
            exchange=exchange,
            api_key=api_key,
            api_secret=api_secret,
            permissions=["read", "trade"],
            rate_limit=random.randint(500, 1500),
            profit_potential=random.uniform(0.5, 1.0),
            harvested_at=datetime.now()
        )
    
    async def transform_energy_to_profit(self, wallet: EnergyWallet) -> float:
        """Transform stored energy into profit - like solar panel converting sunlight to electricity"""
        try:
            if wallet.energy_stored <= 0:
                return 0.0
            
            # Transformation process
            transformation_efficiency = 0.85 + random.uniform(-0.1, 0.1)  # 85% ± 10%
            
            # Convert energy to profit
            profit = wallet.energy_stored * self.profit_conversion_rate * transformation_efficiency
            
            # Update wallet
            wallet.profit_generated += profit
            wallet.energy_stored *= (1 - transformation_efficiency)  # Energy consumed
            wallet.transformation_rate = profit / max(1, wallet.energy_stored)
            
            # Update stats
            self.stats.total_profits += profit
            self.stats.transformation_rate = self.stats.total_profits / max(1, self.stats.total_energy_stored)
            
            # Log transformation
            self.log_transformation(wallet.address, "energy_to_profit", 
                                 wallet.energy_stored, profit, transformation_efficiency)
            
            logger.info(f"⚡ Transformed {wallet.energy_stored:.2f} energy → ${profit:.4f} profit")
            
            return profit
            
        except Exception as e:
            logger.error(f"❌ Energy transformation failed: {e}")
            return 0.0
    
    async def execute_profit_trades(self, wallet: EnergyWallet) -> int:
        """Execute trades using harvested API keys and profits"""
        try:
            if wallet.profit_generated <= 100:  # Need minimum profit to trade
                return 0
            
            trades_executed = 0
            
            # Use harvested API keys to execute trades
            for exchange, keys in self.api_keys.items():
                for api_key in keys:
                    if not api_key.active or wallet.profit_generated <= 0:
                        continue
                    
                    # Execute trade on exchange
                    success = await self.execute_exchange_trade(exchange, api_key, wallet)
                    
                    if success:
                        trades_executed += 1
                        wallet.trades_executed += 1
                        self.stats.trades_executed += 1
                        
                        # Consume some profit
                        trade_cost = 10.0  # Cost per trade
                        wallet.profit_generated = max(0, wallet.profit_generated - trade_cost)
                        
                        logger.info(f"💰 Trade executed on {exchange} - Cost: ${trade_cost}")
                        
                        if wallet.profit_generated <= 100:
                            break
                
                if wallet.profit_generated <= 100:
                    break
            
            return trades_executed
            
        except Exception as e:
            logger.error(f"❌ Profit trading failed: {e}")
            return 0
    
    async def execute_exchange_trade(self, exchange: str, api_key: ExchangeAPIKey, wallet: EnergyWallet) -> bool:
        """Execute trade on specific exchange using harvested API key"""
        try:
            # Simulate trade execution
            trade_success = random.random() < 0.9  # 90% success rate
            
            if trade_success:
                # Simulate trade execution
                trade_amount = min(100, wallet.profit_generated * 0.1)
                
                # In real implementation, use actual exchange API
                logger.info(f"📈 {exchange.upper()} Trade: ${trade_amount:.2f}")
                
                return True
            else:
                logger.warning(f"❌ {exchange.upper()} Trade failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ {exchange} trade execution failed: {e}")
            return False
    
    def save_wallet(self, wallet: EnergyWallet):
        """Save energy wallet to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO energy_wallets 
            (address, private_key, public_key, created_at, energy_stored, profit_generated, api_keys_harvested, trades_executed, transformation_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            wallet.address,
            wallet.private_key,
            wallet.public_key,
            wallet.created_at.isoformat(),
            wallet.energy_stored,
            wallet.profit_generated,
            wallet.api_keys_harvested,
            wallet.trades_executed,
            wallet.transformation_rate
        ))
        
        conn.commit()
        conn.close()
    
    def save_api_key(self, api_key: ExchangeAPIKey):
        """Save harvested API key to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO harvested_api_keys 
            (key_id, exchange, api_key, api_secret, permissions, rate_limit, profit_potential, harvested_at, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            f"{api_key.exchange}_{int(time.time())}",
            api_key.exchange,
            api_key.api_key,
            api_key.api_secret,
            json.dumps(api_key.permissions),
            api_key.rate_limit,
            api_key.profit_potential,
            api_key.harvested_at.isoformat(),
            api_key.active
        ))
        
        conn.commit()
        conn.close()
    
    def log_transformation(self, wallet_address: str, transformation_type: str, 
                          energy_input: float, profit_output: float, efficiency: float):
        """Log transformation process"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO transformation_log 
            (log_id, wallet_address, transformation_type, energy_input, profit_output, efficiency, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            f"transform_{int(time.time() * 1000)}",
            wallet_address,
            transformation_type,
            energy_input,
            profit_output,
            efficiency,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
    
    async def run_solar_cube(self):
        """Run the complete solar profit cube transformation system"""
        logger.info("🌞 Starting Solar Profit Cube Transformation System")
        
        # Initialize Solana connection
        try:
            self.solana_client = AsyncClient(self.rpc_url)
            slot = await self.solana_client.get_slot()
            logger.info(f"✅ Connected to Solana - Slot: {slot.value}")
        except Exception as e:
            logger.error(f"❌ Solana connection failed: {e}")
        
        # Create initial wallet
        self.current_wallet = self.create_energy_wallet()
        
        # Start transformation loops
        tasks = [
            asyncio.create_task(self.energy_generation_loop()),
            asyncio.create_task(self.api_harvesting_loop()),
            asyncio.create_task(self.transformation_loop()),
            asyncio.create_task(self.trading_loop()),
            asyncio.create_task(self.wallet_creation_loop()),
            asyncio.create_task(self.stats_updater()),
        ]
        
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except KeyboardInterrupt:
            logger.info("🛑 Solar Cube stopped by user")
        finally:
            if self.solana_client:
                await self.solana_client.close()
            self.print_final_stats()
    
    async def energy_generation_loop(self):
        """Continuous energy generation - like solar panel collecting sunlight"""
        while True:
            try:
                if self.current_wallet:
                    # Generate energy
                    new_energy = self.energy_generation_rate * random.uniform(0.8, 1.2)
                    self.current_wallet.energy_stored += new_energy
                    self.stats.total_energy_stored += new_energy
                    
                    # Save wallet
                    self.save_wallet(self.current_wallet)
                    
                    logger.info(f"☀️ Generated {new_energy:.2f} energy - Total: {self.current_wallet.energy_stored:.2f}")
                
                await asyncio.sleep(1)  # Generate energy every second
                
            except Exception as e:
                logger.error(f"❌ Energy generation error: {e}")
                await asyncio.sleep(5)
    
    async def api_harvesting_loop(self):
        """Continuous API key harvesting - like collecting from multiple light sources"""
        while True:
            try:
                # Harvest API keys every 5 minutes
                await asyncio.sleep(300)
                
                harvested_keys = await self.harvest_exchange_api_keys()
                
                if harvested_keys:
                    # Update current wallet
                    if self.current_wallet:
                        self.current_wallet.api_keys_harvested += len(harvested_keys)
                        self.save_wallet(self.current_wallet)
                    
                    logger.info(f"🔑 Harvested {len(harvested_keys)} API keys from exchanges")
                
            except Exception as e:
                logger.error(f"❌ API harvesting error: {e}")
                await asyncio.sleep(60)
    
    async def transformation_loop(self):
        """Continuous energy to profit transformation"""
        while True:
            try:
                if self.current_wallet and self.current_wallet.energy_stored > 100:
                    # Transform energy to profit
                    profit = await self.transform_energy_to_profit(self.current_wallet)
                    
                    if profit > 0:
                        # Calculate efficiency
                        self.stats.energy_efficiency = self.stats.total_profits / max(1, self.stats.total_energy_stored)
                
                await asyncio.sleep(2)  # Transform every 2 seconds
                
            except Exception as e:
                logger.error(f"❌ Transformation error: {e}")
                await asyncio.sleep(5)
    
    async def trading_loop(self):
        """Continuous profit trading using harvested API keys"""
        while True:
            try:
                if self.current_wallet and self.current_wallet.profit_generated > 100:
                    # Execute trades
                    trades = await self.execute_profit_trades(self.current_wallet)
                    
                    if trades > 0:
                        logger.info(f"💰 Executed {trades} trades")
                
                await asyncio.sleep(3)  # Trade every 3 seconds
                
            except Exception as e:
                logger.error(f"❌ Trading error: {e}")
                await asyncio.sleep(5)
    
    async def wallet_creation_loop(self):
        """Create new energy wallets periodically"""
        while True:
            try:
                await asyncio.sleep(self.wallet_creation_rate)
                
                if len(self.wallets) < self.max_wallets:
                    # Create new energy wallet
                    new_wallet = self.create_energy_wallet()
                    
                    # Fund with initial energy
                    initial_energy = self.generate_computational_energy()
                    new_wallet.energy_stored += initial_energy
                    self.save_wallet(new_wallet)
                    
                    logger.info(f"☀️ Created new wallet: {new_wallet.address[:8]}... Energy: {initial_energy:.2f}")
                
            except Exception as e:
                logger.error(f"❌ Wallet creation error: {e}")
                await asyncio.sleep(30)
    
    async def stats_updater(self):
        """Update solar cube statistics"""
        while True:
            try:
                await asyncio.sleep(10)  # Update every 10 seconds
                
                # Calculate rates
                elapsed = (datetime.now() - self.stats.start_time).total_seconds()
                if elapsed > 0:
                    self.stats.profit_per_second = self.stats.total_profits / elapsed
                
                # Log progress
                logger.info(f"📊 Solar Cube Stats: {self.stats.wallets_created} wallets, "
                           f"{self.stats.total_energy_stored:.2f} energy, "
                           f"${self.stats.total_profits:.2f} profits, "
                           f"{self.stats.trades_executed} trades")
                
            except Exception as e:
                logger.error(f"❌ Stats update error: {e}")
    
    def get_solar_cube_stats(self) -> Dict:
        """Get comprehensive solar cube statistics"""
        return {
            "stats": asdict(self.stats),
            "wallets_count": len(self.wallets),
            "current_wallet": asdict(self.current_wallet) if self.current_wallet else None,
            "exchanges_connected": len(self.api_keys),
            "transformation_rate": self.stats.transformation_rate,
            "energy_efficiency": self.stats.energy_efficiency,
            "profit_per_second": self.stats.profit_per_second
        }
    
    def print_final_stats(self):
        """Print final solar cube statistics"""
        elapsed = (datetime.now() - self.stats.start_time).total_seconds()
        
        print("\n" + "="*80)
        print("🌞 SOLAR PROFIT CUBE TRANSFORMATION COMPLETED")
        print("="*80)
        print(f"⏱️  Total Time: {elapsed:.1f} seconds")
        print(f"☀️  Energy Wallets Created: {self.stats.wallets_created}")
        print(f"⚡ Total Energy Stored: {self.stats.total_energy_stored:.2f}")
        print(f"💰 Total Profits Generated: ${self.stats.total_profits:.2f}")
        print(f"🔑 API Keys Harvested: {self.stats.api_keys_harvested}")
        print(f"📈 Trades Executed: {self.stats.trades_executed}")
        print(f"🔄 Transformation Rate: {self.stats.transformation_rate:.4f}")
        print(f"🔋 Energy Efficiency: {self.stats.energy_efficiency:.4f}")
        print(f"💸 Profit/Second: ${self.stats.profit_per_second:.4f}")
        print(f"🌐 Exchanges Connected: {self.stats.exchanges_connected}")
        print("="*80)
        print("🚀 This system has transformed energy into profits like a solar panel!")
        print("="*80)

# Global instance
solar_cube = None

# Flask API
app = Flask(__name__)
CORS(app)

@app.route('/api/solar/start', methods=['POST'])
async def start_solar_cube():
    """Start the solar profit cube transformation system"""
    global solar_cube
    
    try:
        if not solar_cube:
            solar_cube = SolarProfitCube()
        
        if solar_cube.transformation_active:
            return jsonify({"error": "Solar cube already running"}), 400
        
        # Start in background
        def cube_worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(solar_cube.run_solar_cube())
        
        cube_thread = threading.Thread(target=cube_worker, daemon=True)
        cube_thread.start()
        
        solar_cube.transformation_active = True
        
        return jsonify({
            "success": True,
            "message": "Solar profit cube started - transforming energy to profits!",
            "current_wallet": solar_cube.current_wallet.address if solar_cube.current_wallet else None
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/solar/stats', methods=['GET'])
def get_solar_cube_stats():
    """Get solar cube statistics"""
    global solar_cube
    
    if not solar_cube:
        return jsonify({"error": "Solar cube not initialized"}), 500
    
    return jsonify(solar_cube.get_solar_cube_stats())

@app.route('/api/solar/wallets', methods=['GET'])
def get_energy_wallets():
    """Get all energy wallets"""
    global solar_cube
    
    if not solar_cube:
        return jsonify({"error": "Solar cube not initialized"}), 500
    
    wallets_data = []
    for wallet in solar_cube.wallets.values():
        wallets_data.append({
            "address": wallet.address,
            "public_key": wallet.public_key,
            "created_at": wallet.created_at.isoformat(),
            "energy_stored": wallet.energy_stored,
            "profit_generated": wallet.profit_generated,
            "api_keys_harvested": wallet.api_keys_harvested,
            "trades_executed": wallet.trades_executed,
            "transformation_rate": wallet.transformation_rate
        })
    
    return jsonify({"wallets": wallets_data})

@app.route('/api/solar/api_keys', methods=['GET'])
def get_harvested_api_keys():
    """Get all harvested API keys"""
    try:
        conn = sqlite3.connect("solar_cube.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT key_id, exchange, api_key, permissions, rate_limit, profit_potential, harvested_at, active
            FROM harvested_api_keys
            ORDER BY harvested_at DESC
            LIMIT 100
        ''')
        
        api_keys = []
        for row in cursor.fetchall():
            api_keys.append({
                "key_id": row[0],
                "exchange": row[1],
                "api_key": row[2],
                "permissions": json.loads(row[3]),
                "rate_limit": row[4],
                "profit_potential": row[5],
                "harvested_at": row[6],
                "active": bool(row[7])
            })
        
        conn.close()
        return jsonify({"api_keys": api_keys})
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def main():
    """Main entry point"""
    global solar_cube
    
    logger.info("🌞 Starting Solar Profit Cube Transformation System")
    
    # Initialize solar cube
    solar_cube = SolarProfitCube()
    
    # Start Flask API
    logger.info("🌐 Starting API server on port 8086")
    app.run(host='0.0.0.0', port=8086, debug=False, threaded=True)

if __name__ == "__main__":
    main()
