import asyncio
import logging
import time
from app.config import Config, CYCLE
from app.market_data import book_ticker_stream
from app.arbitrage import Quote, evaluate_cycle
from app.telemetry import send_telemetry

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("mr-market-intelligence")

async def run():
    cfg = Config()
    quotes = {}
    last_alert = 0.0
    log.info("PAPER ONLY | cycle=%s | capital=%s %s",
             " -> ".join(CYCLE), cfg.start_amount, cfg.start_asset)
    while True:
        try:
            async for tick in book_ticker_stream():
                quotes[tick["symbol"]] = Quote(
                    tick["bid"], tick["bid_qty"], tick["ask"],
                    tick["ask_qty"], tick["event_time"])
                result = evaluate_cycle(CYCLE, cfg.start_amount, quotes,
                                        cfg.taker_fee_rate, cfg.slippage_bps)
                if result is None:
                    continue
                now = time.monotonic()
                if (result["profit_bps"] >= cfg.min_net_profit_bps
                        and now - last_alert >= cfg.cooldown_seconds):
                    last_alert = now
                    event = {"type": "paper_opportunity",
                             "timestamp_ms": int(time.time() * 1000),
                             "mode": "PAPER_ONLY", **result}
                    log.warning("PAPER OPPORTUNITY net=%+.6f %s (%+.2f bps)",
                                result["profit"], cfg.start_asset,
                                result["profit_bps"])
                    try:
                        await send_telemetry(cfg.telemetry_url, event)
                    except Exception:
                        log.exception("Telemetry delivery failed")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Market stream error; reconnecting in 3 seconds")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(run())
