import json
from typing import AsyncIterator
import websockets

STREAM = "wss://stream.binance.com:9443/ws/!bookTicker"

async def book_ticker_stream() -> AsyncIterator[dict]:
    async with websockets.connect(
        STREAM, ping_interval=20, ping_timeout=20,
        close_timeout=5, max_queue=1000
    ) as ws:
        async for raw in ws:
            msg = json.loads(raw)
            if isinstance(msg, dict) and msg.get("s"):
                yield {
                    "symbol": msg["s"],
                    "bid": float(msg["b"]),
                    "bid_qty": float(msg["B"]),
                    "ask": float(msg["a"]),
                    "ask_qty": float(msg["A"]),
                    "event_time": int(msg.get("E", 0)),
                }
