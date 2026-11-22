"""TSMOM daily vs every 3 days on Indodax data, as pre-registered in PREREGISTERED_tsmom_every_3_days.md.

Usage: cd research && python3 fetch.py && python3 tsmom_cadence_study.py
Reads closes.json (Indodax IDR daily closes from fetch.py). Standard library only.
"""
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import bot  # noqa: E402  (uses the live bot's own momentum, volatility and sizing functions)

COINS = ["BTC", "ETH", "SOL", "XRP", "DOGE"]
BUY, SELL, BAND, LB = 0.0020, 0.0041, 0.5, 21
START = int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp())

D = json.loads((HERE / "closes.json").read_text())
days = sorted(set.intersection(*[set(map(int, D[c])) for c in COINS]))
today0 = int(datetime.now(timezone.utc).timestamp()) // 86400 * 86400
days = [t for t in days if t < today0]  # completed days only
px = {c: [float(D[c][str(t)]) for t in days] for c in COINS}
i0 = next(i for i, t in enumerate(days) if t >= START)


def targets(i):
    """Target weights decided with closes up to day i-1 (traded at day i's close)."""
    sig = {}
    for c in COINS:
        closes = px[c][: i]  # up to and including day i-1
        sig[c] = (bot.momentum(closes, LB), bot.annual_vol(closes))
    return bot.target_weights(sig)


def run(every, phase):
    w = {c: 0.0 for c in COINS}
    eq, curve, turn, fees = 1.0, [], 0.0, 0.0
    for i in range(i0, len(days)):
        if i > i0:
            g = sum(w[c] * (px[c][i] / px[c][i - 1] - 1) for c in COINS)
            eq *= 1 + g
            for c in COINS:
                w[c] = w[c] * (px[c][i] / px[c][i - 1]) / (1 + g)
        if (days[i] // 86400 - phase) % every == 0:
            tgt = targets(i)
            buys = sells = 0.0
            for c in COINS:
                cur, t = w[c], tgt.get(c, 0.0)
                if (t == 0 and cur > 0) or (t > 0 and abs(t - cur) > BAND * t):
                    if t > cur:
                        buys += t - cur
                    else:
                        sells += cur - t
                    w[c] = t
            cost = BUY * buys + SELL * sells
            eq *= 1 - cost
            turn += buys + sells
            fees += cost
        curve.append(eq)
    n = len(curve)
    yrs = n / 365
    r = [curve[k] / curve[k - 1] - 1 for k in range(1, n)]
    m = sum(r) / len(r)
    sd = math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))
    peak, mdd = 0.0, 0.0
    for x in curve:
        peak = max(peak, x)
        mdd = min(mdd, x / peak - 1)
    by_year, prev = {}, 1.0
    for k, t in enumerate(days[i0:]):
        by_year[datetime.fromtimestamp(t, timezone.utc).year] = curve[k]
    out_y = {}
    for y in sorted(by_year):
        out_y[y] = round(by_year[y] / prev - 1, 4)
        prev = by_year[y]
    return {"CAGR": round(curve[-1] ** (1 / yrs) - 1, 4), "sharpe": round(m / sd * math.sqrt(365), 3),
            "max_dd": round(mdd, 4), "turnover_per_year": round(turn / yrs, 1),
            "fees_per_year": round(fees / yrs, 4), "by_year": out_y}


res = {"DAILY": run(1, 0)}
for p in (0, 1, 2):
    res[f"EVERY_3D_p{p}"] = run(3, p)
three = [res[f"EVERY_3D_p{p}"] for p in (0, 1, 2)]
avg = {k: round(sum(x[k] for x in three) / 3, 4) for k in ("CAGR", "sharpe", "max_dd", "turnover_per_year", "fees_per_year")}
res["EVERY_3D_average"] = avg
d = res["DAILY"]
checks = {
    "avg Sharpe >= daily + 0.05": bool(avg["sharpe"] >= d["sharpe"] + 0.05),
    "every phase CAGR >= daily - 1pp": bool(all(x["CAGR"] >= d["CAGR"] - 0.01 for x in three)),
    "avg MaxDD within 5pp of daily": bool(avg["max_dd"] >= d["max_dd"] - 0.05),
}
out = {"period": [datetime.fromtimestamp(days[i0], timezone.utc).date().isoformat(),
                  datetime.fromtimestamp(days[-1], timezone.utc).date().isoformat()],
       "coins": COINS, "costs": {"buy": BUY, "sell": SELL}, "results": res,
       "checks": checks, "PASS": all(checks.values())}
(HERE / "results").mkdir(exist_ok=True)
(HERE / "results" / "tsmom_cadence_study.json").write_text(json.dumps(out, indent=2))
print(json.dumps(out, indent=2))
