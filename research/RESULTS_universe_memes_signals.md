# Results: auto-updating coin list, meme coins, other signals (run 2026-11-22, pre-registered in 1fbc3ad)

Script: `research/universe_memes_study.py`; raw output `research/results/universe_memes_study.json`.
Data: Indodax daily candles of all 438 IDR pairs (404 non-stable coins with ≥ 30 days; 171 tradable
with spread ≤ 2% on 22 Nov 2026), 2022-01-01 → 2026-11-21, in-sample 2022–24 / out-of-sample
2025–26. Costs: buy 0.20%, sell 0.41% + half of each coin's spread. Deflated Sharpe with N = 61.
(This study adds spread costs per coin, so U1+S1 is a bit lower than in earlier studies:
+13.2% vs +15.7%/yr.) **Survivorship bias:** only coins still listed today are included, which
flatters memes.

## Headline
| Universe + signal | CAGR | Sharpe | Max DD | 2022–24 Sharpe | 2025–26 Sharpe | DSR |
|---|---|---|---|---|---|---|
| **Live: majors-5 + TSMOM 21d** | **+13.2%** | **0.76** | −24% | 1.22 | **−0.11** | 0.38 |
| Majors-5 + close > SMA50 | +18.8% | 1.01 | −22% | 1.38 | 0.37 | 0.61 |
| Majors-5 + Donchian 20/10 | +16.1% | 1.06 | −17% | 1.53 | 0.08 | 0.64 |
| Auto top-5 majors + TSMOM 21d | +8.5% | 0.55 | −24% | 0.88 | −0.10 | 0.22 |
| Majors-5 + meme sleeve (best signal, SMA50) | +15.7% | 0.72 | −38% | 1.33 | −0.03 | 0.35 |
| Memes only (range over the 5 signals) | −2.5% … −6.2% | −0.38 … −0.09 | −30% … −48% | | −0.41 … −0.91 | ≤ 0.01 |
| Majors-5 buy & hold (equal weight) | +0.8% | 0.32 | −70% | | −0.39 | |
| Memes buy & hold (equal weight) | −20.2% | 0.04 | −85% | | −0.17 | |
All 25 combinations are in the JSON (5 universes × TSMOM 21d, TSMOM 63d, SMA50, SMA20>SMA100, Donchian).

## Q1 – auto-updating coin list: NO (fails)
The auto top-5 by volume (U2) mostly picks the same coins (BTC/ETH 65 of 65 months, XRP 58,
DOGE 56, SOL 37; sometimes ADA, BNB, HYPE, SAND, TRX) but switches in coins at their volume peak,
which hurt: Sharpe 0.55 vs 0.76. Rule (a) fails. Kept the fixed list.
**Added anyway (pre-registered safety guard):** a coin whose 30-day median IDR volume falls below
Rp300M is never bought and any holding is sold ("exit only"); a held coin that can't be traded
(delisted / suspended) raises a WARNING. Plus a daily "big-coin watch" line listing the top
IDR markets by 24h volume, so a lasting change is visible; changing the list stays a human
decision (repo variable COINS), ideally after re-running this study.

## Q2 – meme coins: NO (fails every check, for every signal)
- Memes only: negative return with every signal (−2.5% to −6.2%/yr), out-of-sample Sharpe −0.41
  to −0.91, DSR ≤ 0.01. Adding a meme sleeve to the majors lowered Sharpe for every signal and
  deepened drawdowns to −27% … −43%.
- Of the 35 listed memes, **33 (94%) are more than 80% below their peak** and 32 (91%) are below
  their Indodax listing price; median −92% since listing, median volatility 139%/yr — and these
  are the survivors. Only PEPE (+278%), JELLYJELLY (+105%) and PIPPIN (+15%) are above listing.
- Trend rules can't fix this: memes crash faster than a 21–63 day signal can exit, and the rare
  rallies are short. Wide spreads add cost (0.5–17% on many memes).

## Q3 – other signals on the live coins: NO switch yet (promising, not proven)
SMA50 and Donchian 20/10 beat TSMOM 21d on Sharpe (+0.25 / +0.30) and in 2025–26, with equal or
smaller drawdowns — but their DSR (0.61 / 0.64) is below the 0.95 required after 61 trials, so by
the rule the live signal stays TSMOM 21d. Important context: **the live rule has been flat to
negative since 2025 (2025 −2%, 2026 −4%; out-of-sample Sharpe −0.11)** while majors buy & hold lost
~33%/yr; it protected capital but did not earn. Suggested next step (not decided here): track
SMA50 and Donchian as extra shadow lines in the nightly ledger and re-test at the 2027-03-23
verdict with the new data.

## Decision
- Live coins unchanged (BTC, ETH, SOL, XRP, DOGE); no memes; signal stays TSMOM 21d.
- Code: liquidity safety guard (exit-only below Rp300M 30-day median volume), delisting warning,
  big-coin watch in every run summary and RESULT_JSON.
