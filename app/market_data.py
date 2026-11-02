import json
import math

import httpx
import websockets


async def fetch_symbols(rest_base):
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(f"{rest_base}/api/v3/exchangeInfo")
        response.raise_for_status()
        return parse_symbols(response.json())


def parse_symbols(info):
    out = {}
    for s in info.get("symbols", []):
        if s.get("status") != "TRADING" or not s.get("baseAsset") or not s.get("quoteAsset") or not s.get("symbol"):
            continue
        min_notional = 0.0
        for f in s.get("filters", []):
            if f.get("filterType") in ("NOTIONAL", "MIN_NOTIONAL"):
                try:
                    min_notional = float(f.get("minNotional", 0))
                except (TypeError, ValueError):
                    pass
        out[(s["baseAsset"], s["quoteAsset"])] = {"symbol": s["symbol"], "min_notional": min_notional}
    return out


def parse_book_ticker(msg):
    data = msg.get("data", msg) if isinstance(msg, dict) else None
    if not isinstance(data, dict) or not data.get("s"):
        return None
    try:
        bid, bid_qty = float(data["b"]), float(data["B"])
        ask, ask_qty = float(data["a"]), float(data["A"])
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(x) for x in (bid, bid_qty, ask, ask_qty)):
        return None
    if bid <= 0 or ask <= 0 or bid_qty <= 0 or ask_qty <= 0 or bid > ask:
        return None  # invalid or crossed book
    return {"symbol": data["s"], "bid": bid, "bid_qty": bid_qty, "ask": ask, "ask_qty": ask_qty}


async def book_ticker_stream(ws_base, symbols):
    streams = "/".join(f"{s.lower()}@bookTicker" for s in sorted(symbols))
    url = f"{ws_base}/stream?streams={streams}"
    async with websockets.connect(url, ping_interval=20, ping_timeout=20,
                                  close_timeout=5, max_queue=1000) as ws:
        async for raw in ws:
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            tick = parse_book_ticker(msg)
            if tick:
                yield tick
