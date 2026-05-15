#!/usr/bin/env python3
"""
SIMPLE GATE.IO BOT WITH AUTO-INSTALL OLLAMA
- Auto-installs Ollama if not present
- Uses your 1000 micro-cap coins for trading
- Solid Ollama Llama integration for trading decisions
- Real balance checking and order placement
"""

import asyncio
import aiohttp
import json
import hmac
import hashlib
import time
import os
import requests
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Optional
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging

# Try to import Gate.io SDK like the working bot
try:
    import gate_api
    from gate_api import ApiClient, Configuration, SpotApi
    GATE_SDK_AVAILABLE = True
except ImportError:
    gate_api = None
    GATE_SDK_AVAILABLE = False

# Retry function from the working bot
def with_retry(fn, *args, retries=3, base_delay=1.0, **kwargs):
    delay = base_delay
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            logger.warning(f"Retry {attempt} on {getattr(fn, '__name__', 'call')}: {exc}")
            if attempt >= retries:
                break
            time.sleep(delay)
            delay *= 2
    if last_exc:
        logger.error(f"Retry exhausted on {getattr(fn, '__name__', 'call')}: {last_exc}")
    return None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# REAL GATE.IO API CREDENTIALS
GATE_API_KEY = os.getenv("GATE_API_KEY", "")
GATE_API_SECRET = os.getenv("GATE_API_SECRET", "")
GATE_BASE_URL = "https://api.gateio.ws"  # Correct base URL

# OLLAMA CONFIGURATION
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "deepseek-r1"  # Try DeepSeek first, will fallback if needed

# YOUR 10 MICRO-CAP COINS (from your data)
MICRO_CAP_COINS = [
    {"symbol": "VADER", "price": 0.001007, "change": -0.1072, "volume": 11136},
    {"symbol": "OBT", "price": 0.001016, "change": 0.0000, "volume": 20370},
    {"symbol": "INSP", "price": 0.001021, "change": -0.0916, "volume": 25832},
    {"symbol": "3KDS", "price": 0.001050, "change": 0.0343, "volume": 10575},
    {"symbol": "IOST", "price": 0.001052, "change": -0.0348, "volume": 11768},
    {"symbol": "IQ", "price": 0.001059, "change": -0.0065, "volume": 9053},
    {"symbol": "LIKE", "price": 0.001060, "change": 0.0241, "volume": 20811},
    {"symbol": "DRESS", "price": 0.001064, "change": 0.0400, "volume": 47018},
    {"symbol": "AZUR", "price": 0.001069, "change": -0.0192, "volume": 15532},
    {"symbol": "LOULOU", "price": 0.001070, "change": -0.0011, "volume": 9249},
]

