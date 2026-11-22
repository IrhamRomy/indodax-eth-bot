"""Fee-aware ML variants study, exactly as pre-registered in PREREGISTERED_fee_aware_ml.md.

Usage: python -I research/fee_aware_study.py <path to quant-paper-trial clone> <out_dir>
Needs numpy, pandas, lightgbm, scipy. Regenerates the paper trial's purged quarterly walk-forward
out-of-sample probabilities for the primary config (H18, k1.5) with the paper trial's own code,
then simulates the pre-registered variants with Indodax costs (buy 0.20%, sell 0.41%).
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

PAPER, OUT = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(PAPER))
from quantbot import strategy as st  # noqa: E402
from quantbot.features import BARS_PER_YEAR, FEATURES, panel_features, triple_barrier  # noqa: E402

OOS = pd.Timestamp("2022-01-01", tz="UTC")
RETRAIN = pd.DateOffset(months=3)
BUY, SELL = 0.0020, 0.0041

frames = {}
for f in sorted((PAPER / "research" / "data").glob("*_4h.csv.gz")):
    df = pd.read_csv(f, index_col=0, parse_dates=True)
    frames[f.name.split("_")[0]] = df[df.index + pd.Timedelta(hours=4) <= pd.Timestamp.now(tz="UTC")]
idx = frames["BTCUSDT"].index
frames = {s: f.reindex(idx) for s, f in frames.items()}
panel = panel_features(frames)
panel["ret_next"] = np.exp(panel["lr_next"]) - 1

probs_file = OUT / "oos_probs_primary.csv.gz"
if not probs_file.exists():
    lab = []
    for s, f in frames.items():
        fe = panel[panel.symbol == s].set_index("time")
        tb = triple_barrier(f["close"].reindex(fe.index), fe["sigma"], st.HORIZON, st.BARRIER_K)
        pos = tb["t1_pos"].to_numpy()
        t1 = np.full(len(pos), np.datetime64("NaT"), dtype="datetime64[ns]")
        ok = np.isfinite(pos)
        t1[ok] = fe.index.to_numpy()[pos[ok].astype(int)]
        lab.append(pd.DataFrame({"time": fe.index, "symbol": s, "y": tb["y"].to_numpy(),
                                 "t1": pd.to_datetime(t1, utc=True)}))
    d = panel.merge(pd.concat(lab), on=["time", "symbol"]).dropna(subset=FEATURES)
    preds = []
    for a in pd.date_range(OOS, d.time.max(), freq=RETRAIN):
        b = a + RETRAIN
        tr = d[(d.time < a) & (d.t1 < a) & d.y.notna()]  # purged: label must end before the test window
        te = d[(d.time >= a) & (d.time < b)]
        if te.empty:
            continue
        m = st.train(tr, tr.y)
        preds.append(te[["time", "symbol"]].assign(prob=m.predict(te[FEATURES])))
        print("fold", a.date(), len(tr), len(te), flush=True)
    pd.concat(preds).pivot(index="time", columns="symbol", values="prob").to_csv(probs_file)

P = lambda c: panel.pivot(index="time", columns="symbol", values=c).loc[OOS:]  # noqa: E731
RET, SIG, R126 = P("ret_next"), P("sigma"), P("ret_126")
prob = pd.read_csv(probs_file, index_col=0, parse_dates=True).reindex(RET.index)[RET.columns]
pv, r126 = prob.to_numpy(), R126.to_numpy()
sig_np, ret_np = SIG.to_numpy(), RET.fillna(0).to_numpy()
hours = RET.index.hour


def run(signal_fn, band: float, every_days: int, buy: float, sell: float, phase: int = 0):
    n = RET.shape[1]
    w, on = np.zeros(n), np.zeros(n, dtype=bool)
    rets, turn, fees, day_count = [], 0.0, 0.0, -1
    for i in range(len(RET) - 1):
        dt_buy = dt_sell = 0.0
        if hours[i] == 0:
            day_count += 1
            if (day_count - phase) % every_days == 0:
                on = signal_fn(i, on)
                tgt = np.where(on, st.size(sig_np[i]), 0.0)
                tgt = np.nan_to_num(tgt)
                g = tgt.sum()
                if g > st.MAX_GROSS:
                    tgt *= st.MAX_GROSS / g
                new = w.copy()
                for j in range(n):
                    flip = (tgt[j] == 0) != (w[j] == 0)
                    drift = tgt[j] > 0 and abs(tgt[j] - w[j]) > band * tgt[j]
                    if flip or drift:
                        new[j] = tgt[j]
                diff = new - w
                dt_buy, dt_sell = diff[diff > 0].sum(), -diff[diff < 0].sum()
                w = new
        cost = buy * dt_buy + sell * dt_sell
        turn += dt_buy + dt_sell
        fees += cost
        gross = (w * ret_np[i]).sum()
        rets.append(gross - cost)
        w = w * (1 + ret_np[i]) / (1 + gross)  # weights drift with prices
    s = pd.Series(rets, index=RET.index[:-1])
    yrs = len(s) / BARS_PER_YEAR
    return s, turn / yrs, fees / yrs


def ml_fn(thr_in, thr_out):
    return lambda i, on: np.array([st.ml_signal(p, o, thr_in, thr_out) if np.isfinite(p) else False
                                   for p, o in zip(pv[i], on)])


tsmom_fn = lambda i, on: np.array([st.tsmom_signal(x) for x in r126[i]])  # noqa: E731

VARIANTS = {  # pre-registered: (signal, band, decide every N days)
    "ML_deployed": (ml_fn(0.55, 0.50), 0.50, 1),
    "A_strict_entry": (ml_fn(0.60, 0.50), 0.50, 1),
    "B_every_3_days": (ml_fn(0.55, 0.50), 0.50, 3),
    "C_strict_wide_band": (ml_fn(0.60, 0.50), 0.75, 1),
    "TSMOM": (tsmom_fn, 0.50, 1),
}


def stats(r, turn, fee):
    eq = (1 + r).cumprod()
    yrs = len(r) / BARS_PER_YEAR
    return dict(CAGR=round(float(eq.iloc[-1] ** (1 / yrs) - 1), 4),
                sharpe=round(float(r.mean() / r.std() * np.sqrt(BARS_PER_YEAR)), 3),
                max_dd=round(float((eq / eq.cummax() - 1).min()), 4),
                turnover_per_year=round(float(turn), 1), fees_per_year=round(float(fee), 4),
                by_year={int(y): round(float(v), 4) for y, v in ((1 + r).groupby(r.index.year).prod() - 1).items()})


results, series = {}, {}
for cost_name, (b, s_) in {"indodax": (BUY, SELL), "flat_0.30": (0.003, 0.003)}.items():
    for name, (fn, band, every) in VARIANTS.items():
        r, t, f = run(fn, band, every, b, s_)
        results[f"{name}@{cost_name}"] = stats(r, t, f)
        if cost_name == "indodax":
            series[name] = r
        print(name, cost_name, {k: v for k, v in results[f"{name}@{cost_name}"].items() if k != "by_year"}, flush=True)
btc = RET["BTCUSDT"].iloc[:-1]
results["BTC_buy_hold"] = stats(btc, 0.0, 0.0)

# Deflated Sharpe, N = 36 (27 grid + 6 turnover-study variants already tried + 3 new)
summ = json.loads((PAPER / "research/results/summary.json").read_text())
turn = json.loads((PAPER / "research/results/turnover_study.json").read_text())["variants"]
prior = list(summ["grid_sharpe"].values()) + [v["sharpe"] for k, v in turn.items()
                                              if k.startswith("ML_") and k.endswith("cost0.0015")]
new = [results[f"{n}@indodax"]["sharpe"] for n in ("A_strict_entry", "B_every_3_days", "C_strict_wide_band")]
trial_sr = np.array(prior + new) / np.sqrt(BARS_PER_YEAR)
g = 0.5772156649


def dsr(r):
    sr, n, t = r.mean() / r.std(), len(trial_sr), len(r)
    sr0 = np.sqrt(np.var(trial_sr, ddof=1)) * ((1 - g) * norm.ppf(1 - 1 / n) + g * norm.ppf(1 - 1 / (n * np.e)))
    return float(norm.cdf((sr - sr0) * np.sqrt(t - 1) / np.sqrt(1 - r.skew() * sr + (r.kurt() + 2) / 4 * sr ** 2)))


base = results["ML_deployed@indodax"]
verdict = {}
for n in ("A_strict_entry", "B_every_3_days", "C_strict_wide_band"):
    v = results[f"{n}@indodax"]
    checks = {"CAGR>0": bool(v["CAGR"] > 0),
              "Sharpe>=deployed+0.10": bool(v["sharpe"] >= base["sharpe"] + 0.10),
              "MaxDD within 5pp of deployed": bool(v["max_dd"] >= base["max_dd"] - 0.05)}
    verdict[n] = {"pass": all(checks.values()), "checks": checks, "DSR_N36": round(dsr(series[n]), 3)}
# Post-hoc robustness (NOT part of the pre-registered decision): does B depend on which day the
# 3-day cycle starts? Reported for honesty; the decision above is unchanged by it.
robust = {}
for ph in (0, 1, 2):
    r, t, f = run(ml_fn(0.55, 0.50), 0.50, 3, BUY, SELL, phase=ph)
    robust[f"B_phase{ph}"] = {k: v for k, v in stats(r, t, f).items()}
for ph in (0, 1, 2):
    r, t, f = run(tsmom_fn, 0.50, 3, BUY, SELL, phase=ph)
    robust[f"TSMOM_every3d_phase{ph}"] = {k: v for k, v in stats(r, t, f).items() if k != "by_year"}
passing = [n for n in verdict if verdict[n]["pass"]]
chosen = max(passing, key=lambda n: results[f"{n}@indodax"]["sharpe"]) if passing else None
out = {"oos_period": [str(RET.index[0]), str(RET.index[-2])], "trials_N": len(trial_sr), "results": results,
       "verdict": verdict, "promoted_to_shadow": chosen,
       "DSR_N36_ML_deployed": round(dsr(series["ML_deployed"]), 3), "robustness_posthoc": robust}
(OUT / "fee_aware_study.json").write_text(json.dumps(out, indent=2))
print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))
