"""Indodax ETH/IDR momentum bot (time-series momentum, daily).

Rule: if ETH/IDR's close is higher than it was LOOKBACK_DAYS days ago, hold ETH;
otherwise hold rupiah. Runs once a day from GitHub Actions.

Safety:
- Python standard library only (no third-party packages to trust).
- Dry run unless the repo variable LIVE_TRADING is exactly "true".
- The API key should have view + trade permission only (never withdraw);
  this code never calls any withdraw method.
- One order per day at most; client_order_id makes a re-run on the same day
  get rejected by Indodax instead of trading twice.
- MAX_TRADE_IDR caps the size of any single order.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
from decimal import ROUND_DOWN, Decimal
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = "https://indodax.com"
PAIR = "eth_idr"        # private API pair name
PAIR_ID = "ethidr"      # public /api/pairs id
SYMBOL = "ETHIDR"       # OHLC symbol
COIN = "eth"
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) eth-momentum/1.0"  # UAs containing "bot" get HTTP 403

LOOKBACK_DAYS = int(os.environ.get("LOOKBACK_DAYS", "21"))
MAX_TRADE_IDR = int(os.environ.get("MAX_TRADE_IDR", "1000000"))  # safety cap per order
MAX_SPREAD = 0.01        # skip trading if bid/ask spread > 1%
BUY_BUFFER = 0.995       # spend 99.5% of free IDR, leaving room for fees/rounding
ALLOWED_METHODS = {"getInfo", "trade"}  # this bot never needs anything else


# ---------------------------------------------------------------- HTTP helpers
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


# ---------------------------------------------------------------- strategy
def completed_daily_closes(candles: list[dict], now_ts: int) -> list[tuple[int, float]]:
    """Keep only fully closed daily candles (drop today's, still-forming candle)."""
    today_start = now_ts - now_ts % 86400
    rows = sorted((int(c["Time"]), float(c["Close"])) for c in candles)
    return [(t, c) for t, c in rows if t < today_start]


def momentum_signal(closes: list[float], lookback: int) -> tuple[str, float]:
    """Return ('ETH' or 'IDR', lookback return)."""
    if len(closes) < lookback + 1:
        raise RuntimeError(f"need {lookback + 1} daily closes, got {len(closes)}")
    ret = closes[-1] / closes[-1 - lookback] - 1.0
    return ("ETH" if ret > 0 else "IDR"), ret


def decide(target: str, idr_free: float, eth_free: float, bid: float,
           min_idr: float, min_eth: float, max_trade_idr: int) -> dict | None:
    """Return the order to send, or None if nothing to do."""
    if target == "ETH":
        spend = math.floor(min(idr_free * BUY_BUFFER, max_trade_idr))
        if spend >= min_idr:
            return {"type": "buy", "order_type": "market", "idr": spend}
        return None
    # target == "IDR": sell ETH
    amount = min(Decimal(str(eth_free)), Decimal(str(max_trade_idr)) / Decimal(str(bid)))
    amount = amount.quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
    if amount >= Decimal(str(min_eth)) and float(amount) * bid >= min_idr:
        return {"type": "sell", "order_type": "market", COIN: f"{amount:f}"}
    return None


# ---------------------------------------------------------------- main
def log(msg: str) -> None:
    print(msg, flush=True)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(msg + "\n\n")


def main() -> int:
    live = os.environ.get("LIVE_TRADING", "").strip().lower() == "true"
    key = os.environ.get("INDODAX_API_KEY", "").strip()
    secret = os.environ.get("INDODAX_API_SECRET", "").strip()
    now = int(time.time())
    log(f"### Run {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC — mode: {'LIVE' if live else 'DRY RUN'}")

    # 1) Market checks
    pair = next(p for p in public("/api/pairs") if p["id"] == PAIR_ID)
    if pair.get("is_maintenance") or pair.get("is_market_suspended"):
        log("Pair is in maintenance/suspended. No trade.")
        return 0
    min_idr = float(pair["trade_min_base_currency"])
    min_eth = float(pair["trade_min_traded_currency"])

    t = public(f"/api/ticker/{PAIR_ID}")["ticker"]
    bid, ask = float(t["buy"]), float(t["sell"])
    spread = (ask - bid) / ask
    log(f"ETH/IDR bid {bid:,.0f} ask {ask:,.0f} (spread {spread:.3%})")

    # 2) Signal from completed daily candles
    candles = public(f"/tradingview/history_v2?symbol={SYMBOL}&tf=1D"
                     f"&from={now - (LOOKBACK_DAYS + 15) * 86400}&to={now}")
    daily = completed_daily_closes(candles, now)
    last_t = daily[-1][0]
    if now - last_t > 2 * 86400 + 3600:
        log(f"Latest daily candle is stale ({datetime.fromtimestamp(last_t, timezone.utc):%Y-%m-%d}). No trade.")
        return 1
    target, ret = momentum_signal([c for _, c in daily], LOOKBACK_DAYS)
    log(f"{LOOKBACK_DAYS}-day return {ret:+.2%} → target: **hold {target}**")

    if not key or not secret:
        log("No API key set — signal only. Add INDODAX_API_KEY / INDODAX_API_SECRET secrets to see balances.")
        return 0

    # 3) Balances
    info = private("getInfo", key, secret)
    bal = info["balance"]
    idr_free, eth_free = float(bal.get("idr", 0)), Decimal(str(bal.get(COIN, "0")))
    equity = idr_free + float(eth_free) * bid
    log(f"Free balance: Rp{idr_free:,.0f} + {eth_free:.8f} ETH ≈ Rp{equity:,.0f} total")
    if int(info.get("withdraw_status", 0)) == 1:
        log("Note: this account can withdraw. Make sure the API key itself has NO withdraw permission.")

    # 4) Decide
    order = decide(target, idr_free, eth_free, bid, min_idr, min_eth, MAX_TRADE_IDR)
    if order is None:
        log("Already positioned (or amount below Indodax minimum). No trade.")
        return 0
    if spread > MAX_SPREAD:
        log(f"Spread {spread:.2%} > {MAX_SPREAD:.0%}. Skipping trade today.")
        return 0
    order["client_order_id"] = f"tsmom-{datetime.now(timezone.utc):%Y%m%d}-{order['type']}"
    log(f"Order: `{order}`")

    if not live:
        log("DRY RUN — no order sent. Set repo variable LIVE_TRADING=true to trade.")
        return 0

    # 5) Execute
    res = private("trade", key, secret, pair=PAIR, **order)
    log(f"Order sent. Indodax response: `{res}`")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # fail loudly so GitHub emails you
        log(f"ERROR: {type(e).__name__}: {e}")
        sys.exit(1)