class SimpleGateioBot:
    """Simple Gate.io bot that actually works with real account - USING GATE.IO SDK"""
    
    def __init__(self):
        self.api_key = GATE_API_KEY
        self.api_secret = GATE_API_SECRET
        self.base_url = GATE_BASE_URL
        
        # Use Gate.io SDK like the working bot
        self.gate_client = None
        self.setup_gate_client()
        
        # Account data - WILL BE FETCHED FROM REAL ACCOUNT
        self.account_balances = {}
        self.total_usdt_balance = 0.0  # REAL balance from API
        self.available_balance = 0.0   # REAL available balance
        
        # Trading data
        self.active_orders = []
        self.trades_history = []
        self.micro_caps = MICRO_CAP_COINS  # Use your 10 coins
        
        # Ollama integration
        self.ollama_connected = False
        self.ollama_installed = False
        self.install_and_check_ollama()
        
        logger.info("🚀 Simple Gate.io Bot with Gate.io SDK Initialized")
        logger.info(f"🔑 API Key: {self.api_key[:10]}...")
        logger.info(f"📊 Using {len(self.micro_caps)} micro-cap coins")
        logger.info(f"🤖 Ollama: {OLLAMA_URL} - Model: {OLLAMA_MODEL}")
    
    def setup_gate_client(self):
        """Setup Gate.io client using official SDK - EXACTLY LIKE WORKING BOT"""
        if not GATE_SDK_AVAILABLE:
            logger.error("❌ Gate.io SDK not available - install with: pip install gate-api")
            return
        
        try:
            # Use the EXACT same configuration as the working gatefutures.py
            cfg = Configuration(key=self.api_key, secret=self.api_secret)
            # NO host setting - use default V4 endpoint
            self.gate_client = SpotApi(ApiClient(cfg))
            logger.info("✅ Gate.io SDK client initialized with V4 endpoint")
        except Exception as e:
            logger.error(f"❌ Failed to setup Gate.io client: {e}")
    
    async def get_account_balances(self) -> bool:
        """Get REAL account balances using Gate.io SDK - EXACTLY LIKE WORKING BOT"""
        if not self.gate_client:
            logger.error("❌ Gate.io client not initialized")
            return False
        
        try:
            logger.info("💰 Getting REAL account balances using Gate.io SDK...")
            
            # Use the exact same pattern as the working gatefutures.py
            def _call():
                return list(self.gate_client.list_spot_accounts())
            
            balances = with_retry(_call)
            
            if balances:
                self.account_balances = {}
                self.total_usdt_balance = 0.0
                self.available_balance = 0.0
                
                for balance in balances:
                    currency = balance.currency
                    available = float(balance.available)
                    total = float(balance.total)
                    
                    self.account_balances[currency] = {
                        'currency': currency,
                        'available': available,
                        'total': total
                    }
                    
                    if currency == 'USDT':
                        self.available_balance = available
                        self.total_usdt_balance = total
                
                logger.info(f"✅ REAL balance fetched: ${self.total_usdt_balance:.2f} USDT")
                return True
            else:
                logger.error("❌ No balance data received")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to get account balances: {e}")
            return False
    
    def get_account_balances_sync(self) -> bool:
        """Sync version for UI calls - USING GATE.IO SDK ONLY"""
        if not self.gate_client:
            logger.error("❌ Gate.io client not initialized")
            return False
        
        try:
            logger.info("💰 Getting REAL account balances using Gate.io SDK...")
            
            # Use the exact same pattern as the working gatefutures.py
            def _call():
                return list(self.gate_client.list_spot_accounts())
            
            balances = with_retry(_call)
            
            if balances:
                self.account_balances = {}
                self.total_usdt_balance = 0.0
                self.available_balance = 0.0
                
                for balance in balances:
                    currency = balance.currency
                    available = float(balance.available)
                    total = float(balance.total)
                    
                    self.account_balances[currency] = {
                        'currency': currency,
                        'available': available,
                        'total': total
                    }
                    
                    if currency == 'USDT':
                        self.available_balance = available
                        self.total_usdt_balance = total
                
                logger.info(f"✅ REAL balance fetched: ${self.total_usdt_balance:.2f} USDT")
                return True
            else:
                logger.error("❌ No balance data received")
                return False
                
        except Exception as e:
            logger.error(f"❌ Failed to get account balances: {e}")
            return False
    
    def install_ollama(self):
        """Auto-install Ollama if not present"""
        try:
            logger.info("🔧 Checking if Ollama is installed...")
            
            # Check if ollama command exists
            result = subprocess.run(['which', 'ollama'], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.info("📦 Ollama command not found. Checking if Ollama app exists...")
                
                # Check if Ollama app is installed in /Applications
                if os.path.exists('/Applications/Ollama.app'):
                    logger.info("✅ Ollama app found in /Applications")
                    # Try to add to PATH
                    ollama_path = '/Applications/Ollama.app/Contents/MacOS/ollama'
                    if os.path.exists(ollama_path):
                        logger.info("🔗 Creating symlink for ollama command...")
                        subprocess.run(['ln', '-sf', ollama_path, '/usr/local/bin/ollama'], 
                                     capture_output=True)
                        self.ollama_installed = True
                    else:
                        logger.error("❌ Ollama app found but binary not accessible")
                        return False
                else:
                    logger.info("📦 Ollama not found. Installing Ollama...")
                    
                    # Install Ollama (macOS/Linux)
                    install_script = """
                    curl -fsSL https://ollama.com/install.sh | sh
                    """
                    
                    # Run install script
                    process = subprocess.Popen(['sh', '-c', install_script], 
                                             stdout=subprocess.PIPE, 
                                             stderr=subprocess.PIPE,
                                             text=True)
                    
                    logger.info("⏳ Installing Ollama (this may take a few minutes)...")
                    stdout, stderr = process.communicate()
                    
                    if process.returncode == 0:
                        logger.info("✅ Ollama installed successfully!")
                        self.ollama_installed = True
                    else:
                        logger.error(f"❌ Failed to install Ollama: {stderr}")
                        return False
            else:
                logger.info("✅ Ollama is already installed")
                self.ollama_installed = True
            
            # Start Ollama service
            logger.info("🚀 Starting Ollama service...")
            try:
                # Try to start Ollama service
                subprocess.Popen(['ollama', 'serve'], 
                                stdout=subprocess.DEVNULL, 
                                stderr=subprocess.DEVNULL)
                logger.info("✅ Ollama service started")
            except FileNotFoundError:
                logger.error("❌ Cannot start Ollama service - command not found")
                logger.info("💡 Please start Ollama manually: Open Ollama app or run 'ollama serve'")
                # Don't return False - continue with the app
            except Exception as e:
                logger.error(f"❌ Error starting Ollama service: {e}")
                logger.info("💡 Please start Ollama manually: Open Ollama app or run 'ollama serve'")
                # Don't return False - continue with the app
            
            # Wait a bit for service to start
            time.sleep(3)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error installing Ollama: {e}")
            return False
    
    def install_ollama_model(self):
        """Install or fallback to a working model"""
        try:
            logger.info(f"📦 Checking available models...")
            
            # Check available models
            response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=10)
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                logger.info(f"📦 Available models: {model_names}")
                
                # Try DeepSeek first (your preferred model)
                if OLLAMA_MODEL in model_names:
                    logger.info(f"🧪 Testing {OLLAMA_MODEL} model...")
                    
                    # Test if DeepSeek actually works (not just installed)
                    test_payload = {
                        "model": OLLAMA_MODEL,
                        "prompt": "Say 'test'",
                        "stream": False
                    }
                    
                    test_response = requests.post(f"{OLLAMA_URL}/api/generate", 
                                                json=test_payload, timeout=15)
                    
                    if test_response.status_code == 200:
                        logger.info(f"✅ {OLLAMA_MODEL} is working!")
                        return True
                    else:
                        logger.warning(f"⚠️ {OLLAMA_MODEL} installed but not working (500 error)")
                        logger.info("🔄 Trying fallback model...")
                
                # Fallback to lighter models
                fallback_models = ["llama3.2:1b", "llama3.2:3b", "llama3.2", "qwen2.5:1.5b", "gemma2:2b"]
                
                for model in fallback_models:
                    if model in model_names:
                        logger.info(f"🧪 Testing fallback model: {model}")
                        
                        test_payload = {
                            "model": model,
                            "prompt": "Say 'test'",
                            "stream": False
                        }
                        
                        test_response = requests.post(f"{OLLAMA_URL}/api/generate", 
                                                    json=test_payload, timeout=10)
                        
                        if test_response.status_code == 200:
                            logger.info(f"✅ Using working model: {model}")
                            self.ollama_model = model
                            return True
                
                # If no working model found, try to install a light one
                logger.info("📥 No working model found. Installing llama3.2:1b...")
                install_process = subprocess.run(['ollama', 'pull', 'llama3.2:1b'], 
                                               capture_output=True, text=True)
                
                if install_process.returncode == 0:
                    logger.info("✅ llama3.2:1b installed!")
                    self.ollama_model = "llama3.2:1b"
                    return True
                else:
                    logger.error(f"❌ Failed to install model: {install_process.stderr}")
                    return False
            else:
                logger.error("❌ Cannot connect to Ollama API")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error checking models: {e}")
            return False
    
    def install_and_check_ollama(self):
        """Install Ollama and check connection - AUTO-START SERVER"""
        try:
            logger.info("🤖 Setting up Ollama server...")
            
            # First, try to start existing Ollama or install it
            if not self.install_ollama():
                logger.error("❌ Failed to setup Ollama")
                self.ollama_connected = False
                return
            
            # Wait for server to be ready
            logger.info("⏳ Waiting for Ollama server to be ready...")
            for i in range(10):  # Try for 10 seconds
                try:
                    response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=2)
                    if response.status_code == 200:
                        logger.info("✅ Ollama server is responding!")
                        break
                except:
                    time.sleep(1)
                    continue
            else:
                logger.error("❌ Ollama server not responding after 10 seconds")
                self.ollama_connected = False
                return
            
            # Install model if needed
            if not self.install_ollama_model():
                logger.error("❌ Failed to install Ollama model")
                self.ollama_connected = False
                return
            
            # Final connection test
            response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                logger.info(f"✅ Ollama server ready! Available models: {model_names}")
                
                # Use first available model if default not found
                if OLLAMA_MODEL not in model_names and model_names:
                    self.ollama_model = model_names[0]
                    logger.info(f"🔄 Using model: {self.ollama_model}")
                else:
                    self.ollama_model = OLLAMA_MODEL
                
                self.ollama_connected = True
                logger.info("🤖 Ollama server is ready for trading!")
            else:
                logger.error("❌ Ollama server not responding")
                self.ollama_connected = False
                
        except Exception as e:
            logger.error(f"❌ Cannot setup Ollama: {e}")
            self.ollama_connected = False
    
    def ask_ollama(self, prompt: str) -> str:
        """Ask local Ollama Llama for trading decision"""
        if not self.ollama_connected:
            return "HOLD"
        
        try:
            payload = {
                "model": self.ollama_model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for consistent decisions
                    "max_tokens": 100
                }
            }
            
            response = requests.post(f"{OLLAMA_URL}/api/generate", 
                                   json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                decision = result.get('response', '').strip().upper()
                
                # Extract decision from response
                if 'BUY' in decision:
                    return 'BUY'
                elif 'SELL' in decision:
                    return 'SELL'
                else:
                    return 'HOLD'
            else:
                logger.error(f"❌ Ollama request failed: {response.status_code}")
                return 'HOLD'
        
        except Exception as e:
            logger.error(f"❌ Ollama error: {e}")
            return 'HOLD'
    
    def generate_signature(self, method: str, url: str, params: dict = None, timestamp: str = None) -> str:
        """Generate Gate.io API signature - CORRECT FORMAT"""
        if timestamp is None:
            timestamp = str(int(time.time()))
        
        if params is None:
            params = {}
        
        # Gate.io v4 API signature format:
        # The signature is HMAC-SHA512 of: timestamp + method + url + query_string
        # For private endpoints without query params, it's just: timestamp + method + url
        
        # Build the string to sign
        if method == 'GET' and params:
            # For GET requests with parameters, include sorted query string
            query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
            sign_string = f"{timestamp}{method.upper()}{url}?{query_string}"
        else:
            # For POST requests or GET without params (like /api/v4/spot/accounts)
            sign_string = f"{timestamp}{method.upper()}{url}"
        
        logger.info(f"🔏 Signing: {sign_string}")
        
        # Generate HMAC-SHA512 signature
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha512
        ).hexdigest()
        
        logger.info(f"🔏 Signature: {signature[:20]}...")
        return signature
    
    async def make_request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """Make authenticated API request - FIXED SIGNATURE"""
        try:
            url = f"{self.base_url}{endpoint}"
            timestamp = str(int(time.time()))
            
            # Generate signature
            signature = self.generate_signature(method, endpoint, params, timestamp)
            
            headers = {
                'KEY': self.api_key,
                'Timestamp': timestamp,
                'SIGN': signature
            }
            
            if method == 'GET':
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, headers=headers, params=params, timeout=10) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logger.error(f"Request failed: {response.status} - {error_text}")
                            return {}
            
            elif method == 'POST':
                headers['Content-Type'] = 'application/json'
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, headers=headers, json=params, timeout=10) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logger.error(f"Request failed: {response.status} - {error_text}")
                            return {}
        
        except Exception as e:
            logger.error(f"API request error: {e}")
            return {}
    
    async def get_account_balances(self) -> bool:
        """Get REAL account balances from Gate.io v4 API"""
        try:
            logger.info("💰 Getting REAL account balances from Gate.io v4...")
            
            # Use correct v4 endpoint for spot accounts
            spot_data = await self.make_request('GET', '/api/v4/spot/accounts')
            if spot_data:
                self.total_usdt_balance = 0.0
                self.available_balance = 0.0
                
                for balance in spot_data:
                    currency = balance['currency']
                    available = float(balance['available'])
                    frozen = float(balance['frozen'])
                    total = float(balance['total'])
                    
                    # Store all balances
                    self.account_balances[f"spot_{currency}"] = {
                        'currency': currency,
                        'available': available,
                        'frozen': frozen,
                        'total': total
                    }
                    
                    # Calculate REAL USDT total
                    if currency == 'USDT':
                        self.total_usdt_balance += total
                        self.available_balance += available
                        logger.info(f"💰 REAL USDT Balance: {total:.2f} (Available: {available:.2f})")
                    
                    # Show other currencies too
                    elif total > 0:
                        logger.info(f"🪙 {currency}: {total:.6f} (Available: {available:.6f})")
                
                logger.info(f"✅ REAL Account Connected - Total USDT: ${self.total_usdt_balance:.2f}")
                logger.info(f"💸 REAL Available USDT: ${self.available_balance:.2f}")
                return True
            else:
                logger.error("❌ Failed to get account balances from v4 API")
                return False
        
        except Exception as e:
            logger.error(f"Error getting REAL balances: {e}")
            return False
    
    def get_trading_decision(self, coin_data: dict) -> str:
        """Ask Ollama Llama for trading decision using your micro-cap data"""
        prompt = f"""
You are an expert micro-cap crypto trading AI. Analyze this coin and make a decision:

COIN DATA:
- Symbol: {coin_data['symbol']}
- Price: ${coin_data['price']:.6f}
- 24h Change: {coin_data['change']*100:+.2f}%
- Volume: ${coin_data.get('volume', 0):.0f}

ACCOUNT STATUS:
- Available Balance: ${self.available_balance:.2f}
- Total Balance: ${self.total_usdt_balance:.2f}

MICRO-CAP TRADING STRATEGY:
- Target coins under $0.10 (micro-caps)
- Look for pumps (+5%+) and dumps (-5%-)
- Minimum order: $1.00
- Consider volume and momentum
- High volatility = high opportunity

RISK ASSESSMENT:
- Price change: {coin_data['change']*100:+.2f}% ({'PUMP' if coin_data['change'] > 0.05 else 'DUMP' if coin_data['change'] < -0.05 else 'NEUTRAL'})
- Volume strength: {'HIGH' if coin_data.get('volume', 0) > 50000 else 'MEDIUM' if coin_data.get('volume', 0) > 10000 else 'LOW'}

DECISION RULES:
- BUY: Strong pump (+5%+) with good volume, or oversold dump with reversal potential
- SELL: Strong dump (-5%+) to short, or take profits on pumps
- HOLD: No clear signal, low volume, or neutral movement

Based on this analysis, what is your decision?

Respond with only: BUY, SELL, or HOLD
"""
        
        decision = self.ask_ollama(prompt)
        logger.info(f"🤖 Ollama decision for {coin_data['symbol']}: {decision}")
        return decision
    
    async def auto_trade_with_micro_caps(self):
        """Auto-trading using your 1000 micro-cap coins"""
        if not self.ollama_connected:
            logger.warning("🤖 Ollama not connected - skipping auto-trade")
            return
        
        if self.available_balance < 1.0:
            logger.warning("💸 Insufficient balance for auto-trading")
            return
        
        logger.info(f"📊 Analyzing {len(self.micro_caps)} micro-cap coins...")
        
        # Analyze top 50 coins from your list
        top_coins = self.micro_caps[:50]
        trades_made = 0
        
        for coin in top_coins:
            if self.available_balance < 1.0:
                logger.info("💸 Budget exhausted - stopping auto-trade")
                break
            
            if trades_made >= 5:  # Limit to 5 trades per cycle
                break
            
            # Get Ollama decision
            decision = self.get_trading_decision(coin)
            
            # Log decision to UI
            timestamp = datetime.now().strftime("%H:%M:%S")
            logger.info(f"[{timestamp}] 🤖 {coin['symbol']}: {decision} (Price: ${coin['price']:.6f}, Change: {coin['change']*100:+.2f}%)")
            
            if decision == 'BUY':
                # Place small buy order ($1)
                order_size = min(1.0, self.available_balance * 0.8)
                result = await self.place_order(coin['symbol'], 'buy', order_size)
                
                if result:
                    logger.info(f"🤖 AUTO-TRADE: BOUGHT {coin['symbol']} for ${order_size:.2f}")
                    self.available_balance -= order_size
                    trades_made += 1
            
            elif decision == 'SELL':
                # Place small sell order ($1 worth)
                price = coin['price']
                amount = 1.0 / price  # $1 worth
                result = await self.place_order(coin['symbol'], 'sell', amount)
                
                if result:
                    logger.info(f"🤖 AUTO-TRADE: SOLD {coin['symbol']} (${amount:.6f} coins)")
                    trades_made += 1
        
        # Update balance after trades
        await self.get_account_balances()
        logger.info(f"✅ Auto-trading completed - {trades_made} trades made")
    
    async def get_market_tickers(self) -> List[dict]:
        """Get market tickers - focus on micro-caps under $0.10"""
        try:
            tickers_data = await self.make_request('GET', '/api/v4/spot/tickers')
            if tickers_data:
                # Filter for USDT pairs and micro-caps
                micro_tickers = []
                total_tickers = 0
                
                for ticker in tickers_data:
                    symbol = ticker['currency_pair']
                    if symbol.endswith('_USDT'):
                        total_tickers += 1
                        price = float(ticker['last'])
                        
                        # Focus on micro-caps (under $0.10)
                        if 0.001 <= price <= 0.10:  # Micro-cap range
                            change = float(ticker['change_percentage']) / 100
                            volume = float(ticker['base_volume'])
                            
                            micro_tickers.append({
                                'symbol': symbol.replace('_USDT', ''),
                                'price': price,
                                'change': change,
                                'volume': volume,
                                'volume_usdt': volume * price
                            })
                
                # Sort by price (cheapest first) and by volume
                micro_tickers.sort(key=lambda x: (x['price'], -x['volume_usdt']))
                
                logger.info(f"📊 Found {len(micro_tickers)} micro-caps under $0.10 (out of {total_tickers} total)")
                
                # Log top 10 cheapest
                for i, ticker in enumerate(micro_tickers[:10]):
                    logger.info(f"  {i+1}. {ticker['symbol']}: ${ticker['price']:.6f} ({ticker['change']*100:+.2f}%)")
                
                return micro_tickers
            return []
        
        except Exception as e:
            logger.error(f"Error getting tickers: {e}")
            return []
    
    async def place_order(self, symbol: str, side: str, amount: float, price: float = None) -> dict:
        """Place real order"""
        try:
            order_data = {
                'currency_pair': f"{symbol}_USDT",
                'type': 'market',
                'side': side,
                'amount': str(amount)
            }
            
            if price:
                order_data['price'] = str(price)
                order_data['type'] = 'limit'
            
            result = await self.make_request('POST', '/api/v4/spot/orders', order_data)
            
            if result and 'id' in result:
                logger.info(f"✅ Order placed: {side} {symbol} - Amount: {amount} - ID: {result['id']}")
                return result
            else:
                logger.error(f"❌ Order failed: {result}")
                return {}
        
        except Exception as e:
            logger.error(f"Error placing order: {e}")
            return {}
    
    async def get_active_orders(self) -> List[dict]:
        """Get active orders"""
        try:
            orders_data = await self.make_request('GET', '/api/v4/spot/orders')
            if orders_data:
                active_orders = [order for order in orders_data if order['status'] == 'open']
                return active_orders
            return []
        
        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            return []

