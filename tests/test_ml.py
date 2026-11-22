import importlib.util
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HAVE_ML = all(importlib.util.find_spec(m) for m in ("lightgbm", "pandas", "numpy"))


@unittest.skipUnless(HAVE_ML, "ML dependencies not installed")
class TestShadow(unittest.TestCase):
    def setUp(self):
        import pandas as pd
        from ml import shadow
        from ml.features import FEATURES
        self.pd, self.shadow, self.FEATURES = pd, shadow, FEATURES

    def panel(self, probs_by_day):
        """Build a fake feature panel; 'prob' is smuggled in ret_1 for the fake model."""
        rows = []
        for d, probs in enumerate(probs_by_day):
            t = self.pd.Timestamp("2026-01-01", tz="UTC") + self.pd.Timedelta(days=d)
            for s in self.shadow.SYMBOLS:
                r = {f: 0.0 for f in self.FEATURES}
                r.update(ret_1=probs.get(s, 0.4), time=t, symbol=s, sigma=0.0135)
                rows.append(r)
        return self.pd.DataFrame(rows)

    class FakeModel:
        def predict(self, X):
            return X["ret_1"].to_numpy()

    def test_hysteresis(self):
        # day 0: BTC 0.56 → enter; day 1: 0.52 → stay (above 0.50); day 2: 0.49 → exit
        p = self.panel([{"BTCUSDT": 0.56}, {"BTCUSDT": 0.52}])
        self.assertTrue(self.shadow.decide(p, self.FakeModel())["on"]["BTCUSDT"])
        p = self.panel([{"BTCUSDT": 0.56}, {"BTCUSDT": 0.52}, {"BTCUSDT": 0.49}])
        self.assertFalse(self.shadow.decide(p, self.FakeModel())["on"]["BTCUSDT"])
        p = self.panel([{"BTCUSDT": 0.52}])  # never crossed 0.55 → flat
        self.assertFalse(self.shadow.decide(p, self.FakeModel())["on"]["BTCUSDT"])

    def test_sizing_and_cap(self):
        # sigma 0.0135 per 4h bar → ~63% annual vol → 6%/63% ≈ 9.5% weight
        d = self.shadow.decide(self.panel([{s: 0.6 for s in self.shadow.SYMBOLS}]), self.FakeModel())
        for w in d["weights_usdt"].values():
            self.assertAlmostEqual(w, 0.06 / (0.0135 * (6 * 365) ** 0.5), places=4)
        self.assertLessEqual(sum(d["weights_usdt"].values()), 1.0 + 1e-9)

    def test_model_hash_checked(self):
        model = self.shadow.load_model()  # real file must pass the SHA-256 check
        self.assertGreater(model.num_trees(), 0)


if __name__ == "__main__":
    unittest.main()
