"""Auto-universe, meme coins and other signals — as pre-registered in
research/PREREGISTERED_universe_memes_signals.md (commit 1fbc3ad).

Usage: python -I research/universe_memes_study.py <history_all.json> <snapshot.json> <out_dir>
history_all.json: {coin: [daily candles from Indodax tradingview/history_v2]} for all IDR pairs.
snapshot.json:    {"pairs": /api/pairs, "summaries": /api/summaries} taken the same day.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

HIST, SNAP, OUT = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
OUT.mkdir(parents=True, exist_ok=True)
TODAY = pd.Timestamp.now(tz="UTC").normalize()
START, OOS = pd.Timestamp("2022-01-01", tz="UTC"), pd.Timestamp("2025-01-01", tz="UTC")
BUY, SELL, MIN_HS = 0.0020, 0.0041, 0.0005
TV, VOLN, BAND = 0.06, 60, 0.5
MAJORS = ["btc", "eth", "sol", "xrp", "doge"]
MEMES = ("bome bonk brett cat cheems chillguy degen dogs fartcoin floki giga goat griffain jellyjelly "
         "meme mew mog moodeng myro pengu pepe pippin pnut ponke popcat shib spx sundog toshi trump "
         "turbo useless vine wif zerebro").split()
STABLE_EXACT = {"dai", "tusd", "fdusd", "busd", "pyusd", "xaut", "paxg"}


def is_stable(c):
    return c in STABLE_EXACT or c.startswith(("usd", "idr", "eur"))


# ---------------- data ----------------
raw = json.loads(HIST.read_text())
close, volidr = {}, {}
for c, rows in raw.items():
    if not rows or is_stable(c):
        continue
    df = pd.DataFrame(rows)
    df["t"] = pd.to_datetime(df["Time"].astype("int64"), unit="s", utc=True)
    df = df.drop_duplicates("t").set_index("t").sort_index()
    df = df[df.index < TODAY]
    if len(df) < 30:
        continue
    cl = df["Close"].astype(float)
    close[c] = cl.where(cl > 0)
    volidr[c] = df["Volume"].astype(float) * cl
C = pd.DataFrame(close).sort_index()
V = pd.DataFrame(volidr).reindex(C.index)
C = C.loc[pd.Timestamp("2021-01-01", tz="UTC"):]
V = V.loc[C.index]
listed = C.notna().cumsum()                      # days of history so far (point in time)
Cf = C.ffill().where(listed > 0)
R = Cf.pct_change(fill_method=None).fillna(0.0).clip(-0.95, 10)  # guard against bad ticks
vol30 = V.rolling(30, min_periods=20).median()

snap = json.loads(SNAP.read_text())
spread = {}
for p in snap["pairs"]:
    if p["base_currency"] != "idr":
        continue
    t = snap["summaries"].get(p["ticker_id"]) or {}
    try:
        b, a = float(t["buy"]), float(t["sell"])
        spread[p["traded_currency"]] = (a - b) / a if a > 0 else 1.0
    except (KeyError, ValueError):
        spread[p["traded_currency"]] = 1.0
tradable = [c for c in C.columns if spread.get(c, 1.0) <= 0.02]
hs = pd.Series({c: max(spread.get(c, 1.0) / 2, MIN_HS) for c in C.columns})
memes_present = [m for m in MEMES if m in tradable]

# ---------------- universes (boolean membership per day) ----------------
def monthly_top(n, allow_memes):
    mem = pd.DataFrame(False, index=C.index, columns=C.columns)
    cand = [c for c in tradable if allow_memes or c not in MEMES]
    month_starts = C.index[C.index.is_month_start]
    chosen = {}
    for d in month_starts:
        prev = C.index[C.index < d]
        if len(prev) == 0:
            continue
        p = prev[-1]
        elig = [c for c in cand if listed.at[p, c] >= 180 and pd.notna(vol30.at[p, c])]
        top = vol30.loc[p, elig].sort_values(ascending=False).index[:n].tolist()
        chosen[str(d.date())] = top
        mem.loc[d:, :] = False
        mem.loc[d:, top] = True
    return mem, chosen


U = {}
U["U1_majors5"] = pd.DataFrame(False, index=C.index, columns=C.columns)
U["U1_majors5"][MAJORS] = True
U["U2_auto_majors"], chosen_u2 = monthly_top(5, False)
U["U3_auto_all"], chosen_u3 = monthly_top(5, True)
u4 = pd.DataFrame(False, index=C.index, columns=C.columns)
for m in memes_present:
    u4[m] = (listed[m] >= 90) & (vol30[m] >= 2e8)
U["U4_memes"] = u4
U["U5_majors_plus_memes"] = U["U1_majors5"] | u4
CAPS = {"U1_majors5": {}, "U2_auto_majors": {}, "U3_auto_all": {m: 0.10 for m in MEMES},
        "U4_memes": {m: 0.10 for m in MEMES}, "U5_majors_plus_memes": {m: 0.05 for m in MEMES}}

# ---------------- signals (use data up to and including day t) ----------------
sma = lambda n: Cf.rolling(n, min_periods=n).mean()  # noqa: E731
hi20 = Cf.shift(1).rolling(20, min_periods=20).max()
lo10 = Cf.shift(1).rolling(10, min_periods=10).min()


def donchian():
    on = pd.DataFrame(False, index=C.index, columns=C.columns)
    state = np.zeros(C.shape[1], dtype=bool)
    cf, h, lo = Cf.to_numpy(), hi20.to_numpy(), lo10.to_numpy()
    out = np.zeros_like(cf, dtype=bool)
    for i in range(len(cf)):
        enter = cf[i] > h[i]
        exit_ = cf[i] < lo[i]
        state = np.where(state, ~exit_, enter)
        state &= np.isfinite(cf[i])
        out[i] = state
    on.loc[:, :] = out
    return on


S = {"S1_tsmom21": (Cf / Cf.shift(21) - 1) > 0,
     "S2_tsmom63": (Cf / Cf.shift(63) - 1) > 0,
     "S3_above_sma50": Cf > sma(50),
     "S4_sma20_gt_sma100": sma(20) > sma(100),
     "S5_donchian20_10": donchian()}
VOL = np.log(Cf).diff().rolling(VOLN, min_periods=VOLN).std() * math.sqrt(365)


def targets(uname, on):
    m = U[uname] & on & VOL.notna()
    caps = pd.Series({c: CAPS[uname].get(c, 0.25) for c in C.columns})
    w = (TV / VOL).where(m, 0.0).fillna(0.0)
    w = w.clip(upper=caps, axis=1)
    if uname == "U5_majors_plus_memes":
        mm = [c for c in C.columns if c in MEMES]
        ms = w[mm].sum(axis=1)
        w[mm] = w[mm].mul((0.20 / ms).where(ms > 0.20, 1.0), axis=0)
    g = w.sum(axis=1)
    return w.div(g.where(g > 1, 1.0), axis=0)


def equal_weight(uname):
    m = U[uname].astype(float)
    w = m.div(m.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    return w.where(C.index.is_month_start[:, None] | (w == 0), np.nan).ffill().fillna(0.0)


def simulate(tgt, band=BAND):
    tg = tgt.shift(1).loc[START:].to_numpy()   # 1-day lag
    rr = R.loc[START:].to_numpy()
    buyc = (BUY + hs.reindex(C.columns)).to_numpy()
    sellc = (SELL + hs.reindex(C.columns)).to_numpy()
    w = np.zeros(C.shape[1])
    out, turn = np.zeros(len(tg)), 0.0
    for i in range(len(tg)):
        gross = float(w @ rr[i])
        w = w * (1 + rr[i]) / (1 + gross) if gross > -1 else w * 0
        t = np.nan_to_num(tg[i])
        flip = (t == 0) != (w == 0)
        drift = (t > 0) & (np.abs(t - w) > band * t)
        new = np.where(flip | drift, t, w)
        d = new - w
        cost = float(np.clip(d, 0, None) @ buyc + np.clip(-d, 0, None) @ sellc)
        turn += np.abs(d).sum()
        w = new
        out[i] = gross - cost
    s = pd.Series(out, index=C.loc[START:].index)
    return s, turn / (len(s) / 365)


def stats(s, turn=None):
    def blk(x):
        eq = (1 + x).cumprod()
        yrs = len(x) / 365
        sd = x.std()
        return {"CAGR": round(float(eq.iloc[-1] ** (1 / yrs) - 1), 4),
                "sharpe": round(float(x.mean() / sd * math.sqrt(365)), 3) if sd > 0 else 0.0,
                "max_dd": round(float((eq / eq.cummax() - 1).min()), 4)}
    d = blk(s)
    d["IS_2022_2024"] = blk(s[s.index < OOS])
    d["OOS_2025_2026"] = blk(s[s.index >= OOS])
    d["by_year"] = {int(y): round(float(v), 4) for y, v in ((1 + s).groupby(s.index.year).prod() - 1).items()}
    if turn is not None:
        d["turnover_per_year"] = round(float(turn), 1)
    return d


results, series = {}, {}
for un in U:
    for sn, on in S.items():
        s, t = simulate(targets(un, on))
        results[f"{un}|{sn}"], series[f"{un}|{sn}"] = stats(s, t), s
        r = results[f"{un}|{sn}"]
        print(f"{un:22s} {sn:20s} CAGR {r['CAGR']:+.1%} SR {r['sharpe']:.2f} DD {r['max_dd']:.0%} "
              f"OOS SR {r['OOS_2025_2026']['sharpe']:.2f} turn {r['turnover_per_year']}", flush=True)
    s, t = simulate(equal_weight(un), band=0.0 if un != "U1_majors5" else 0.0)
    results[f"{un}|BUY_HOLD_EW"] = stats(s, t)

# ---------------- Deflated Sharpe (N = 25 here + 36 earlier) ----------------
prior = json.loads((OUT / "prior_trial_sharpes.json").read_text()) if (OUT / "prior_trial_sharpes.json").exists() else []
trial_sr = np.array([series[k].mean() / series[k].std() for k in series] + [x / math.sqrt(365) for x in prior])
N, g = len(series) + 36, 0.5772156649
sr0 = math.sqrt(np.var(trial_sr, ddof=1)) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * math.e)))


def dsr(s):
    sr, t = s.mean() / s.std(), len(s)
    return float(norm.cdf((sr - sr0) * math.sqrt(t - 1) / math.sqrt(1 - s.skew() * sr + (s.kurt() + 2) / 4 * sr ** 2)))


for k in series:
    results[k]["DSR_N61"] = round(dsr(series[k]), 3)

# ---------------- decision rules ----------------
b = results["U1_majors5|S1_tsmom21"]
q1r = results["U2_auto_majors|S1_tsmom21"]
q1 = {"full Sharpe >= U1 - 0.05": q1r["sharpe"] >= b["sharpe"] - 0.05,
      "MaxDD within 5pp": q1r["max_dd"] >= b["max_dd"] - 0.05,
      "OOS Sharpe >= U1 - 0.10": q1r["OOS_2025_2026"]["sharpe"] >= b["OOS_2025_2026"]["sharpe"] - 0.10}
q2 = {}
for sn in S:
    u1, u5, u4 = (results[f"U1_majors5|{sn}"], results[f"U5_majors_plus_memes|{sn}"], results[f"U4_memes|{sn}"])
    ch = {"full Sharpe >= U1 + 0.10": u5["sharpe"] >= u1["sharpe"] + 0.10,
          "OOS Sharpe >= U1": u5["OOS_2025_2026"]["sharpe"] >= u1["OOS_2025_2026"]["sharpe"],
          "MaxDD within 5pp": u5["max_dd"] >= u1["max_dd"] - 0.05,
          "DSR >= 0.95": u5["DSR_N61"] >= 0.95,
          "memes-only CAGR > 0 in IS and OOS": u4["IS_2022_2024"]["CAGR"] > 0 and u4["OOS_2025_2026"]["CAGR"] > 0}
    q2[sn] = {"checks": {k: bool(v) for k, v in ch.items()}, "pass": bool(all(ch.values()))}
q3 = {}
for sn in list(S)[1:]:
    x = results[f"U1_majors5|{sn}"]
    ch = {"full Sharpe >= S1 + 0.10": x["sharpe"] >= b["sharpe"] + 0.10,
          "OOS Sharpe >= S1": x["OOS_2025_2026"]["sharpe"] >= b["OOS_2025_2026"]["sharpe"],
          "MaxDD within 5pp": x["max_dd"] >= b["max_dd"] - 0.05,
          "DSR >= 0.95": x["DSR_N61"] >= 0.95}
    q3[sn] = {"checks": {k: bool(v) for k, v in ch.items()}, "pass": bool(all(ch.values()))}

# ---------------- descriptive meme facts ----------------
meme_facts = {}
for m in [x for x in MEMES if x in C.columns]:
    c = C[m].dropna()
    if len(c) < 30:
        continue
    eq = c / c.iloc[0]
    meme_facts[m] = {"listed_since": str(c.index[0].date()), "days": len(c),
                     "return_since_listing": round(float(eq.iloc[-1] - 1), 3),
                     "drawdown_from_peak_now": round(float(c.iloc[-1] / c.max() - 1), 3),
                     "ann_vol": round(float(np.log(c).diff().std() * math.sqrt(365)), 2),
                     "median_daily_volume_idr_last30": round(float(V[m].iloc[-30:].median()), -6) if m in V else None,
                     "spread_now": round(spread.get(m, 1.0), 4), "tradable": m in tradable}

out = {"data_end": str(C.index[-1].date()), "coins_in_data": int(C.shape[1]), "tradable_coins": len(tradable),
       "memes_tradable": memes_present, "N_trials_for_DSR": N, "results": results,
       "Q1_auto_universe": {"checks": {k: bool(v) for k, v in q1.items()}, "pass": bool(all(q1.values()))},
       "Q2_memes": q2, "Q3_signals": q3, "U2_monthly_picks": chosen_u2, "U3_monthly_picks": chosen_u3,
       "meme_facts": meme_facts}
(OUT / "universe_memes_study.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: out[k] for k in ("data_end", "coins_in_data", "tradable_coins", "memes_tradable",
                                      "Q1_auto_universe", "Q2_memes", "Q3_signals")}, indent=1))
