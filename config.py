import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Config:
    start_asset: str = os.getenv("START_ASSET", "USDT").upper()
    start_amount: float = float(os.getenv("START_AMOUNT", "100"))
    taker_fee_rate: float = float(os.getenv("TAKER_FEE_RATE", "0.001"))
    slippage_bps: float = float(os.getenv("SLIPPAGE_BPS", "2"))
    min_net_profit_bps: float = float(os.getenv("MIN_NET_PROFIT_BPS", "8"))
    cooldown_seconds: float = float(os.getenv("OPPORTUNITY_COOLDOWN_SECONDS", "5"))
    telemetry_url: str = os.getenv("TELEMETRY_URL", "").strip()

CYCLE = ("USDT", "BTC", "ETH", "USDT")
