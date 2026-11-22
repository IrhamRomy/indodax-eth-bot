# indodax-eth-bot

Small live-trading bot for **ETH/IDR on Indodax**, run once a day by GitHub Actions.

**Rule (time-series momentum):** if ETH/IDR closed higher than it did 21 days ago → hold ETH; otherwise hold rupiah.
Once a day at 11:07 WIB the bot checks the signal and, if needed, places one market order (all-in or all-out).

> This is an experiment with small money. The edge is **not proven** (see the paper trial in `quant-paper-trial`).
> Rp150k will not earn USD 350/month; the point is to measure real fees, slippage and reliability.

## Safety design
- Standard-library Python only — no third-party packages.
- **Dry run by default.** Trades only if repo variable `LIVE_TRADING` = `true`.
- The code can only call `getInfo` and `trade`; any other API method (e.g. withdraw) is refused in code.
- API key must be created with **view + trade only** (no withdraw). Then even a leaked key can't move coins out.
- At most one order per day (`client_order_id` = `tsmom-YYYYMMDD-side`; a same-day re-run is rejected by Indodax).
- `MAX_TRADE_IDR` caps any single order (default Rp1,000,000).
- Skips trading if the market is in maintenance, the spread is > 1%, or price data is stale.
- Workflow has `contents: read` only; `actions/checkout` pinned to a commit SHA.

## Setup (10 minutes)
1. **Indodax API key:** Indodax → Profile → **Trade API** → create key with **view** and **trade**. Do **not** tick withdraw.
2. **GitHub secrets:** repo → Settings → Secrets and variables → Actions → **Secrets** → New:
   - `INDODAX_API_KEY`
   - `INDODAX_API_SECRET`
3. **Dry-run test:** Actions tab → *daily-trade* → **Run workflow**. Open the run → the summary shows signal, your balance and the order it *would* send.
4. **Go live (only when you're ready):** Settings → Secrets and variables → Actions → **Variables** → New: `LIVE_TRADING` = `true`.
   The next scheduled run (or a manual run) will trade.
5. **Stop anytime:** delete the `LIVE_TRADING` variable (or set it to `false`), or disable the workflow in the Actions tab.
   For an emergency, also delete the API key on Indodax.

Optional variable: `MAX_TRADE_IDR` (e.g. `200000`) to cap order size.

## Costs and tax (as of Nov 2026)
- Market orders pay Indodax's taker fee (all-in fee incl. tax; check your rate in Indodax Profile).
- Sells carry final PPh 22 of 0.21% (PMK 50/2025), withheld by Indodax — no extra filing for the trade itself.
- A full switch (sell → buy) costs roughly 0.5–0.7% round trip. Momentum switches a handful of times per year.

## Tests
```
python3 -I -m unittest discover -s tests -v
```
Includes the HMAC-SHA512 test vector from Indodax's official API docs and a fake-exchange end-to-end test.
