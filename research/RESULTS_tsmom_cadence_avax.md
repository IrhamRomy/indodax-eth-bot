# Results: TSMOM cadence and AVAX (run 2026-11-22, after pre-registrations 67f2858 and 2911683)

Script: `research/tsmom_cadence_avax_study.py`; raw output: `research/results/tsmom_cadence_avax_study.json`.
Indodax IDR daily closes to 2026-11-21, 1-day signal lag, costs buy 0.20% / sell 0.41%
(+0.31% each way on AVAX for its bid-ask spread). Sharpe from daily returns (×√365).

## Question 1: decide every 3 days instead of daily? — NO (both rules fail)
Indodax, 5 coins, 2022-01-01 → 2026-11-21:
| Variant | CAGR | Sharpe | Max DD | Turnover/yr |
|---|---|---|---|---|
| **D1 daily (live)** | **+15.7%** | **0.88** | −21.8% | 17.6× |
| D3 start day 0 | +15.7% | 0.88 | −20.8% | 11.0× |
| D3 start day 1 | +11.9% | 0.70 | −25.6% | 10.3× |
| D3 start day 2 | +14.2% | 0.82 | −21.8% | 10.6× |
| D3 average | +13.9% | 0.80 | −22.7% | 10.6× |
| AVG3 (average of last 3 days' targets) | +11.9% | 0.80 | −16.6% | 8.7× |
| 3 staggered tranches (context) | +14.0% | 0.82 | −19.5% | 10.6× |

- Rule A (67f2858, every 3 days): avg Sharpe 0.80 < 0.88 + 0.05 and start day 1 CAGR 11.9% <
  15.7% − 1pp → **FAIL**. The Binance-data side finding does not replicate on Indodax.
- Rule B (2911683, AVG3): Sharpe 0.80 < 0.98, CAGR lower, and on Binance 8 coins AVG3 0.56 <
  D1 0.64 → **FAIL**. (AVG3 does have a smaller drawdown, −16.6% vs −21.8%, but that was not the
  pre-registered criterion, and the return cost is ~4%/yr.)
- Context: at 2× costs the slower variants close the gap (D1 0.59 vs D3 avg 0.62), so if Indodax
  fees ever rise a lot this is worth re-testing. On Binance 8-coin daily data D1 also wins
  (0.64 vs D3 avg 0.56).

## Question 2: add AVAX? — NO
Indodax, 2022-07-01 → 2026-11-21, live daily rule:
| Universe | CAGR | Sharpe | Max DD | Turnover/yr |
|---|---|---|---|---|
| 5 coins (live) | +19.4% | 1.02 | −21.8% | 18.8× |
| 6 coins (+AVAX) | +21.2% | 0.98 | −26.2% | 21.6× |
By year 5 coins: −6%, +46%, +61%, 0%, −2% · 6 coins: −8%, +70%, +60%, −3%, −5% (2022 H2 → 2026).
- Rule C: Sharpe 0.98 < 1.02 and drawdown 4.4pp deeper (limit 3pp) → **FAIL**. AVAX adds a bit of
  return in a strong year (2023) but more risk and more cost; it moves closely with SOL/ETH, so it
  adds little diversification. Liquidity passes today (Rp180M/day, spread 0.61–0.65%), but its
  spread is ~3× the other coins' and its volume ~1/150 of BTC's.
- AVAX stays in the ML shadow model only (its weight stays in rupiah). Re-check if its Indodax
  volume and spread improve.

## Note on the two pre-registrations
67f2858 (every 3 days) was committed at 20:25 WIB from the same working session, shortly before
2911683 (AVG3 + AVAX) at 20:28; both before any result. Both are evaluated exactly as written,
and both fail, so there is no conflict to resolve.

## Decision
Live bot unchanged: daily TSMOM on BTC, ETH, SOL, XRP, DOGE. No new shadow lines.
