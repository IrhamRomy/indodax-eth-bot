# Pre-registration: TSMOM trading cadence, and adding AVAX (written 2026-11-22, before any result)

Context: research/RESULTS_fee_aware_ml.md noticed (post hoc) that TSMOM rebalanced every 3 days
looked better than daily on all three start days. Post-hoc findings must be re-tested under a
rule fixed in advance. Romy also asked to add AVAX.

## Data and common setup (fixed)
Indodax IDR daily closes (research/fetch.py), completed days only. Signal from the previous day's
close, executed at the next day's close (1-day lag, conservative vs the live 04:07 UTC run).
TSMOM: hold a coin if its 21-day return > 0; weight = 6% / 60-day annualised vol, max 25% per
coin, max 100% total; 50% no-trade band (exits always execute).
Costs: buy 0.20%, sell 0.41% of traded value (measured on the first live trade). AVAX trades pay
an extra 0.31% each way (half of its ~0.62% bid-ask spread on 22 Nov 2026; the others' spreads
are < 0.2% and are ignored, as before). Also reported at 2× costs.

## Question 1: rebalance cadence (5 coins: btc, eth, sol, xrp, doge; 2022-01-01 → latest)
- D1 (current live rule): decide daily.
- **AVG3 (the variant that would be deployed)**: decide daily, but the target is the average of
  the TSMOM targets of the last 3 days (stateless; equivalent in spirit to three staggered
  sub-portfolios, so no start-day luck). 50% band as usual.
- Context only (reported, not decisive): D3 on each of the three start days and their average;
  a true 3-tranche staggered version.
Adopt AVG3 only if ALL hold on Indodax 5-coin data:
1. Sharpe(AVG3) ≥ Sharpe(D1) + 0.10;
2. CAGR(AVG3) ≥ CAGR(D1);
3. Max drawdown(AVG3) no worse than D1's by more than 5 percentage points;
4. Consistency: on the paper trial's Binance 8-coin 4h data resampled to daily closes, Sharpe(AVG3)
   ≥ Sharpe(D1) (same rule, same costs, 2022-01-01 → latest).
If it passes, Claude implements it behind a repo variable (default OFF) and Romy decides whether
to switch it on. If it fails, the live rule stays daily.

## Question 2: add AVAX? (Indodax AVAX history starts 2022-04; test 2022-07-01 → latest for both)
Compare 5 coins vs 6 coins (+AVAX) using the live rule (D1; if Q1 passes, also report with AVG3).
Add AVAX to the live COINS only if ALL hold:
1. Sharpe(6 coins) ≥ Sharpe(5 coins);
2. Max drawdown(6 coins) no worse than 5 coins' by more than 3 percentage points;
3. Liquidity today: AVAX/IDR 24h volume ≥ Rp100M and spread ≤ 1% (the bot also skips any coin
   whose spread is > 1% on the day, so this keeps being checked live).
Otherwise AVAX stays out (it remains in the ML shadow model, where its weight stays in rupiah).

No other variants, thresholds or periods will be tried for these two questions.
