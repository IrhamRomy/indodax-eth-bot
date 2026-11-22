# Results: portfolio kill switch and daily crash breaker (run 2026-11-22)

Pre-registration: research/PREREGISTERED_risk_controls.md (commit 4b4e076, written before any result).
Code: research/risk_controls_study.py; data: research/fetch_risk_data.py; numbers:
research/results/risk_controls_study.json. Period 2018-07-01 → 2026-11-21, costs buy 0.20% / sell 0.41%.
Sanity check: D1 on 2018-07 → 2021-12 reproduces the regime-filter study exactly
(Indodax +32.5%, Sharpe 1.78; Binance +62.9%, Sharpe 2.04).

## Verdict: REJECTED — no variant passes. bot.py stays unchanged.
Every variant fails rule 1 (max drawdown at least 3 pp better than D1) on both data sets;
C10 and C15 also cost more than 2 pp CAGR on Binance.

| Variant | A Indodax CAGR | Sharpe | MaxDD | Triggers | B Binance CAGR | Sharpe | MaxDD | Triggers |
|---|---|---|---|---|---|---|---|---|
| D1 (live) | +21.5% | 1.20 | −21.8% | – | +32.8% | 1.21 | −37.3% | – |
| K20 | +20.4% | 1.15 | −22.6% | 2 | +35.4% | 1.31 | −35.7% | 6 |
| K25 | +21.5% | 1.20 | −21.8% | 0 | +34.6% | 1.27 | −37.6% | 3 |
| K30 | +21.5% | 1.20 | −21.8% | 0 | +33.4% | 1.24 | −37.9% | 3 |
| C10 | +20.7% | 1.20 | −22.9% | 69 | +29.6% | 1.16 | −37.8% | 160 |
| C15 | +20.6% | 1.17 | −21.8% | 21 | +29.9% | 1.14 | −39.1% | 49 |
| K25+C15 | +20.6% | 1.17 | −21.8% | 0 + 21 | +31.6% | 1.20 | −39.4% | 3 + 49 |

Worst 30-day / worst 1-day loss of D1: Indodax −13.4% / −5.9%; Binance −19.4% / −9.9%.

## Why the extra controls don't help
- The live rule's sizing already caps exposure: on average 21% invested on Indodax (30% Binance),
  so a −11% BTC day (2019-09-24) cost the portfolio −5.9%.
- The momentum exit usually fires before the crash day: on 2020-03-12 (BTC −34% on Indodax,
  −40% on Binance) the portfolio was 0% invested and lost nothing.
- On Indodax, D1's drawdown never reached 25%, so K25/K30 never fired. K20 fired twice and sold
  near bottoms (CAGR −1.1 pp, deeper max DD). On Binance K20 helped (+2.6 pp CAGR, DD +1.6 pp) but
  missed the 3 pp bar, and its gain came from the 2022 period only.
- Crash breakers sell after the big red day; crypto often rebounds within the 7-day block, so
  they mostly add costs (69–160 extra sells).

## "Bear last" savings case (descriptive, not part of the decision)
Indodax, Rp300k deposited each month 2021-01 → 2022-12 (bull 2021, bear 2022 at the end), Rp7.2M in:

| Strategy | Final value | Money-weighted return |
|---|---|---|
| Buy & hold, equal weight | Rp4.82M | −33.7%/yr |
| D1 (live rule) | Rp6.92M | −3.7%/yr |
| C10 | Rp7.16M | −0.5%/yr |
| K20 / K25 / K30 | Rp6.92M (never triggered) | −3.7%/yr |
| C15, K25+C15 | Rp6.84M | −4.8%/yr |

The live rule itself is what protects against "bear last": it cut the loss from −34%/yr to −4%/yr.
(Approximation: each deposit is invested at the strategy's current weights.)

## Notes
- Current context: D1's deepest Indodax drawdown is the present one (peak 2025-07-22, trough
  2026-08-16, −21.8%), i.e. the 2025–26 market, consistent with the earlier OOS finding.
- Intraday (1-minute) protection was not tested: daily data only, and it would need exchange-side
  stop orders or an always-on server; per-trade stops (J4) were already rejected.
- Trial count after this study: N = 74.
