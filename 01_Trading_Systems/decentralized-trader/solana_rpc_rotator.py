#!/usr/bin/env python3
"""
PRODUCTION SOLANA RPC ROTATOR
Rotates between multiple Solana RPC endpoints for maximum reliability
GitHub integration and Docker-ready for global deployment
"""

import asyncio
import json
import time
import logging
import aiohttp
import random
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import os
import signal

# Solana RPC endpoints
RPC_ENDPOINTS = [
    "https://api.mainnet-beta.solana.com",
    "https://solana-api.projectserum.com",
    "https://rpc.ankr.com/solana",
    "https://solana-mainnet.rpc.extrnode.com",
    "https://api.devnet.solana.com",  # Fallback
    "https://solana-mainnet.g.alchemy.com/v2/demo",  # Demo key
]

# WebSocket endpoints
WS_ENDPOINTS = [
    "wss://api.mainnet-beta.solana.com",
    "wss://solana-api.projectserum.com",
    "wss://rpc.ankr.com/solana/ws",
    "wss://solana-mainnet.rpc.extrnode.com/ws",
]

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class EndpointStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
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
    total_requests: int = 0
    error_rate: float = 0.0
    priority: int = 1  # 1 = highest priority
    supports_websocket: bool = False
    rate_limit_remaining: int = 100
    rate_limit_reset: Optional[datetime] = None

@dataclass
class LoadBalancingConfig:
    """Load balancing configuration"""
    strategy: str = "round_robin"  # round_robin, weighted, health_based
    health_check_interval: int = 30  # seconds
    failure_threshold: int = 3  # consecutive failures before marking as failed
    recovery_threshold: int = 2  # consecutive successes before marking as healthy
    max_latency_ms: float = 1000  # max acceptable latency

