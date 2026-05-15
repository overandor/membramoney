import os
# ============================================================

# PRODUCTION DRIFT MARKET MAKER

# Target: $0.01 profit per 3 minutes ($4.80/day minimum)

# Strategy: Adaptive spread + inventory management + edge capture

# ============================================================

import asyncio
import json
import base64
import time
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, field
from collections import deque
import statistics
import logging # Added for structured logging

import websockets
from solana.keypair import Keypair
from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Processed, Confirmed

from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.system_program import transfer, TransferParams
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price
from solders.instruction import Instruction

from driftpy.drift_client import DriftClient
from driftpy.account_subscription_config import AccountSubscriptionConfig
from driftpy.constants.numeric_constants import BASE_PRECISION, PRICE_PRECISION
from driftpy.types import (
    OrderParams, OrderType, PositionDirection, MarketType
)

# ============================================================

# CONFIGURATION

# ============================================================

RPC_HTTP = "https://api.mainnet-beta.solana.com"
JITO_URL = "wss://mainnet.block-engine.jito.wtf/api/v1/bundles"
MARKET_INDEX = 0  # SOL-PERP

TIP_ACCOUNTS = [
    "96gYZGLnJYVFmbjzopPSU6QiEV5fGqZNyN9nmNhvrZU5",
    "HFqU5x63VTqvQss8hp11i4wVV8bD44PuwIjQAmQK1H5t",
    "Cw8CFyM9FkoMi7K7Crf6HNQqf4uEMzpKw6QNghXLvLkY",
]

# Target Economics

TARGET_PROFIT_PER_3MIN = 0.01  # $0.01 USD
ASSUMED_SOL_PRICE = 100.0      # $100/SOL for rough math
MIN_EDGE_BPS = 8               # 8 bps minimum edge to quote
TARGET_FILL_RATE = 0.15        # 15% of quotes should fill
MAX_POSITION_SIZE = 5.0        # Max 5 SOL position
INVENTORY_SKEW_FACTOR = 0.0002 # 2 bps skew per 1 SOL inventory

# ============================================================

# DATA STRUCTURES

# ============================================================

@dataclass
class TrackedOrder:
    order_id: int
    direction: str  # 'bid' or 'ask'
    price: Decimal
    size: Decimal
    timestamp: float
    bundle_id: Optional[str] = None

@dataclass
class Fill:
    timestamp: float
    direction: str
    price: Decimal
    size: Decimal
    pnl: Decimal

@dataclass
class MarketState:
    mid_price: Decimal
    bid: Decimal
    ask: Decimal
    volatility: Decimal
    last_update: float

# ============================================================

# PERFORMANCE TRACKER

# ============================================================

