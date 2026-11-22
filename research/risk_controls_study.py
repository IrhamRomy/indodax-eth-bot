"""Portfolio kill switch + daily crash breaker — as pre-registered in research/PREREGISTERED_risk_controls.md (4b4e076).

Usage: python -I research/risk_controls_study.py <indodax_5.json> <binance_8_daily.json> <out_dir>
Data from research/fetch_risk_data.py. Base rule identical to research/regime_filter_study.py.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

IND, BIN, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
BUY, SELL, LB, VOLN, TV, MAXW, BAND = 0.0020, 0.0041, 21, 60, 0.06, 0.25, 0.5
TODAY = pd.Timestamp.now(tz="UTC").normalize()
START = "2018-07-01"
VARIANTS = {"D1": {}, "K20": {"kill": 0.20}, "K25": {"kill": 0.25}, "K30": {"kill": 0.30},
            "C10": {"crash": 0.10}, "C15": {"crash": 0.15}, "K25+C15": {"kill": 0.25, "crash": 0.15}}
HALT_DAYS, BLOCK_DAYS = 30, 7


def load_indodax():
    raw = json.loads(IND.read_text())
    d = {c: pd.Series({pd.Timestamp(int(r["Time"]), unit="s", tz="UTC"): float(r["Close"]) for r in rows})
         for c, rows in raw.items()}
    df = pd.DataFrame(d).sort_index()
    return df[df.index < TODAY]


def load_binance():
    raw = json.loads(BIN.read_text())
    d = {s.replace("USDT", "").lower(): pd.Series({pd.Timestamp(int(k[0]), unit="ms", tz="UTC"): float(k[4])
                                                  for k in rows}) for s, rows in raw.items()}
    df = pd.DataFrame(d).sort_index()
    return df[df.index < TODAY]


def targets(px):
    mom = px / px.shift(LB) - 1
    vol = np.log(px).diff().rolling(VOLN).std() * math.sqrt(365)
    w = (TV / vol).clip(upper=MAXW).where(mom > 0, 0.0).fillna(0.0)
    g = w.sum(axis=1)
    return w.div(g.where(g > 1, 1.0), axis=0)


def simulate(px, start, end, kill=None, crash=None):
    tg = targets(px).shift(1).loc[start:end]  # decided on yesterday's close
    rr = px.pct_change(fill_method=None).fillna(0.0).loc[start:end]
    n = px.shape[1]
    w = np.zeros(n)
    eq, peak, halt_until = 1.0, 1.0, -1
    block = np.full(n, -1)
    out, turn, kills, crashes = [], 0.0, 0, 0
    for i in range(len(tg)):
        r = rr.iloc[i].to_numpy()
        gross = float(w @ r)
        held = w > 0
        w = w * (1 + r) / (1 + gross)
        eq *= 1 + gross
        t = np.nan_to_num(tg.iloc[i].to_numpy())
        if kill is not None:
            if i == halt_until:          # 30-day pause over: reset the peak, D1 resumes
                peak = eq
            if i < halt_until:
                t = np.zeros(n)
            else:
                peak = max(peak, eq)
                if eq <= (1 - kill) * peak:
                    kills += 1
                    halt_until = i + HALT_DAYS
                    t = np.zeros(n)
        if crash is not None:
            hit = held & (r <= -crash)
            crashes += int(hit.sum())
            block = np.where(hit, i + BLOCK_DAYS, block)
            t = np.where(i < block, 0.0, t)
        flip = (t == 0) != (w == 0)
        drift = (t > 0) & (np.abs(t - w) > BAND * t)
        new = np.where(flip | drift, t, w)
        d = new - w
        cost = float(np.clip(d, 0, None).sum() * BUY + np.clip(-d, 0, None).sum() * SELL)
        turn += np.abs(d).sum()
        w = new
        eq *= 1 - cost
        out.append((1 + gross) * (1 - cost) - 1)
    s = pd.Series(out, index=tg.index)
    return s, turn / (len(s) / 365), kills, crashes


def stats(s, turn=None, kills=0, crashes=0):
    eq = (1 + s).cumprod()
    res = {"CAGR": round(float(eq.iloc[-1] ** (365 / len(s)) - 1), 4),
           "sharpe": round(float(s.mean() / s.std() * math.sqrt(365)), 3),
           "max_dd": round(float((eq / eq.cummax() - 1).min()), 4),
           "worst_30d": round(float((eq / eq.shift(30) - 1).min()), 4),
           "worst_1d": round(float(s.min()), 4),
           "by_year": {int(y): round(float(v), 4) for y, v in ((1 + s).groupby(s.index.year).prod() - 1).items()}}
    if turn is not None:
        res.update(turnover_per_year=round(float(turn), 1), kill_triggers=kills, crash_triggers=crashes)
    return res


def dca(s, monthly=300_000):
    """Deposit on the first day of each month; balance follows the strategy's daily returns."""
    bal, flows = 0.0, []
    for i, (ts, r) in enumerate(s.items()):
        if i == 0 or ts.month != s.index[i - 1].month:
            bal += monthly
            flows.append(i)
        bal *= 1 + r
    n = len(s)

    def f(rd):
        return sum(monthly * (1 + rd) ** (n - k) for k in flows) - bal
    lo, hi = -0.05, 0.05
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(mid) < 0 else (lo, mid)
    return {"deposited": monthly * len(flows), "final": round(bal), "mwr_per_year": round((1 + mid) ** 365 - 1, 4)}


