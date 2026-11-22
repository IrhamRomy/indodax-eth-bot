import math
import os
import sys
import time
import unittest
from decimal import Decimal
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402

MINS = {c: (10_000, 1e-8) for c in ["btc", "eth", "sol", "xrp", "doge"]}


class TestSafety(unittest.TestCase):
    def test_official_doc_vector(self):
        # Example from Indodax official Private REST API docs (getInfo)
        secret = ("f60617a68fcce028f0a90bc9eb765d17379eb548cc935c01a7ee3186eecf870e"
                  "9b68f27a31bcfe8d")
        body = "method=getInfo&timestamp=1578304294000&recvWindow=1578303937000"
        self.assertEqual(
            bot.sign(secret, body),
            "bab004e5a518740d7a33b38b44dbebecd3fb39f40b42391af39fcce06edabff5"
            "233b3e8064a07c528d1c751a6923d5116026c7786e01b22e2d35277a098cae99")

    def test_withdraw_blocked(self):
        with self.assertRaises(ValueError):
            bot.private("withdrawCoin", "k", "s")

    def test_other_hosts_blocked(self):
        with self.assertRaises(ValueError):
            bot._http("https://evil.example.com/tapi")
        with self.assertRaises(ValueError):
            bot._http("https://indodax.com.evil.example/api")


class TestSignal(unittest.TestCase):
    def test_drops_today_candle(self):
        day = 86400
        now = 100 * day + 5000
        candles = [{"Time": 98 * day, "Close": 1}, {"Time": 99 * day, "Close": 2},
                   {"Time": 100 * day, "Close": 99}]
        self.assertEqual(bot.completed_daily_closes(candles, now), [(98 * day, 1.0), (99 * day, 2.0)])

    def test_momentum(self):
        self.assertGreater(bot.momentum([100] + [1] * 20 + [110], 21), 0)
        self.assertLess(bot.momentum([100] + [1] * 20 + [90], 21), 0)
        with self.assertRaises(RuntimeError):
            bot.momentum([1] * 10, 21)

    def test_vol(self):
        closes = [100 * math.exp(0.02 * (-1) ** k) for k in range(61)]
        self.assertAlmostEqual(bot.annual_vol(closes), 0.04 * math.sqrt(365), delta=0.05)

    def test_weights(self):
        w = bot.target_weights({"btc": (0.1, 0.40), "eth": (-0.1, 0.6), "doge": (0.2, 0.10)})
        self.assertAlmostEqual(w["btc"], 0.15)
        self.assertEqual(w["eth"], 0.0)
        self.assertEqual(w["doge"], 0.25)            # capped at MAX_WEIGHT
        w = bot.target_weights({c: (0.1, 0.05) for c in "abcde"})
        self.assertAlmostEqual(sum(w.values()), 1.0)  # never more than 100% invested


class TestPlan(unittest.TestCase):
    bids = {"btc": 1_000_000_000.0, "eth": 30_000_000.0}

    def test_exit_sells_everything(self):
        s, b = bot.plan_orders({"btc": 0.0, "eth": 0.0}, {"eth": Decimal("0.0048")}, self.bids, 0, MINS)
        self.assertEqual(s, [{"coin": "eth", "type": "sell", "order_type": "market", "eth": "0.00480000"}])
        self.assertEqual(b, [])

    def test_buy_from_cash(self):
        s, b = bot.plan_orders({"btc": 0.15, "eth": 0.10}, {}, self.bids, 1_000_000, MINS)
        self.assertEqual(s, [])
        orders = bot.size_buys(b, 1_000_000)
        self.assertEqual({o["coin"]: o["idr"] for o in orders}, {"btc": 150_000, "eth": 100_000})

    def test_band_no_trade(self):
        # target 10%, holding 12% → inside the 50% band
        s, b = bot.plan_orders({"eth": 0.10}, {"eth": Decimal("0.004")}, {"eth": 30_000_000.0},
                               880_000, MINS)
        self.assertEqual((s, b), ([], []))

    def test_trim_when_too_big(self):
        # target 10%, holding ~40% → sell back to 10%
        s, _ = bot.plan_orders({"eth": 0.10}, {"eth": Decimal("0.01")}, {"eth": 30_000_000.0},
                               450_000, MINS)
        self.assertEqual(len(s), 1)
        self.assertAlmostEqual(float(s[0]["eth"]) * 30_000_000, 225_000, delta=100)

    def test_below_minimum_skipped(self):
        s, b = bot.plan_orders({"eth": 0.05}, {}, {"eth": 30_000_000.0}, 100_000, MINS)
        self.assertEqual(b, [])  # Rp5,000 < Rp10,000 minimum

    def test_buys_scaled_to_cash(self):
        orders = bot.size_buys([{"coin": "btc", "want_idr": 200_000, "min_idr": 10_000},
                                {"coin": "eth", "want_idr": 200_000, "min_idr": 10_000}], 200_000)
        self.assertLessEqual(sum(o["idr"] for o in orders), 200_000)

    def test_cap(self):
        s, b = bot.plan_orders({"btc": 0.25}, {}, self.bids, 50_000_000, MINS)
        self.assertEqual(b[0]["want_idr"], bot.MAX_TRADE_IDR)


