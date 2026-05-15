#!/usr/bin/env python3
"""
Real Market Maker for Gate.io
Continuous quoting with inventory management and dynamic spread
"""

import ccxt.async_support as ccxt
import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from rich.console import Console
from rich.table import Table

load_dotenv()
console = Console()

# Configuration
API_KEY = os.getenv('GATE_API_KEY', '')
API_SECRET = os.getenv('GATE_API_SECRET', '')

if not API_KEY or not API_SECRET:
    console.print('[bold red]FATAL: GATE_API_KEY and GATE_API_SECRET must be set')
    sys.exit(1)

# Market Making Parameters (Micro Account: $9)
BASE_SPREAD = 0.003          # 0.3% base spread (wider for micro caps)
VOLATILITY_ADJUSTMENT = 0.005  # Up to 0.5% added for volatility
FEE_BUFFER = 0.0015          # 0.15% fee coverage
MAX_INVENTORY_USD = 1.0      # Max $1 inventory skew (conservative for $9)
QUOTE_SIZE_USD = 0.30        # $0.30 per quote (small for micro account)
INVENTORY_SKEW_PCT = 0.002    # 0.2% skew per $1 inventory
MAX_SPREAD = 0.015           # 1.5% max spread
MIN_SPREAD = 0.002           # 0.2% min spread
MAX_POSITION_PCT = 0.10      # Max 10% of balance per position

# Risk
MAX_POSITION_AGE = 300       # 5 minutes max hold

@dataclass
class InventoryState:
    """Track net inventory position"""
    symbol: str
    net_contracts: float = 0.0   # Positive = net long, negative = net short
    avg_entry: float = 0.0
    total_bought: float = 0.0   # Running total
    total_sold: float = 0.0     # Running total
    spread_captured: float = 0.0  # Cumulative spread profit
    last_quote_time: float = 0.0
    bid_order_id: str = ''
    ask_order_id: str = ''
    bid_price: float = 0.0
    ask_price: float = 0.0

@dataclass
class TradeMetrics:
    """Track performance metrics"""
    total_trades: int = 0
    maker_fills: int = 0
    taker_fills: int = 0
    total_spread_captured: float = 0.0
    total_fees_paid: float = 0.0
    inventory_pnl: float = 0.0
    avg_fill_slippage: float = 0.0

