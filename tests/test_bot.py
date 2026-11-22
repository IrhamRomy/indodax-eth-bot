import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot  # noqa: E402


class TestSign(unittest.TestCase):
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


class TestSignal(unittest.TestCase):
    def test_drops_today_candle(self):
        day = 86400
        now = 100 * day + 5000
        candles = [{"Time": 98 * day, "Close": 1}, {"Time": 99 * day, "Close": 2},
                   {"Time": 100 * day, "Close": 99}]
        self.assertEqual(bot.completed_daily_closes(candles, now), [(98 * day, 1.0), (99 * day, 2.0)])

    def test_up_and_down(self):
        self.assertEqual(bot.momentum_signal([100] + [1] * 20 + [110], 21)[0], "ETH")
        self.assertEqual(bot.momentum_signal([100] + [1] * 20 + [90], 21)[0], "IDR")
        self.assertEqual(bot.momentum_signal([100] * 22, 21)[0], "IDR")  # flat → cash

    def test_not_enough_data(self):
        with self.assertRaises(RuntimeError):
            bot.momentum_signal([1] * 10, 21)


class TestDecide(unittest.TestCase):
    kw = dict(bid=31_000_000, min_idr=10_000, min_eth=0.00031847, max_trade_idr=1_000_000)

    def test_buy_all_idr(self):
        o = bot.decide("ETH", 150_000, 0, **self.kw)
        self.assertEqual(o, {"type": "buy", "order_type": "market", "idr": 149_250})

    def test_sell_all_eth(self):
        o = bot.decide("IDR", 0, 0.00483871, **self.kw)
        self.assertEqual(o, {"type": "sell", "order_type": "market", "eth": "0.00483871"})

    def test_already_positioned(self):
        self.assertIsNone(bot.decide("ETH", 500, 0.0048, **self.kw))   # dust IDR
        self.assertIsNone(bot.decide("IDR", 150_000, 0.0000001, **self.kw))  # dust ETH

    def test_cap(self):
        o = bot.decide("ETH", 50_000_000, 0, **self.kw)
        self.assertEqual(o["idr"], 1_000_000)
        o = bot.decide("IDR", 0, 1.0, **self.kw)
        self.assertLessEqual(float(o["eth"]) * self.kw["bid"], 1_000_000)


class TestMainFlow(unittest.TestCase):
    """End-to-end with a fake Indodax: checks what would be sent."""

    def run_main(self, live, closes, balance):
        import time
        from unittest import mock
        sent = []
        day = 86400
        today = int(time.time()) // day * day
        candles = [{"Time": today - (len(closes) - i) * day, "Close": c} for i, c in enumerate(closes)]

        def fake_http(url, data=None, headers=None):
            if url.endswith("/api/pairs"):
                return [{"id": "ethidr", "trade_min_base_currency": 10000,
                         "trade_min_traded_currency": 0.00031847}]
            if "/api/ticker/" in url:
                return {"ticker": {"buy": "31000000", "sell": "31050000"}}
            if "history_v2" in url:
                return candles
            body = data.decode()
            sent.append(body)
            if "method=getInfo" in body:
                return {"success": 1, "return": {"balance": balance, "withdraw_status": 1}}
            return {"success": 1, "return": {"order_id": 1}}

        env = {"LIVE_TRADING": "true" if live else "false",
               "INDODAX_API_KEY": "k", "INDODAX_API_SECRET": "s", "GITHUB_STEP_SUMMARY": ""}
        with mock.patch.object(bot, "_http", fake_http), mock.patch.dict(os.environ, env):
            self.assertEqual(bot.main(), 0)
        return sent

    def test_dry_run_sends_no_order(self):
        sent = self.run_main(False, [100] * 21 + [90], {"idr": 0, "eth": "0.0048"})
        self.assertEqual(len(sent), 1)
        self.assertIn("method=getInfo", sent[0])

    def test_live_sell_when_down(self):
        sent = self.run_main(True, [100] * 21 + [90], {"idr": 0, "eth": "0.0048"})
        self.assertIn("method=trade", sent[-1])
        self.assertIn("type=sell", sent[-1])
        self.assertIn("eth=0.00480000", sent[-1])
        self.assertIn("pair=eth_idr", sent[-1])

    def test_live_buy_when_up(self):
        sent = self.run_main(True, [100] * 21 + [110], {"idr": 150000, "eth": "0"})
        self.assertIn("type=buy", sent[-1])
        self.assertIn("idr=149250", sent[-1])

    def test_live_hold(self):
        sent = self.run_main(True, [100] * 21 + [110], {"idr": 100, "eth": "0.0048"})
        self.assertEqual(len(sent), 1)  # only getInfo, no trade


if __name__ == "__main__":
    unittest.main()