class PerformanceTracker:
    def __init__(self):
        self.fills: deque = deque(maxlen=100)
        self.realized_pnl = Decimal("0")
        self.unrealized_pnl = Decimal("0")
        self.position = Decimal("0")
        self.avg_entry = Decimal("0")
        self.bundles_sent = 0
        self.bundles_landed = 0
        self.last_3min_pnl = Decimal("0")
        self.start_time = time.time()

    def add_fill(self, direction: str, price: Decimal, size: Decimal):
        """Track a fill and update position"""
        fill_value = price * size

        if direction == 'bid':  # We bought
            # Update position
            old_pos = self.position
            self.position += size

            # Update average entry
            if old_pos <= 0:  # Was flat or short, now long or flat
                self.avg_entry = price
            else:  # Adding to long
                total_value = (self.avg_entry * old_pos) + fill_value
                self.avg_entry = total_value / self.position

        else:  # We sold
            old_pos = self.position
            self.position -= size

            # Realize PnL if we had inventory
            if old_pos > 0:  # Had long position
                realized = (price - self.avg_entry) * min(size, old_pos)
                self.realized_pnl += realized

            if old_pos >= 0:  # Was long or flat, now short or flat
                self.avg_entry = price
            else:  # Adding to short
                total_value = abs((self.avg_entry * old_pos) - fill_value)
                self.avg_entry = total_value / abs(self.position)

        self.fills.append(Fill(
            timestamp=time.time(),
            direction=direction,
            price=price,
            size=size,
            pnl=self.realized_pnl
        ))

    def calculate_unrealized_pnl(self, mark_price: Decimal) -> Decimal:
        """Calculate unrealized PnL on current position"""
        if abs(self.position) < Decimal("0.001"):
            self.unrealized_pnl = Decimal("0")
        else:
            self.unrealized_pnl = (mark_price - self.avg_entry) * self.position
        return self.unrealized_pnl

    def get_total_pnl(self, mark_price: Decimal) -> Decimal:
        """Total PnL = realized + unrealized"""
        self.calculate_unrealized_pnl(mark_price)
        return self.realized_pnl + self.unrealized_pnl

    def get_3min_pnl(self) -> Decimal:
        """Calculate PnL in last 3 minutes"""
        cutoff = time.time() - 180
        recent_fills = [f for f in self.fills if f.timestamp > cutoff]

        if not recent_fills:
            return Decimal("0")

        # Simple approximation: sum of spread capture
        pnl = Decimal("0")
        for i in range(1, len(recent_fills)):
            prev = recent_fills[i-1]
            curr = recent_fills[i]

            # If we bought then sold, we captured spread
            if prev.direction == 'bid' and curr.direction == 'ask':
                pnl += (curr.price - prev.price) * min(prev.size, curr.size)
            elif prev.direction == 'ask' and curr.direction == 'bid':
                pnl += (prev.price - curr.price) * min(prev.size, curr.size)

        return pnl

    def print_status(self, mark_price: Decimal):
        """Print performance summary"""
        runtime = (time.time() - self.start_time) / 60
        total_pnl = self.get_total_pnl(mark_price)
        success_rate = (self.bundles_landed / max(1, self.bundles_sent)) * 100

        logging.info(f"{'='*60}")
        logging.info(f"📊 PERFORMANCE [{runtime:.1f} min runtime]")
        logging.info(f"{'='*60}")
        logging.info(f"Position: {self.position:+.3f} SOL @ ${float(mark_price):.2f}")
        logging.info(f"Realized PnL: ${float(self.realized_pnl * mark_price):.4f}")
        logging.info(f"Unrealized PnL: ${float(self.unrealized_pnl * mark_price):.4f}")
        logging.info(f"Total PnL: ${float(total_pnl * mark_price):.4f}")
        logging.info(f"3-Min PnL: ${float(self.get_3min_pnl() * mark_price):.4f}")
        logging.info(f"Fills: {len(self.fills)} | Bundle Success: {success_rate:.1f}%")
        logging.info(f"Target: ${TARGET_PROFIT_PER_3MIN:.2f}/3min = ${TARGET_PROFIT_PER_3MIN * 20:.2f}/hour")
        logging.info(f"{'='*60}")

# ============================================================

# VOLATILITY ESTIMATOR

# ============================================================

class VolatilityEstimator:
    def __init__(self, window_seconds: int = 300):
        self.window = window_seconds
        self.price_history: deque = deque(maxlen=1000)

    def update(self, price: Decimal):
        self.price_history.append({
            'price': price,
            'timestamp': time.time()
        })

    def get_volatility(self) -> Decimal:
        """Calculate realized volatility (std dev of returns)"""
        if len(self.price_history) < 10:
            return Decimal("0.001")  # Default 0.1%

        # Filter to window
        cutoff = time.time() - self.window
        recent = [p['price'] for p in self.price_history if p['timestamp'] > cutoff]

        if len(recent) < 10:
            return Decimal("0.001")

        # Calculate returns
        returns = []
        for i in range(1, len(recent)):
            ret = (recent[i] - recent[i-1]) / recent[i-1]
            returns.append(float(ret))

        # Return standard deviation
        try:
            vol = Decimal(str(statistics.stdev(returns)))
            return max(vol, Decimal("0.0005"))  # Min 5 bps
        except:
            return Decimal("0.001")

# ============================================================

# QUOTE ENGINE - THE MONEY MAKER

# ============================================================

