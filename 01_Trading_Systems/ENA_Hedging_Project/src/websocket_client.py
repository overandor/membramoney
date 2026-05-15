#!/usr/bin/env python3
"""
WEBSOCKET CLIENT FOR ENA HEDGING SYSTEM
Real-time market data streaming
"""

import asyncio
import websockets
import json
import time
import logging
from typing import Dict, List, Callable, Optional

log = logging.getLogger(__name__)

class WebSocketClient:
    """WebSocket client for real-time market data"""
    
    def __init__(self, config, on_message_callback: Callable):
        self.config = config
        self.on_message_callback = on_message_callback
        self.ws = None
        self.running = False
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 10
        self.last_ping = time.time()
        self.subscribed_channels = set()
        
    async def connect(self) -> bool:
        """Connect to WebSocket"""
        try:
            log.info(f"📡 Connecting to WebSocket: {self.config.ws_url}")
            self.ws = await websockets.connect(
                self.config.ws_url,
                ping_interval=self.config.ws_ping_interval,
                ping_timeout=self.config.ws_timeout,
                close_timeout=self.config.ws_timeout
            )
            
            self.running = True
            self.reconnect_attempts = 0
            log.info("✅ WebSocket connected successfully")
            return True
            
        except Exception as e:
            log.error(f"❌ WebSocket connection failed: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        if self.ws:
            await self.ws.close()
            log.info("📡 WebSocket disconnected")
    
    async def subscribe_order_book(self, symbol: str, level: int = 5, interval: int = 0):
        """Subscribe to order book updates"""
        if not self.ws:
            log.error("❌ WebSocket not connected")
            return False
        
        try:
            subscribe_msg = {
                "time": int(time.time()),
                "channel": "futures.order_book",
                "event": "subscribe",
                "payload": [symbol, level, interval]
            }
            
            await self.ws.send(json.dumps(subscribe_msg))
            self.subscribed_channels.add(f"futures.order_book.{symbol}")
            log.info(f"📊 Subscribed to order book: {symbol}")
            return True
            
        except Exception as e:
            log.error(f"❌ Failed to subscribe to order book: {e}")
            return False
    
    async def subscribe_trades(self, symbol: str):
        """Subscribe to trades"""
        if not self.ws:
            log.error("❌ WebSocket not connected")
            return False
        
        try:
            subscribe_msg = {
                "time": int(time.time()),
                "channel": "futures.trades",
                "event": "subscribe",
                "payload": [symbol]
            }
            
            await self.ws.send(json.dumps(subscribe_msg))
            self.subscribed_channels.add(f"futures.trades.{symbol}")
            log.info(f"📈 Subscribed to trades: {symbol}")
            return True
            
        except Exception as e:
            log.error(f"❌ Failed to subscribe to trades: {e}")
            return False
    
    async def subscribe_tickers(self, symbol: str):
        """Subscribe to ticker updates"""
        if not self.ws:
            log.error("❌ WebSocket not connected")
            return False
        
        try:
            subscribe_msg = {
                "time": int(time.time()),
                "channel": "futures.tickers",
                "event": "subscribe",
                "payload": [symbol]
            }
            
            await self.ws.send(json.dumps(subscribe_msg))
            self.subscribed_channels.add(f"futures.tickers.{symbol}")
            log.info(f"💰 Subscribed to tickers: {symbol}")
            return True
            
        except Exception as e:
            log.error(f"❌ Failed to subscribe to tickers: {e}")
            return False
    
    async def unsubscribe_all(self):
        """Unsubscribe from all channels"""
        if not self.ws:
            return
        
        for channel in list(self.subscribed_channels):
            try:
                unsubscribe_msg = {
                    "time": int(time.time()),
                    "channel": channel.split('.')[0],
                    "event": "unsubscribe",
                    "payload": [channel.split('.')[1]]
                }
                await self.ws.send(json.dumps(unsubscribe_msg))
                self.subscribed_channels.remove(channel)
            except Exception as e:
                log.error(f"❌ Failed to unsubscribe from {channel}: {e}")
    
    async def send_ping(self):
        """Send ping to keep connection alive"""
        if self.ws and self.running:
            try:
                ping_msg = {
                    "time": int(time.time()),
                    "channel": "futures.ping",
                    "event": "ping",
                    "payload": []
                }
                await self.ws.send(json.dumps(ping_msg))
                self.last_ping = time.time()
            except Exception as e:
                log.error(f"❌ Failed to send ping: {e}")
    
    async def process_messages(self):
        """Process incoming WebSocket messages"""
        try:
            async for message in self.ws:
                if not self.running:
                    break
                
                try:
                    data = json.loads(message)
                    
                    # Handle different message types
                    if data.get('channel') == 'futures.order_book':
                        await self.handle_order_book(data)
                    elif data.get('channel') == 'futures.trades':
                        await self.handle_trades(data)
                    elif data.get('channel') == 'futures.tickers':
                        await self.handle_tickers(data)
                    elif data.get('channel') == 'futures.ping':
                        await self.handle_ping(data)
                    else:
                        log.debug(f"📨 Unknown message type: {data.get('channel')}")
                    
                except json.JSONDecodeError as e:
                    log.error(f"❌ Failed to decode JSON: {e}")
                except Exception as e:
                    log.error(f"❌ Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            log.warning("⚠️ WebSocket connection closed")
            await self.handle_reconnect()
        except Exception as e:
            log.error(f"❌ WebSocket error: {e}")
            await self.handle_reconnect()
    
    async def handle_order_book(self, data):
        """Handle order book updates"""
        if data.get('event') == 'update' and data.get('result'):
            result = data['result']
            symbol = result.get('s', '')
            bids = result.get('bids', [])
            asks = result.get('asks', [])
            
            if bids and asks:
                await self.on_message_callback('order_book', {
                    'symbol': symbol,
                    'bids': bids,
                    'asks': asks,
                    'timestamp': data.get('time', time.time())
                })
    
    async def handle_trades(self, data):
        """Handle trade updates"""
        if data.get('event') == 'update' and data.get('result'):
            result = data['result']
            for trade in result:
                await self.on_message_callback('trade', {
                    'symbol': trade.get('s', ''),
                    'price': trade.get('p', 0),
                    'size': trade.get('v', 0),
                    'side': trade.get('S', ''),
                    'timestamp': trade.get('t', time.time())
                })
    
    async def handle_tickers(self, data):
        """Handle ticker updates"""
        if data.get('event') == 'update' and data.get('result'):
            result = data['result']
            await self.on_message_callback('ticker', {
                'symbol': result.get('s', ''),
                'last_price': result.get('c', 0),
                'volume_24h': result.get('v', 0),
                'change_24h': result.get('P', 0),
                'high_24h': result.get('h', 0),
                'low_24h': result.get('l', 0),
                'timestamp': data.get('time', time.time())
            })
    
    async def handle_ping(self, data):
        """Handle ping responses"""
        self.last_ping = time.time()
        log.debug("🏓 Ping received")
    
    async def handle_reconnect(self):
        """Handle reconnection logic"""
        if not self.running:
            return
        
        self.reconnect_attempts += 1
        
        if self.reconnect_attempts > self.max_reconnect_attempts:
            log.error(f"❌ Max reconnection attempts ({self.max_reconnect_attempts}) reached")
            self.running = False
            return
        
        wait_time = min(self.config.ws_reconnect_delay * self.reconnect_attempts, 60)
        log.info(f"🔄 Reconnecting in {wait_time} seconds... (attempt {self.reconnect_attempts})")
        
        await asyncio.sleep(wait_time)
        
        if await self.connect():
            # Resubscribe to all channels
            for channel in list(self.subscribed_channels):
                parts = channel.split('.')
                if len(parts) >= 2:
                    channel_type = parts[0]
                    symbol = parts[1]
                    
                    if channel_type == 'futures.order_book':
                        await self.subscribe_order_book(symbol)
                    elif channel_type == 'futures.trades':
                        await self.subscribe_trades(symbol)
                    elif channel_type == 'futures.tickers':
                        await self.subscribe_tickers(symbol)
    
    async def start(self, symbol: str):
        """Start WebSocket client with symbol subscriptions"""
        if not await self.connect():
            return False
        
        # Subscribe to essential channels
        await self.subscribe_order_book(symbol)
        await self.subscribe_tickers(symbol)
        
        # Start message processing
        await self.process_messages()
        
        return True
    
    async def stop(self):
        """Stop WebSocket client"""
        self.running = False
        await self.unsubscribe_all()
        await self.disconnect()

class MarketDataManager:
    """Manages market data from WebSocket"""
    
    def __init__(self, config):
        self.config = config
        self.order_books = {}  # symbol -> order book data
        self.tickers = {}      # symbol -> ticker data
        self.trades = []       # recent trades
        self.callbacks = {}    # event callbacks
        
    def add_callback(self, event_type: str, callback: Callable):
        """Add callback for specific event type"""
        if event_type not in self.callbacks:
            self.callbacks[event_type] = []
        self.callbacks[event_type].append(callback)
    
    def remove_callback(self, event_type: str, callback: Callable):
        """Remove callback for specific event type"""
        if event_type in self.callbacks:
            try:
                self.callbacks[event_type].remove(callback)
            except ValueError:
                pass
    
    async def handle_message(self, message_type: str, data: Dict):
        """Handle incoming market data message"""
        if message_type == 'order_book':
            symbol = data['symbol']
            self.order_books[symbol] = {
                'bids': data['bids'],
                'asks': data['asks'],
                'timestamp': data['timestamp']
            }
        elif message_type == 'ticker':
            symbol = data['symbol']
            self.tickers[symbol] = data
        elif message_type == 'trade':
            self.trades.append(data)
            # Keep only last 100 trades
            if len(self.trades) > 100:
                self.trades.pop(0)
        
        # Trigger callbacks
        if message_type in self.callbacks:
            for callback in self.callbacks[message_type]:
                try:
                    await callback(data)
                except Exception as e:
                    log.error(f"❌ Callback error: {e}")
    
    def get_order_book(self, symbol: str) -> Optional[Dict]:
        """Get order book for symbol"""
        return self.order_books.get(symbol)
    
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker for symbol"""
        return self.tickers.get(symbol)
    
    def get_mid_price(self, symbol: str) -> Optional[float]:
        """Get mid price for symbol"""
        order_book = self.get_order_book(symbol)
        if order_book and order_book['bids'] and order_book['asks']:
            best_bid = float(order_book['bids'][0][0])
            best_ask = float(order_book['asks'][0][0])
            return (best_bid + best_ask) / 2
        return None
    
    def get_spread_bps(self, symbol: str) -> Optional[float]:
        """Get spread in basis points for symbol"""
        order_book = self.get_order_book(symbol)
        if order_book and order_book['bids'] and order_book['asks']:
            best_bid = float(order_book['bids'][0][0])
            best_ask = float(order_book['asks'][0][0])
            mid = (best_bid + best_ask) / 2
            return (best_ask - best_bid) / mid * 10000
        return None
