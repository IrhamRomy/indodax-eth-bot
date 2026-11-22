"""Shadow ledger: compares TSMOM (live rule), ML alone, a 50:50 blend and the shadow rules SMA50 and
Donchian 20/10 on the bot's real daily signals.

Used by the nightly Claude check-in. Input is the RESULT_JSON line the bot prints in its
GitHub Actions log. Three virtual portfolios, each starting with Rp1,000,000 (so Indodax's
Rp10k minimum doesn't distort the comparison), follow the bot's exact rules (bot.plan_orders,
bot.size_buys) at the run's real bid/ask prices with real costs:
  sell 0.41% (0.2% fee + 0.21% PPh 22), buy 0.20%   (measured on the first live trade)

Usage:  python research/shadow_ledger.py --log job.log --run-id 123 --run-date 2026-11-23
Writes: reviews/shadow_state.json, reviews/shadow_ledger.csv; prints a markdown summary.
Standard library only. Never places orders and never needs API keys.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bot  # noqa: E402

REVIEWS = ROOT / "reviews"
STATE = REVIEWS / "shadow_state.json"
LEDGER = REVIEWS / "shadow_ledger.csv"
NOTIONAL = 1_000_000.0
SELL_COST, BUY_COST = 0.0041, 0.0020
NAMES = ("TSMOM", "ML_alone", "Blend_50_50", "SMA50", "Donchian_20_10")
ALT_KEYS = {"SMA50": "SMA50", "Donchian_20_10": "DONCHIAN_20_10"}  # RESULT_JSON alt_targets names


def parse_record(log_text: str) -> dict:
    lines = [ln for ln in log_text.splitlines() if "RESULT_JSON " in ln]
    if not lines:
        raise SystemExit("no RESULT_JSON line in this log (bot older than ledger support, or it crashed early)")
    return json.loads(lines[-1].split("RESULT_JSON ", 1)[1])


def equity(pf: dict, bids: dict) -> float:
    return pf["idr"] + sum(q * bids.get(c, 0.0) for c, q in pf["units"].items())


def step(pf: dict, target: dict | None, rec: dict) -> tuple[list[str], float, float]:
    """Apply one day's target to a virtual portfolio. Returns (trade notes, fees, traded IDR)."""
    coins = {c: v for c, v in rec["coins"].items() if v.get("status") == "ok"}
    if target is None or not coins:
        return ["no signal today → hold"], 0.0, 0.0
    bids = {c: v["bid"] for c, v in coins.items()}
    asks = {c: v["ask"] for c, v in coins.items()}
    mins = {c: (v["min_idr"], v["min_coin"]) for c, v in coins.items()}
    target = {c: w for c, w in target.items() if c in coins}
    holdings = {c: Decimal(str(q)) for c, q in pf["units"].items()}
    sells, buys = bot.plan_orders(target, holdings, bids, pf["idr"], mins, max_trade_idr=10**15)
    notes, fees, traded = [], 0.0, 0.0
    for o in sells:
        c = o["coin"]
        q = min(float(o[c]), pf["units"].get(c, 0.0))
        gross = q * bids[c]
        pf["units"][c] = pf["units"].get(c, 0.0) - q
        if pf["units"][c] * bids[c] < 1.0:  # less than Rp1 left = dust from 8-decimal rounding
            pf["units"].pop(c)
        pf["idr"] += gross * (1 - SELL_COST)
        fees += gross * SELL_COST
        traded += gross
        notes.append(f"sell {c.upper()} Rp{gross:,.0f}")
    for o in bot.size_buys(buys, pf["idr"]):
        c, idr = o["coin"], float(o["idr"])
        pf["idr"] -= idr
        pf["units"][c] = pf["units"].get(c, 0.0) + idr * (1 - BUY_COST) / asks[c]
        fees += idr * BUY_COST
        traded += idr
        notes.append(f"buy {c.upper()} Rp{idr:,.0f}")
    return notes or ["no trade"], fees, traded


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--run-date", required=True, help="UTC date of the run, YYYY-MM-DD")
    a = ap.parse_args()

    rec = parse_record(Path(a.log).read_text(errors="replace"))
    REVIEWS.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text()) if STATE.exists() else {
        "start": a.run_date, "notional": NOTIONAL, "processed": {},
        "portfolios": {n: {"idr": NOTIONAL, "units": {}, "peak": NOTIONAL, "fees": 0.0, "traded": 0.0}
                       for n in NAMES}}
    for n in NAMES:  # portfolios added later start with fresh virtual capital on their first day
        if n not in state["portfolios"]:
            state["portfolios"][n] = {"idr": NOTIONAL, "units": {}, "peak": NOTIONAL, "fees": 0.0,
                                      "traded": 0.0, "start": a.run_date}
    if a.run_date in state["processed"]:
        print(f"Run date {a.run_date} already in the ledger (run {state['processed'][a.run_date]}). Nothing to do.")
        return 0

    tsmom, ml = rec.get("tsmom_target"), rec.get("ml_target")
    alt = rec.get("alt_targets") or {}
    targets = {"TSMOM": tsmom, "ML_alone": ml,
               "Blend_50_50": bot.blend(tsmom, ml, 0.5) if (tsmom is not None and ml is not None) else None}
    targets.update({n: alt.get(k) for n, k in ALT_KEYS.items()})
    bids = {c: v["bid"] for c, v in rec["coins"].items()}
    out = [f"### Shadow ledger — {a.run_date} (run {a.run_id})", "",
           "| Portfolio | Today | Equity | Since start | Max DD | Invested | Fees paid | Turnover |",
           "|---|---|---|---|---|---|---|---|"]
    row = {"date": a.run_date, "run_id": a.run_id, "live_equity": rec.get("equity"),  # None in public-log mode
           "live_invested": rec.get("live_invested"),
           "ml_ok": ml is not None, "agree": None}
    for n in NAMES:
        pf = state["portfolios"][n]
        notes, fee, traded = step(pf, targets[n], rec)
        eq = equity(pf, bids)
        pf["peak"] = max(pf["peak"], eq)
        pf["fees"] += fee
        pf["traded"] += traded
        dd = eq / pf["peak"] - 1
        inv = 1 - pf["idr"] / eq if eq else 0.0
        out.append(f"| {n} | {'; '.join(notes)} | Rp{eq:,.0f} | {eq / NOTIONAL - 1:+.2%} | {dd:.1%} | "
                   f"{inv:.0%} | Rp{pf['fees']:,.0f} | {pf['traded'] / NOTIONAL:.1f}× |")
        row[f"{n}_equity"] = round(eq, 2)
        row[f"{n}_invested"] = round(inv, 4)
    if tsmom is not None and ml is not None:
        row["agree"] = sum((tsmom.get(c, 0) > 0) == (ml.get(c, 0) > 0) for c in tsmom) / max(len(tsmom), 1)
        out.append(f"\nSignal agreement TSMOM vs ML (in/out per coin): {row['agree']:.0%}")
    state["processed"][a.run_date] = a.run_id
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True))
    old_rows = list(csv.DictReader(LEDGER.open())) if LEDGER.exists() else []
    fields = list(dict.fromkeys([k for r in old_rows for k in r] + list(row)))  # keep order, add new columns
    with LEDGER.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in old_rows + [row]:
            w.writerow(r)
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