class SimpleBotUI:
    """Simple UI for the Gate.io bot"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Gate.io Trading Bot - Real Account")
        self.root.geometry("1000x700")
        self.root.configure(bg='#f0f0f0')
        
        # Initialize bot
        self.bot = SimpleGateioBot()
        self.running = False
        
        # Create UI
        self.create_widgets()
        
        # Initialize bot in background
        threading.Thread(target=self.initialize_bot, daemon=True).start()
        
        # Start update loop
        self.update_ui()
    
    def create_widgets(self):
        """Create UI widgets"""
        # Title with status
        title_frame = tk.Frame(self.root, bg='#f0f0f0')
        title_frame.pack(fill=tk.X, padx=20, pady=(10, 5))
        
        title_label = tk.Label(title_frame, text="🚀 GATE.IO TRADING BOT - REAL ACCOUNT", 
                               font=('Arial', 16, 'bold'), bg='#f0f0f0', fg='#2ecc71')
        title_label.pack(side=tk.LEFT)
        
        # Status indicators
        status_frame = tk.Frame(title_frame, bg='#f0f0f0')
        status_frame.pack(side=tk.RIGHT, padx=10)
        
        self.gateio_status_label = tk.Label(status_frame, text="🔌 GATE.IO: CHECKING...", 
                                           font=('Arial', 10, 'bold'), bg='#f0f0f0', fg='#f39c12')
        self.gateio_status_label.pack()
        
        self.ollama_status_label = tk.Label(status_frame, text="🤖 OLLAMA: CHECKING...", 
                                           font=('Arial', 10, 'bold'), bg='#f0f0f0', fg='#9b59b6')
        self.ollama_status_label.pack()
        
        # Account info frame
        account_frame = tk.LabelFrame(self.root, text="💰 Account Information", 
                                     font=('Arial', 12, 'bold'), bg='#f0f0f0')
        account_frame.pack(fill=tk.X, padx=20, pady=5)
        
        self.balance_label = tk.Label(account_frame, text="Loading balance...", 
                                     font=('Arial', 14), bg='#f0f0f0', fg='#3498db')
        self.balance_label.pack(pady=5)
        
        self.available_label = tk.Label(account_frame, text="Available: $0.00", 
                                       font=('Arial', 12), bg='#f0f0f0', fg='#27ae60')
        self.available_label.pack(pady=5)
        
        # Main content
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        # Left panel - Tickers with export functionality
        left_frame = tk.LabelFrame(main_frame, text="📊 Micro-Cap Tickers", 
                                  font=('Arial', 12, 'bold'), bg='#f0f0f0')
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Export buttons
        export_frame = tk.Frame(left_frame, bg='#f0f0f0')
        export_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Button(export_frame, text="📋 COPY LIST", command=self.copy_coin_list,
                 bg='#3498db', fg='white', font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        tk.Button(export_frame, text="💾 SAVE CSV", command=self.save_coin_list,
                 bg='#27ae60', fg='white', font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        tk.Button(export_frame, text="📄 SAVE TXT", command=self.save_coin_list_txt,
                 bg='#e67e22', fg='white', font=('Arial', 9, 'bold')).pack(side=tk.LEFT, padx=2)
        
        self.tickers_tree = ttk.Treeview(left_frame, columns=('Price', 'Change', 'Volume'), 
                                        show='tree headings', height=15)
        self.tickers_tree.heading('#0', text='Symbol')
        self.tickers_tree.heading('Price', text='Price')
        self.tickers_tree.heading('Change', text='Change %')
        self.tickers_tree.heading('Volume', text='Volume')
        
        self.tickers_tree.column('#0', width=100)
        self.tickers_tree.column('Price', width=80)
        self.tickers_tree.column('Change', width=80)
        self.tickers_tree.column('Volume', width=100)
        
        self.tickers_tree.pack(padx=10, pady=5)
        
        # Right panel - Orders & Log
        right_frame = tk.Frame(main_frame, bg='#f0f0f0')
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Orders
        orders_frame = tk.LabelFrame(right_frame, text="📋 Active Orders", 
                                    font=('Arial', 12, 'bold'), bg='#f0f0f0')
        orders_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.orders_text = tk.Text(orders_frame, height=6, width=40, 
                                  bg='#2c3e50', fg='#ecf0f1', font=('Courier', 9))
        self.orders_text.pack(padx=10, pady=10)
        
        # Ollama decisions
        ollama_frame = tk.LabelFrame(right_frame, text="🤖 OLLAMA DECISIONS", 
                                    font=('Arial', 12, 'bold'), bg='#f0f0f0')
        ollama_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.ollama_text = tk.Text(ollama_frame, height=6, width=40, 
                                  bg='#2c3e50', fg='#e74c3c', font=('Courier', 9))
        self.ollama_text.pack(padx=10, pady=10)
        
        # Activity log
        log_frame = tk.LabelFrame(right_frame, text="📝 Activity Log", 
                                 font=('Arial', 12, 'bold'), bg='#f0f0f0')
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=40, 
                                                 bg='#2c3e50', fg='#ecf0f1', font=('Courier', 9))
        self.log_text.pack(padx=10, pady=10)
        
        # Control panel
        control_frame = tk.Frame(self.root, bg='#f0f0f0')
        control_frame.pack(fill=tk.X, padx=20, pady=5)
        
        # Test connection button
        self.test_button = tk.Button(control_frame, text="🔍 TEST CONNECTION", 
                                    command=self.test_connections,
                                    bg='#3498db', fg='white', font=('Arial', 10, 'bold'),
                                    width=15, height=2)
        self.test_button.pack(side=tk.LEFT, padx=5)
        
        # Refresh balance button
        self.refresh_button = tk.Button(control_frame, text="🔄 REFRESH BALANCE", 
                                       command=self.refresh_balance,
                                       bg='#f39c12', fg='white', font=('Arial', 10, 'bold'),
                                       width=15, height=2)
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Trading buttons
        self.buy_button = tk.Button(control_frame, text="💚 BUY Selected", 
                                    command=self.buy_selected,
                                    bg='#27ae60', fg='white', font=('Arial', 10, 'bold'),
                                    width=15, height=2)
        self.buy_button.pack(side=tk.LEFT, padx=5)
        
        self.sell_button = tk.Button(control_frame, text="❤️ SELL Selected", 
                                     command=self.sell_selected,
                                     bg='#e74c3c', fg='white', font=('Arial', 10, 'bold'),
                                     width=15, height=2)
        self.sell_button.pack(side=tk.LEFT, padx=5)
        
        self.auto_trade_button = tk.Button(control_frame, text="🤖 AUTO-TRADE", 
                                          command=self.start_auto_trading,
                                          bg='#9b59b6', fg='white', font=('Arial', 10, 'bold'),
                                          width=15, height=2)
        self.auto_trade_button.pack(side=tk.LEFT, padx=5)
        
        # Store current tickers for export
        self.current_tickers = []
        
        self.log_activity("🚀 Gate.io Bot initialized")
        self.log_activity("🔌 Connecting to real account...")
    
    def copy_coin_list(self):
        """Copy coin list to clipboard"""
        if not self.current_tickers:
            messagebox.showwarning("No Data", "No coin data to copy")
            return
        
        # Format coin list
        coin_text = "Symbol,Price,Change%,Volume_USDT\n"
        for ticker in self.current_tickers:
            coin_text += f"{ticker['symbol']},${ticker['price']:.6f},{ticker['change']*100:+.2f}%,${ticker['volume_usdt']:.0f}\n"
        
        # Copy to clipboard
        self.root.clipboard_clear()
        self.root.clipboard_append(coin_text)
        self.log_activity(f"📋 Copied {len(self.current_tickers)} coins to clipboard")
        messagebox.showinfo("Success", f"Copied {len(self.current_tickers)} coins to clipboard!")
    
    def save_coin_list(self):
        """Save coin list as CSV"""
        if not self.current_tickers:
            messagebox.showwarning("No Data", "No coin data to save")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            initialfile=f"micro_caps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write("Symbol,Price,Change%,Volume_USDT\n")
                    for ticker in self.current_tickers:
                        f.write(f"{ticker['symbol']},${ticker['price']:.6f},{ticker['change']*100:+.2f}%,${ticker['volume_usdt']:.0f}\n")
                
                self.log_activity(f"💾 Saved {len(self.current_tickers)} coins to {filename}")
                messagebox.showinfo("Success", f"Saved {len(self.current_tickers)} coins to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")
    
    def save_coin_list_txt(self):
        """Save coin list as TXT"""
        if not self.current_tickers:
            messagebox.showwarning("No Data", "No coin data to save")
            return
        
        from tkinter import filedialog
        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"micro_caps_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(f"MICRO-CAP COINS LIST - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("="*60 + "\n\n")
                    
                    pumps = [t for t in self.current_tickers if t['change'] > 0.05]
                    dumps = [t for t in self.current_tickers if t['change'] < -0.05]
                    
                    f.write(f"📊 TOTAL: {len(self.current_tickers)} micro-caps under $0.10\n")
                    f.write(f"🚀 PUMPS (5%+): {len(pumps)}\n")
                    f.write(f"📉 DUMPS (-5%+): {len(dumps)}\n\n")
                    
                    f.write("TOP 50 CHEAPEST:\n")
                    f.write("-"*60 + "\n")
                    for i, ticker in enumerate(self.current_tickers[:50]):
                        f.write(f"{i+1:2d}. {ticker['symbol']:8s} ${ticker['price']:.6f} {ticker['change']*100:+6.2f}% Vol:${ticker['volume_usdt']:8.0f}\n")
                
                self.log_activity(f"📄 Saved {len(self.current_tickers)} coins to {filename}")
                messagebox.showinfo("Success", f"Saved {len(self.current_tickers)} coins to {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")
    
    def test_connections(self):
        """Test Gate.io and Ollama connections"""
        self.log_activity("🔍 Testing connections...")
        
        # Test Gate.io connection in background
        threading.Thread(target=self.test_gateio_connection, daemon=True).start()
        
        # Test Ollama connection
        self.test_ollama_connection()
    
    def test_gateio_connection(self):
        """Test Gate.io API connection"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            success = loop.run_until_complete(self.bot.get_account_balances())
            
            if success:
                self.root.after(0, lambda: self.gateio_status_label.config(text="🔌 GATE.IO: ✅ CONNECTED", fg='#27ae60'))
                self.root.after(0, lambda: self.log_activity("✅ Gate.io connection successful"))
                self.root.after(0, self.update_balance_display)
            else:
                self.root.after(0, lambda: self.gateio_status_label.config(text="🔌 GATE.IO: ❌ FAILED", fg='#e74c3c'))
                self.root.after(0, lambda: self.log_activity("❌ Gate.io connection failed"))
        
        except Exception as e:
            self.root.after(0, lambda: self.gateio_status_label.config(text="🔌 GATE.IO: ❌ ERROR", fg='#e74c3c'))
            self.root.after(0, lambda: self.log_activity(f"❌ Gate.io error: {e}"))
    
    def test_ollama_connection(self):
        """Test Ollama connection"""
        try:
            response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [m['name'] for m in models]
                self.ollama_status_label.config(text=f"🤖 OLLAMA: ✅ READY ({len(models)} models)", fg='#27ae60')
                self.log_activity(f"✅ Ollama connected - Models: {model_names}")
            else:
                self.ollama_status_label.config(text="🤖 OLLAMA: ❌ OFFLINE", fg='#e74c3c')
                self.log_activity("❌ Ollama not responding")
        except Exception as e:
            self.ollama_status_label.config(text="🤖 OLLAMA: ❌ ERROR", fg='#e74c3c')
            self.log_activity(f"❌ Ollama error: {e}")
    
    def refresh_balance(self):
        """Refresh account balance"""
        self.log_activity("🔄 Refreshing balance...")
        threading.Thread(target=self.test_gateio_connection, daemon=True).start()
    
    def start_auto_trading(self):
        """Start automatic trading with Ollama"""
        if not self.bot.ollama_connected:
            messagebox.showwarning("Ollama Not Connected", 
                                  "Please start Ollama first: 'ollama serve'")
            return
        
        if self.bot.total_usdt_balance < 1.0:
            messagebox.showwarning("Insufficient Balance", 
                                  f"Need at least $1.00 to trade. Current balance: ${self.bot.total_usdt_balance:.2f}")
            return
        
        self.log_activity("🤖 Starting AUTO-TRADING with Ollama...")
        threading.Thread(target=self.auto_trading_loop, daemon=True).start()
    
    def auto_trading_loop(self):
        """Auto-trading loop with your micro-cap coins"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            # Run auto-trade with your 1000 coins
            loop.run_until_complete(self.bot.auto_trade_with_micro_caps())
            
            # Update UI
            self.root.after(0, self.update_balance_display)
            self.root.after(0, lambda: self.log_activity("✅ Auto-trading cycle completed"))
            
        except Exception as e:
            self.root.after(0, lambda: self.log_activity(f"❌ Auto-trading error: {e}"))
    
    def update_tickers_display(self, tickers):
        """Update tickers display with your micro-cap coins"""
        # Use your micro-cap coins instead of API data
        display_coins = self.bot.micro_caps[:100]  # Show top 100
        
        # Store current tickers for export
        self.current_tickers = display_coins
        
        # Clear existing items
        for item in self.tickers_tree.get_children():
            self.tickers_tree.delete(item)
        
        # Add your coins with color coding
        for ticker in display_coins:
            # Color based on price change
            change_pct = ticker['change'] * 100
            if change_pct > 5:
                tag = 'pump'
            elif change_pct > 0:
                tag = 'green'
            elif change_pct < -5:
                tag = 'dump'
            else:
                tag = 'red'
            
            # Format display
            price_str = f"${ticker['price']:.6f}"
            change_str = f"{change_pct:+.2f}%"
            volume_str = f"${ticker.get('volume', 0):.0f}"
            
            self.tickers_tree.insert('', 'end', text=ticker['symbol'],
                                    values=(price_str, change_str, volume_str),
                                    tags=(tag,))
        
        # Configure tags for colors
        self.tickers_tree.tag_configure('pump', foreground='#ff6b6b', background='#ffe0e0')
        self.tickers_tree.tag_configure('green', foreground='#51cf66')
        self.tickers_tree.tag_configure('red', foreground='#ff6b6b')
        self.tickers_tree.tag_configure('dump', foreground='#c92a2a', background='#ffe0e0')
        
        # Log summary
        if display_coins:
            pumps = [t for t in display_coins if t['change'] > 0.05]  # 5%+ pumps
            dumps = [t for t in display_coins if t['change'] < -0.05]  # 5%+ dumps
            
            self.log_activity(f"📊 Displaying {len(display_coins)} micro-caps from your list")
            if pumps:
                self.log_activity(f"🚀 {len(pumps)} pumps detected (5%+)")
            if dumps:
                self.log_activity(f"📉 {len(dumps)} dumps detected (-5%+)")
    
    def log_ollama_decision(self, symbol: str, decision: str):
        """Log Ollama decision to UI"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ollama_text.insert(tk.END, f"[{timestamp}] {symbol}: {decision}\n")
        self.ollama_text.see(tk.END)
    
    def initialize_bot(self):
        """Initialize bot connection - USING GATE.IO SDK ONLY"""
        # Update status to checking
        self.gateio_status_label.config(text="🔌 GATE.IO: CHECKING...", fg='#f39c12')
        
        # Use the Gate.io SDK directly - no asyncio needed for SDK calls
        try:
            success = self.bot.get_account_balances_sync()
            
            if success:
                self.gateio_status_label.config(text="🔌 GATE.IO: ✅ CONNECTED", fg='#27ae60')
                self.update_balance_display()
                self.log_activity(f"✅ Connected! REAL Balance: ${self.bot.total_usdt_balance:.2f}")
            else:
                self.gateio_status_label.config(text="🔌 GATE.IO: ❌ FAILED", fg='#e74c3c')
                self.log_activity("❌ Failed to connect to account")
        except Exception as e:
            self.gateio_status_label.config(text="🔌 GATE.IO: ❌ ERROR", fg='#e74c3c')
            self.log_activity(f"❌ Connection error: {e}")
        
        # Update Ollama status
        if self.bot.ollama_connected:
            self.ollama_status_label.config(text="🤖 OLLAMA: ✅ READY", fg='#27ae60')
            self.log_activity("🤖 Ollama connected and ready")
        else:
            self.ollama_status_label.config(text="🤖 OLLAMA: ❌ OFFLINE", fg='#e74c3c')
            self.log_activity("❌ Ollama not connected - click 'TEST CONNECTION'")
    
    def update_balance_display(self):
        """Update balance display"""
        self.balance_label.config(text=f"Total USDT: ${self.bot.total_usdt_balance:.2f}")
        self.available_label.config(text=f"Available USDT: ${self.bot.available_balance:.2f}")
        
        # Show other currencies in log
        for key, balance in self.bot.account_balances.items():
            if balance['currency'] != 'USDT' and balance['total'] > 0:
                self.log_activity(f"🪙 {balance['currency']}: {balance['total']:.6f}")
    
    def log_activity(self, message):
        """Log activity"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        logger.info(message)
    
    def refresh_data(self):
        """Refresh all data"""
        threading.Thread(target=self.refresh_data_thread, daemon=True).start()
    
    def refresh_data_thread(self):
        """Refresh data in background"""
        # Show scanning status
        self.root.after(0, lambda: self.status_label.config(text="🔍 SCANNING...", fg='#f39c12'))
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Get fresh data
        loop.run_until_complete(self.bot.get_account_balances())
        tickers = loop.run_until_complete(self.bot.get_market_tickers())
        orders = loop.run_until_complete(self.bot.get_active_orders())
        
        # Update UI
        self.root.after(0, lambda: self.update_balance_display())
        self.root.after(0, lambda: self.update_tickers_display(tickers))
        self.root.after(0, lambda: self.update_orders_display(orders))
        
        # Reset status to connected
        self.root.after(0, lambda: self.status_label.config(text="✅ CONNECTED", fg='#27ae60'))
        
        self.log_activity("🔄 Data refreshed")
    
    def update_tickers_display(self, tickers):
        """Update tickers display"""
        # Store current tickers for export
        self.current_tickers = tickers
        
        # Clear existing items
        for item in self.tickers_tree.get_children():
            self.tickers_tree.delete(item)
        
        # Add tickers with color coding
        for ticker in tickers:
            # Color based on price change
            change_pct = ticker['change'] * 100
            if change_pct > 5:
                tag = 'pump'
            elif change_pct > 0:
                tag = 'green'
            elif change_pct < -5:
                tag = 'dump'
            else:
                tag = 'red'
            
            # Format display
            price_str = f"${ticker['price']:.6f}"
            change_str = f"{change_pct:+.2f}%"
            volume_str = f"${ticker['volume_usdt']:.0f}"
            
            self.tickers_tree.insert('', 'end', text=ticker['symbol'],
                                    values=(price_str, change_str, volume_str),
                                    tags=(tag,))
        
        # Configure tags for colors
        self.tickers_tree.tag_configure('pump', foreground='#ff6b6b', background='#ffe0e0')
        self.tickers_tree.tag_configure('green', foreground='#51cf66')
        self.tickers_tree.tag_configure('red', foreground='#ff6b6b')
        self.tickers_tree.tag_configure('dump', foreground='#c92a2a', background='#ffe0e0')
        
        # Log summary
        if tickers:
            pumps = [t for t in tickers if t['change'] > 0.05]  # 5%+ pumps
            dumps = [t for t in tickers if t['change'] < -0.05]  # 5%+ dumps
            
            self.log_activity(f"📊 {len(tickers)} micro-caps loaded")
            if pumps:
                self.log_activity(f"🚀 {len(pumps)} pumps detected (5%+)")
            if dumps:
                self.log_activity(f"📉 {len(dumps)} dumps detected (-5%+)")
    
    def update_orders_display(self, orders):
        """Update orders display"""
        self.orders_text.delete(1.0, tk.END)
        
        if orders:
            for order in orders:
                order_info = f"{order['side']} {order['currency_pair']}\n"
                order_info += f"Amount: {order['amount']}\n"
                order_info += f"Price: {order.get('price', 'Market')}\n"
                order_info += f"Status: {order['status']}\n"
                order_info += "-" * 30 + "\n"
                self.orders_text.insert(tk.END, order_info)
        else:
            self.orders_text.insert(tk.END, "No active orders")
    
    def buy_selected(self):
        """Buy selected ticker"""
        selection = self.tickers_tree.selection()
        if selection:
            item = self.tickers_tree.item(selection[0])
            symbol = item['text']
            
            # Place small buy order ($1 worth)
            threading.Thread(target=self.place_order_thread, args=(symbol, 'buy', 1.0), daemon=True).start()
        else:
            messagebox.showwarning("No Selection", "Please select a ticker to buy")
    
    def sell_selected(self):
        """Sell selected ticker"""
        selection = self.tickers_tree.selection()
        if selection:
            item = self.tickers_tree.item(selection[0])
            symbol = item['text']
            
            # Place small sell order ($1 worth)
            threading.Thread(target=self.place_order_thread, args=(symbol, 'sell', 1.0), daemon=True).start()
        else:
            messagebox.showwarning("No Selection", "Please select a ticker to sell")
    
    def place_order_thread(self, symbol: str, side: str, amount: float):
        """Place order in background"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(self.bot.place_order(symbol, side, amount))
        
        if result:
            self.root.after(0, lambda: self.log_activity(f"✅ {side.upper()} order placed for {symbol}"))
        else:
            self.root.after(0, lambda: self.log_activity(f"❌ Failed to place {side} order for {symbol}"))
    
    def update_ui(self):
        """Update UI periodically - CONTINUOUS SCANNING"""
        if self.bot.total_usdt_balance > 0:
            # Continuous refresh every 10 seconds
            threading.Thread(target=self.refresh_data_thread, daemon=True).start()
            self.log_activity("🔄 Continuous scanning active...")
        
        # Schedule next update (every 10 seconds for continuous scanning)
        self.root.after(10000, self.update_ui)
    
    def run(self):
        """Run the UI"""
        self.root.mainloop()

def main():
    """Main function"""
    print("🚀 SIMPLE GATE.IO TRADING BOT")
    print("="*50)
    print("💰 Real Account Connection")
    print("📊 Shows Actual Balance")
    print("⚡ Places Real Orders")
    print("="*50)
    
    ui = SimpleBotUI()
    ui.run()

if __name__ == "__main__":
    main()
