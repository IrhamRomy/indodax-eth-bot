# Pre-registration: auto-updating coin list, meme coins, and other signals (written 2026-11-22, before any result)

Romy's questions: (1) if the big coins change, can the bot change too? (2) should it trade meme
coins on Indodax, using all the usual signals (momentum, trend, breakout…)? Tested together, once.

## Data (fixed)
Indodax daily candles for all 438 IDR pairs (tradingview/history_v2, fetched 2026-11-22).
IDR volume per day = Volume (coin units) × Close. Completed days only. Signal from yesterday's
close, traded at today's close. Period 2022-01-01 → 2026-11-21; also split into
in-sample 2022–2024 and out-of-sample 2025-01-01 → 2026-11-21.
**Known bias:** only coins still listed today are in the data (Indodax delisted 22 assets on
10 Sep 2026 and others earlier). This favours meme coins (the ones that died are missing), so
the meme rule below is deliberately strict.

Excluded everywhere (not trading assets): usdt, usdc, and any other stablecoin / fiat- or
gold-backed token (usd*, idr*, eur*, dai, tusd, fdusd, busd, pyusd, xaut, paxg).

## Meme list (fixed now, by name only, before looking at any return)
bome, bonk, brett, cat, cheems, chillguy, degen, dogs, fartcoin, floki, giga, goat, griffain,
jellyjelly, meme, mew, mog, moodeng, myro, pengu, pepe, pippin, pnut, ponke, popcat, shib, spx,
sundog, toshi, trump, turbo, useless, vine, wif, zerebro. (DOGE stays in the majors, as live.)

## Universes
- U1 Majors-5 fixed (live): btc, eth, sol, xrp, doge.
- U2 Auto-majors: on the 1st of each month, the 5 non-meme, non-stable coins with the highest
  trailing 30-day median IDR volume that have ≥ 180 days of Indodax history (point in time).
- U3 Auto-all: same as U2 but memes allowed (top 5 by volume, any type).
- U4 Memes only: memes with ≥ 90 days of history and trailing 30-day median IDR volume ≥ Rp200M.
- U5 Majors-5 + meme sleeve: U1 plus U4, each meme capped at 5%, memes together ≤ 20%.

## Signals (each applied to each universe)
- S1 TSMOM 21d (live): hold if close > close 21 days ago.
- S2 TSMOM 63d.
- S3 Trend: close > 50-day simple moving average.
- S4 MA cross: 20-day SMA > 100-day SMA.
- S5 Donchian breakout: enter when close > highest close of the prior 20 days; exit when close <
  lowest close of the prior 10 days.
- Benchmark (not a trial): equal-weight buy & hold of the universe, rebalanced monthly.
Sizing for all: 6% / 60-day annualised vol, max 25% per coin (10% per meme in U3/U4; 5% in U5),
max 100% total, 50% no-trade band, decided daily.

## Costs
Buy 0.20%, sell 0.41% of traded value (measured live) + half of each coin's bid-ask spread from
the 2026-11-22 snapshot (minimum 0.05%). Coins with a snapshot spread > 2% are not tradable and
are excluded from every universe.

## Trials and statistics
5 universes × 5 signals = 25 trials. Deflated Sharpe uses N = 61 (these 25 + 36 earlier trials).

## Decision rules (fixed now)
Q1 – auto-updating coin list. Adopt U2+S1 as an option in the code only if ALL hold vs U1+S1:
  (a) full-period Sharpe ≥ U1's − 0.05; (b) max drawdown within 5 pp; (c) out-of-sample
  2025–26 Sharpe ≥ U1's − 0.10. If it passes, it is added behind repo variable UNIVERSE=auto
  (default stays "fixed"; Romy decides). Independently of this test, a SAFETY guard is added:
  a coin that is delisted, suspended, or whose 30-day median IDR volume falls below Rp300M is
  not bought, and any holding in it is sold (exits always allowed), with a warning in the summary.
Q2 – meme coins. Add a meme sleeve (U5) live only if, for the SAME signal, ALL hold vs U1:
  (a) full-period Sharpe ≥ U1's + 0.10; (b) out-of-sample Sharpe ≥ U1's; (c) max drawdown within
  5 pp; (d) DSR(N=61) ≥ 0.95; (e) the meme-only universe U4 with that signal has positive CAGR in
  BOTH the in-sample and out-of-sample halves. Otherwise no memes.
Q3 – other signals on the live coins. Replace S1 on U1 only if another signal has full-period
  Sharpe ≥ S1's + 0.10, out-of-sample Sharpe ≥ S1's, max drawdown within 5 pp and DSR(N=61) ≥ 0.95.
Nothing else will be tried for these questions.
