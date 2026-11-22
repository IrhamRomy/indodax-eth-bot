"""BTC 200-day regime filter — as pre-registered in research/PREREGISTERED_regime_filter.md (2043b53/05574f2).

Usage: python -I research/regime_filter_study.py <indodax_5.json> <binance_8_daily.json> <out_dir>
indodax_5.json: {coin: Indodax tradingview/history_v2 daily candles since 2017}
binance_8_daily.json: {SYMBOL: Binance /api/v3/klines 1d rows since 2017}
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


def regime(px):
    btc = px["btc"]
    return btc > btc.rolling(200, min_periods=200).mean()  # False until 200 days exist


def simulate(px, tgt, start, end):
    tg = tgt.shift(1).loc[start:end]  # decided on yesterday's close
    rr = px.pct_change(fill_method=None).fillna(0.0).loc[start:end]
    w = np.zeros(px.shape[1])
    out, turn = [], 0.0
    for i in range(len(tg)):
        r = rr.iloc[i].to_numpy()
        gross = float(w @ r)
        w = w * (1 + r) / (1 + gross)
        t = np.nan_to_num(tg.iloc[i].to_numpy())
        flip = (t == 0) != (w == 0)
        drift = (t > 0) & (np.abs(t - w) > BAND * t)
        new = np.where(flip | drift, t, w)
        d = new - w
        cost = float(np.clip(d, 0, None).sum() * BUY + np.clip(-d, 0, None).sum() * SELL)
        turn += np.abs(d).sum()
        w = new
        out.append(gross - cost)
    s = pd.Series(out, index=tg.index)
    return s, turn / (len(s) / 365)


def stats(s, turn):
    eq = (1 + s).cumprod()
    return {"CAGR": round(float(eq.iloc[-1] ** (365 / len(s)) - 1), 4),
            "sharpe": round(float(s.mean() / s.std() * math.sqrt(365)), 3),
            "max_dd": round(float((eq / eq.cummax() - 1).min()), 4),
            "turnover_per_year": round(float(turn), 1),
            "by_year": {int(y): round(float(v), 4) for y, v in ((1 + s).groupby(s.index.year).prod() - 1).items()}}


def block(px, start, end):
    t = targets(px)
    tr = t.where(regime(px), 0.0)
    a, b = stats(*simulate(px, t, start, end)), stats(*simulate(px, tr, start, end))
    return {"D1": a, "D1_REGIME": b,
            "share_days_bull": round(float(regime(px).loc[start:end].mean()), 3)}


ind, binance = load_indodax(), load_binance()
H = ("2018-07-01", "2021-12-31")
res = {"H1_indodax_2018_2021": block(ind, *H),
       "H2_binance_2018_2021": block(binance, *H),
       "context_indodax_2022_2026": block(ind, "2022-01-01", str(ind.index[-1].date()))}
checks = {}
for h in ("H1_indodax_2018_2021", "H2_binance_2018_2021"):
    a, b = res[h]["D1"], res[h]["D1_REGIME"]
    checks[h] = {"Sharpe >= D1 + 0.05": bool(b["sharpe"] >= a["sharpe"] + 0.05),
                 "MaxDD not worse than D1": bool(b["max_dd"] >= a["max_dd"]),
                 "CAGR >= D1 - 2pp": bool(b["CAGR"] >= a["CAGR"] - 0.02)}
res["checks"] = checks
res["pass"] = bool(all(all(c.values()) for c in checks.values()))
(OUT / "regime_filter_study.json").write_text(json.dumps(res, indent=2))
for k, v in res.items():
    if isinstance(v, dict) and "D1" in v:
        print(k, "| bull days", v["share_days_bull"])
        for n in ("D1", "D1_REGIME"):
            x = v[n]
            print(f"   {n:10s} CAGR {x['CAGR']:+.1%} Sharpe {x['sharpe']:.2f} MaxDD {x['max_dd']:.1%} "
                  f"turn {x['turnover_per_year']} {x['by_year']}")
print(json.dumps({"checks": checks, "pass": res["pass"]}, indent=1))
