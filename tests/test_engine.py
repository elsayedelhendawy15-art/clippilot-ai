"""Unit tests. All prices below are SYNTHETIC test inputs, not market data.
Run: python -m unittest discover -s tests -t ."""
import unittest

from app.arbitrage import Plan, Quote, build_legs, evaluate_cycle
from app.config import expand_cycles, load_config
from app.market_data import parse_book_ticker, parse_symbols

SYMBOLS = {("BTC", "USDT"): {"symbol": "BTCUSDT", "min_notional": 5.0},
           ("ETH", "BTC"): {"symbol": "ETHBTC", "min_notional": 0.0},
           ("ETH", "USDT"): {"symbol": "ETHUSDT", "min_notional": 5.0}}
CYCLE = ("USDT", "BTC", "ETH", "USDT")


def plan(cycle=CYCLE):
    return Plan(cycle, tuple(build_legs(cycle, SYMBOLS)))


def quotes(t=0.0, qty=10.0, btc=60000.0, ethbtc=0.05, eth=3000.0):
    return {"BTCUSDT": Quote(btc, qty, btc, qty, t), "ETHBTC": Quote(ethbtc, qty, ethbtc, qty, t),
            "ETHUSDT": Quote(eth, qty, eth, qty, t)}


class Engine(unittest.TestCase):
    def test_legs_and_sides(self):
        legs = build_legs(CYCLE, SYMBOLS)
        self.assertEqual([(l.symbol, l.side) for l in legs],
                         [("BTCUSDT", "BUY"), ("ETHBTC", "BUY"), ("ETHUSDT", "SELL")])
        self.assertIsNone(build_legs(("USDT", "BTC", "XRP", "USDT"), SYMBOLS))

    def test_consistent_market_loses_about_costs(self):
        r, why = evaluate_cycle(plan(), 100, quotes(), 0.001, 2, 5, 1.0)
        self.assertIsNone(why)
        self.assertAlmostEqual(r["profit_bps"], -35.95, places=1)

    def test_reverse_direction(self):
        rev = ("USDT", "ETH", "BTC", "USDT")
        r, why = evaluate_cycle(plan(rev), 100, quotes(), 0.001, 2, 5, 1.0)
        self.assertIsNone(why)
        self.assertAlmostEqual(r["profit_bps"], -35.95, places=1)

    def test_mispricing_math(self):
        q = quotes(eth=3015.0)  # ETH/USDT 0.5% rich vs the other two legs
        r, _ = evaluate_cycle(plan(), 100, q, 0.001, 2, 5, 1.0)
        k = (1 - 0.0002) * (1 - 0.001)
        expected = 100 / 60000 * k / 0.05 * k * 3015 * k
        self.assertAlmostEqual(r["end_amount"], expected, places=9)
        self.assertGreater(r["profit_bps"], 8)

    def test_insufficient_size_rejected(self):
        r, why = evaluate_cycle(plan(), 100, quotes(qty=1e-6), 0.001, 2, 5, 1.0)
        self.assertIsNone(r)
        self.assertEqual(why, "insufficient_size")

    def test_stale_quote_rejected(self):
        r, why = evaluate_cycle(plan(), 100, quotes(t=0.0), 0.001, 2, 5, 100.0)
        self.assertEqual(why, "stale_quote")

    def test_missing_quote_rejected(self):
        q = quotes()
        del q["ETHBTC"]
        self.assertEqual(evaluate_cycle(plan(), 100, q, 0.001, 2, 5, 1.0)[1], "missing_quote")

    def test_min_notional_rejected(self):
        self.assertEqual(evaluate_cycle(plan(), 1, quotes(), 0.001, 2, 5, 1.0)[1], "below_min_notional")


class Parsing(unittest.TestCase):
    def test_book_ticker_ok_and_bad(self):
        good = {"stream": "btcusdt@bookTicker",
                "data": {"u": 1, "s": "BTCUSDT", "b": "100.0", "B": "2", "a": "100.5", "A": "3"}}
        self.assertEqual(parse_book_ticker(good)["ask"], 100.5)
        crossed = {"data": {"s": "X", "b": "101", "B": "1", "a": "100", "A": "1"}}
        self.assertIsNone(parse_book_ticker(crossed))
        for bad in ({"data": {"s": "X", "b": "nan", "B": "1", "a": "1", "A": "1"}},
                    {"data": {"s": "X", "b": "0", "B": "1", "a": "1", "A": "1"}},
                    {"data": {"s": "X"}}, None, []):
            self.assertIsNone(parse_book_ticker(bad))

    def test_symbols(self):
        info = {"symbols": [
            {"symbol": "BTCUSDT", "status": "TRADING", "baseAsset": "BTC", "quoteAsset": "USDT",
             "filters": [{"filterType": "NOTIONAL", "minNotional": "5.00000000"}]},
            {"symbol": "OLDUSDT", "status": "BREAK", "baseAsset": "OLD", "quoteAsset": "USDT", "filters": []}]}
        out = parse_symbols(info)
        self.assertEqual(out[("BTC", "USDT")], {"symbol": "BTCUSDT", "min_notional": 5.0})
        self.assertNotIn(("OLD", "USDT"), out)


class Config(unittest.TestCase):
    def test_defaults_and_expand(self):
        cfg = load_config({})
        self.assertEqual(len(expand_cycles(cfg.cycles)), 2)

    def test_refuses_non_paper(self):
        with self.assertRaises(SystemExit):
            load_config({"TRADING_MODE": "LIVE"})

    def test_bad_values(self):
        for env in ({"CYCLES": "USDT>BTC>USDT"}, {"CYCLES": "BTC>ETH>XRP>BTC"},
                    {"TAKER_FEE_RATE": "-1"}, {"START_AMOUNT": "nan"}, {"BINANCE_WS_BASE": "ws://x"}):
            with self.assertRaises(SystemExit):
                load_config(env)


if __name__ == "__main__":
    unittest.main()