class RealMarketMaker:
    """Continuous market maker with inventory management"""
    
    def __init__(self):
        self.exchange: Optional[ccxt.gateio] = None
        self.inventory: Dict[str, InventoryState] = {}
        self.metrics = TradeMetrics()
        self.symbols: List[str] = []
        self.running = False
        
    async def init(self):
        """Initialize exchange"""
        self.exchange = ccxt.gateio({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap',
                'defaultSettle': 'usdt'
            }
        })
        await self.exchange.load_markets()
        console.print('[green]✓ Exchange connected')
    
    async def get_balance(self) -> float:
        """Get USDT balance"""
        bal = await self.exchange.fetch_balance()
        return bal.get('USDT', {}).get('free', 0)
    
    async def fetch_subcent_tickers(self) -> List[str]:
        """Find sub-cent perpetuals"""
        console.print('[cyan]Scanning for sub-cent tickers...')
        tickers = await self.exchange.fetch_tickers()
        subcent = []
        
        for symbol, data in tickers.items():
            if not symbol.endswith(':USDT'):
                continue
            
            price = data.get('last', 0)
            volume = data.get('quoteVolume', 0)
            
            if 0 < price < 0.01 and volume > 5000:
                try:
                    market = self.exchange.market(symbol)
                    if market.get('swap', False):
                        subcent.append(symbol)
                        console.print(f'  [dim]{symbol} @ ${price:.6f}')
                except:
                    continue
        
        return subcent[:5]  # Top 5 sub-cent
    
    async def build_symbol_snapshot(self, symbol: str) -> Dict:
        """Build comprehensive symbol snapshot for LLM analysis"""
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            ob = await self.exchange.fetch_order_book(symbol, 5, {'type': 'swap'})
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '1m', limit=5, params={'type': 'swap'})
            
            best_bid = ob['bids'][0][0] if ob['bids'] else 0
            best_ask = ob['asks'][0][0] if ob['asks'] else 0
            spread = (best_ask - best_bid) if best_bid and best_ask else 0
            spread_pct = spread / ((best_bid + best_ask) / 2) if best_bid and best_ask else 0
            
            # Calculate momentum
            momentum_1m = 0
            if len(ohlcv) > 1:
                momentum_1m = (ohlcv[-1][4] - ohlcv[0][4]) / ohlcv[0][4]
            
            # Book imbalance
            bid_vol = sum(b[1] for b in ob['bids'][:3])
            ask_vol = sum(a[1] for a in ob['asks'][:3])
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0
            
            return {
                'symbol': symbol.split('/')[0],
                'price': ticker['last'],
                'bid': best_bid,
                'ask': best_ask,
                'spread': spread,
                'spread_pct': spread_pct * 100,
                'volume_24h': ticker.get('quoteVolume', 0),
                'change_24h': ticker.get('percentage', 0),
                'momentum_1m': momentum_1m * 100,
                'imbalance': imbalance,
                'valid': True
            }
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    async def query_llm(self, prompt: str, provider: str = "groq") -> str:
        """Query single LLM provider"""
        try:
            if provider == "groq":
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        'https://api.groq.com/openai/v1/chat/completions',
                        headers={'Authorization': f'Bearer {os.getenv("GROQ_API_KEY", "")}', 'Content-Type': 'application/json'},
                        json={'model': 'llama3-8b-8192', 'messages': [{'role': 'user', 'content': prompt}], 'max_tokens': 150, 'temperature': 0.3}
                    ) as resp:
                        data = await resp.json()
                        return data['choices'][0]['message']['content'] if 'choices' in data else ''
            elif provider == "local":
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{os.getenv('OLLAMA_URL', 'http://localhost:11434')}/api/generate",
                        json={'model': 'llama3.2:3b', 'prompt': prompt, 'stream': False}
                    ) as resp:
                        data = await resp.json()
                        return data.get('response', '')
        except Exception as e:
            return ''
    
    def build_llm_prompt(self, snapshot: Dict) -> str:
        """Build structured prompt for LLM"""
        return f"""Analyze this crypto perpetual market snapshot and return JSON ONLY:

Symbol: {snapshot['symbol']}
Price: ${snapshot['price']:.6f}
Spread: {snapshot['spread']:.8f} ({snapshot['spread_pct']:.3f}%)
24h Volume: ${snapshot['volume_24h']:,.0f}
24h Change: {snapshot['change_24h']:.2f}%
1m Momentum: {snapshot['momentum_1m']:.3f}%
Book Imbalance: {snapshot['imbalance']:.3f} (+1=heavy buy, -1=heavy sell)

Return strict JSON:
{{"bias": "long|short|neutral", "confidence": 0.0-1.0, "reason": "brief explanation", "volatility": "low|medium|high"}}"""
    
    async def get_llm_signal(self, snapshot: Dict) -> Dict:
        """Get aggregated signal from multiple LLMs with majority vote"""
        if not snapshot['valid']:
            return {'bias': 'neutral', 'confidence': 0, 'reason': 'invalid snapshot'}
        
        prompt = self.build_llm_prompt(snapshot)
        
        # Query multiple LLMs
        responses = await asyncio.gather(
            self.query_llm(prompt, 'groq'),
            self.query_llm(prompt, 'local'),
            return_exceptions=True
        )
        
        # Parse responses
        parsed = []
        for r in responses:
            if isinstance(r, str):
                try:
                    # Extract JSON from response
                    import re
                    json_match = re.search(r'\{.*\}', r, re.DOTALL)
                    if json_match:
                        parsed.append(json.loads(json_match.group()))
                except:
                    pass
        
        if not parsed:
            return {'bias': 'neutral', 'confidence': 0, 'reason': 'no valid llm responses'}
        
        # Majority vote
        bias_counts = {'long': 0, 'short': 0, 'neutral': 0}
        confidences = []
        reasons = []
        
        for p in parsed:
            bias = p.get('bias', 'neutral')
            if bias in bias_counts:
                bias_counts[bias] += 1
            confidences.append(p.get('confidence', 0))
            reasons.append(p.get('reason', ''))
        
        final_bias = max(bias_counts, key=bias_counts.get)
        avg_conf = sum(confidences) / len(confidences)
        
        return {
            'bias': final_bias,
            'confidence': avg_conf,
            'reason': reasons[0] if reasons else 'consensus',
            'votes': bias_counts
        }
    
    async def get_microstructure(self, symbol: str) -> Dict:
        """Get market microstructure data"""
        try:
            book = await self.exchange.fetch_order_book(symbol, 10, {'type': 'swap'})
            ticker = await self.exchange.fetch_ticker(symbol)
            ohlcv = await self.exchange.fetch_ohlcv(symbol, '1m', limit=3, params={'type': 'swap'})
            
            best_bid = book['bids'][0][0] if book['bids'] else 0
            best_ask = book['asks'][0][0] if book['asks'] else 0
            mid = (best_bid + best_ask) / 2 if best_bid and best_ask else ticker['last']
            
            # Calculate volatility from recent candles
            volatility = 0
            if len(ohlcv) >= 3:
                closes = [c[4] for c in ohlcv]
                avg_volatility = sum(abs((closes[i] - closes[i-1]) / closes[i-1]) 
                                 for i in range(1, len(closes))) / (len(closes) - 1)
                volatility = avg_volatility
            
            # Book imbalance
            bid_vol = sum(b[1] for b in book['bids'][:5])
            ask_vol = sum(a[1] for a in book['asks'][:5])
            imbalance = (bid_vol - ask_vol) / (bid_vol + ask_vol) if (bid_vol + ask_vol) > 0 else 0
            
            return {
                'mid': mid,
                'bid': best_bid,
                'ask': best_ask,
                'volatility': volatility,
                'imbalance': imbalance,
                'valid': True
            }
        except Exception as e:
            return {'valid': False, 'error': str(e)}
    
    def calculate_spread(self, volatility: float) -> float:
        """Dynamic spread: base + volatility + fee buffer"""
        vol_adjustment = min(VOLATILITY_ADJUSTMENT, volatility * 2)
        spread = BASE_SPREAD + vol_adjustment + FEE_BUFFER
        return max(MIN_SPREAD, min(MAX_SPREAD, spread))
    
    def calculate_inventory_skew(self, symbol: str, mid: float) -> Tuple[float, float]:
        """Calculate bid/ask skew based on net inventory"""
        inv = self.inventory.get(symbol)
        if not inv:
            return (0, 0)
        
        # Net inventory value in USD
        inventory_value = inv.net_contracts * mid
        
        # Calculate skew: if too long, lower both quotes to sell faster
        # If too short, raise both quotes to buy faster
        skew = inventory_value * INVENTORY_SKEW_PCT
        
        # Limit skew
        max_skew = mid * MAX_SPREAD * 0.5
        skew = max(-max_skew, min(max_skew, skew))
        
        return (skew, inventory_value)
    
    async def place_quotes(self, symbol: str, micro: Dict) -> bool:
        """Place continuous bid/ask quotes with inventory skew"""
        inv = self.inventory.setdefault(symbol, InventoryState(symbol))
        
        mid = micro['mid']
        spread = self.calculate_spread(micro['volatility'])
        half_spread = spread / 2
        
        # Calculate inventory skew
        skew, inventory_value = self.calculate_inventory_skew(symbol, mid)
        
        # If inventory too skewed, pause quoting that side
        if abs(inventory_value) > MAX_INVENTORY_USD:
            console.print(f'[yellow]{symbol}: Inventory limit reached (${inventory_value:.2f})')
            await self.flatten_inventory(symbol)
            return False
        
        # Calculate quote prices with skew
        # If net long (positive inventory), lower prices to sell faster
        # If net short (negative inventory), raise prices to buy faster
        bid_price = mid * (1 - half_spread) - skew
        ask_price = mid * (1 + half_spread) - skew
        
        # Calculate sizes
        quote_contracts = QUOTE_SIZE_USD / mid
        
        # Cancel existing quotes
        await self.cancel_all_quotes(symbol)
        
        # Place new quotes
        try:
            bid_order = await self.exchange.create_limit_order(
                symbol, 'buy', quote_contracts, bid_price,
                {'postOnly': True, 'type': 'swap'}
            )
            inv.bid_order_id = bid_order.get('id', '')
            inv.bid_price = bid_price
            
            ask_order = await self.exchange.create_limit_order(
                symbol, 'sell', quote_contracts, ask_price,
                {'postOnly': True, 'type': 'swap'}
            )
            inv.ask_order_id = ask_order.get('id', '')
            inv.ask_price = ask_price
            inv.last_quote_time = time.time()
            
            short_sym = symbol.split('/')[0]
            console.print(f'[dim]{short_sym}: Bid ${bid_price:.8f} / Ask ${ask_price:.8f} '
                         f'(spread {spread*100:.2f}%, inv ${inventory_value:.2f})')
            return True
            
        except Exception as e:
            console.print(f'[red]Quote error {symbol}: {e}')
            return False
    
    async def cancel_all_quotes(self, symbol: str):
        """Cancel existing quotes"""
        inv = self.inventory.get(symbol)
        if not inv:
            return
        
        for order_id in [inv.bid_order_id, inv.ask_order_id]:
            if order_id:
                try:
                    await self.exchange.cancel_order(order_id, symbol, {'type': 'swap'})
                except:
                    pass
        
        inv.bid_order_id = ''
        inv.ask_order_id = ''
    
    async def check_fills(self, symbol: str, micro: Dict):
        """Check for fills and update inventory"""
        inv = self.inventory.get(symbol)
        if not inv:
            return
        
        mid = micro['mid']
        
        # Check bid fill
        if inv.bid_order_id:
            try:
                order = await self.exchange.fetch_order(inv.bid_order_id, symbol, {'type': 'swap'})
                if order['status'] == 'closed' and order['filled'] > 0:
                    fill_price = float(order['average'] or order['price'])
                    filled_contracts = float(order['filled'])
                    
                    # Update inventory: bought contracts
                    inv.net_contracts += filled_contracts
                    inv.total_bought += filled_contracts * fill_price
                    inv.bid_order_id = ''
                    
                    self.metrics.total_trades += 1
                    self.metrics.maker_fills += 1
                    
                    # Calculate spread captured
                    spread_captured = (inv.ask_price - fill_price) * filled_contracts
                    inv.spread_captured += spread_captured
                    self.metrics.total_spread_captured += spread_captured
                    
                    short_sym = symbol.split('/')[0]
                    console.print(f'[green]{short_sym}: BOUGHT {filled_contracts:.0f} @ ${fill_price:.8f} '
                                 f'(inv: {inv.net_contracts:+.0f}, spread captured: ${spread_captured:.4f})')
            except Exception:
                pass
        
        # Check ask fill
        if inv.ask_order_id:
            try:
                order = await self.exchange.fetch_order(inv.ask_order_id, symbol, {'type': 'swap'})
                if order['status'] == 'closed' and order['filled'] > 0:
                    fill_price = float(order['average'] or order['price'])
                    filled_contracts = float(order['filled'])
                    
                    # Update inventory: sold contracts
                    inv.net_contracts -= filled_contracts
                    inv.total_sold += filled_contracts * fill_price
                    inv.ask_order_id = ''
                    
                    self.metrics.total_trades += 1
                    self.metrics.maker_fills += 1
                    
                    # Calculate spread captured
                    spread_captured = (fill_price - inv.bid_price) * filled_contracts
                    inv.spread_captured += spread_captured
                    self.metrics.total_spread_captured += spread_captured
                    
                    short_sym = symbol.split('/')[0]
                    console.print(f'[green]{short_sym}: SOLD {filled_contracts:.0f} @ ${fill_price:.8f} '
                                 f'(inv: {inv.net_contracts:+.0f}, spread captured: ${spread_captured:.4f})')
            except Exception:
                pass
    
    async def flatten_inventory(self, symbol: str):
        """Close inventory with market order if needed"""
        inv = self.inventory.get(symbol)
        if not inv or abs(inv.net_contracts) < 1:
            return
        
        console.print(f'[yellow]Flattening {symbol} inventory: {inv.net_contracts:+.0f} contracts')
        
        try:
            if inv.net_contracts > 0:
                # Net long, sell
                await self.exchange.create_market_order(
                    symbol, 'sell', abs(inv.net_contracts),
                    {'reduceOnly': True, 'type': 'swap'}
                )
            else:
                # Net short, buy
                await self.exchange.create_market_order(
                    symbol, 'buy', abs(inv.net_contracts),
                    {'reduceOnly': True, 'type': 'swap'}
                )
            
            inv.net_contracts = 0
            console.print(f'[green]Inventory flattened')
        except Exception as e:
            console.print(f'[red]Flatten error: {e}')
    
    async def update_inventory_pnl(self, symbol: str, micro: Dict):
        """Update unrealized PnL on inventory"""
        inv = self.inventory.get(symbol)
        if not inv or inv.net_contracts == 0:
            return
        
        mid = micro['mid']
        # Unrealized PnL = (current price - avg entry) * position
        if inv.avg_entry > 0:
            unrealized = (mid - inv.avg_entry) * inv.net_contracts
            self.metrics.inventory_pnl = unrealized
    
    def should_skip_market(self, micro: Dict) -> bool:
        """Skip extreme markets"""
        # Skip if volatility too high
        if micro['volatility'] > 0.01:  # 1% per minute
            return True
        
        # Skip if extreme imbalance
        if abs(micro['imbalance']) > 0.7:
            return True
        
        return False
    
    async def run_cycle(self, symbol: str):
        """Single market making cycle with LLM signal filter"""
        # Check available balance first
        try:
            balance = await self.get_balance()
            if balance < 1.0:  # Need at least $1 to quote
                return
        except:
            return
        
        # Get market data
        micro = await self.get_microstructure(symbol)
        if not micro['valid']:
            return
        
        # Skip bad markets
        if self.should_skip_market(micro):
            short_sym = symbol.split('/')[0]
            console.print(f'[dim]{short_sym}: Skipping (vol={micro["volatility"]:.4f}, imb={micro["imbalance"]:.2f})')
            return
        
        # Get LLM signal for bias
        snapshot = await self.build_symbol_snapshot(symbol)
        llm_signal = await self.get_llm_signal(snapshot)
        
        short_sym = symbol.split('/')[0]
        
        # Filter: Only trade if confidence >= 0.6
        if llm_signal['confidence'] < 0.6:
            console.print(f'[dim]{short_sym}: LLM confidence too low ({llm_signal["confidence"]:.2f})')
            return
        
        # Log LLM signal
        console.print(f'[cyan]{short_sym}: LLM {llm_signal["bias"].upper()} (conf={llm_signal["confidence"]:.2f}, votes={llm_signal["votes"]})')
        
        # Use LLM bias to filter quoting
        # If strongly biased, only quote that side or widen opposite
        if llm_signal['bias'] == 'long':
            # Bullish - bias toward buying
            pass  # Normal quoting
        elif llm_signal['bias'] == 'short':
            # Bearish - bias toward selling  
            pass  # Normal quoting
        else:
            # Neutral - be cautious
            pass
        
        # Check for fills
        await self.check_fills(symbol, micro)
        
        # Update inventory PnL
        await self.update_inventory_pnl(symbol, micro)
        
        # Refresh quotes if needed
        inv = self.inventory.get(symbol)
        time_since_quote = time.time() - (inv.last_quote_time if inv else 0)
        
        # Refresh every 3 seconds or if orders missing
        need_refresh = time_since_quote > 3 or not inv or (not inv.bid_order_id and not inv.ask_order_id)
        
        if need_refresh:
            await self.place_quotes(symbol, micro)
    
    async def print_status(self):
        """Print current status"""
        balance = await self.get_balance()
        
        table = Table(title='Market Maker Status')
        table.add_column('Metric', style='cyan')
        table.add_column('Value', style='green')
        
        table.add_row('Balance', f'${balance:.2f}')
        table.add_row('Total Trades', str(self.metrics.total_trades))
        table.add_row('Maker Fills', str(self.metrics.maker_fills))
        table.add_row('Spread Captured', f'${self.metrics.total_spread_captured:.4f}')
        table.add_row('Inventory PnL', f'${self.metrics.inventory_pnl:.4f}')
        
        # Per-symbol inventory
        for sym, inv in self.inventory.items():
            if inv.net_contracts != 0:
                short_sym = sym.split('/')[0]
                table.add_row(f'Inventory {short_sym}', f'{inv.net_contracts:+.0f}')
        
        console.print('\n')
        console.print(table)
    
    async def run(self):
        """Main loop"""
        await self.init()
        
        # Get symbols
        self.symbols = await self.fetch_subcent_tickers()
        if not self.symbols:
            console.print('[red]No sub-cent tickers found')
            return
        
        console.print(f'[cyan]Market making on {len(self.symbols)} symbols')
        console.print('[cyan]Press Ctrl+C to stop\n')
        
        self.running = True
        cycle_count = 0
        
        try:
            while self.running:
                # Run cycle for each symbol
                for symbol in self.symbols:
                    await self.run_cycle(symbol)
                    await asyncio.sleep(0.2)  # Small delay between symbols
                
                cycle_count += 1
                
                # Print status every 10 cycles
                if cycle_count % 10 == 0:
                    await self.print_status()
                
                await asyncio.sleep(1)  # 1 second between full cycles
                
        except KeyboardInterrupt:
            console.print('\n[yellow]Stopping...')
            for symbol in self.symbols:
                await self.cancel_all_quotes(symbol)
                await self.flatten_inventory(symbol)
            console.print('[green]Stopped')

async def main():
    """Main entry point with proper cleanup"""
    mm = RealMarketMaker()
    try:
        await mm.run()
    finally:
        # Ensure exchange is properly closed
        if mm.exchange:
            try:
                await mm.exchange.close()
                console.print('[dim]Exchange connection closed')
            except Exception:
                pass

if __name__ == '__main__':
    asyncio.run(main())
