from __future__ import annotations
import asyncio, json, logging, time
import websockets
from app.config import Settings

log = logging.getLogger(__name__)

class GatePublicWS:
    def __init__(self, cfg: Settings, on_book_ticker):
        self.cfg = cfg
        self.on_book_ticker = on_book_ticker
        self.shutdown = False

    async def run_book_ticker(self, symbols: list[str]) -> None:
        backoff = 1.0
        while not self.shutdown:
            try:
                if not symbols:
                    await asyncio.sleep(1.0)
                    continue
                async with websockets.connect(self.cfg.gate_ws_url, ping_interval=20, ping_timeout=20, max_size=2**23) as ws:
                    await ws.send(json.dumps({
                        "time": int(time.time()),
                        "channel": "futures.book_ticker",
                        "event": "subscribe",
                        "payload": symbols,
                    }))
                    backoff = 1.0
                    async for raw in ws:
                        data = json.loads(raw)
                        result = data.get("result") or data.get("payload")
                        if data.get("channel") != "futures.book_ticker":
                            continue
                        if isinstance(result, list):
                            for item in result:
                                await self.on_book_ticker(item)
                        elif isinstance(result, dict):
                            await self.on_book_ticker(result)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.warning("public ws reconnect: %s", e)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 20.0)
