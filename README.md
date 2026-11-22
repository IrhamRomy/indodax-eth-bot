# indodax-eth-bot (multi-coin momentum)

Small live-trading bot for **Indodax IDR markets**, run once a day (11:07 WIB) by GitHub Actions.
Default coins: **BTC, ETH, SOL, XRP, DOGE** (the most liquid majors on Indodax).

## The rule (same as the TSMOM strategy in `quant-paper-trial`)
1. For each coin: if its price is higher than 21 days ago → hold it; otherwise → rupiah.
2. Size: `6% ÷ coin's yearly volatility`, max 25% per coin, max 100% in total. The rest stays in rupiah.
   Example: BTC at 34% vol → 18% of the account; a coin at 50% vol → 12%.
3. 50% no-trade band: a coin is only re-sized when it's off target by more than half its target (saves fees).
   Exits (signal turns negative) always execute. Sells go first, then buys with the freed rupiah.

> The edge is **not proven**. Treat this as a small-money experiment.

## Backtest on Indodax's own prices (2022-01-01 → 2026-11-22, 0.32% cost per trade, signal from previous close)
| Strategy | CAGR | Sharpe | Max drawdown |
|---|---|---|---|
| ETH-only momentum (old version) | −0.1% | 0.20 | −52.5% |
| 5-coin equal-weight momentum | +19.8% | 0.67 | −40.1% |
| **5-coin vol-targeted momentum (this bot)** | **+15.4%** | **0.87** | **−22.0%** |
| BTC buy & hold | +10.5% | 0.45 | −63.3% |

Caveats: the 5 coins were chosen because they are big *today* (hindsight bias), one backtest period only,
and 2022 still lost 12%. Reproduce with `cd research && python3 fetch.py && python3 bt.py`.

## ML sleeve (shadow mode)
The LightGBM model from `quant-paper-trial` (files in `ml/`: unchanged `features.py`, `model.txt`
with SHA-256 check) runs every day **in shadow mode**: the run summary shows its P(up) per coin,
its target weights, and the orders that **ML alone** and a **50:50 TSMOM+ML** blend *would* place on
your real balance — but only TSMOM trades.
- Signal = the paper trial's exactly (same Binance 4h data, same decision bar, same 0.55/0.50 rule);
  the on/off memory is replayed from the last ~2 months of decisions instead of stored.
- BNB, ADA and AVAX are in the model but not traded here; their share stays in rupiah.
- Backtest at ~0.30% cost (paper-trial data): ML −0.2%/yr vs TSMOM +4.8%/yr. Not proven yet.
- **To go live later:** repo variable `ML_WEIGHT` = `0.5` (final weight = 50% TSMOM + 50% ML).
  Recommended only after the paper-trial verdict (23 Mar 2027) and with ≥ Rp1,000,000.
  With `ML_WEIGHT` > 0, if the ML part fails on a day, **no** trades are placed that day.
- Dependencies: `requirements-ml.txt` (same hash-pinned, wheels-only set as the paper trial).
  If they fail to install, shadow mode just logs "ML signal unavailable" and TSMOM carries on.

## How much to deposit
Indodax's minimum order is Rp10,000. A typical position is 10–18% of the account and a re-size is ~half of that,
so below ~**Rp500,000** many adjustments are too small to place. Rp1,000,000+ works smoothly.
The bot treats **all free rupiah** in the Indodax account as its money — keep savings elsewhere.
Coins not in `COINS` are never touched.

## Safety design
- TSMOM core is standard-library Python only; the ML sleeve uses hash-pinned wheels (lightgbm, numpy, pandas).
- **Dry run by default.** Trades only if repo variable `LIVE_TRADING` = `true`.
- Code can only call `getInfo` and `trade`, only on https://indodax.com; withdraw is refused in code.
- API key must have **view + trade only** (no withdraw).
- Max one order per coin per side per day (`client_order_id`); `MAX_TRADE_IDR` caps each order (default Rp1,000,000).
- A coin is skipped for the day if it's in maintenance, its spread is > 1%, or its price data is stale.
- Workflow has `contents: read` only; `actions/checkout` pinned to a commit SHA.

## Setup
1. Indodax → Trade API (**V1**) → key with **View + Trade** only.
2. GitHub repo → Settings → Secrets and variables → Actions → **Secrets**: `INDODAX_API_KEY`, `INDODAX_API_SECRET`.
3. Actions → *daily-trade* → **Run workflow** → check the summary (signal table, equity, planned orders).
4. Go live: **Variables** → `LIVE_TRADING` = `true`. Stop: delete it (and delete the API key in an emergency).

Optional variables: `COINS` (e.g. `btc,eth,sol`), `MAX_TRADE_IDR` (e.g. `2000000`), `ML_WEIGHT` (default `0` = shadow).

## Costs and tax (Nov 2026)
- Market orders pay Indodax's all-in taker fee (check your rate in Indodax Profile).
- Sells carry final PPh 22 of 0.21% (PMK 50/2025), withheld by Indodax.
- Backtest turnover ≈ 18× equity per year → ~6% of equity per year in costs. Costs are the main enemy.

## Note on Trade API V1
Indodax will retire V1 (legacy `/tapi`) after an announced date. Migrate to TAPI v2 before then.

## Tests
`python3 -I -m unittest discover -s tests -v` — includes Indodax's official signing test vector and fake-exchange end-to-end tests.
