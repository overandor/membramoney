"""Trading agent with autonomous trading support."""

import hashlib
import hmac
import logging
import os
import random
import secrets
import threading
import time
from datetime import datetime
from typing import Dict, List

import requests


class TradingAgent:
    def __init__(self):
        self.positions: Dict[str, Dict] = {}
        self.orders: List[Dict] = []
        self.market_data: Dict[str, Dict] = {}
        self.strategies: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

        self.autonomous_enabled = False
        self.autonomous_thread = None
        self.autonomous_symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
        self.autonomous_interval = 60

        self.exchanges = {
            "gateio": {
                "api_key": os.getenv("GATE_API_KEY"),
                "secret": os.getenv("GATE_API_SECRET"),
                "enabled": bool(os.getenv("GATE_API_KEY") and os.getenv("GATE_API_SECRET")),
            }
        }

        self.default_strategy = {
            "risk_per_trade": 0.10,
            "max_positions": 10,
            "take_profit": 0.02,
            "stop_loss": 0.01,
            "leverage": 10,
            "balance_usd": 1.0,
        }
        self.simulate_orders = True

    def start_autonomous_trading(self, symbols: List[str] = None, interval: int = 60):
        with self.lock:
            if self.autonomous_enabled:
                return {"message": "Autonomous trading already running"}
            self.autonomous_enabled = True
            self.autonomous_symbols = symbols or self.autonomous_symbols
            self.autonomous_interval = interval
            self.autonomous_thread = threading.Thread(target=self._autonomous_loop, daemon=True)
            self.autonomous_thread.start()
            self.logger.info(f"Autonomous trading started on {self.autonomous_symbols}")
            return {"message": "Autonomous trading started", "symbols": self.autonomous_symbols}

    def stop_autonomous_trading(self):
        with self.lock:
            self.autonomous_enabled = False
            self.logger.info("Autonomous trading stopped")
            return {"message": "Autonomous trading stopped"}

    def _autonomous_loop(self):
        self.logger.info("Autonomous loop started")
        while self.autonomous_enabled:
            try:
                self.logger.info(f"Scanning {len(self.autonomous_symbols)} symbols...")
                for symbol in self.autonomous_symbols:
                    self.logger.info(f"Analyzing {symbol}...")
                    analysis = self.analyze_market(symbol)
                    self.logger.info(
                        f"{symbol} analysis: {analysis.get('recommendation')} "
                        f"confidence={analysis.get('confidence'):.2f}"
                    )
                    position_size = 0.001
                    price = analysis.get("data", {}).get("price", 50000)
                    if symbol.startswith("BTC"):
                        amount = position_size / price
                    elif symbol.startswith("ETH"):
                        amount = position_size / 3000
                    else:
                        amount = position_size / 100

                    if analysis["recommendation"] == "buy" and analysis["confidence"] >= 0.7:
                        result = self.create_order(
                            user="autonomous", symbol=symbol, side="buy",
                            amount=amount, order_type="market"
                        )
                        self.logger.info(f"MICRO BUY: {symbol} amount={amount:.8f} status={result.get('status')}")
                    elif analysis["recommendation"] == "sell" and analysis["confidence"] >= 0.7:
                        result = self.create_order(
                            user="autonomous", symbol=symbol, side="sell",
                            amount=amount, order_type="market"
                        )
                        self.logger.info(f"MICRO SELL: {symbol} amount={amount:.8f} status={result.get('status')}")
                    else:
                        self.logger.info(f"Skipping {symbol}: {analysis.get('recommendation')}")
                time.sleep(self.autonomous_interval)
            except Exception as e:
                self.logger.error(f"Autonomous trading error: {e}")
                time.sleep(self.autonomous_interval)

    def get_autonomous_status(self) -> Dict:
        with self.lock:
            return {
                "enabled": self.autonomous_enabled,
                "symbols": self.autonomous_symbols,
                "interval": self.autonomous_interval,
                "active": self.autonomous_thread and self.autonomous_thread.is_alive(),
            }

    def configure_exchange(self, exchange: str, api_key: str, secret: str) -> Dict:
        with self.lock:
            if exchange in self.exchanges:
                self.exchanges[exchange]["api_key"] = api_key
                self.exchanges[exchange]["secret"] = secret
                self.exchanges[exchange]["enabled"] = True
                self.logger.info(f"Exchange {exchange} configured")
                return {"message": f"Exchange {exchange} configured"}
            return {"error": "Exchange not supported"}

    def get_market_data(self, symbol: str) -> Dict:
        try:
            price = random.uniform(30000, 70000) if "BTC" in symbol else random.uniform(1500, 4000)
            change_24h = random.uniform(-5, 5)
            return {
                "symbol": symbol,
                "price": price,
                "change_24h": change_24h,
                "volume": random.uniform(1000000, 10000000),
                "high": price * (1 + abs(change_24h) / 100),
                "low": price * (1 - abs(change_24h) / 100),
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"error": str(e)}

    def create_order(self, user: str, symbol: str, side: str, amount: float,
                     price: float = None, order_type: str = "market") -> Dict:
        with self.lock:
            if not self.simulate_orders and self.exchanges["gateio"]["enabled"]:
                try:
                    api_key = self.exchanges["gateio"]["api_key"]
                    api_secret = self.exchanges["gateio"]["secret"]
                    url = "https://api.gateio.ws/api/v4/futures/usdt/orders"

                    if symbol.startswith("BTC"):
                        contract_multiplier = 0.01
                    elif symbol.startswith("ETH"):
                        contract_multiplier = 0.1
                    elif symbol.startswith("SOL"):
                        contract_multiplier = 10
                    else:
                        contract_multiplier = 1

                    size_in_contracts = int((amount / contract_multiplier) * 10)
                    if size_in_contracts < 1:
                        size_in_contracts = 1

                    params = {
                        "settle": "usdt",
                        "contract": symbol.replace("/", "_"),
                        "size": str(size_in_contracts),
                        "price": str(price) if price else "0",
                        "side": side.lower(),
                        "type": "market" if order_type == "market" else "limit",
                        "time_in_force": "ioc",
                    }

                    timestamp = str(int(time.time()))
                    query_string = "&".join([f"{k}={v}" for k, v in sorted(params.items())])
                    sign_str = f"POST\n/api/v4/futures/usdt/orders\n{query_string}"
                    signature = hmac.new(
                        api_secret.encode("utf-8"), sign_str.encode("utf-8"), hashlib.sha512
                    ).hexdigest()

                    headers = {
                        "KEY": api_key,
                        "Timestamp": timestamp,
                        "SIGN": signature,
                        "Content-Type": "application/json",
                    }

                    response = requests.post(f"{url}?{query_string}", json={}, headers=headers, timeout=10)

                    if response.status_code == 200:
                        result = response.json()
                        order_id = result.get("id", secrets.token_hex(16))
                        order = {
                            "order_id": order_id, "user": user, "symbol": symbol,
                            "side": side, "amount": amount, "price": price,
                            "type": order_type, "status": "placed",
                            "exchange": "gateio", "leverage": 10,
                            "created_at": datetime.now().isoformat(),
                        }
                        self.orders.append(order)
                        self.logger.info(f"REAL ORDER: {order_id} {side} {amount} {symbol}")
                        return {"order_id": order_id, "status": "placed", "exchange": "gateio"}
                    else:
                        error = response.text
                        self.logger.error(f"Gate.io order failed: {error}")
                        return {"order_id": secrets.token_hex(16), "status": "error", "error": error}
                except Exception as e:
                    self.logger.error(f"Error placing real order: {e}")
                    return {"order_id": secrets.token_hex(16), "status": "error", "error": str(e)}
            else:
                order_id = secrets.token_hex(16)
                order = {
                    "order_id": order_id, "user": user, "symbol": symbol,
                    "side": side, "amount": amount, "price": price,
                    "type": order_type, "status": "simulated",
                    "created_at": datetime.now().isoformat(),
                }
                self.orders.append(order)
                self.logger.info(f"SIMULATED ORDER: {order_id} for {user}")
                return {"order_id": order_id, "status": "simulated"}

    def get_positions(self, user: str) -> List[Dict]:
        with self.lock:
            return [pos for pos in self.positions.values() if pos.get("user") == user]

    def get_orders(self, user: str) -> List[Dict]:
        with self.lock:
            return [order for order in self.orders if order.get("user") == user]

    def analyze_market(self, symbol: str, use_ai: bool = False) -> Dict:
        market_data = self.get_market_data(symbol)
        analysis = {
            "symbol": symbol, "trend": "neutral", "sentiment": "neutral",
            "recommendation": "hold", "confidence": 0.5, "data": market_data,
        }
        change = market_data.get("change_24h", 0)
        if change > 2:
            analysis.update({"trend": "bullish", "sentiment": "positive",
                             "recommendation": "buy", "confidence": 0.7})
        elif change < -2:
            analysis.update({"trend": "bearish", "sentiment": "negative",
                             "recommendation": "sell", "confidence": 0.7})
        return analysis

    def run_strategy(self, strategy_name: str, symbols: List[str]) -> Dict:
        results = []
        for symbol in symbols:
            analysis = self.analyze_market(symbol)
            if analysis["recommendation"] != "hold":
                results.append({
                    "symbol": symbol, "action": analysis["recommendation"],
                    "confidence": analysis["confidence"], "reason": analysis["trend"],
                })
        return {"strategy": strategy_name, "results": results,
                "timestamp": datetime.now().isoformat()}

    def set_strategy(self, user: str, strategy_name: str, params: Dict) -> Dict:
        with self.lock:
            strategy_id = f"{user}_{strategy_name}"
            self.strategies[strategy_id] = {
                "user": user, "name": strategy_name,
                "params": params, "created_at": datetime.now().isoformat(),
            }
            return {"message": "Strategy set", "strategy_id": strategy_id}

    def get_portfolio_value(self, user: str) -> Dict:
        positions = self.get_positions(user)
        total_value = sum(
            pos["amount"] * self.get_market_data(pos["symbol"]).get("price", 0)
            for pos in positions
        )
        return {
            "user": user, "total_value": total_value,
            "positions_count": len(positions),
            "timestamp": datetime.now().isoformat(),
        }
