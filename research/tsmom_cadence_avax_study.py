"""TSMOM cadence + AVAX study, as pre-registered in:
  research/PREREGISTERED_tsmom_every_3_days.md   (67f2858: D1 vs D3 start days)
  research/PREREGISTERED_tsmom_cadence_avax.md    (2911683: AVG3 variant, AVAX question)

Usage: python -I research/tsmom_cadence_avax_study.py <indodax closes.json> <paper-trial clone> <out_dir>
closes.json comes from research/fetch.py (Indodax daily closes). Stdlib + numpy + pandas.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CLOSES, PAPER, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
BUY, SELL, AVAX_EXTRA = 0.0020, 0.0041, 0.0031
LB, VOLN, TV, MAXW, BAND = 21, 60, 0.06, 0.25, 0.5
TODAY = pd.Timestamp.now(tz="UTC").normalize()

raw = json.loads(CLOSES.read_text())
indodax = pd.DataFrame({c.lower(): pd.Series({pd.Timestamp(int(t), unit="s", tz="UTC"): v
                                               for t, v in d.items()}) for c, d in raw.items()}).sort_index()
indodax = indodax[indodax.index < TODAY]  # completed days only


def binance_daily() -> pd.DataFrame:
    out = {}
    for f in sorted((PAPER / "research" / "data").glob("*_4h.csv.gz")):
        df = pd.read_csv(f, index_col=0, parse_dates=True)
        df = df[df.index + pd.Timedelta(hours=4) <= pd.Timestamp.now(tz="UTC")]
        out[f.name.split("USDT")[0].lower()] = df["close"].resample("1D").last()
    d = pd.DataFrame(out)
    return d[d.index < TODAY]


def targets(px: pd.DataFrame) -> pd.DataFrame:
    """Daily TSMOM target weights computed from each day's close (used the NEXT day)."""
    mom = px / px.shift(LB) - 1
    vol = np.log(px).diff().rolling(VOLN).std() * math.sqrt(365)
    w = (TV / vol).clip(upper=MAXW).where(mom > 0, 0.0).fillna(0.0)
    g = w.sum(axis=1)
    return w.div(g.where(g > 1, 1.0), axis=0)


def simulate(px, tgt, start, decide=lambda day: True, extra=None, cost_mult=1.0):
    """Signal from yesterday's close, executed at today's close. Returns daily returns, turnover/yr."""
    px, tgt = px.loc[:, tgt.columns], tgt.shift(1)  # 1-day lag
    rets = px.pct_change()
    idx = px.loc[start:].index
    extra = extra or {}
    w = pd.Series(0.0, index=px.columns)
    out, turn = [], 0.0
    for i, day in enumerate(idx):
        r = rets.loc[day].fillna(0.0)
        gross = float((w * r).sum())
        w = w * (1 + r) / (1 + gross) if (1 + gross) != 0 else w
        cost = 0.0
        if decide(day) and tgt.loc[day].notna().all():
            t = tgt.loc[day]
            new = w.copy()
            for c in px.columns:
                flip = (t[c] == 0) != (w[c] == 0)
                drift = t[c] > 0 and abs(t[c] - w[c]) > BAND * t[c]
                if flip or drift:
                    new[c] = t[c]
            d = new - w
            for c in px.columns:
                if d[c] > 0:
                    cost += d[c] * (BUY + extra.get(c, 0.0)) * cost_mult
                elif d[c] < 0:
                    cost += -d[c] * (SELL + extra.get(c, 0.0)) * cost_mult
            turn += d.abs().sum()
            w = new
        out.append(gross - cost)
    s = pd.Series(out, index=idx)
    return s, turn / (len(s) / 365)


