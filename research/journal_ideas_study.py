"""Journal-review ideas J1-J4 vs live TSMOM 21d — as pre-registered in
research/PREREGISTERED_journal_ideas.md (commit 113cb61).

Usage: python -I research/journal_ideas_study.py <data_dir> <out_dir> [<binance_4h_dir>]
data_dir: majors.json ({coin: Indodax tradingview/history_v2 daily candles}) and
          summaries.json (Indodax /api/summaries, same day).
binance_4h_dir (optional): <SYM>USDT_4h.csv.gz files from the paper trial, for the robustness check.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

DATA, OUT = Path(sys.argv[1]), Path(sys.argv[2])
BIN = Path(sys.argv[3]) if len(sys.argv) > 3 else None
OUT.mkdir(parents=True, exist_ok=True)
TODAY = pd.Timestamp.now(tz="UTC").normalize()
START, OOS = pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
TV, VOLN, BAND, CAP = 0.06, 60, 0.5, 0.25
N_PRIOR = 61


def load_indodax():
    raw = json.loads((DATA / "majors.json").read_text())
    close = {}
    for c, rows in raw.items():
        df = pd.DataFrame(rows)
        df["t"] = pd.to_datetime(df["Time"].astype("int64"), unit="s", utc=True)
        df = df.drop_duplicates("t").set_index("t").sort_index()
        close[c] = df.loc[df.index < TODAY, "Close"].astype(float)
    C = pd.DataFrame(close).sort_index().loc["2021-01-01":]
    summ = json.loads((DATA / "summaries.json").read_text())["tickers"]
    hs = {}
    for c in C.columns:
        t = summ.get(f"{c}_idr", {})
        b, a = float(t.get("buy", 0) or 0), float(t.get("sell", 0) or 0)
        hs[c] = max((a - b) / a / 2 if a > 0 else 0.0, 0.0005)
    hs = pd.Series(hs)
    return C, 0.0020 + hs, 0.0041 + hs


def load_binance():
    close = {}
    for f in sorted(BIN.glob("*_4h.csv.gz")):
        d = pd.read_csv(f, index_col=0, parse_dates=True)
        d = d[d.index + pd.Timedelta(hours=4) <= TODAY]
        close[f.name.split("USDT")[0].lower()] = d["close"].resample("1D").last()
    C = pd.DataFrame(close).sort_index().loc["2020-06-01":]
    z = pd.Series(0.0015, index=C.columns)
    return C, z, z


def run_all(C, buyc, sellc):
    Cf = C.ffill()
    R = Cf.pct_change(fill_method=None).fillna(0.0).clip(-0.95, 10)
    VOL = np.log(Cf).diff().rolling(VOLN, min_periods=VOLN).std() * math.sqrt(365)
    dvol = VOL / math.sqrt(365)
    ret = lambda n: Cf / Cf.shift(n) - 1  # noqa: E731

    def size(frac):
        w = (TV / VOL * frac).where(VOL.notna(), 0.0).fillna(0.0).clip(upper=CAP)
        g = w.sum(axis=1)
        return w.div(g.where(g > 1, 1.0), axis=0)

    r28 = ret(28)
    q67 = r28.expanding(min_periods=180).quantile(2 / 3)
    on21 = ret(21) > 0

    def trail_stop():
        out = np.zeros(C.shape, dtype=bool)
        cf, sig, dv = Cf.to_numpy(), on21.to_numpy(), dvol.to_numpy()
        holding = np.zeros(C.shape[1], dtype=bool)
        armed = np.ones(C.shape[1], dtype=bool)    # may enter on a fresh signal
        peak = np.zeros(C.shape[1])
        for i in range(len(cf)):
            for j in range(C.shape[1]):
                if not sig[i, j]:
                    holding[j], armed[j] = False, True
                    continue
                if holding[j]:
                    peak[j] = max(peak[j], cf[i, j])
                    if np.isfinite(dv[i, j]) and cf[i, j] < peak[j] * (1 - 3 * dv[i, j]):
                        holding[j], armed[j] = False, False   # stopped: wait for a fresh signal
                elif armed[j]:
                    holding[j], peak[j] = True, cf[i, j]
            out[i] = holding
        return pd.DataFrame(out, index=C.index, columns=C.columns)

    frac_mh = sum((ret(h) > 0).astype(float) for h in (7, 14, 28, 56)) / 4
    variants = {
        "LIVE_tsmom21": size(on21.astype(float)),
        "J1_tsmom28": size((r28 > 0).astype(float)),
        "J2_tsmom28_top_third": size(((r28 > q67) & q67.notna()).astype(float)),
        "J3_multi_horizon": size(frac_mh.where(ret(56).notna(), 0.0)),
        "J4_tsmom21_trailstop": size(trail_stop().astype(float)),
    }
    bc, sc = buyc.reindex(C.columns).to_numpy(), sellc.reindex(C.columns).to_numpy()

    def simulate(tgt):
        tg, rr = tgt.shift(1).loc[START:].to_numpy(), R.loc[START:].to_numpy()
        w, out, turn = np.zeros(C.shape[1]), np.zeros(len(tg)), 0.0
        for i in range(len(tg)):
            gross = float(w @ rr[i])
            w = w * (1 + rr[i]) / (1 + gross) if gross > -1 else w * 0
            t = np.nan_to_num(tg[i])
            flip = (t == 0) != (w == 0)
            drift = (t > 0) & (np.abs(t - w) > BAND * t)
            new = np.where(flip | drift, t, w)
            d = new - w
            out[i] = gross - float(np.clip(d, 0, None) @ bc + np.clip(-d, 0, None) @ sc)
            turn += np.abs(d).sum()
            w = new
        s = pd.Series(out, index=C.loc[START:].index)
        return s, turn / (len(s) / 365)

    res, ser = {}, {}
    for k, tgt in variants.items():
        s, t = simulate(tgt)
        ser[k] = s
        res[k] = stats(s) | {"turnover_per_year": round(t, 1)}
    ew = R.loc[START:].mean(axis=1)
    res["BUY_HOLD_EW"] = stats(ew)
    return res, ser


def stats(s):
    def blk(x):
        eq = (1 + x).cumprod()
        sd = x.std()
        return {"CAGR": round(float(eq.iloc[-1] ** (365 / len(x)) - 1), 4),
                "sharpe": round(float(x.mean() / sd * math.sqrt(365)), 3) if sd > 0 else 0.0,
                "max_dd": round(float((eq / eq.cummax() - 1).min()), 4)}
    d = blk(s)
    d["IS_2022_2024"] = blk(s[s.index < OOS])
    d["OOS_2025_2026"] = blk(s[s.index >= OOS])
    d["by_year"] = {int(y): round(float(v), 4) for y, v in ((1 + s).groupby(s.index.year).prod() - 1).items()}
    return d


res_i, ser_i = run_all(*load_indodax())
out = {"indodax_majors5": res_i}
if BIN:
    out["binance_8coins"], _ = run_all(*load_binance())

# Deflated Sharpe: variance of trial Sharpes = all earlier study Sharpes found in results/ + these 4
prior = []
for f in ("universe_memes_study.json", "tsmom_cadence_avax_study.json", "fee_aware_study.json"):
    p = OUT / f
    if p.exists():
        def walk(x, depth=0):
            if isinstance(x, dict):
                if "sharpe" in x and "IS_2022_2024" in x:
                    prior.append(float(x["sharpe"]))
                for v in x.values():
                    walk(v, depth + 1)
        walk(json.loads(p.read_text()))
new = [ser_i[k] for k in ser_i if k.startswith("J")]
trial_sr = np.array([x / math.sqrt(365) for x in prior] + [s.mean() / s.std() for s in new])
N, g = N_PRIOR + len(new), 0.5772156649
sr0 = math.sqrt(np.var(trial_sr, ddof=1)) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * math.e)))
for k, s in ser_i.items():
    sr = s.mean() / s.std()
    out["indodax_majors5"][k]["DSR_N65"] = round(float(norm.cdf(
        (sr - sr0) * math.sqrt(len(s) - 1) / math.sqrt(1 - s.skew() * sr + (s.kurt() + 2) / 4 * sr ** 2))), 3)
out["dsr_note"] = f"N={N}; trial-Sharpe variance from {len(prior)} earlier study Sharpes + {len(new)} new"

live, b_live = out["indodax_majors5"]["LIVE_tsmom21"], out.get("binance_8coins", {}).get("LIVE_tsmom21")
for k in [k for k in ser_i if k.startswith("J")]:
    r = out["indodax_majors5"][k]
    checks = {"a_DSR>=0.95": r["DSR_N65"] >= 0.95,
              "b_OOS_sharpe>live": r["OOS_2025_2026"]["sharpe"] > live["OOS_2025_2026"]["sharpe"],
              "c_maxDD_not_5pts_worse": r["max_dd"] >= live["max_dd"] - 0.05,
              "d_binance_sharpe>=live": (out["binance_8coins"][k]["sharpe"] >= b_live["sharpe"]) if b_live else None}
    r["checks"] = checks
    r["verdict"] = "REPLACE LIVE" if all(v for v in checks.values() if v is not None) else (
        "NOTE FOR MARCH VERDICT" if all(v for kk, v in checks.items() if kk != "a_DSR>=0.95" and v is not None) else "REJECT")
(OUT / "journal_ideas_study.json").write_text(json.dumps(out, indent=1))
for mk in [m for m in out if m != "dsr_note"]:
    print(f"== {mk}")
    for k, r in out[mk].items():
        print(f"  {k:24s} CAGR {r['CAGR']:+6.1%} SR {r['sharpe']:5.2f} DD {r['max_dd']:6.1%} "
              f"OOS SR {r['OOS_2025_2026']['sharpe']:5.2f} turn {r.get('turnover_per_year', '-')} "
              f"DSR {r.get('DSR_N65', '-')} {r.get('verdict', '')}")
print(out["dsr_note"])
