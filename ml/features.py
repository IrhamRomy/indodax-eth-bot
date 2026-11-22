"""Feature engineering and triple-barrier labels.

Shared by research and the live paper bot so both use the exact same code path.

References
- Gu, Kelly & Xiu (2020), Review of Financial Studies 33(5): momentum, liquidity and
  volatility are the dominant predictive signals.
- Moskowitz, Ooi & Pedersen (2012), Journal of Financial Economics 104(2): time-series momentum.
- López de Prado (2018), Advances in Financial Machine Learning, ch. 3: triple-barrier labels.
"""
import numpy as np
import pandas as pd

BARS_PER_YEAR = 6 * 365          # 4h bars
MOM_WINDOWS = [1, 6, 18, 42, 126]  # 4h, 1d, 3d, 7d, 21d
VOL_WIN = 42                     # 7 days
LONG_WIN = 126                   # 21 days
WARMUP = LONG_WIN + 10

FEATURES = (
    [f"ret_{w}" for w in MOM_WINDOWS]
    + [f"zret_{w}" for w in MOM_WINDOWS[1:]]
    + ["vol_42", "vol_ratio", "range_18", "dist_sma", "volu_z", "xs_rank_42", "mkt_ret_42", "mkt_vol_42"]
)


def coin_features(df: pd.DataFrame) -> pd.DataFrame:
    """Per-coin features using only data up to and including each bar's close."""
    c = df["close"]
    lr = np.log(c).diff()
    out = pd.DataFrame(index=df.index)
    vol = lr.rolling(VOL_WIN).std()
    for w in MOM_WINDOWS:
        r = np.log(c / c.shift(w))
        out[f"ret_{w}"] = r
        if w > 1:
            out[f"zret_{w}"] = r / (vol * np.sqrt(w))
    out["vol_42"] = vol * np.sqrt(BARS_PER_YEAR)
    out["vol_ratio"] = vol / lr.rolling(LONG_WIN).std()
    out["range_18"] = ((df["high"] - df["low"]) / c).rolling(18).mean()
    out["dist_sma"] = c / c.rolling(LONG_WIN).mean() - 1
    lv = np.log(df["quote_volume"].clip(lower=1))
    out["volu_z"] = (lv - lv.rolling(LONG_WIN).mean()) / lv.rolling(LONG_WIN).std()
    out["sigma"] = vol  # per-bar vol, used for barriers and sizing (not a model feature)
    out["lr_next"] = lr.shift(-1)  # realised next-bar return (research only, never a feature)
    return out


def panel_features(frames: dict[str, pd.DataFrame], market: str = "BTCUSDT") -> pd.DataFrame:
    """Stack per-coin features and add cross-sectional / market features."""
    feats = {s: coin_features(f) for s, f in frames.items()}
    r42 = pd.DataFrame({s: f["ret_42"] for s, f in feats.items()})
    ranks = r42.rank(axis=1, pct=True)
    rows = []
    for s, f in feats.items():
        f = f.copy()
        f["xs_rank_42"] = ranks[s]
        f["mkt_ret_42"] = feats[market]["ret_42"]
        f["mkt_vol_42"] = feats[market]["vol_42"]
        f["symbol"] = s
        rows.append(f.iloc[WARMUP:])
    return pd.concat(rows).reset_index().rename(columns={"index": "time", "open_time": "time"})


def triple_barrier(close: pd.Series, sigma: pd.Series, horizon: int, k: float) -> pd.DataFrame:
    """Label 1 if the upper barrier (+k*sigma*sqrt(h)) is hit before the lower one or, if neither,
    the return at the vertical barrier is positive. Returns label and event end index t1."""
    c = close.to_numpy()
    s = sigma.to_numpy()
    n = len(c)
    y = np.full(n, np.nan)
    t1 = np.full(n, np.nan)
    width = k * s * np.sqrt(horizon)
    logc = np.log(c)
    for i in range(n - horizon):
        if not np.isfinite(width[i]):
            continue
        path = logc[i + 1:i + 1 + horizon] - logc[i]
        up = np.nonzero(path >= width[i])[0]
        dn = np.nonzero(path <= -width[i])[0]
        fu = up[0] if len(up) else horizon
        fd = dn[0] if len(dn) else horizon
        if fu < fd:
            y[i], t1[i] = 1, i + 1 + fu
        elif fd < fu:
            y[i], t1[i] = 0, i + 1 + fd
        else:
            y[i], t1[i] = float(path[-1] > 0), i + horizon
    return pd.DataFrame({"y": y, "t1_pos": t1}, index=close.index)