def tranche(px, tgt, start, extra=None, cost_mult=1.0):
    """Three staggered sub-portfolios (1/3 capital each), each deciding every 3 days on its own day."""
    parts = [simulate(px, tgt, start, decide=lambda d, p=p: (d.value // 86_400_000_000_000) % 3 == p,
                      extra=extra, cost_mult=cost_mult) for p in range(3)]
    eqs = [(1 + s).cumprod() for s, _ in parts]
    eq = sum(eqs) / 3
    return eq.pct_change().fillna(eq.iloc[0] - 1), sum(t for _, t in parts) / 3


def stats(s, turn):
    eq = (1 + s).cumprod()
    yrs = len(s) / 365
    return {"CAGR": round(float(eq.iloc[-1] ** (1 / yrs) - 1), 4),
            "sharpe": round(float(s.mean() / s.std() * math.sqrt(365)), 3),
            "max_dd": round(float((eq / eq.cummax() - 1).min()), 4),
            "turnover_per_year": round(float(turn), 1),
            "by_year": {int(y): round(float(v), 4) for y, v in ((1 + s).groupby(s.index.year).prod() - 1).items()}}


def phase(p):
    return lambda d: (d.value // 86_400_000_000_000) % 3 == p


def avg3(tgt):
    return tgt.rolling(3).mean()


def cadence_block(px, start, extra=None, cost_mult=1.0, tranche_too=True):
    t = targets(px)
    res = {"D1": stats(*simulate(px, t, start, extra=extra, cost_mult=cost_mult))}
    for p in range(3):
        res[f"D3_p{p}"] = stats(*simulate(px, t, start, decide=phase(p), extra=extra, cost_mult=cost_mult))
    res["D3_avg"] = {k: round(float(np.mean([res[f"D3_p{p}"][k] for p in range(3)])), 4)
                     for k in ("CAGR", "sharpe", "max_dd", "turnover_per_year")}
    res["AVG3"] = stats(*simulate(px, avg3(t), start, extra=extra, cost_mult=cost_mult))
    if tranche_too:
        res["TRANCHE3"] = stats(*tranche(px, t, start, extra=extra, cost_mult=cost_mult))
    return res


FIVE = ["btc", "eth", "sol", "xrp", "doge"]
out = {"data_end": str(indodax.index[-1].date())}

# ---- Question 1 (Indodax, 5 coins, 2022-01-01 →) ----
q1 = cadence_block(indodax[FIVE], "2022-01-01")
q1_2x = cadence_block(indodax[FIVE], "2022-01-01", cost_mult=2.0, tranche_too=False)
bn = binance_daily()
bn_res = cadence_block(bn, "2022-01-01", tranche_too=False)
out.update(q1_indodax=q1, q1_indodax_2x_costs=q1_2x, q1_binance_8coins=bn_res)

D1 = q1["D1"]
# Rule A (67f2858): every 3 days
ruleA = {"avg Sharpe >= D1 + 0.05": q1["D3_avg"]["sharpe"] >= D1["sharpe"] + 0.05,
         "every start day CAGR >= D1 CAGR - 1pp": all(q1[f"D3_p{p}"]["CAGR"] >= D1["CAGR"] - 0.01 for p in range(3)),
         "avg MaxDD within 5pp of D1": q1["D3_avg"]["max_dd"] >= D1["max_dd"] - 0.05}
# Rule B (2911683): AVG3
ruleB = {"Sharpe >= D1 + 0.10": q1["AVG3"]["sharpe"] >= D1["sharpe"] + 0.10,
         "CAGR >= D1": q1["AVG3"]["CAGR"] >= D1["CAGR"],
         "MaxDD within 5pp of D1": q1["AVG3"]["max_dd"] >= D1["max_dd"] - 0.05,
         "Binance 8-coin Sharpe(AVG3) >= Sharpe(D1)": bn_res["AVG3"]["sharpe"] >= bn_res["D1"]["sharpe"]}
out["ruleA_every_3_days"] = {"checks": {k: bool(v) for k, v in ruleA.items()}, "pass": bool(all(ruleA.values()))}
out["ruleB_avg3"] = {"checks": {k: bool(v) for k, v in ruleB.items()}, "pass": bool(all(ruleB.values()))}

# ---- Question 2: AVAX (2022-07-01 →) ----
SIX = FIVE + ["avax"]
start2 = "2022-07-01"
q2 = {}
for name, cols in (("5_coins", FIVE), ("6_coins_with_AVAX", SIX)):
    t = targets(indodax[cols])
    q2[f"{name}_D1"] = stats(*simulate(indodax[cols], t, start2, extra={"avax": AVAX_EXTRA}))
    if out["ruleB_avg3"]["pass"]:
        q2[f"{name}_AVG3"] = stats(*simulate(indodax[cols], avg3(t), start2, extra={"avax": AVAX_EXTRA}))
a, b = q2["5_coins_D1"], q2["6_coins_with_AVAX_D1"]
ruleC = {"Sharpe(6) >= Sharpe(5)": b["sharpe"] >= a["sharpe"],
         "MaxDD(6) within 3pp of 5": b["max_dd"] >= a["max_dd"] - 0.03,
         "liquidity today (vol >= Rp100M, spread <= 1%)": True}  # checked live on 22 Nov: Rp180M, 0.61-0.65%
out["q2_avax"] = q2
out["ruleC_add_avax"] = {"checks": {k: bool(v) for k, v in ruleC.items()}, "pass": bool(all(ruleC.values()))}
(OUT / "tsmom_cadence_avax_study.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: v for k, v in out.items() if k.startswith("rule") or k == "data_end"}, indent=2))
for blk in ("q1_indodax", "q1_indodax_2x_costs", "q1_binance_8coins"):
    print("\n" + blk)
    for k, v in out[blk].items():
        print(f"  {k:9s}", {x: v[x] for x in ("CAGR", "sharpe", "max_dd", "turnover_per_year")})
print("\nq2_avax")
for k, v in q2.items():
    print(f"  {k:24s}", {x: v[x] for x in ("CAGR", "sharpe", "max_dd", "turnover_per_year")}, v["by_year"])
