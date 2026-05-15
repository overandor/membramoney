#!/usr/bin/env python3
"""
Gate.io API Client for Hedging Project
Handles all API communications with proper error handling
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

class GateIOClient:
    """Professional Gate.io API client"""
    
    def __init__(self):
        self.api_key = os.getenv("GATE_API_KEY", "")
        self.api_secret = os.getenv("GATE_API_SECRET", "")
        self.base_url = "https://api.gateio.ws/api/v4"
        self.settle = "usdt"
        self.logger = logging.getLogger('GateIOClient')
        
        if not self.api_key or not self.api_secret:
            self.logger.warning("⚠️  API keys not configured - using public endpoints only")
    
    def _sign_request(self, method: str, path: str, query_string: str, payload: str) -> Dict[str, str]:
        """Generate Gate.io API signature"""
        if not self.api_secret:
            return {}
        
        ts = str(int(time.time()))
        payload_hash = hashlib.sha512(payload.encode('utf-8')).hexdigest()
        sign_str = f"{method.upper()}\n{path}\n{query_string}\n{payload_hash}\n{ts}"
        sign = hmac.new(
            self.api_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            digestmod=hashlib.sha512,
        ).hexdigest()
        
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "KEY": self.api_key,
            "Timestamp": ts,
            "SIGN": sign,
        }
    
    def _make_request(self, method: str, path: str, payload: str = "", private: bool = False) -> APIResult:
        """Make API request with error handling"""
        headers = self._sign_request(method, path, "", payload) if private else {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        try:
            url = f"{self.base_url}{path}"
            response = requests.request(
                method, 
                url, 
                headers=headers, 
                data=payload if payload else None, 
                timeout=10
            )
            
            if response.status_code == 200:
                return APIResult(success=True, data=response.json())
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                self.logger.error(f"API Error: {error_msg}")
                return APIResult(success=False, error=error_msg)
                
        except requests.exceptions.Timeout:
            error_msg = "Request timeout"
            self.logger.error(error_msg)
            return APIResult(success=False, error=error_msg)
        except requests.exceptions.ConnectionError:
            error_msg = "Connection error"
            self.logger.error(error_msg)
            return APIResult(success=False, error=error_msg)
        except Exception as e:
            error_msg = f"Request exception: {str(e)}"
            self.logger.error(error_msg)
            return APIResult(success=False, error=error_msg)
    
    def get_best_bid_ask(self, symbol: str) -> tuple:
        """Get best bid and ask prices"""
        result = self.get_order_book(symbol, 1)
        
        if result.success and result.data:
            data = result.data
            if data.get('asks') and data.get('bids'):
                best_bid = float(data['bids'][0]['p'])
                best_ask = float(data['asks'][0]['p'])
                return best_bid, best_ask
        
        return None, None
    
    def get_order_book(self, symbol: str, limit: int = 10) -> APIResult:
        """Get order book"""
        return self._make_request("GET", f"/futures/{self.settle}/order_book?contract={symbol}&limit={limit}")
    
    def get_positions(self) -> APIResult:
        """Get current positions"""
        return self._make_request("GET", f"/futures/{self.settle}/positions", "", private=True)
    
    def place_order(self, symbol: str, side: str, size: float, price: float = 0, 
                   order_type: str = "limit", tif: str = "ioc") -> APIResult:
        """Place order"""
        order_data = {
            "settle": self.settle,
            "contract": symbol,
            "size": str(size),
            "price": str(price),
            "type": order_type,
            "tif": tif
        }
        
        payload = json.dumps(order_data, separators=(",", ":"))
        return self._make_request("POST", f"/futures/{self.settle}/orders", payload, private=True)
    
    def cancel_order(self, order_id: str) -> APIResult:
        """Cancel order"""
        return self._make_request("DELETE", f"/futures/{self.settle}/orders/{order_id}", "", private=True)
    
    def get_account(self) -> APIResult:
        """Get account information"""
        return self._make_request("GET", f"/futures/{self.settle}/accounts", "", private=True)
    
    def get_contracts(self) -> APIResult:
        """Get available contracts"""
        return self._make_request("GET", f"/futures/{self.settle}/contracts")
    
    def calculate_nominal_size(self, price: float, target_nominal: float) -> float:
        """Calculate order size for target nominal value"""
        size = target_nominal / price
        min_size = 0.001  # Gate.io minimum
        return max(size, min_size)
