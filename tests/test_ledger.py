import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research"))
import shadow_ledger as sl  # noqa: E402

REC = {"coins": {"btc": {"bid": 1e9, "ask": 1.001e9, "status": "ok", "min_idr": 10000, "min_coin": 1e-8},
                 "eth": {"bid": 3e7, "ask": 3.003e7, "status": "ok", "min_idr": 10000, "min_coin": 1e-8}}}


class TestLedger(unittest.TestCase):
    def test_parse_last_record(self):
        log = "noise\nx RESULT_JSON {\"a\": 1}\nmore\nt RESULT_JSON {\"a\": 2}\n"
        self.assertEqual(sl.parse_record(log), {"a": 2})
        with self.assertRaises(SystemExit):
            sl.parse_record("no record here")

    def test_buy_then_sell_costs(self):
        pf = {"idr": 1_000_000.0, "units": {}}
        notes, fee, traded = sl.step(pf, {"btc": 0.2, "eth": 0.0}, REC)
        self.assertEqual(len(notes), 1)
        self.assertAlmostEqual(traded, 200_000, delta=1)
        self.assertAlmostEqual(fee, 200_000 * sl.BUY_COST, delta=1)
        notes, fee, traded = sl.step(pf, {"btc": 0.0, "eth": 0.0}, REC)
        self.assertNotIn("btc", pf["units"])
        self.assertLess(pf["idr"], 1_000_000)  # paid both buy and sell costs

    def test_no_signal_holds(self):
        pf = {"idr": 1_000_000.0, "units": {"btc": 0.0001}}
        notes, fee, _ = sl.step(pf, None, REC)
        self.assertEqual((pf["units"], fee), ({"btc": 0.0001}, 0.0))


if __name__ == "__main__":
    unittest.main()