def run(px, end):
    full, sub = {}, {}
    series = {}
    for name, kw in VARIANTS.items():
        s, turn, k, c = simulate(px, START, end, **kw)
        series[name] = s
        full[name] = stats(s, turn, k, c)
        sub[name] = {"2018-07..2021": stats(s.loc[:"2021-12-31"]), "2022..end": stats(s.loc["2022-01-01":])}
    return full, sub, series


ind, binance = load_indodax(), load_binance()
end_i, end_b = str(ind.index[-1].date()), str(binance.index[-1].date())
res = {"period": {"A_indodax": [START, end_i], "B_binance": [START, end_b]}}
res["A_indodax"], res["A_sub"], _ = run(ind, end_i)
res["B_binance"], res["B_sub"], _ = run(binance, end_b)

# descriptive "bear last" savings case: fresh start 2021-01-01, bull 2021 then bear 2022
bear_last = {}
for name, kw in VARIANTS.items():
    s, *_ = simulate(ind, "2021-01-01", "2022-12-31", **kw)
    bear_last[name] = dca(s)
ew = ind.pct_change(fill_method=None).loc["2021-01-01":"2022-12-31"].mean(axis=1, skipna=True).fillna(0.0)
bear_last["buy_hold_equal_weight"] = dca(ew)
res["bear_last_dca_indodax_2021_2022"] = bear_last

checks, candidates = {}, []
for v in VARIANTS:
    if v == "D1":
        continue
    ok = {}
    for data in ("A_indodax", "B_binance"):
        a, b = res[data]["D1"], res[data][v]
        ok[data] = {"MaxDD better by >= 3pp": bool(b["max_dd"] >= a["max_dd"] + 0.03),
                    "CAGR >= D1 - 2pp": bool(b["CAGR"] >= a["CAGR"] - 0.02),
                    "Sharpe >= D1 - 0.05": bool(b["sharpe"] >= a["sharpe"] - 0.05)}
    checks[v] = ok
    if all(all(x.values()) for x in ok.values()):
        candidates.append(v)
res["checks"] = checks
calmar = {v: res["A_indodax"][v]["CAGR"] / abs(res["A_indodax"][v]["max_dd"]) for v in candidates}
res["candidates"] = candidates
res["chosen"] = max(candidates, key=lambda v: (calmar[v], -res["A_indodax"][v].get("kill_triggers", 0)
                                                - res["A_indodax"][v].get("crash_triggers", 0))) if candidates else None
(OUT / "risk_controls_study.json").write_text(json.dumps(res, indent=2))

for data in ("A_indodax", "B_binance"):
    print(f"\n== {data} {res['period'][data]}")
    for v, x in res[data].items():
        print(f"  {v:8s} CAGR {x['CAGR']:+6.1%} Sharpe {x['sharpe']:.2f} MaxDD {x['max_dd']:6.1%} "
              f"worst30d {x['worst_30d']:6.1%} worst1d {x['worst_1d']:6.1%} turn {x['turnover_per_year']:5.1f} "
              f"kills {x['kill_triggers']} crashes {x['crash_triggers']}")
for data in ("A_sub", "B_sub"):
    print(f"\n== {data}")
    for v, x in res[data].items():
        print("  " + v.ljust(8) + "  ".join(f"{p}: CAGR {y['CAGR']:+.1%} SR {y['sharpe']:.2f} DD {y['max_dd']:.1%}"
                                         for p, y in x.items()))
print("\n== bear-last DCA (Indodax, Rp300k/month, 2021-01 → 2022-12)")
for v, x in bear_last.items():
    print(f"  {v:22s} deposited Rp{x['deposited']:,} final Rp{x['final']:,} MWR {x['mwr_per_year']:+.1%}/yr")
print("\nchecks:", json.dumps(checks, indent=1))
print("candidates:", candidates, "chosen:", res["chosen"])
