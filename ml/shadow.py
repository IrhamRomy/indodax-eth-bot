"""ML sleeve: the LightGBM model from quant-paper-trial, applied to the live Indodax bot.

Uses exactly the paper trial's inputs and rules so the two can be compared:
- 4h USDT candles from Binance's public market-data host (the data the model was trained on),
  8 coins, features from ml/features.py (an unchanged copy of quantbot/features.py).
- Decision once a day on the 4h bar opening at 00:00 UTC.
- Long when P(up) > 0.55, stay long while P(up) > 0.50 (hysteresis), otherwise flat.
- Weight = 6% / annualised vol, max 25% per coin, max 100% total.

The hysteresis needs to know whether a coin was "on" yesterday. Instead of storing state,
it is replayed from the model's own decisions over the last ~2 months of daily bars, starting
flat. The replay forgets its starting point within days, so it is deterministic and stateless.

Only coins that trade on Indodax get a weight; the share the model would put into coins that
are too thin on Indodax (BNB, ADA, AVAX) stays in rupiah.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

from .features import BARS_PER_YEAR, FEATURES, panel_features

HERE = Path(__file__).resolve().parent
MODEL, META = HERE / "model.txt", HERE / "model_meta.json"
DATA_HOST = "https://data-api.binance.vision"
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"]
BAR = pd.Timedelta(hours=4)
DECISION_HOUR_UTC = 0
THR_IN, THR_OUT = 0.55, 0.50
RISK_PER_COIN, MAX_WEIGHT, MAX_GROSS = 0.06, 0.25, 1.0
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "trades", "taker_base", "taker_quote", "ignore"]


def load_model() -> lgb.Booster:
    meta = json.loads(META.read_text())
    if hashlib.sha256(MODEL.read_bytes()).hexdigest() != meta["sha256"]:
        raise RuntimeError("model file hash mismatch - refusing to run (possible tampering)")
    return lgb.Booster(model_file=str(MODEL))


def fetch(symbol: str, limit: int = 600) -> pd.DataFrame:
    url = f"{DATA_HOST}/api/v3/klines?" + urllib.parse.urlencode(
        {"symbol": symbol, "interval": "4h", "limit": limit})
    if not url.startswith(DATA_HOST + "/"):
        raise ValueError("refusing non-Binance-data URL")
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:  # nosec B310 - fixed https host above
                raw = json.load(r)
            if not isinstance(raw, list) or not raw or len(raw[0]) != 12:
                raise ValueError(f"unexpected response shape for {symbol}")
            df = pd.DataFrame(raw, columns=COLS)
            df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms", utc=True)
            df = df.drop(columns=["close_time", "ignore"]).set_index("open_time").astype(float).sort_index()
            df = df[df.index + BAR <= pd.Timestamp.now(tz="UTC")]  # closed bars only
            if df.index.has_duplicates or (df.index.to_series().diff().dropna() != BAR).any():
                raise ValueError(f"gaps/duplicates in {symbol} data")
            if (df[["open", "high", "low", "close"]] <= 0).any().any():
                raise ValueError(f"non-positive prices in {symbol}")
            return df
        except Exception as e:  # network or data problem: retry, then give up
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {symbol}: {last}")


def decide(panel: pd.DataFrame, model: lgb.Booster) -> dict:
    """Replay daily decisions with hysteresis; return the latest decision's details."""
    dec = panel[panel.time.dt.hour == DECISION_HOUR_UTC].dropna(subset=FEATURES)
    if dec.empty:
        raise RuntimeError("no decision bars with complete features")
    dec = dec.assign(prob=model.predict(dec[FEATURES]))
    on: dict[str, bool] = {}
    for t in sorted(dec.time.unique()):
        rows = dec[dec.time == t].set_index("symbol")
        on = {s: bool(s in rows.index and (rows.loc[s, "prob"] > THR_IN
                                           or (on.get(s, False) and rows.loc[s, "prob"] > THR_OUT)))
              for s in SYMBOLS}
    last_t = dec.time.max()
    rows = dec[dec.time == last_t].set_index("symbol")
    raw = {}
    for s in SYMBOLS:
        if s in rows.index and on[s]:
            ann = float(rows.loc[s, "sigma"]) * np.sqrt(BARS_PER_YEAR)
            raw[s] = min(RISK_PER_COIN / ann, MAX_WEIGHT) if ann > 0 else 0.0
        else:
            raw[s] = 0.0
    g = sum(raw.values())
    w = {s: x * (MAX_GROSS / g if g > MAX_GROSS else 1.0) for s, x in raw.items()}
    return {"decision_bar": last_t, "prob": rows["prob"].to_dict(), "on": on, "weights_usdt": w}


def ml_targets(coins: list[str]) -> dict:
    """Return {'targets': {coin: weight}, 'detail': ...} for the given Indodax coin codes."""
    model = load_model()
    frames = {s: fetch(s) for s in SYMBOLS}
    idx = frames["BTCUSDT"].index
    panel = panel_features({s: f.reindex(idx) for s, f in frames.items()})
    d = decide(panel, model)
    targets = {c: float(d["weights_usdt"].get(f"{c.upper()}USDT", 0.0)) for c in coins}
    return {"targets": targets, "detail": d}
