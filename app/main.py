import asyncio
import logging
import time
from collections import Counter, defaultdict

from app.arbitrage import Plan, Quote, build_legs, evaluate_cycle
from app.config import expand_cycles, load_config
from app.market_data import book_ticker_stream, fetch_symbols
from app.telemetry import Telemetry

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("mr-market-intelligence")


class Scanner:
    def __init__(self, cfg, plans, submit):
        self.cfg = cfg
        self.submit = submit
        self.quotes = {}
        self.by_symbol = defaultdict(list)
        for plan in plans:
            for leg in plan.legs:
                self.by_symbol[leg.symbol].append(plan)
        self.last_alert = {}
        self.ticks = 0
        self.evaluated = 0
        self.rejects = Counter()
        self.best_bps = {}
        self.last_report = time.monotonic()

    def reset(self):
        self.quotes.clear()  # never reuse prices from a previous connection

    def on_tick(self, tick, now):
        cfg = self.cfg
        self.ticks += 1
        self.quotes[tick["symbol"]] = Quote(tick["bid"], tick["bid_qty"], tick["ask"],
                                            tick["ask_qty"], now)
        for plan in self.by_symbol.get(tick["symbol"], ()):
            result, reason = evaluate_cycle(plan, cfg.start_amount, self.quotes, cfg.taker_fee_rate,
                                            cfg.slippage_bps, cfg.max_quote_age_s, now)
            if result is None:
                self.rejects[reason] += 1
                continue
            self.evaluated += 1
            bps = result["profit_bps"]
            if bps > self.best_bps.get(plan.key, float("-inf")):
                self.best_bps[plan.key] = bps
            if bps >= cfg.min_net_profit_bps and now - self.last_alert.get(plan.key, -1e9) >= cfg.cooldown_seconds:
                self.last_alert[plan.key] = now
                log.warning("PAPER OPPORTUNITY %s net=%+.6f %s (%+.2f bps)", plan.key,
                            result["profit"], cfg.start_asset, bps)
                self.submit({"type": "paper_opportunity", "mode": "PAPER_ONLY",
                             "timestamp_ms": int(time.time() * 1000), **result})
        if now - self.last_report >= 60:
            self.last_report = now
            best = {k: round(v, 2) for k, v in self.best_bps.items()}
            log.info("stats | ticks=%d evaluated=%d rejected=%s best_net_bps=%s",
                     self.ticks, self.evaluated, dict(self.rejects), best)


async def run():
    cfg = load_config()
    log.info("PAPER ONLY | capital=%s %s | cycles=%s", cfg.start_amount, cfg.start_asset,
             "; ".join(">".join(c) for c in cfg.cycles))
    if cfg.telemetry_url and not cfg.telemetry_token:
        log.warning("TELEMETRY_URL is set but TELEMETRY_TOKEN is empty: the Worker will reject events")

    delay = 1.0
    while True:  # load the symbol list, retrying with backoff
        try:
            symbols = await fetch_symbols(cfg.rest_base)
            break
        except Exception as exc:
            log.error("Could not load exchange info (%s); retrying in %.0fs", type(exc).__name__, delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    plans = []
    for cycle in expand_cycles(cfg.cycles):
        legs = build_legs(cycle, symbols)
        if legs is None:
            log.warning("Skipping %s: a symbol does not exist or is not trading", ">".join(cycle))
        else:
            plans.append(Plan(cycle, tuple(legs)))
    if not plans:
        raise SystemExit("No usable cycles")
    needed = {leg.symbol for p in plans for leg in p.legs}
    log.info("Watching %d symbols: %s", len(needed), ", ".join(sorted(needed)))

    telemetry = Telemetry(cfg.telemetry_url, cfg.telemetry_token)
    sender = asyncio.create_task(telemetry.run())
    scanner = Scanner(cfg, plans, telemetry.submit)
    delay = 1.0
    try:
        while True:
            scanner.reset()
            started = time.monotonic()
            try:
                async for tick in book_ticker_stream(cfg.ws_base, needed):
                    scanner.on_tick(tick, time.monotonic())
                log.warning("Market stream closed")
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("Market stream error")
            if time.monotonic() - started > 60:
                delay = 1.0
            log.warning("Reconnecting in %.0f seconds", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)
    finally:
        sender.cancel()


if __name__ == "__main__":
    asyncio.run(run())