class TestMainFlow(unittest.TestCase):
    """End-to-end against a fake Indodax: checks exactly what would be sent."""

    def run_main(self, live, trend, balance):
        sent, day = [], 86400
        today = int(time.time()) // day * day
        prices = {"btc": 1.0e9, "eth": 3.0e7, "sol": 2.0e6, "xrp": 3.0e4, "doge": 3.0e3}

        def series(c):
            n = 90
            return [{"Time": today - (n - i) * day,
                     "Close": prices[c] * (1 + trend[c] * i / n) * (1 + 0.02 * (-1) ** i)} for i in range(n)]

        def fake_http(url, data=None, headers=None):
            if url.endswith("/api/pairs"):
                return [{"id": f"{c}idr", "trade_min_base_currency": 10000,
                         "trade_min_traded_currency": 1e-8} for c in prices]
            if url.endswith("/api/summaries"):
                return {"tickers": {f"{c}_idr": {"buy": str(p), "sell": str(p * 1.001)} for c, p in prices.items()}}
            if "history_v2" in url:
                sym = url.split("symbol=")[1].split("IDR")[0].lower()
                return series(sym)
            body = data.decode()
            sent.append(body)
            if "method=getInfo" in body:
                return {"success": 1, "return": {"balance": balance}}
            return {"success": 1, "return": {"order_id": 1}}

        env = {"LIVE_TRADING": "true" if live else "false",
               "INDODAX_API_KEY": "k", "INDODAX_API_SECRET": "s", "GITHUB_STEP_SUMMARY": ""}
        with mock.patch.object(bot, "_http", fake_http), mock.patch.object(bot.time, "sleep"), \
                mock.patch.dict(os.environ, env):
            self.assertEqual(bot.main(), 0)
        return [b for b in sent if "method=trade" in b]

    down = {"btc": -0.3, "eth": -0.3, "sol": -0.3, "xrp": -0.3, "doge": -0.3}
    mixed = {"btc": 0.3, "eth": -0.3, "sol": 0.3, "xrp": -0.3, "doge": -0.3}

    def test_dry_run_sends_nothing(self):
        self.assertEqual(self.run_main(False, self.down, {"idr": 0, "eth": "0.0048"}), [])

    def test_all_down_sells_eth(self):
        trades = self.run_main(True, self.down, {"idr": 0, "eth": "0.0048"})
        self.assertEqual(len(trades), 1)
        self.assertIn("pair=eth_idr", trades[0])
        self.assertIn("type=sell", trades[0])
        self.assertIn("eth=0.00480000", trades[0])
        self.assertIn("client_order_id=tsmom-", trades[0])

    def test_mixed_rotates(self):
        trades = self.run_main(True, self.mixed, {"idr": 500000, "eth": "0.0048"})
        pairs = sorted(t.split("pair=")[1].split("&")[0] + ":" + t.split("type=")[1].split("&")[0] for t in trades)
        self.assertEqual(pairs, ["btc_idr:buy", "eth_idr:sell", "sol_idr:buy"])
        self.assertTrue(trades[0].count("type=sell"))  # sells go first


if __name__ == "__main__":
    unittest.main()
