"""Indodax multi-coin momentum bot (time-series momentum, vol-targeted, daily).

Same rule as the quant-paper-trial TSMOM strategy:
- For each coin: if its IDR price is higher than LOOKBACK_DAYS days ago, hold it;
  otherwise hold rupiah.
- Position size = TARGET_VOL / coin's annual volatility (60-day), max MAX_WEIGHT
  per coin, max 100% invested in total. The rest stays in rupiah.
- 50% no-trade band: only adjust a coin when its weight is off target by more
  than half the target (saves fees). Exits (target 0) always execute.

Safety:
- Python standard library only (no third-party packages to trust).
- Dry run unless the repo variable LIVE_TRADING is exactly "true".
- Only calls getInfo and trade; withdraw and anything else is refused in code.
- Only talks to https://indodax.com.
- At most one order per coin per side per day (client_order_id), so a re-run
  the same day can't trade twice.
- MAX_TRADE_IDR caps each single order. Coins outside COINS are never touched.

ML sleeve (ml/shadow.py, the LightGBM model from quant-paper-trial):
- ML_WEIGHT = 0 (default): shadow mode. The ML signal is computed and logged with the
  orders it *would* place (ML alone and a 50:50 blend), but only TSMOM trades.
  If the ML part fails, it is logged and TSMOM trades normally.
- ML_WEIGHT > 0: final target per coin = (1 - ML_WEIGHT) * TSMOM + ML_WEIGHT * ML.
  If the ML part fails, NO trades are placed that day.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import ROUND_DOWN, Decimal

BASE = "https://indodax.com"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) momentum-trader/2.0"  # UAs containing "bot" get HTTP 403

COINS = [c.strip().lower() for c in os.environ.get("COINS", "btc,eth,sol,xrp,doge").split(",") if c.strip()]
LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "21"))
VOL_DAYS = 60
TARGET_VOL = float(os.environ.get("TARGET_VOL", "0.06"))     # per-coin annual vol budget
MAX_WEIGHT = float(os.environ.get("MAX_WEIGHT", "0.25"))     # max share of equity per coin
BAND = 0.5                                                   # no-trade band (fraction of target)
MAX_TRADE_IDR = int(os.environ.get("MAX_TRADE_IDR", "1000000"))
ML_WEIGHT = float(os.environ.get("ML_WEIGHT", "0") or 0)  # 0 = ML in shadow mode (logged, never traded)
if not 0.0 <= ML_WEIGHT <= 1.0:
    raise SystemExit(f"ML_WEIGHT must be between 0 and 1, got {ML_WEIGHT}")
MAX_SPREAD = 0.01
BUY_BUFFER = 0.995
ALLOWED_METHODS = {"getInfo", "trade"}
RECORD: dict = {}  # machine-readable summary, printed as one "RESULT_JSON {...}" line at the end


# ---------------------------------------------------------------- HTTP
def _http(url: str, data: bytes | None = None, headers: dict | None = None) -> object:
    if not url.startswith(BASE + "/"):
        raise ValueError(f"refusing to call non-Indodax URL: {url}")
    h = {"User-Agent": USER_AGENT}
    h.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=h, method="POST" if data else "GET")
    with urllib.request.urlopen(req, timeout=20) as r:  # nosec B310 - https://indodax.com only (checked above)
        return json.load(r)


def public(path: str) -> object:
    return _http(BASE + path)


def sign(secret: str, body: str) -> str:
    """HMAC-SHA512 of the url-encoded request body, hex (Indodax 'Sign' header)."""
    return hmac.new(secret.encode(), body.encode(), hashlib.sha512).hexdigest()


def private(method: str, key: str, secret: str, **params) -> dict:
    if method not in ALLOWED_METHODS:
        raise ValueError(f"method {method!r} is not allowed in this bot")
    params = {"method": method, "timestamp": int(time.time() * 1000), "recvWindow": 10000, **params}
    body = urllib.parse.urlencode(params)
    res = _http(BASE + "/tapi", data=body.encode(),
                headers={"Key": key, "Sign": sign(secret, body),
                         "Content-Type": "application/x-www-form-urlencoded"})
    if not isinstance(res, dict) or res.get("success") != 1:
        raise RuntimeError(f"Indodax {method} failed: {res}")
    return res["return"]


# ---------------------------------------------------------------- strategy (pure functions)
def completed_daily_closes(candles: list[dict], now_ts: int) -> list[tuple[int, float]]:
    """Keep only fully closed daily candles (drop today's, still-forming candle)."""
    today_start = now_ts - now_ts % 86400
    rows = sorted((int(c["Time"]), float(c["Close"])) for c in candles)
    return [(t, c) for t, c in rows if t < today_start]


def momentum(closes: list[float], lookback: int) -> float:
    if len(closes) < lookback + 1:
        raise RuntimeError(f"need {lookback + 1} daily closes, got {len(closes)}")
    return closes[-1] / closes[-1 - lookback] - 1.0


def annual_vol(closes: list[float], days: int = VOL_DAYS) -> float:
    if len(closes) < days + 1:
        raise RuntimeError(f"need {days + 1} daily closes for volatility, got {len(closes)}")
    r = [math.log(closes[k] / closes[k - 1]) for k in range(len(closes) - days, len(closes))]
    m = sum(r) / days
    return math.sqrt(sum((x - m) ** 2 for x in r) / (days - 1)) * math.sqrt(365)


def target_weights(signals: dict[str, tuple[float, float]], target_vol: float = TARGET_VOL,
                   max_weight: float = MAX_WEIGHT) -> dict[str, float]:
    """signals: coin -> (momentum return, annual vol). Returns coin -> target weight."""
    w = {c: (min(target_vol / v, max_weight) if r > 0 and v > 0 else 0.0) for c, (r, v) in signals.items()}
    total = sum(w.values())
    return {c: x / total for c, x in w.items()} if total > 1 else w


def plan_orders(targets: dict[str, float], holdings: dict[str, Decimal], bids: dict[str, float],
                idr_free: float, mins: dict[str, tuple[float, float]],
                band: float = BAND, max_trade_idr: int = MAX_TRADE_IDR) -> tuple[list[dict], list[dict]]:
    """Return (sell_orders, buy_wishes). Buy wishes carry 'want_idr' and are sized later from real IDR."""
    equity = idr_free + sum(float(holdings.get(c, 0)) * bids[c] for c in bids)
    sells, buys = [], []
    if equity <= 0:
        return sells, buys
    for c, t in targets.items():
        if c not in bids:
            continue
        held = holdings.get(c, Decimal(0))
        cur = float(held) * bids[c] / equity
        min_idr, min_coin = mins[c]
        if (t == 0 and cur > 0) or (t > 0 and cur - t > band * t):
            amount = held if t == 0 else Decimal(str((cur - t) * equity / bids[c]))
            amount = min(amount, held, Decimal(str(max_trade_idr)) / Decimal(str(bids[c])))
            amount = amount.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            if amount >= Decimal(str(min_coin)) and float(amount) * bids[c] >= min_idr:
                sells.append({"coin": c, "type": "sell", "order_type": "market", c: f"{amount:f}"})
        elif t > 0 and t - cur > band * t:
            want = min((t - cur) * equity, max_trade_idr)
            if want >= min_idr:
                buys.append({"coin": c, "want_idr": want, "min_idr": min_idr})
    return sells, buys


def size_buys(buys: list[dict], idr_free: float) -> list[dict]:
    """Turn buy wishes into market orders that fit the rupiah actually available."""
    budget = idr_free * BUY_BUFFER
    total = sum(b["want_idr"] for b in buys)
    scale = min(1.0, budget / total) if total > 0 else 0.0
    out = []
    for b in buys:
        idr = math.floor(b["want_idr"] * scale)
        if idr >= b["min_idr"]:
            out.append({"coin": b["coin"], "type": "buy", "order_type": "market", "idr": idr})
    return out


# ---------------------------------------------------------------- main
def log(msg: str) -> None:
    print(msg, flush=True)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(msg + "\n\n")


def balances(key: str, secret: str) -> tuple[float, dict[str, Decimal]]:
    bal = private("getInfo", key, secret)["balance"]
    return float(bal.get("idr", 0)), {c: Decimal(str(bal.get(c, "0"))) for c in COINS}


def send(order: dict, key: str, secret: str, live: bool, day: str) -> None:
    order = dict(order)
    coin = order.pop("coin")
    order["client_order_id"] = f"tsmom-{day}-{coin}-{order['type']}"
    log(f"- {order['type'].upper()} {coin.upper()}: `{order}`")
    if live:
        res = private("trade", key, secret, pair=f"{coin}_idr", **order)
        RECORD.setdefault("orders_sent", []).append({"coin": coin, **order, "response": res})
        log(f"  → sent, Indodax response: `{res}`")


def blend(a: dict[str, float], b: dict[str, float], wb: float) -> dict[str, float]:
    """(1 - wb) * a + wb * b, per coin."""
    return {c: (1 - wb) * a.get(c, 0.0) + wb * b.get(c, 0.0) for c in set(a) | set(b)}


def fmt_weights(t: dict[str, float]) -> str:
    return ", ".join(f"{c.upper()} {t.get(c, 0.0):.0%}" for c in COINS) + f" | rupiah {1 - sum(t.values()):.0%}"


ML_DETAIL: dict = {}


def ml_part(coins: list[str]) -> tuple[dict[str, float] | None, str]:
    """Run the ML sleeve. Returns (targets or None, markdown log)."""
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:  # python -I leaves the script folder off sys.path
            sys.path.insert(0, here)
        from ml.shadow import ml_targets  # heavy deps (lightgbm/pandas) only loaded here
        r = ml_targets(coins)
    except Exception as e:
        return None, f"ML signal unavailable: {type(e).__name__}: {e}"
    d = r["detail"]
    ML_DETAIL.update(decision_bar=str(d["decision_bar"]),
                     prob={k: float(v) for k, v in d["prob"].items()}, on={k: bool(v) for k, v in d["on"].items()})
    rows = [f"ML decision bar {d['decision_bar']:%Y-%m-%d %H:%M} UTC (Binance 4h data)",
            "", "| Coin | P(up) | ML says | ML weight |", "|---|---|---|---|"]
    for s in sorted(d["prob"]):
        c = s.replace("USDT", "").lower()
        note = "" if c in coins else " (not in bot coin list → stays rupiah)"
        rows.append(f"| {c.upper()} | {d['prob'][s]:.3f} | {'long' if d['on'][s] else 'flat'} | "
                    f"{d['weights_usdt'][s]:.0%}{note} |")
    return r["targets"], "\n".join(rows)


def describe(orders: list[dict], bids: dict[str, float]) -> str:
    parts = []
    for o in orders:
        c = o["coin"]
        idr = o["idr"] if o["type"] == "buy" else float(o[c]) * bids[c]
        parts.append(f"{o['type']} {c.upper()} ≈Rp{idr:,.0f}")
    return ", ".join(parts) or "no orders"


def main() -> int:
    live = os.environ.get("LIVE_TRADING", "").strip().lower() == "true"
    key = os.environ.get("INDODAX_API_KEY", "").strip()
    secret = os.environ.get("INDODAX_API_SECRET", "").strip()
    now = int(time.time())
    day = datetime.now(timezone.utc).strftime("%Y%m%d")
    log(f"### Run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC — mode: {'LIVE' if live else 'DRY RUN'}")
    RECORD.update(time=datetime.now(timezone.utc).isoformat(timespec="seconds"), live=live,
                  ml_weight=ML_WEIGHT, coins={}, orders_sent=[])

    pairs = {p["id"]: p for p in public("/api/pairs")}
    tickers = public("/api/summaries")["tickers"]

    signals, bids, mins = {}, {}, {}
    rows = ["| Coin | Price (bid) | 21d return | Vol (yr) | Status |", "|---|---|---|---|---|"]
    for c in COINS:
        p, t = pairs.get(f"{c}idr"), tickers.get(f"{c}_idr")
        if not p or not t:
            rows.append(f"| {c.upper()} | – | – | – | not listed, skipped |")
            continue
        bid, ask = float(t["buy"]), float(t["sell"])
        spread = (ask - bid) / ask if ask else 1.0
        candles = public(f"/tradingview/history_v2?symbol={c.upper()}IDR&tf=1D"
                         f"&from={now - (VOL_DAYS + 30) * 86400}&to={now}")
        daily = completed_daily_closes(candles, now)
        problem = None
        if p.get("is_maintenance") or p.get("is_market_suspended"):
            problem = "maintenance"
        elif spread > MAX_SPREAD:
            problem = f"spread {spread:.2%} too wide"
        elif not daily or now - daily[-1][0] > 2 * 86400 + 3600:
            problem = "stale price data"
        closes = [x for _, x in daily]
        try:
            r, v = momentum(closes, LOOKBACK_DAYS), annual_vol(closes)
        except RuntimeError as e:
            problem, r, v = problem or str(e), float("nan"), float("nan")
        rows.append(f"| {c.upper()} | {bid:,.0f} | {r:+.1%} | {v:.0%} | {problem or 'ok'} |")
        RECORD["coins"][c] = {"bid": bid, "ask": ask, "ret21": r, "vol": v, "status": problem or "ok",
                              "min_idr": float(p["trade_min_base_currency"]),
                              "min_coin": float(p["trade_min_traded_currency"])}
        if problem:
            continue  # leave this coin untouched today
        signals[c], bids[c] = (r, v), bid
        mins[c] = (float(p["trade_min_base_currency"]), float(p["trade_min_traded_currency"]))
    log("\n".join(rows))

    tsmom = target_weights(signals)
    log("TSMOM target: " + fmt_weights(tsmom))

    ml, ml_log = ml_part(list(bids))
    RECORD.update(tsmom_target=tsmom, ml_target=ml, ml_detail=ML_DETAIL or None,
                  ml_error=None if ml is not None else ml_log)
    log(f"#### ML sleeve — {'SHADOW (not traded)' if ML_WEIGHT == 0 else f'LIVE, weight {ML_WEIGHT:.0%}'}")
    log(ml_log)
    if ml is None and ML_WEIGHT > 0:
        log("ML is part of live trading but failed today → no trades placed.")
        return 1
    if ml is not None:
        log("ML target: " + fmt_weights(ml))
    targets = blend(tsmom, ml, ML_WEIGHT) if (ml is not None and ML_WEIGHT > 0) else tsmom
    log("**Trading target:** " + fmt_weights(targets))
    RECORD["trading_target"] = targets

    if not key or not secret:
        log("No API key set — signals only.")
        return 0

    idr_free, holdings = balances(key, secret)
    equity = idr_free + sum(float(holdings[c]) * bids[c] for c in bids)
    held = ", ".join(f"{float(holdings[c]):.8g} {c.upper()}" for c in COINS if holdings[c] > 0) or "no coins"
    log(f"Equity managed by bot ≈ Rp{equity:,.0f} (free rupiah Rp{idr_free:,.0f} + {held})")
    RECORD.update(equity=equity, idr_free=idr_free, holdings={c: str(q) for c, q in holdings.items() if q > 0})

    if ml is not None and ML_WEIGHT == 0:
        for name, t in (("ML alone", ml), ("50:50 TSMOM+ML", blend(tsmom, ml, 0.5))):
            s_, b_ = plan_orders(t, holdings, bids, idr_free, mins)
            freed = sum(float(o[o["coin"]]) * bids[o["coin"]] for o in s_)
            would = s_ + size_buys(b_, idr_free + freed)
            RECORD.setdefault("shadow_orders", {})[name] = would
            log(f"Shadow — {name} would place: {describe(would, bids)}")

    sells, buys = plan_orders(targets, holdings, bids, idr_free, mins)
    if not sells and not buys:
        log("Within the no-trade band (or below Indodax minimums). No trade today.")
        return 0

    if not live:
        sell_idr = sum(float(o[o["coin"]]) * bids[o["coin"]] for o in sells)
        log("Planned orders (DRY RUN — nothing sent):")
        for o in sells + size_buys(buys, idr_free + sell_idr):
            send(o, key, secret, False, day)
        log("Set repo variable LIVE_TRADING=true to trade.")
        return 0

    log("Orders:")
    for o in sells:
        send(o, key, secret, True, day)
    if buys:
        if sells:
            time.sleep(3)
        idr_free, _ = balances(key, secret)  # real rupiah after the sells
        for o in size_buys(buys, idr_free):
            send(o, key, secret, True, day)
    return 0


def print_record(code: int, error: str | None = None) -> None:
    RECORD.update(exit_code=code, error=error)
    print("RESULT_JSON " + json.dumps(RECORD, default=str, sort_keys=True), flush=True)


if __name__ == "__main__":
    try:
        rc = main()
        print_record(rc)
        sys.exit(rc)
    except Exception as e:  # fail loudly so GitHub emails you
        log(f"ERROR: {type(e).__name__}: {e}")
        print_record(1, f"{type(e).__name__}: {e}")
        sys.exit(1)
