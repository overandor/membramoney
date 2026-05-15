"""Web3 blockchain agent."""

import logging
import threading
from typing import Dict, List
from datetime import datetime

import requests


class Web3Agent:
    def __init__(self):
        self.connected_wallets: Dict[str, Dict] = {}
        self.transactions: List[Dict] = []
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

        self.rpc_endpoints = {
            "ethereum": "https://eth.llamarpc.com",
            "polygon": "https://polygon-rpc.com",
            "bsc": "https://bsc-dataseed.binance.org",
            "arbitrum": "https://arb1.arbitrum.io/rpc",
        }

    def connect_wallet(self, user: str, address: str, chain: str = "ethereum") -> Dict:
        with self.lock:
            wallet_id = f"{user}_{address}_{chain}"
            self.connected_wallets[wallet_id] = {
                "user": user,
                "address": address,
                "chain": chain,
                "connected_at": datetime.now().isoformat(),
            }
            self.logger.info(f"Wallet connected: {address[:10]}... for user {user}")
            return {"wallet_id": wallet_id, "address": address, "chain": chain}

    def get_balance(self, address: str, chain: str = "ethereum") -> Dict:
        try:
            rpc_url = self.rpc_endpoints.get(chain, self.rpc_endpoints["ethereum"])
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getBalance",
                "params": [address, "latest"],
                "id": 1,
            }
            response = requests.post(rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    balance_wei = int(result["result"], 16)
                    balance_eth = balance_wei / 10**18
                    return {
                        "address": address,
                        "chain": chain,
                        "balance_wei": balance_wei,
                        "balance_eth": balance_eth,
                        "formatted": f"{balance_eth:.6f} ETH",
                    }
            return {"error": "Failed to get balance"}
        except Exception as e:
            return {"error": str(e)}

    def get_gas_price(self, chain: str = "ethereum") -> Dict:
        try:
            rpc_url = self.rpc_endpoints.get(chain, self.rpc_endpoints["ethereum"])
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_gasPrice",
                "params": [],
                "id": 1,
            }
            response = requests.post(rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    gas_wei = int(result["result"], 16)
                    gas_gwei = gas_wei / 10**9
                    return {
                        "chain": chain,
                        "gas_wei": gas_wei,
                        "gas_gwei": gas_gwei,
                        "formatted": f"{gas_gwei:.2f} Gwei",
                    }
            return {"error": "Failed to get gas price"}
        except Exception as e:
            return {"error": str(e)}

    def estimate_gas(self, to: str, from_address: str, data: str = "0x", chain: str = "ethereum") -> Dict:
        try:
            rpc_url = self.rpc_endpoints.get(chain, self.rpc_endpoints["ethereum"])
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_estimateGas",
                "params": [{"to": to, "from": from_address, "data": data}],
                "id": 1,
            }
            response = requests.post(rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    gas = int(result["result"], 16)
                    return {"chain": chain, "gas_limit": gas, "formatted": f"{gas:,} units"}
            return {"error": "Failed to estimate gas"}
        except Exception as e:
            return {"error": str(e)}

    def get_transaction_count(self, address: str, chain: str = "ethereum") -> Dict:
        try:
            rpc_url = self.rpc_endpoints.get(chain, self.rpc_endpoints["ethereum"])
            payload = {
                "jsonrpc": "2.0",
                "method": "eth_getTransactionCount",
                "params": [address, "latest"],
                "id": 1,
            }
            response = requests.post(rpc_url, json=payload, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if "result" in result:
                    nonce = int(result["result"], 16)
                    return {"address": address, "chain": chain, "nonce": nonce}
            return {"error": "Failed to get transaction count"}
        except Exception as e:
            return {"error": str(e)}

    def record_transaction(self, user: str, tx_hash: str, chain: str, details: Dict) -> Dict:
        with self.lock:
            self.transactions.append(
                {
                    "user": user,
                    "tx_hash": tx_hash,
                    "chain": chain,
                    "details": details,
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return {"message": "Transaction recorded"}

    def get_user_transactions(self, user: str) -> List[Dict]:
        with self.lock:
            return [tx for tx in self.transactions if tx["user"] == user]

    def get_supported_chains(self) -> List[str]:
        return list(self.rpc_endpoints.keys())

    def get_wallets(self, user: str) -> List[Dict]:
        with self.lock:
            return [
                {
                    "wallet_id": wid,
                    "address": w["address"],
                    "chain": w["chain"],
                    "connected_at": w["connected_at"],
                }
                for wid, w in self.connected_wallets.items()
                if w["user"] == user
            ]
