from dataclasses import dataclass
from typing import Mapping

@dataclass(frozen=True)
class Quote:
    bid: float
    bid_qty: float
    ask: float
    ask_qty: float
    event_time: int

def conversion_rate(src: str, dst: str, quotes: Mapping[str, Quote]):
    direct, inverse = src + dst, dst + src
    if direct in quotes:
        q = quotes[direct]
        return q.bid if q.bid > 0 else None
    if inverse in quotes:
        q = quotes[inverse]
        return 1.0 / q.ask if q.ask > 0 else None
    return None

def evaluate_cycle(cycle, start_amount, quotes, fee_rate, slippage_bps):
    if len(cycle) < 3 or cycle[0] != cycle[-1]:
        return None
    amount = start_amount
    legs = []
    slip = max(0.0, 1.0 - slippage_bps / 10000.0)
    for src, dst in zip(cycle[:-1], cycle[1:]):
        rate = conversion_rate(src, dst, quotes)
        if rate is None:
            return None
        amount_out = amount * rate * slip * (1.0 - fee_rate)
        legs.append({"from": src, "to": dst, "input": amount,
                     "rate": rate, "output_after_costs": amount_out})
        amount = amount_out
    profit = amount - start_amount
    bps = profit / start_amount * 10000 if start_amount else 0.0
    return {"cycle": list(cycle), "start_asset": cycle[0],
            "start_amount": start_amount, "end_amount": amount,
            "profit": profit, "profit_bps": bps, "legs": legs}
