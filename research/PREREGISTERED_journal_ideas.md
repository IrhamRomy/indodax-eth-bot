# Pre-registration: ideas from the crypto-trading journal review (written 2026-11-22, before any result)

Romy asked to review the journals behind the search "quant trading crypto journal pdf", security-scan
them first, and check whether anything would improve the daily-trade code. Twelve papers were
downloaded and scanned (no JavaScript, launch actions, embedded files or forms in any of them; one
false `/JS` byte match inside compressed data), then read as plain text. Four testable ideas come out
of the peer-reviewed / best-documented ones. They are tested once, here, on the live setup.

## Variants (all long-only spot, same sizing as live: 6% / 60-day vol, max 25% per coin, gross ≤ 100%,
50% no-trade band, signal from yesterday's close)
- **J1 TSMOM 28d**: long if the 28-day return > 0. Source: Han, Kang & Ryu (time-series momentum
  under realistic assumptions: best long-only look-back 28 days, survives 15 bp costs); Liu &
  Tsyvinski (2021, RFS) time-series momentum at 1–4 week horizons.
- **J2 TSMOM 28d, top third of its own history**: long if the 28-day return is above the 2/3
  quantile of that coin's own past 28-day returns (expanding window, ≥ 180 days). Source: Han, Kang &
  Ryu's exact long rule ("top third of its history").
- **J3 Multi-horizon TSMOM**: exposure = (6%/vol) × fraction of the 7, 14, 28 and 56-day returns
  that are > 0 (0, ¼, ½, ¾ or 1 of the full weight). Source: Gbadebo (2026) multi-horizon momentum;
  Liu & Tsyvinski 1–4 weeks.
- **J4 TSMOM 21d + volatility trailing stop**: as live, but exit when the close falls more than
  3 × (60-day daily vol) below the highest close since entry; after a stop, re-enter only after the
  21-day signal has turned off and on again. Source: AdaptiveTrend (arXiv 2602.11708, trailing stop
  calibrated to volatility).

Not tested, with reason: CTREND (Fieberg et al., JFQA 2025) and cross-sectional momentum need a
cross-section of hundreds of coins (the bot trades 5); the ML classifier papers (Attanasio et al.
2019; Asgari & Khasteh; Zhao & Rinaldo; Crone et al.; Alessandretti et al.) use short test windows
and little or no trading cost, and the fee-aware ML study here already found ML ≈ breakeven at
Indodax costs; AdaptiveTrend's long-short 6-hour futures setup is not available on Indodax spot.

## Data and costs (fixed)
Indodax IDR daily closes for btc, eth, sol, xrp, doge (tradingview/history_v2, fetched today),
2022-01-01 → yesterday; in-sample 2022–2024, out-of-sample 2025-01-01 →. Costs as in the previous
study: buy 0.20%, sell 0.41%, plus half the current bid-ask spread (min 0.05%).
Robustness check: the same 4 rules on the paper-trial's Binance data (8 coins, daily closes, 0.15% per side).

## Decision rule (fixed)
Recommend replacing the live signal only if one variant has ALL of:
(a) Deflated Sharpe ≥ 0.95, counting N = 61 earlier trials + these 4 = 65;
(b) out-of-sample 2025–26 Sharpe higher than live TSMOM 21d;
(c) max drawdown no more than 5 points worse than live;
(d) Sharpe on the Binance robustness data ≥ TSMOM 21d's.
Otherwise the live code stays unchanged; a variant meeting (b)–(d) but not (a) is only noted for
the 2027-03-23 verdict.
