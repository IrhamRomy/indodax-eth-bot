# Pre-registration: fee-aware variants of the ML sleeve (written 2026-11-22, before any result)

Why: the paper-trial LightGBM model's trading rules (enter P(up) > 0.55, exit < 0.50, daily
decision, 50% no-trade band) were chosen assuming 0.15% cost per trade. Indodax costs more:
measured on the first live trade, a market SELL costs 0.41% (0.20% fee + 0.21% PPh 22) and a BUY
about 0.20%. This study tests, once, whether trading less often rescues the ML sleeve at those costs.

The model itself is NOT changed or retrained differently: same features, labels (triple barrier,
18 bars, 1.5σ), LightGBM parameters and purged quarterly walk-forward as research/backtest.py in
IrhamRomy/quant-paper-trial. Only the trading rules on top of its probabilities differ.

## Variants (fixed now; no others will be tried)
| Name | Enter if P(up) > | Exit if P(up) < | Decide every | No-trade band |
|---|---|---|---|---|
| ML_deployed (reference) | 0.55 | 0.50 | 1 day | 50% |
| A_strict_entry | 0.60 | 0.50 | 1 day | 50% |
| B_every_3_days | 0.55 | 0.50 | 3 days | 50% |
| C_strict_wide_band | 0.60 | 0.50 | 1 day | 75% |
References at the same costs: TSMOM (21-day momentum, daily, 50% band) and BTC buy & hold.

Sizing unchanged: 6% / annualised vol per coin, max 25% per coin, max 100% total, 8 coins,
Binance 4h data, out-of-sample 2022-01-01 → latest closed bar. Decisions on the 00:00 UTC bar.

## Costs
Asymmetric, charged on traded notional: buys 0.20%, sells 0.41%. Also reported at a flat 0.30%.

## Decision rule (fixed now)
A variant is added to the bot as an extra SHADOW line (logged, never traded) only if ALL hold:
1. CAGR > 0 after Indodax costs;
2. Sharpe ≥ ML_deployed's Sharpe + 0.10 at the same costs;
3. Max drawdown no worse than ML_deployed's by more than 5 percentage points.
If several pass, only the one with the highest Sharpe is added. If none pass, nothing changes.
The Deflated Sharpe Ratio is reported with N = 36 trials (27 grid configs + 6 turnover-study
variants already tried in the paper trial + these 3). Even a variant that passes is only a
candidate for real money if its DSR ≥ 0.95 AND it also beats TSMOM in the shadow ledger at the
paper-trial verdict on 2027-03-23. Thresholds, variants and costs will not be changed after
seeing results.
