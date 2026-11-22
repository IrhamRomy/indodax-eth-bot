# Results: fee-aware variants of the ML sleeve (run 2026-11-22, after pre-registration bca2e4c)

Script: `research/fee_aware_study.py`; raw output: `research/results/fee_aware_study.json`.
Out-of-sample 2022-01-01 → 2026-11-20, purged quarterly walk-forward (20 folds) with the paper
trial's own code, 8 coins, Binance 4h data, Indodax costs (buy 0.20%, sell 0.41%).
Sanity check: at a flat 0.30% the deployed ML (−0.2%/yr, Sharpe 0.115, turnover 53.6×) and TSMOM
(+4.8%/yr, Sharpe 0.31, turnover 34.8×) reproduce the paper trial's turnover_study.json.

## Pre-registered comparison (Indodax costs)
| Variant | CAGR | Sharpe | Max DD | Turnover/yr | Fees/yr (of capital) | DSR (N=36) | Rule |
|---|---|---|---|---|---|---|---|
| ML_deployed | −0.5% | 0.10 | −41.3% | 53.6× | 16.4% | 0.24 | reference |
| A_strict_entry (0.60) | +0.2% | 0.11 | −41.4% | 34.9× | 10.6% | 0.25 | fail |
| B_every_3_days | +13.7% | 0.65 | −43.3% | 28.1× | 8.6% | 0.69 | **pass** |
| C_strict_wide_band | +0.5% | 0.13 | −41.3% | 34.7× | 10.6% | 0.26 | fail |
| TSMOM (daily) | +4.6% | 0.30 | −41.5% | 34.8× | 10.6% | – | reference |
| BTC buy & hold | +7.9%* | | −67% | 0 | 0 | – | reference |
*BTC: by year −65%, +156%, +122%, −6%, −33%.

By year (Indodax costs): ML_deployed −29%, +9%, +52%, +7%, −22% · B −42%, +49%, +56%, +56%, −11% ·
TSMOM −40%, +66%, +15%, +5%, +4% (2022 → 2026 YTD).

## Post-hoc robustness check (not part of the pre-registered rule; reported for honesty)
"Every 3 days" depends on which day the 3-day cycle starts. Same variant B, other start days:
| B start day | CAGR | Sharpe | Max DD |
|---|---|---|---|
| phase 0 (tested) | +13.7% | 0.65 | −43.3% |
| phase 1 | −6.7% | −0.17 | −48.0% |
| phase 2 | −2.6% | 0.00 | −39.0% |
| average | +1.5% | 0.16 | |
So B's pass is mostly **luck of the start day**, not a real improvement: averaged over start days
it is about the same as the deployed rule. Its DSR (0.69) is also below 0.95.

The same check on TSMOM every 3 days gives +4.5% to +7.0%/yr (Sharpe 0.30–0.39) on every start
day, with fees ~6%/yr instead of ~10.6%/yr — a consistent, modest gain. This was NOT pre-registered,
so it is only a hypothesis to test properly later, not a reason to change the live bot.

## Decision
- By the letter of the rule, B qualifies as an extra shadow line. Because the robustness check
  shows the result is driven by the cycle start day, **B is not added**; the bot is unchanged
  (being more conservative than the rule is not the bias pre-registration guards against).
- The ML sleeve stays in shadow as the deployed rule. None of the variants is a real-money
  candidate (all DSR < 0.95).
- Main lesson: at Indodax costs the ML model pays ~16% of capital per year in fees; its signal is
  too weak to cover that. Trading less helps only if the signal survives it, and here it does not
  robustly.
- Next step (if wanted): pre-register "TSMOM every 3 days, all three start days averaged" and test
  it on Indodax data before touching the live strategy.