class SolanaRPCRotator:
    """Production Solana RPC rotator with load balancing"""
    
    def __init__(self, config: LoadBalancingConfig = None):
        self.config = config or LoadBalancingConfig()
        self.endpoints: List[RPCEndpoint] = []
        self.current_endpoint_index = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.health_check_task: Optional[asyncio.Task] = None
        self.request_count = 0
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "avg_latency": 0.0,
            "endpoint_switches": 0,
            "last_switch": None
        }
        
        # Initialize endpoints
        self._initialize_endpoints()
        
        logger.info("🔄 Solana RPC Rotator initialized")
        logger.info(f"📊 Loaded {len(self.endpoints)} RPC endpoints")
    
    def _initialize_endpoints(self):
        """Initialize all RPC endpoints"""
        for i, url in enumerate(RPC_ENDPOINTS):
            # Check if WebSocket is available
            ws_url = url.replace("https://", "wss://").replace("http://", "ws://")
            supports_ws = ws_url in WS_ENDPOINTS
            
            endpoint = RPCEndpoint(
                url=url,
                name=f"RPC-{i+1}",
                status=EndpointStatus.UNKNOWN,
                latency_ms=0,
                last_check=datetime.now(),
                priority=1 if i < 2 else 2,  # First 2 are high priority
                supports_websocket=supports_ws
            )
            self.endpoints.append(endpoint)
    
    async def start(self):
        """Start the rotator with health monitoring"""
        if self.session:
            return
        
        # Create HTTP session with proper timeout and retry
        timeout = aiohttp.ClientTimeout(total=10, connect=3)
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=20,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )
        
        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={
                "User-Agent": "SolanaRPCRotator/1.0",
                "Content-Type": "application/json"
            }
        )
        
        # Start health monitoring
        self.health_check_task = asyncio.create_task(self._health_monitor())
        
        logger.info("✅ RPC Rotator started with health monitoring")
    
    async def stop(self):
        """Stop the rotator and cleanup resources"""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        
        if self.session:
            await self.session.close()
            self.session = None
        
        logger.info("🛑 RPC Rotator stopped")
    
    async def _health_monitor(self):
        """Monitor health of all endpoints"""
        logger.info("🏥 Starting health monitoring...")
        
        while True:
            try:
                await self._check_all_endpoints()
                await asyncio.sleep(self.config.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Health monitor error: {e}")
                await asyncio.sleep(5)
    
    async def _check_all_endpoints(self):
        """Check health of all endpoints"""
        tasks = []
        for endpoint in self.endpoints:
            task = asyncio.create_task(self._check_endpoint_health(endpoint))
            tasks.append(task)
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Log endpoint status
        healthy_count = len([e for e in self.endpoints if e.status == EndpointStatus.HEALTHY])
        logger.info(f"🏥 Health check complete: {healthy_count}/{len(self.endpoints)} endpoints healthy")
    
    async def _check_endpoint_health(self, endpoint: RPCEndpoint):
        """Check health of a single endpoint"""
        try:
            start_time = time.time()
            
            # Simple health check - get latest blockhash
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getLatestBlockhash"
            }
            
            async with self.session.post(endpoint.url, json=payload, timeout=5) as response:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data:
                        # Success
                        latency = (time.time() - start_time) * 1000
                        endpoint.latency_ms = latency
                        endpoint.last_check = datetime.now()
                        endpoint.success_count += 1
                        endpoint.total_requests += 1
                        
                        # Update status based on latency
                        if latency < self.config.max_latency_ms:
                            if endpoint.status != EndpointStatus.HEALTHY:
                                endpoint.status = EndpointStatus.HEALTHY
                                logger.info(f"✅ {endpoint.name} recovered")
                        else:
                            endpoint.status = EndpointStatus.DEGRADED
                        
                        # Update error rate
                        endpoint.error_rate = endpoint.failure_count / max(1, endpoint.total_requests)
                        
                        # Check rate limit headers
                        rate_limit_remaining = response.headers.get('x-ratelimit-remaining')
                        if rate_limit_remaining:
                            endpoint.rate_limit_remaining = int(rate_limit_remaining)
                        
                        rate_limit_reset = response.headers.get('x-ratelimit-reset')
                        if rate_limit_reset:
                            endpoint.rate_limit_reset = datetime.fromtimestamp(int(rate_limit_reset))
                    else:
                        raise Exception("Invalid response format")
                else:
                    raise Exception(f"HTTP {response.status}")
                
        except Exception as e:
            # Failure
            endpoint.failure_count += 1
            endpoint.total_requests += 1
            endpoint.last_check = datetime.now()
            endpoint.error_rate = endpoint.failure_count / max(1, endpoint.total_requests)
            
            # Mark as failed if threshold exceeded
            if endpoint.failure_count >= self.config.failure_threshold:
                if endpoint.status != EndpointStatus.FAILED:
                    endpoint.status = EndpointStatus.FAILED
                    logger.warning(f"❌ {endpoint.name} marked as failed: {e}")
    
    def _select_endpoint(self) -> RPCEndpoint:
        """Select best endpoint based on load balancing strategy"""
        healthy_endpoints = [e for e in self.endpoints if e.status == EndpointStatus.HEALTHY]
        
        if not healthy_endpoints:
            # Fallback to degraded endpoints
            healthy_endpoints = [e for e in self.endpoints if e.status == EndpointStatus.DEGRADED]
        
        if not healthy_endpoints:
            # Last resort - try failed endpoints
            healthy_endpoints = self.endpoints
        
        if self.config.strategy == "round_robin":
            return self._round_robin_select(healthy_endpoints)
        elif self.config.strategy == "weighted":
            return self._weighted_select(healthy_endpoints)
        elif self.config.strategy == "health_based":
            return self._health_based_select(healthy_endpoints)
        else:
            return healthy_endpoints[0]
    
    def _round_robin_select(self, endpoints: List[RPCEndpoint]) -> RPCEndpoint:
        """Round-robin selection"""
        if not endpoints:
            raise Exception("No healthy endpoints available")
        
        endpoint = endpoints[self.current_endpoint_index % len(endpoints)]
        self.current_endpoint_index += 1
        return endpoint
    
    def _weighted_select(self, endpoints: List[RPCEndpoint]) -> RPCEndpoint:
        """Weighted selection based on priority and latency"""
        if not endpoints:
            raise Exception("No healthy endpoints available")
        
        # Calculate weights
        weights = []
        for endpoint in endpoints:
            weight = 1.0 / (endpoint.latency_ms + 1)  # Lower latency = higher weight
            weight *= (4 - endpoint.priority)  # Higher priority = higher weight
            weights.append(weight)
        
        # Normalize weights
        total_weight = sum(weights)
        weights = [w / total_weight for w in weights]
        
        # Random selection based on weights
        return random.choices(endpoints, weights=weights)[0]
    
    def _health_based_select(self, endpoints: List[RPCEndpoint]) -> RPCEndpoint:
        """Health-based selection - choose endpoint with lowest error rate"""
        if not endpoints:
            raise Exception("No healthy endpoints available")
        
        # Sort by error rate, then latency
        sorted_endpoints = sorted(endpoints, key=lambda e: (e.error_rate, e.latency_ms))
        return sorted_endpoints[0]
    
    async def execute_request(self, method: str, params: List = None, request_id: int = None) -> Dict:
        """Execute RPC request with automatic failover"""
        if not self.session:
            raise Exception("RPC Rotator not started")
        
        if params is None:
            params = []
        
        if request_id is None:
            request_id = self.request_count
            self.request_count += 1
        
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": params
        }
        
        # Try endpoints until success
        last_error = None
        for attempt in range(3):  # Max 3 attempts
            try:
                endpoint = self._select_endpoint()
                
                start_time = time.time()
                async with self.session.post(endpoint.url, json=payload, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        # Update stats
                        self.stats["total_requests"] += 1
                        self.stats["successful_requests"] += 1
                        latency = (time.time() - start_time) * 1000
                        self.stats["avg_latency"] = (
                            (self.stats["avg_latency"] * (self.stats["successful_requests"] - 1) + latency) 
                            / self.stats["successful_requests"]
                        )
                        
                        endpoint.success_count += 1
                        endpoint.total_requests += 1
                        
                        return data
                    else:
                        raise Exception(f"HTTP {response.status}")
                
            except Exception as e:
                last_error = e
                endpoint.failure_count += 1
                endpoint.total_requests += 1
                
                # Mark endpoint as failed if too many failures
                if endpoint.failure_count >= self.config.failure_threshold:
                    endpoint.status = EndpointStatus.FAILED
                
                logger.warning(f"⚠️ {endpoint.name} failed: {e}")
                
                # Switch to next endpoint
                self.stats["endpoint_switches"] += 1
                self.stats["last_switch"] = datetime.now()
        
        # All endpoints failed
        self.stats["failed_requests"] += 1
        raise Exception(f"All RPC endpoints failed. Last error: {last_error}")
    
    async def get_balance(self, address: str) -> Dict:
        """Get account balance"""
        return await self.execute_request("getBalance", [address])
    
    async def get_latest_blockhash(self) -> Dict:
        """Get latest blockhash"""
        return await self.execute_request("getLatestBlockhash")
    
    async def get_slot(self) -> Dict:
        """Get current slot"""
        return await self.execute_request("getSlot")
    
    async def get_token_balance(self, address: str, mint: str) -> Dict:
        """Get token balance"""
        return await self.execute_request("getTokenAccountBalance", [address, {"mint": mint}])
    
    async def send_transaction(self, transaction: str) -> Dict:
        """Send transaction"""
        return await self.execute_request("sendTransaction", [transaction])
    
    def get_status(self) -> Dict:
        """Get rotator status and statistics"""
        return {
            "config": asdict(self.config),
            "endpoints": [
                {
                    "name": e.name,
                    "url": e.url,
                    "status": e.status.value,
                    "latency_ms": e.latency_ms,
                    "success_count": e.success_count,
                    "failure_count": e.failure_count,
                    "error_rate": e.error_rate,
                    "priority": e.priority,
                    "supports_websocket": e.supports_websocket,
                    "rate_limit_remaining": e.rate_limit_remaining
                }
                for e in self.endpoints
            ],
            "statistics": self.stats,
            "healthy_endpoints": len([e for e in self.endpoints if e.status == EndpointStatus.HEALTHY]),
            "total_endpoints": len(self.endpoints)
        }

# Flask API for external access
from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio

app = Flask(__name__)
CORS(app)

# Global rotator instance
rpc_rotator = None

def run_async(coro):
    """Helper to run async function in sync context"""
    try:
        loop = asyncio.get_running_loop()
        # If we're already in an event loop, we need to run in a thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(coro)

@app.route('/api/rotator_status', methods=['GET'])
def get_rotator_status():
    """Get RPC rotator status"""
    if not rpc_rotator:
        return jsonify({"error": "RPC rotator not initialized"}), 500
    
    return jsonify(rpc_rotator.get_status())

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
        
        if not rpc_rotator:
            return jsonify({"error": "RPC rotator not initialized"}), 500
        
        result = run_async(rpc_rotator.execute_request(method, params, request_id))
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_balance/<address>', methods=['GET'])
def get_balance(address):
    """Get account balance"""
    try:
        if not rpc_rotator:
            return jsonify({"error": "RPC rotator not initialized"}), 500
        
        result = run_async(rpc_rotator.get_balance(address))
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_slot', methods=['GET'])
def get_slot():
    """Get current slot"""
    try:
        if not rpc_rotator:
            return jsonify({"error": "RPC rotator not initialized"}), 500
        
        result = run_async(rpc_rotator.get_slot())
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_latest_blockhash', methods=['GET'])
def get_latest_blockhash():
    """Get latest blockhash"""
    try:
        if not rpc_rotator:
            return jsonify({"error": "RPC rotator not initialized"}), 500
        
        result = run_async(rpc_rotator.get_latest_blockhash())
        return jsonify(result)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

async def main():
    """Main entry point"""
    global rpc_rotator
    
    logger.info("🚀 Starting Solana RPC Rotator")
    
    # Initialize rotator
    config = LoadBalancingConfig(
        strategy="health_based",
        health_check_interval=30,
        failure_threshold=3,
        max_latency_ms=1000
    )
    
    rpc_rotator = SolanaRPCRotator(config)
    await rpc_rotator.start()
    
    # Start Flask app
    def run_flask():
        app.run(host='0.0.0.0', port=8083, debug=False)
    
    import threading
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    try:
        # Keep running
        while True:
            await asyncio.sleep(60)
            
            # Log periodic status
            status = rpc_rotator.get_status()
            logger.info(f"📊 Status: {status['healthy_endpoints']}/{status['total_endpoints']} healthy")
            logger.info(f"📈 Stats: {status['statistics']['total_requests']} requests, {status['statistics']['avg_latency']:.1f}ms avg latency")
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutting down...")
    finally:
        if rpc_rotator:
            await rpc_rotator.stop()

if __name__ == "__main__":
    asyncio.run(main())
