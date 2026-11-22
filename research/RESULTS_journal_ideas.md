# Results: ideas from the crypto-trading journal review (run 2026-11-22, pre-registered in 113cb61)

Script: `research/journal_ideas_study.py`; raw output `research/results/journal_ideas_study.json`.
Data: Indodax IDR daily closes for btc, eth, sol, xrp, doge, 2022-01-01 → 2026-11-21 (in-sample 2022–24,
out-of-sample 2025-01-01 →). Costs: buy 0.20%, sell 0.41% + half the current spread. Same sizing as live.
Robustness: the paper trial's Binance data (8 coins, daily, 0.15% per side). Deflated Sharpe with N = 65.

## Indodax majors-5 (the live setup)
| Rule | CAGR | Sharpe | Max DD | 2025–26 Sharpe | Turnover/yr | DSR | Verdict |
|---|---|---|---|---|---|---|---|
| **Live: TSMOM 21d** | **+14.3%** | **0.82** | −22.9% | **−0.04** | 17.6 | 0.44 | keep |
| J1 TSMOM 28d | +16.5% | 0.93 | −21.7% | −0.12 | 14.5 | 0.53 | reject (worse 2025–26, DSR) |
| J2 TSMOM 28d, top third of own history | +11.3% | 0.80 | −17.3% | −0.41 | 12.1 | 0.42 | reject |
| J3 Multi-horizon 7/14/28/56d | +13.7% | 0.92 | −19.9% | −0.11 | 12.8 | 0.53 | reject (worse 2025–26, DSR) |
| J4 TSMOM 21d + 3σ trailing stop | +10.9% | 0.74 | −22.3% | +0.08 | 17.6 | 0.37 | reject (lower Sharpe, DSR) |
| Equal-weight buy & hold | +3.4% | 0.36 | −69.3% | −0.36 | – | – | |

## Binance 8 coins (robustness, paper-trial data)
| Rule | CAGR | Sharpe | Max DD | 2025–26 Sharpe |
|---|---|---|---|---|
| TSMOM 21d | +19.6% | 0.80 | −33.7% | 0.35 |
| J1 TSMOM 28d | +19.7% | 0.79 | −30.8% | 0.05 |
| J2 top third | +13.2% | 0.71 | −23.5% | −0.16 |
| J3 Multi-horizon | +18.6% | 0.85 | −28.2% | 0.06 |
| J4 Trailing stop | +8.6% | 0.48 | −32.5% | 0.17 |
| Equal-weight buy & hold | −9.9% | 0.17 | −74.4% | −0.47 |

## Decision
No variant passes the pre-registered rule; the live code is unchanged.
- J1 (28-day look-back) and J3 (multi-horizon) are slightly better over the whole period on Indodax
  (Sharpe 0.93 / 0.92 vs 0.82, smaller drawdown, less turnover) but **worse in 2025–26**, and their DSR
  (0.53) is far below 0.95. They match the journals' main message — time-series momentum in crypto is
  real but mostly a bull-market effect (Han, Kang & Ryu) — and add nothing that holds up in the recent
  sideways/bear market.
- The top-third rule (J2) cuts drawdowns but gives up too much return; the trailing stop (J4) adds
  nothing (same number of round trips, exits earlier, misses recoveries).
- Not tested (no edge for a 5-coin spot bot): cross-sectional CTREND (needs hundreds of coins), ML
  classifier papers (short tests, little or no trading cost; ML ≈ breakeven here already).
- Re-check J1 and J3 at the 2027-03-23 verdict with the new data, together with SMA50 and Donchian.
