# Results: BTC 200-day regime filter (run 2026-11-22, pre-registered in 05574f2 before running)

Script: `research/regime_filter_study.py`; raw output `research/results/regime_filter_study.json`.
Rule: as live (daily TSMOM 21d), but all coins sold while BTC is below its 200-day average.
Costs buy 0.20% / sell 0.41%. Holdout 2018-07-01 → 2021-12-31 (not used by any earlier study).

| Data | Rule | CAGR | Sharpe | Max DD | Turnover/yr | By year 2018 / 2019 / 2020 / 2021 |
|---|---|---|---|---|---|---|
| H1 Indodax (btc, eth, xrp, doge, sol) | D1 live | **+32.5%** | **1.78** | −17.9% | 10.8× | −8% / +4% / +88% / +49% |
| | D1 + regime | +26.9% | 1.66 | −15.9% | 7.7× | 0% / 0% / +67% / +39% |
| H2 Binance (8 coins) | D1 live | **+62.9%** | **2.04** | −23.3% | 15.2× | −15% / +10% / +113% / +179% |
| | D1 + regime | +48.4% | 1.84 | −19.9% | 11.1× | 0% / −5% / +70% / +148% |
| Context (already seen): Indodax 2022–26 | D1 live | +15.7% | 0.88 | −21.8% | 17.6× | 2022–26: −12% / +46% / +61% / 0% / −2% |
| | D1 + regime | +16.9% | 1.05 | −18.0% | 12.1× | 0% / +25% / +60% / +6% / +1% |

Checks (both holdouts): Sharpe +0.05 → **fail** (−0.12 and −0.20); drawdown not worse → pass;
CAGR within 2 pp → **fail** (−5.6 pp and −14.5 pp). **Decision: rejected; live code unchanged.**

Why: the filter removes small bear-market losses (2018: −8% → 0%), but BTC crosses its 200-day
average weeks after a new bull market has started, so it misses the strongest early part of the
rally (2020: +88% → +67% on Indodax, +113% → +70% on Binance). Each coin's own 21-day momentum
already moves to cash in bear markets (bear-market losses were only −7.8%/yr vs −40%/yr for
holding), so a second, slower filter mostly costs upside. The filter looked better on 2022–26
because that is the period the idea came from — the holdout shows it does not generalise.
