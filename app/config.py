import math
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _float(env, name, default, lo, hi):
    raw = str(env.get(name, default)).strip()
    try:
        value = float(raw)
    except ValueError:
        raise SystemExit(f"Invalid {name}: {raw!r}")
    if not math.isfinite(value) or value < lo or value > hi:
        raise SystemExit(f"{name} must be between {lo} and {hi}, got {raw}")
    return value


def _parse_cycles(raw, start_asset):
    cycles = []
    for part in raw.split(";"):
        part = part.strip().upper()
        if not part:
            continue
        a = [x.strip() for x in part.split(">")]
        if len(a) != 4 or a[0] != a[3] or len(set(a[:3])) != 3 or not all(x.isalnum() for x in a):
            raise SystemExit(f"Invalid CYCLES entry: {part!r} (expected like USDT>BTC>ETH>USDT)")
        if a[0] != start_asset:
            raise SystemExit(f"Cycle {part} must start with START_ASSET={start_asset}")
        cycles.append(tuple(a))
    if not cycles:
        raise SystemExit("CYCLES is empty")
    return tuple(cycles)


def expand_cycles(cycles):
    """Each triangle is checked in both directions."""
    seen, out = set(), []
    for c in cycles:
        for cand in (c, (c[0], c[2], c[1], c[0])):
            if cand not in seen:
                seen.add(cand)
                out.append(cand)
    return out


@dataclass(frozen=True)
class Config:
    start_asset: str
    start_amount: float
    cycles: tuple
    taker_fee_rate: float
    slippage_bps: float
    min_net_profit_bps: float
    cooldown_seconds: float
    max_quote_age_s: float
    telemetry_url: str
    telemetry_token: str
    ws_base: str
    rest_base: str


def load_config(env=None):
    env = os.environ if env is None else env
    # Hard guard: this program has no trading code. Any other mode is refused.
    mode = str(env.get("TRADING_MODE", "PAPER_ONLY")).strip().upper()
    if mode != "PAPER_ONLY":
        raise SystemExit("Refusing to start: only TRADING_MODE=PAPER_ONLY is supported")

    start_asset = str(env.get("START_ASSET", "USDT")).strip().upper()
    ws_base = str(env.get("BINANCE_WS_BASE", "wss://stream.binance.com:9443")).strip().rstrip("/")
    rest_base = str(env.get("BINANCE_REST_BASE", "https://api.binance.com")).strip().rstrip("/")
    if not ws_base.startswith("wss://") or not rest_base.startswith("https://"):
        raise SystemExit("BINANCE_WS_BASE must start with wss:// and BINANCE_REST_BASE with https://")

    return Config(
        start_asset=start_asset,
        start_amount=_float(env, "START_AMOUNT", 100, 1e-9, 1e9),
        cycles=_parse_cycles(str(env.get("CYCLES", "USDT>BTC>ETH>USDT")), start_asset),
        taker_fee_rate=_float(env, "TAKER_FEE_RATE", 0.001, 0, 0.01),
        slippage_bps=_float(env, "SLIPPAGE_BPS", 2, 0, 500),
        min_net_profit_bps=_float(env, "MIN_NET_PROFIT_BPS", 8, 0, 10000),
        cooldown_seconds=_float(env, "OPPORTUNITY_COOLDOWN_SECONDS", 5, 0, 3600),
        max_quote_age_s=_float(env, "MAX_QUOTE_AGE_MS", 5000, 100, 600000) / 1000.0,
        telemetry_url=str(env.get("TELEMETRY_URL", "")).strip(),
        telemetry_token=str(env.get("TELEMETRY_TOKEN", "")).strip(),
        ws_base=ws_base,
        rest_base=rest_base,
    )
