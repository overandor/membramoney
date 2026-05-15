#!/usr/bin/env python3
"""
SIMPLE SOLANA RPC ROTATOR
Synchronous version for Flask compatibility
"""

import json
import time
import logging
import requests
import random
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

# Solana RPC endpoints
RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-api.projectserum.com",
    "https://rpc.ankr.com/solana",
    "https://solana-mainnet.rpc.extrnode.com",
    "https://api.devnet.solana.com",
]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EndpointStatus(Enum):
    HEALTHY = "healthy"
    FAILED = "failed"
    UNKNOWN = "unknown"

@dataclass
class RPCEndpoint:
    """RPC endpoint with health tracking"""
    url: str
    name: str
    status: EndpointStatus
    latency_ms: float
    last_check: datetime
    success_count: int = 0
    failure_count: int = 0

class SimpleRPCRotator:
    """Simple synchronous RPC rotator"""
    
    def __init__(self):
        self.endpoints = []
        self.current_index = 0
        self.session = requests.Session()
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0
        }
        
        # Initialize endpoints
        for i, url in enumerate(RPC_ENDPOINTS):
            endpoint = RPCEndpoint(
                url=url,
                name=f"RPC-{i+1}",
                status=EndpointStatus.UNKNOWN,
                latency_ms=0,
                last_check=datetime.now()
            )
            self.endpoints.append(endpoint)
        
        logger.info(f"🔄 Simple RPC Rotator initialized with {len(self.endpoints)} endpoints")
    
    def check_endpoint_health(self, endpoint: RPCEndpoint) -> bool:
        """Check health of a single endpoint"""
        try:
            start_time = time.time()
            
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getLatestBlockhash"
            }
            
            response = self.session.post(endpoint.url, json=payload, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    endpoint.latency_ms = (time.time() - start_time) * 1000
                    endpoint.last_check = datetime.now()
                    endpoint.success_count += 1
                    endpoint.status = EndpointStatus.HEALTHY
                    return True
            
            endpoint.failure_count += 1
            endpoint.status = EndpointStatus.FAILED
            return False
            
        except Exception as e:
            endpoint.failure_count += 1
            endpoint.status = EndpointStatus.FAILED
            logger.warning(f"❌ {endpoint.name} failed: {e}")
            return False
    
    def check_all_endpoints(self):
        """Check health of all endpoints"""
        for endpoint in self.endpoints:
            self.check_endpoint_health(endpoint)
        
        healthy_count = len([e for e in self.endpoints if e.status == EndpointStatus.HEALTHY])
        logger.info(f"🏥 Health check: {healthy_count}/{len(self.endpoints)} healthy")
    
    def get_best_endpoint(self) -> RPCEndpoint:
        """Get the best available endpoint"""
        healthy_endpoints = [e for e in self.endpoints if e.status == EndpointStatus.HEALTHY]
        
        if not healthy_endpoints:
            # Try all endpoints if none are healthy
            healthy_endpoints = self.endpoints
        
        # Sort by latency and success rate
        healthy_endpoints.sort(key=lambda e: (e.latency_ms, e.failure_count))
        return healthy_endpoints[0]
    
    def execute_request(self, method: str, params: List = None, request_id: int = None) -> Dict:
        """Execute RPC request with failover"""
        if params is None:
            params = []
        
        if request_id is None:
            request_id = self.stats["total_requests"]
        
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Try endpoints until success
        for attempt in range(3):
            try:
                endpoint = self.get_best_endpoint()
                
                start_time = time.time()
                response = self.session.post(endpoint.url, json=payload, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Update stats
                    self.stats["total_requests"] += 1
                    self.stats["successful_requests"] += 1
                    
                    endpoint.success_count += 1
                    
                    return data
                else:
                    raise Exception(f"HTTP {response.status_code}")
                    
            except Exception as e:
                endpoint.failure_count += 1
                logger.warning(f"⚠️ {endpoint.name} failed: {e}")
        
        # All endpoints failed
        self.stats["failed_requests"] += 1
        raise Exception(f"All RPC endpoints failed. Last error: {e}")
    
    def get_slot(self) -> Dict:
        """Get current slot"""
        return self.execute_request("getSlot")
    
    def get_latest_blockhash(self) -> Dict:
        """Get latest blockhash"""
        return self.execute_request("getLatestBlockhash")
    
    def get_balance(self, address: str) -> Dict:
        """Get account balance"""
        return self.execute_request("getBalance", [address])
    
    def get_status(self) -> Dict:
        """Get rotator status"""
        return {
            "endpoints": [
                {
                    "name": e.name,
                    "url": e.url,
                    "status": e.status.value,
                    "latency_ms": e.latency_ms,
                    "success_count": e.success_count,
                    "failure_count": e.failure_count
                }
                for e in self.endpoints
            ],
            "statistics": self.stats,
            "healthy_endpoints": len([e for e in self.endpoints if e.status == EndpointStatus.HEALTHY]),
            "total_endpoints": len(self.endpoints)
        }

# Global instance
simple_rotator = None

# Flask app
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/rotator_status', methods=['GET'])
def get_rotator_status():
    """Get RPC rotator status"""
    if not simple_rotator:
        return jsonify({"error": "RPC rotator not initialized"}), 500
    
    return jsonify(simple_rotator.get_status())

@app.route('/api/get_slot', methods=['GET'])
def get_slot():
    """Get current slot"""
    try:
        if not simple_rotator:
            return jsonify({"error": "RPC rotator not initialized"}), 500
        
        result = simple_rotator.get_slot()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_latest_blockhash', methods=['GET'])
def get_latest_blockhash():
    """Get latest blockhash"""
    try:
        if not simple_rotator:
            return jsonify({"error": "RPC rotator not initialized"}), 500
        
        result = simple_rotator.get_latest_blockhash()
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_balance/<address>', methods=['GET'])
def get_balance(address):
    """Get account balance"""
    try:
        if not simple_rotator:
            return jsonify({"error": "RPC rotator not initialized"}), 500
        
        result = simple_rotator.get_balance(address)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/rpc_request', methods=['POST'])
def execute_rpc_request():
    """Execute arbitrary RPC request"""
    try:
        data = request.json
        method = data.get('method')
        params = data.get('params', [])
        request_id = data.get('id')
        
        if not method:
            return jsonify({"error": "Method is required"}), 400
        
        if not simple_rotator:
            return jsonify({"error": "RPC rotator not initialized"}), 500
        
        result = simple_rotator.execute_request(method, params, request_id)
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def main():
    """Main function"""
    global simple_rotator
    
    logger.info("🚀 Starting Simple Solana RPC Rotator")
    
    # Initialize rotator
    simple_rotator = SimpleRPCRotator()
    
    # Check endpoint health
    simple_rotator.check_all_endpoints()
    
    # Start periodic health checks
    import threading
    def health_check_worker():
        while True:
            try:
                simple_rotator.check_all_endpoints()
                time.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"❌ Health check error: {e}")
                time.sleep(5)
    
    health_thread = threading.Thread(target=health_check_worker, daemon=True)
    health_thread.start()
    
    # Start Flask app
    logger.info("🌐 Starting Flask server on port 8083")
    app.run(host='0.0.0.0', port=8083, debug=False)

if __name__ == "__main__":
    main()
