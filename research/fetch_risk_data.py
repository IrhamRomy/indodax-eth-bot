"""Fetch daily closes for the risk-controls study (stdlib only).
Usage: python -I research/fetch_risk_data.py <out_dir>
Writes <out_dir>/indodax_5.json (history_v2 candles) and <out_dir>/binance_8_daily.json (klines 1d)."""
import json
import sys
import time
import urllib.request
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) momentum-trader/2.0"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return json.load(r)


now = int(time.time())
start = int(time.mktime((2017, 1, 1, 0, 0, 0, 0, 0, 0)))
ind = {}
for c in ["btc", "eth", "sol", "xrp", "doge"]:
    ind[c] = get(f"https://indodax.com/tradingview/history_v2?symbol={c.upper()}IDR&tf=1D&from={start}&to={now}")
    print("indodax", c, len(ind[c]), file=sys.stderr)
    time.sleep(0.5)
(OUT / "indodax_5.json").write_text(json.dumps(ind))

bn = {}
for s in ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX"]:
    rows, t = [], start * 1000
    while True:
        k = get(f"https://data-api.binance.vision/api/v3/klines?symbol={s}USDT&interval=1d&startTime={t}&limit=1000")
        if not k:
            break
        rows += k
        t = k[-1][0] + 86400000
        if len(k) < 1000:
            break
        time.sleep(0.3)
    bn[s + "USDT"] = rows
    print("binance", s, len(rows), file=sys.stderr)
(OUT / "binance_8_daily.json").write_text(json.dumps(bn))
