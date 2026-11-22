# Pre-registration: portfolio kill switch and daily crash breaker (written 2026-11-22, before any result)

Origin: Romy asked whether the live bot (or the shadows) protect against a "bear last" loss, i.e. a
crash arriving when the balance is largest. Today the live bot has no portfolio drawdown kill switch
(the paper trial has one at 20%) and no crash breaker; it exits only when a coin's 21-day return
turns ≤ 0. The 3σ trailing stop (J4) was already tested and rejected, so stop-loss *per trade* is
not re-tested here. This study tests two *risk controls* added on top of the unchanged live rule.

## Base rule (D1 = live, unchanged)
Daily TSMOM 21d per coin, 6% / 60-day vol sizing, max 25% per coin, max 100% total, 50% no-trade
band, signal from yesterday's close, traded at today's close. Costs: buy 0.20%, sell 0.41%.
A coin joins once it has 61 days of history. Same code path as research/regime_filter_study.py.

## Variants (six, fixed now; no others will be tried for this question)
- **K20 / K25 / K30 — portfolio kill switch.** At each day's close, after marking to market, if
  equity ≤ (1 − X) × running peak equity (X = 20%, 25%, 30%), sell every coin at that close
  (sell cost charged) and hold rupiah for 30 days. On day 31 the peak is reset to current equity
  and D1 resumes. (Live, re-enabling will be a human decision; the 30-day pause is the mechanical
  stand-in so the rule can be backtested.)
- **C10 / C15 — daily crash breaker.** At each day's close, any held coin whose close-to-close
  return that day is ≤ −Y (Y = 10%, 15%) is sold at that close and its target is forced to 0 for
  the next 7 days; then D1 applies again. (Live: run-time price vs 24 hours earlier.)
- **K25+C15 — both together.**

Only daily closes are used, matching what a once-a-day bot can do. Intraday (1-minute) stops are
not tested: they would need exchange-side stop orders or an always-on server (see notes).

## Data
- A. Indodax IDR daily closes: btc, eth, sol, xrp, doge (history_v2, each from listing).
- B. Binance USDT daily closes: BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX (klines 1d, from listing).
Period: **2018-07-01 → last completed day** on both. Sub-periods reported (2018–21, 2022–26) but
the decision uses the full period. All of this data has been seen by earlier studies, so this is
not a holdout test; the bar is "does it buy real drawdown protection at a small, stable cost".

## Metrics (per variant and D1)
CAGR, Sharpe (daily, ×√365), max drawdown, worst 30-day loss, worst 1-day loss, turnover/yr,
number of triggers, by-year returns.
Descriptive only (not part of the decision): "bear last" savings case — Rp300k deposited on the
first day of each month 2021-01 → 2022-12 on Indodax (bull 2021, bear 2022 at the end): final
value and money-weighted annual return for D1, each variant, and buy-and-hold equal-weight.

## Decision rule (fixed now)
A variant is a **candidate** only if, on BOTH A and B over the full period:
1. max drawdown improves by at least 3 percentage points vs D1;
2. CAGR ≥ CAGR(D1) − 2 percentage points;
3. Sharpe ≥ Sharpe(D1) − 0.05.
If several pass: pick the one with the highest CAGR / |max drawdown| on A; tie → the looser
threshold (fewer triggers). If none pass: nothing changes in bot.py.
A passing variant is **not** switched on automatically: it would be added behind a repo variable
(default OFF) and as a line in the nightly shadow ledger, and turned on only with Romy's approval.
Trial count for the deflated-Sharpe bookkeeping: N = 68 (shadow-rule registration) + 6 = 74.
