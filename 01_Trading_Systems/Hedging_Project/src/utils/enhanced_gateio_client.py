#!/usr/bin/env python3
"""
Enhanced Gate.io API Client with proper connection and AI integration
"""

import os
import time
import json
import requests
import hmac
import hashlib
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

@dataclass
class APIResult:
    success: bool
    data: Any = None
    error: str = None

class EnhancedGateIOClient:
    """Enhanced Gate.io API client with proper connection handling"""
    
    def __init__(self):
        # Load environment variables
        self.api_key = os.getenv("GATE_API_KEY", "")
        self.api_secret = os.getenv("GATE_API_SECRET", "")
        self.openrouter_key = os.getenv("OPENROUTER_API_KEY", "")
        
        self.base_url = "https://api.gateio.ws/api/v4"
        self.settle = "usdt"
        self.logger = logging.getLogger('EnhancedGateIOClient')
        
        # Validate API keys
        self._validate_keys()
        
        # Session for connection pooling
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'HedgingProject/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        self.logger.info("🔗 Enhanced Gate.io Client initialized")
        self.logger.info(f"🔑 API Key configured: {'✅' if self.api_key else '❌'}")
        self.logger.info(f"🤖 OpenRouter configured: {'✅' if self.openrouter_key else '❌'}")
    
    def _validate_keys(self):
        """Validate API keys are present and properly formatted"""
        if not self.api_key:
            self.logger.error("❌ GATE_API_KEY not found in environment")
        elif len(self.api_key) < 10:
            self.logger.error("❌ GATE_API_KEY appears too short")
        else:
            self.logger.info(f"✅ GATE_API_KEY: {self.api_key[:8]}...")
        
        if not self.api_secret:
            self.logger.error("❌ GATE_API_SECRET not found in environment")
        elif len(self.api_secret) < 20:
            self.logger.error("❌ GATE_API_SECRET appears too short")
        else:
            self.logger.info(f"✅ GATE_API_SECRET: {self.api_secret[:8]}...")
        
        if not self.openrouter_key:
            self.logger.warning("⚠️  OPENROUTER_API_KEY not found - AI features disabled")
        else:
            self.logger.info(f"✅ OPENROUTER_API_KEY: {self.openrouter_key[:12]}...")
    
    def _sign_request(self, method: str, path: str, query_string: str, payload: str) -> Dict[str, str]:
        """Generate Gate.io API signature with proper format"""
        if not self.api_key or not self.api_secret:
            raise ValueError("API keys not configured for private endpoints")
        
        ts = str(int(time.time()))
        payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        
        # Gate.io v4 signature format
        sign_str = f"{method.upper()}\n{path}\n{query_string}\n{payload_hash}\n{ts}"
        
        sign = hmac.new(
            self.api_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            digestmod=hashlib.sha512,
        ).hexdigest()
        
        return {
            "KEY": self.api_key,
            "Timestamp": ts,
            "SIGN": sign,
        }
    
    def _make_request(self, method: str, path: str, payload: str = "", private: bool = False) -> APIResult:
        """Make API request with enhanced error handling"""
        url = f"{self.base_url}{path}"
        
        # Prepare headers
        headers = {}
        if private:
            try:
                headers.update(self._sign_request(method, path, "", payload))
            except ValueError as e:
                return APIResult(success=False, error=str(e))
        
        try:
            self.logger.debug(f"📡 {method} {url} (private: {private})")
            
            response = self.session.request(
                method, 
                url, 
                headers=headers,
                data=payload if payload else None,
                timeout=15
            )
            
            self.logger.debug(f"📥 Response: {response.status_code}")
            
            if response.status_code == 200:
                return APIResult(success=True, data=response.json())
            elif response.status_code == 401:
                error_msg = "Authentication failed - check API keys"
                self.logger.error(f"❌ {error_msg}")
                return APIResult(success=False, error=error_msg)
            elif response.status_code == 403:
                error_msg = "Access forbidden - insufficient permissions"
                self.logger.error(f"❌ {error_msg}")
                return APIResult(success=False, error=error_msg)
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                self.logger.error(f"❌ {error_msg}")
                return APIResult(success=False, error=error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout (15s)"
            self.logger.error(f"❌ {error_msg}")
            return APIResult(success=False, error=error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error - check internet"
            self.logger.error(f"❌ {error_msg}")
            return APIResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Request exception: {str(e)}"
            self.logger.error(f"❌ {error_msg}")
            return APIResult(success=False, error=error_msg)
    
    def test_connection(self) -> APIResult:
        """Test connection to Gate.io API"""
        self.logger.info("🔍 Testing Gate.io connection...")
        
        # Test public endpoint
        contracts = self._make_request("GET", f"/futures/{self.settle}/contracts")
        if not contracts.success:
            return APIResult(success=False, error=f"Public endpoint failed: {contracts.error}")
        
        # Test private endpoint if keys are available
        if self.api_key and self.api_secret:
            account = self._make_request("GET", f"/futures/{self.settle}/accounts", "", private=True)
            if not account.success:
                return APIResult(success=False, error=f"Private endpoint failed: {account.error}")
            
            balance = float(account.data.get('total', 0))
            self.logger.info(f"💰 Account balance: ${balance:.2f}")
        
        return APIResult(success=True, data={
            'contracts_count': len(contracts.data),
            'api_keys_configured': bool(self.api_key and self.api_secret)
        })
    
    def get_best_bid_ask(self, symbol: str) -> tuple:
        """Get best bid and ask prices"""
        result = self._make_request("GET", f"/futures/{self.settle}/order_book?contract={symbol}&limit=1")
        
        if result.success and result.data:
            data = result.data
            if data.get('asks') and data.get('bids'):
                best_bid = float(data['bids'][0]['p'])
                best_ask = float(data['asks'][0]['p'])
                return best_bid, best_ask
        
        return None, None
    
    def get_positions(self) -> APIResult:
        """Get current positions"""
        return self._make_request("GET", f"/futures/{self.settle}/positions", "", private=True)
    
    def place_order(self, symbol: str, side: str, size: float, price: float = 0, 
                   order_type: str = "limit", tif: str = "ioc") -> APIResult:
        """Place order with enhanced validation"""
        # Validate parameters
        if side not in ["BUY", "SELL"]:
            return APIResult(success=False, error="Invalid side: must be BUY or SELL")
        
        if size <= 0:
            return APIResult(success=False, error="Size must be positive")
        
        if order_type not in ["limit", "market"]:
            return APIResult(success=False, error="Invalid order type")
        
        order_data = {
            "settle": self.settle,
            "contract": symbol,
            "size": str(size),
            "price": str(price),
            "type": order_type,
            "tif": tif
        }
        
        payload = json.dumps(order_data, separators=(",", ":"))
        self.logger.info(f"🎯 Placing {side} order: {size:.6f} {symbol} @ ${price:.6f}")
        
        result = self._make_request("POST", f"/futures/{self.settle}/orders", payload, private=True)
        
        if result.success:
            order_id = result.data.get('id')
            self.logger.info(f"✅ Order placed successfully: {order_id}")
        else:
            self.logger.error(f"❌ Order failed: {result.error}")
        
        return result
    
    def get_account(self) -> APIResult:
        """Get account information"""
        return self._make_request("GET", f"/futures/{self.settle}/accounts", "", private=True)
    
    def get_contracts(self) -> APIResult:
        """Get available contracts"""
        return self._make_request("GET", f"/futures/{self.settle}/contracts")
    
    def calculate_nominal_size(self, price: float, target_nominal: float) -> float:
        """Calculate order size for target nominal value"""
        if price <= 0:
            raise ValueError("Price must be positive")
        
        size = target_nominal / price
        min_size = 0.001  # Gate.io minimum
        return max(size, min_size)
    
    def get_ai_decision(self, market_data: Dict) -> Dict:
        """Get AI trading decision from OpenRouter"""
        if not self.openrouter_key:
            return {
                "action": "HOLD",
                "symbol": "ENA_USDT",
                "confidence": 0.5,
                "reasoning": "AI disabled - no OpenRouter API key"
            }
        
        try:
            headers = {
                "Authorization": f"Bearer {self.openrouter_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/alep/hedging-project",
                "X-Title": "Hedging AI"
            }
            
            prompt = f"""
            Analyze these market conditions for hedging opportunities:
            
            Market Data: {json.dumps(market_data, indent=2)}
            Time: {time.strftime('%Y-%m-%d %H:%M:%S')}
            
            Strategy: Place best bid/ask orders, take profits at 0.2%
            
            Return JSON: {{"action": "BUY/SELL/HOLD", "symbol": "SYMBOL", "confidence": 0.0-1.0, "reasoning": "explanation"}}
            """
            
            data = {
                "model": "anthropic/claude-3-haiku",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.3
            }
            
            response = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result["choices"][0]["message"]["content"]
                
                # Parse JSON response
                if "```json" in content:
                    json_str = content.split("```json")[1].split("```")[0].strip()
                else:
                    json_str = content.strip()
                
                decision = json.loads(json_str)
                self.logger.info(f"🤖 AI Decision: {decision['action']} (confidence: {decision['confidence']:.2f})")
                return decision
            else:
                self.logger.error(f"❌ AI API error: {response.status_code}")
                return {"action": "HOLD", "confidence": 0.5, "reasoning": f"API error: {response.status_code}"}
                
        except Exception as e:
            self.logger.error(f"❌ AI exception: {str(e)}")
            return {"action": "HOLD", "confidence": 0.5, "reasoning": f"Exception: {str(e)}"}
