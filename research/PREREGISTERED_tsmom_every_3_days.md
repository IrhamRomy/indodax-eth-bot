# Pre-registration: live TSMOM deciding every 3 days instead of daily (written 2026-11-22, before any result)

Origin: a side finding of the fee-aware ML study (RESULTS_fee_aware_ml.md): on Binance 8-coin data,
TSMOM every 3 days beat daily TSMOM on all three cycle start days. Because that idea came from
looking at results, it is tested here on different data: Indodax IDR daily prices of the 5 coins the
live bot trades (BTC, ETH, SOL, XRP, DOGE). Same period (2022-01-01 → latest closed day), so this is
a replication on another market and universe, not a fully independent sample.

## Strategy (exactly the live bot's rule; only the decision cadence differs)
- Signal: hold a coin if its close is above its close 21 days earlier, else rupiah.
- Size: 6% / annualised 60-day volatility (daily log returns), max 25% per coin, max 100% total.
- 50% no-trade band; exits always execute.
- Signal from the previous day's close, traded at today's close (one-day lag, conservative).
- Costs: buys 0.20%, sells 0.41% of traded value (measured on the first live trade).

## Variants (fixed now)
- DAILY: decide every day (the live bot today).
- EVERY_3D_p0, p1, p2: decide every 3rd day, on the three possible start days
  (p = days since 1970-01-01 mod 3). Reported individually and as the average of the three.

## Decision rule (fixed now)
"Every 3 days" PASSES only if all hold on Indodax data:
1. Average Sharpe of the three start days ≥ DAILY Sharpe + 0.05;
2. EVERY start day's CAGR ≥ DAILY CAGR − 1 percentage point (no lucky-phase dependence);
3. Average max drawdown no worse than DAILY's by more than 5 percentage points.
If it PASSES: the three start days are added to the nightly shadow ledger as virtual portfolios
(TSMOM_3d_p0/p1/p2) and compared with live daily TSMOM until the paper-trial verdict on 2027-03-23.
The live bot is NOT switched automatically; switching needs Romy's explicit decision after that.
If it FAILS: nothing changes, and the idea is dropped.