class QuoteEngine:
    def __init__(self, performance: PerformanceTracker, volatility: VolatilityEstimator):
        self.performance = performance
        self.volatility = volatility
        self.min_edge = Decimal(str(MIN_EDGE_BPS / 10000))

    def calculate_quotes(self, market: MarketState) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Calculate optimal bid/ask/size to hit profit target

        Math:
        - Need $0.01 per 3 minutes
        - At $100/SOL, that's 0.0001 SOL
        - With 15% fill rate, need 0.0007 SOL edge per quote
        - At 1 SOL size, need 7 bps spread minimum
        """

        # 1. Base spread from volatility + min edge
        vol = self.volatility.get_volatility()
        base_spread = max(vol * Decimal("2.0"), self.min_edge)

        # 2. Widen spread if fills too frequent (adverse selection)
        recent_fills = [f for f in self.performance.fills if time.time() - f.timestamp < 60]
        if len(recent_fills) > 5:  # >5 fills per minute = toxic
            base_spread *= Decimal("1.5")

        # 3. Inventory skew - fade when loaded
        position = self.performance.position
        skew = position * Decimal(str(INVENTORY_SKEW_FACTOR))

        # 4. Calculate quotes
        mid = market.mid_price
        half_spread = base_spread / 2

        bid = mid - half_spread + skew  # When long, bid lower (skew negative)
        ask = mid + half_spread + skew  # When long, ask lower (skew negative)

        # 5. Calculate size - smaller when positioned
        base_size = Decimal("1.0")
        position_pct = abs(position) / Decimal(str(MAX_POSITION_SIZE))
        size = base_size * (Decimal("1") - position_pct * Decimal("0.7"))
        size = max(size, Decimal("0.1"))  # Min 0.1 SOL

        # 6. Risk check - don't quote if at limit
        if abs(position) >= MAX_POSITION_SIZE:
            # Only quote the side that reduces position
            if position > 0:  # Long - only offer
                bid = Decimal("0")
                size = min(size, abs(position))
            else:  # Short - only bid
                ask = Decimal("999999")
                size = min(size, abs(position))

        return bid, ask, size

# ============================================================

# SIMPLIFIED JITO BUNDLE SENDER

# ============================================================

class JitoBundleManager:
    def __init__(self, kp: Keypair, connection: AsyncClient):
        self.kp = kp
        self.connection = connection
        self.tip_accounts = [Pubkey.from_string(t) for t in TIP_ACCOUNTS]

    async def send_update_bundle(
        self,
        drift: DriftClient,
        bid_price: Decimal,
        ask_price: Decimal,
        size: Decimal,
        cancel_orders: bool = True
    ) -> Optional[str]:
        """Send atomic bundle: cancel + place orders"""

        try:
            # Get blockhash
            resp = await self.connection.get_latest_blockhash(Processed)
            blockhash = resp.value.blockhash

            # Build instructions
            instructions = []

            # Add compute budget
            instructions.append(set_compute_unit_limit(400_000))
            instructions.append(set_compute_unit_price(50_000))  # Higher priority

            # Cancel existing orders
            if cancel_orders:
                ix_cancel = drift.get_cancel_orders_ix(
                    market_type=MarketType.PERP,
                    market_index=MARKET_INDEX
                )
                instructions.append(ix_cancel)

            # Place new orders
            if bid_price > 0:
                bid_params = OrderParams(
                    order_type=OrderType.LIMIT,
                    market_type=MarketType.PERP,
                    direction=PositionDirection.LONG,
                    market_index=MARKET_INDEX,
                    base_asset_amount=int(size * BASE_PRECISION),
                    price=int(bid_price * PRICE_PRECISION),
                    post_only=False,  # Allow to take if crossed
                    immediate_or_cancel=True,
                )
                ix_bid = await drift.get_place_perp_order_ix(bid_params)
                instructions.append(ix_bid)

            if ask_price < 999999:
                ask_params = OrderParams(
                    order_type=OrderType.LIMIT,
                    market_type=MarketType.PERP,
                    direction=PositionDirection.SHORT,
                    market_index=MARKET_INDEX,
                    base_asset_amount=int(size * BASE_PRECISION),
                    price=int(ask_price * PRICE_PRECISION),
                    post_only=False,
                    immediate_or_cancel=True,
                )
                ix_ask = await drift.get_place_perp_order_ix(ask_params)
                instructions.append(ix_ask)

            # Add tip
            tip_amount = 50_000  # 0.00005 SOL
            tip_ix = transfer(TransferParams(
                from_pubkey=self.kp.pubkey(),
                to_pubkey=self.tip_accounts[int(time.time()) % len(self.tip_accounts)],
                lamports=tip_amount
            ))
            instructions.append(tip_ix)

            # Build transaction
            msg = MessageV0.try_compile(
                payer=self.kp.pubkey(),
                instructions=instructions,
                address_lookup_tables=[],
                recent_blockhash=blockhash
            )
            tx = VersionedTransaction(msg, [self.kp])

            # Send via Jito
            encoded = base64.b64encode(bytes(tx)).decode('utf-8')
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "sendBundle",
                "params": [[encoded]]
            }

            async with websockets.connect(JITO_URL, ping_interval=20) as ws:
                await ws.send(json.dumps(payload))
                resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
                result = json.loads(resp)

                if "result" in result:
                    return result["result"]

        except Exception as e:
            logging.error(f"Bundle error: {e}") # Changed print to logging.error

        return None

# ============================================================

# MAIN MARKET MAKER

# ============================================================

class ProductionMarketMaker:
    def __init__(self, kp: Keypair):
        self.kp = kp
        self.connection = AsyncClient(RPC_HTTP, commitment=Processed)
        self.drift = DriftClient(
            self.connection,
            kp,
            "mainnet",
            account_subscription=AccountSubscriptionConfig("websocket")
        )
        self.jito = JitoBundleManager(kp, self.connection)

        self.performance = PerformanceTracker()
        self.volatility = VolatilityEstimator()
        self.quote_engine = QuoteEngine(self.performance, self.volatility)

        self.last_update = 0
        self.update_interval = 2.0  # Quote every 2 seconds

    async def sync_fills(self):
        """Check for fills and update performance"""
        try:
            user = await self.drift.get_user_account()
            position_size = Decimal(user.perp_positions[0].base_asset_amount) / BASE_PRECISION

            # Detect fills by position change
            old_position = self.performance.position
            position_delta = position_size - old_position

            if abs(position_delta) > Decimal("0.01"):
                # We got filled!
                market = self.drift.get_perp_market_account(MARKET_INDEX)
                fill_price = Decimal(market.amm.last_oracle_price) / PRICE_PRECISION

                direction = 'bid' if position_delta > 0 else 'ask'
                self.performance.add_fill(direction, fill_price, abs(position_delta))

                logging.info(f"FILL: {direction.upper()} {abs(position_delta):.3f} @ ${float(fill_price):.2f}") # Changed print to logging.info

        except Exception as e:
            logging.warning(f"Sync error: {e}") # Changed print to logging.warning

    async def run(self):
        """Main trading loop"""
        await self.drift.subscribe()
        logging.info("Production Market Maker Online") # Changed print to logging.info
        logging.info(f"Target: ${TARGET_PROFIT_PER_3MIN}/3min = ${TARGET_PROFIT_PER_3MIN*20}/hour") # Changed print to logging.info

        try:
            while True:
                # 1. Get market data
                market_account = self.drift.get_perp_market_account(MARKET_INDEX)
                if not market_account:
                    await asyncio.sleep(1)
                    continue

                mid = Decimal(market_account.amm.last_oracle_price) / PRICE_PRECISION
                self.volatility.update(mid)

                market_state = MarketState(
                    mid_price=mid,
                    bid=mid * Decimal("0.9995"),
                    ask=mid * Decimal("1.0005"),
                    volatility=self.volatility.get_volatility(),
                    last_update=time.time()
                )

                # 2. Check for fills
                await self.sync_fills()

                # 3. Calculate optimal quotes
                bid, ask, size = self.quote_engine.calculate_quotes(market_state)

                # 4. Send update if needed
                now = time.time()
                if now - self.last_update >= self.update_interval:
                    bundle_id = await self.jito.send_update_bundle(
                        self.drift, bid, ask, size
                    )

                    self.performance.bundles_sent += 1
                    if bundle_id:
                        self.performance.bundles_landed += 1
                        logging.info(f"Quotes: Bid ${float(bid):.2f} / Ask ${float(ask):.2f} (Size: {float(size):.2f})") # Changed print to logging.info

                    self.last_update = now

                # 5. Print status every 30s
                if int(now) % 30 == 0:
                    self.performance.print_status(mid)

                await asyncio.sleep(0.5)

        except KeyboardInterrupt:
            logging.info("Shutting down...") # Changed print to logging.info
            self.performance.print_status(mid)
            await self.drift.unsubscribe()

# ============================================================

# ENTRY POINT

# ============================================================

async def main():
    try:
        with open("id.json", "r") as f:
            secret = json.load(f)
        kp = Keypair.from_secret_key(bytes(secret))
    except FileNotFoundError:
        logging.error("Missing id.json - place your Solana private key here") # Changed print to logging.error
        return

    # Configure logging here, before the MarketMaker is instantiated
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler("market_maker.log"),
            logging.StreamHandler()
        ]
    )

    mm = ProductionMarketMaker(kp)
    await mm.run()

if __name__ == "__main__":
    asyncio.run(main())