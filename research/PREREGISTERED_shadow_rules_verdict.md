# Pre-registration: how the SMA50 and Donchian 20/10 shadow lines will be judged (written 2026-11-22)

Background: in research/RESULTS_universe_memes_signals.md both rules beat the live TSMOM 21d on
Indodax 2022–26 (Sharpe 1.01 / 1.06 vs 0.76) but failed the Deflated Sharpe bar (0.61 / 0.64 <
0.95), so they were not switched on. From 2026-11-23 they run as zero-risk shadow lines: the bot
computes their targets every day (RESULT_JSON "alt_targets", never traded) and
research/shadow_ledger.py follows each with Rp1,000,000 virtual capital at the run's real prices
and real Indodax costs (buy 0.20%, sell 0.41%), next to TSMOM, ML_alone and Blend_50_50.

## Rules (fixed now; exactly as in the study)
- SMA50: hold a coin while its latest daily close is above its 50-day simple average.
- DONCHIAN_20_10: enter when the close beats the highest close of the prior 20 days; exit when it
  falls below the lowest close of the prior 10 days (replayed statelessly over 150 days of closes).
- Same coins (btc, eth, sol, xrp, doge), sizing (6% / 60-day vol, max 25% per coin, max 100%),
  50% no-trade band, liquidity guard and daily cadence as the live bot.

## Evidence that will be used at the verdict (2027-03-23)
1. Shadow period: from the first ledger row to the last run before 2027-03-23 (≈ 4 months, data
   unseen today).
2. Holdout 2018-07-01 → 2021-12-31 (never used for these two rules): research/regime_filter_study.py
   data (Indodax 5 coins and Binance 8 coins), same costs, rule implementations from bot.py.
3. Full Indodax history 2018-07-01 → 2027-03-22 for the Deflated Sharpe, counting every trial run
   in this project so far (68 at the time of writing: 61 + 4 journal + 1 regime filter + these 2)
   plus any added later.

## Decision rule (fixed now)
Switch the live signal from TSMOM 21d to rule X only if ALL hold:
(a) shadow period: X's virtual return ≥ TSMOM's, and its max drawdown no worse by more than 5 pp
    (≈ 4 months cannot prove an edge — Sharpe standard error ≈ 1.7 — so this is a consistency check);
(b) holdout 2018–21: Sharpe(X) ≥ Sharpe(TSMOM 21d) on BOTH Indodax and Binance data;
(c) full Indodax history: Sharpe(X) ≥ Sharpe(TSMOM 21d) + 0.10 and DSR(X) ≥ 0.95.
If both rules pass, pick the one with the higher full-history Sharpe. A switch still needs Romy's
explicit approval and is done by code change + tests, never automatically. If neither passes,
the live rule stays TSMOM 21d and the shadow lines keep running.
