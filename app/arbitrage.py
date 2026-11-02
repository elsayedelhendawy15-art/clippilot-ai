from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional


@dataclass(frozen=True)
class Quote:
    bid: float
    bid_qty: float
    ask: float
    ask_qty: float
    received_at: float  # local monotonic seconds (Binance spot bookTicker has no event time)


@dataclass(frozen=True)
class Leg:
    src: str
    dst: str
    symbol: str
    side: str  # "SELL": src is the base asset, sell at bid. "BUY": src is the quote asset, buy at ask.
    min_notional: float


@dataclass(frozen=True)
class Plan:
    cycle: tuple
    legs: tuple

    @property
    def key(self) -> str:
        return ">".join(self.cycle)


def build_legs(cycle, symbols: Mapping) -> Optional[list]:
    """symbols maps (base, quote) -> {"symbol": str, "min_notional": float}."""
    legs = []
    for src, dst in zip(cycle[:-1], cycle[1:]):
        if (src, dst) in symbols:
            info, side = symbols[(src, dst)], "SELL"
        elif (dst, src) in symbols:
            info, side = symbols[(dst, src)], "BUY"
        else:
            return None
        legs.append(Leg(src, dst, info["symbol"], side, info["min_notional"]))
    return legs


def evaluate_cycle(plan: Plan, start_amount: float, quotes: Mapping, fee_rate: float,
                   slippage_bps: float, max_age_s: float, now: float):
    """Returns (result, None) or (None, reason). Profit is net of fees and slippage on every leg,
    and a cycle is rejected unless top-of-book size can actually absorb each leg."""
    slip = 1.0 - slippage_bps / 10000.0
    amount = start_amount
    legs_out = []
    for leg in plan.legs:
        q = quotes.get(leg.symbol)
        if q is None:
            return None, "missing_quote"
        if now - q.received_at > max_age_s:
            return None, "stale_quote"
        if leg.side == "SELL":
            if amount > q.bid_qty:
                return None, "insufficient_size"
            rate = q.bid
            raw_out = amount * q.bid
            notional = raw_out
        else:
            if amount / q.ask > q.ask_qty:
                return None, "insufficient_size"
            rate = 1.0 / q.ask
            raw_out = amount / q.ask
            notional = amount
        if notional < leg.min_notional:
            return None, "below_min_notional"
        out = raw_out * slip * (1.0 - fee_rate)
        legs_out.append({"from": leg.src, "to": leg.dst, "symbol": leg.symbol, "side": leg.side,
                         "input": amount, "rate": rate, "output_after_costs": out})
        amount = out
    profit = amount - start_amount
    return {
        "cycle": list(plan.cycle), "start_asset": plan.cycle[0],
        "start_amount": start_amount, "end_amount": amount,
        "profit": profit, "profit_bps": profit / start_amount * 10000.0,
        "legs": legs_out,
    }, None
