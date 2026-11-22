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


class TestLedgerMain(unittest.TestCase):
    def test_new_lines_and_csv_columns(self):
        import tempfile
        from pathlib import Path
        from unittest import mock
        rec = {**REC, "equity": 100000, "tsmom_target": {"btc": 0.0, "eth": 0.0},
               "ml_target": {"btc": 0.1, "eth": 0.0},
               "alt_targets": {"SMA50": {"btc": 0.2, "eth": 0.0}, "DONCHIAN_20_10": {"btc": 0.0, "eth": 0.1}}}
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            log = d / "run.log"
            log.write_text("RESULT_JSON " + json.dumps(rec))
            # an old ledger without the new columns must be extended, not broken
            (d / "shadow_ledger.csv").write_text("date,run_id,TSMOM_equity\n2026-11-20,1,1000000\n")
            with mock.patch.object(sl, "REVIEWS", d), mock.patch.object(sl, "STATE", d / "s.json"), \
                    mock.patch.object(sl, "LEDGER", d / "shadow_ledger.csv"), \
                    mock.patch.object(sys, "argv", ["x", "--log", str(log), "--run-id", "9", "--run-date", "2026-11-23"]):
                self.assertEqual(sl.main(), 0)
            st = json.loads((d / "s.json").read_text())
            self.assertIn("btc", st["portfolios"]["SMA50"]["units"])
            self.assertIn("eth", st["portfolios"]["Donchian_20_10"]["units"])
            self.assertEqual(st["portfolios"]["TSMOM"]["units"], {})
            rows = (d / "shadow_ledger.csv").read_text().splitlines()
            self.assertIn("SMA50_equity", rows[0])
            self.assertEqual(len(rows), 3)


if __name__ == "__main__":
    unittest.main()
