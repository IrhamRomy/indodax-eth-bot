# Pre-registration: BTC bull/bear regime filter (written 2026-11-22, before any result)

Origin: a descriptive split of the live rule's 2022–2026 Indodax backtest by market regime showed
that all profit came while BTC was above its 200-day average (+33.9%/yr) and that it lost −7.8%/yr
below it. Because the idea came from looking at that period, it is tested only on data not used
by any earlier study: **2018-07-01 → 2021-12-31** (2018 crash, 2019 range, 2020–21 bull).

## Rule tested (one variant only)
- D1 (live): daily TSMOM 21d per coin, 6% / 60-day vol sizing, max 25% per coin, max 100% total,
  50% no-trade band, signal from yesterday's close, traded at today's close.
- D1+REGIME: identical, but when BTC's close (yesterday) is below its own 200-day simple moving
  average, every target is 0 (all coins sold, hold cash). Above it, D1 targets apply unchanged.
Costs: buy 0.20%, sell 0.41% of traded value. A coin joins once it has 61 days of history.

## Holdout data
- H1 Indodax IDR daily closes: btc, eth, xrp, doge, sol (each from its own listing; BTC since 2017).
- H2 Binance USDT daily closes: BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX (each from listing).
Context only (already seen, not decisive): Indodax 5 coins 2022-01-01 → 2026-11-21.

## Decision rule (fixed now)
Adopt only if, in BOTH H1 and H2:
1. Sharpe(D1+REGIME) ≥ Sharpe(D1) + 0.05;
2. max drawdown(D1+REGIME) no worse than D1's;
3. CAGR(D1+REGIME) ≥ CAGR(D1) − 2 percentage points.
If it passes: added to the bot behind repo variable REGIME_FILTER (default OFF, Romy decides) and
as an extra line in the nightly shadow ledger. If it fails: nothing changes.
No other filter (other averages, other lengths, other assets) will be tried for this question.
