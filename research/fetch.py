import json, urllib.request, time, sys
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"}), timeout=30) as r: return json.load(r)
out={}
now=int(time.time())
for c in ["BTC","ETH","SOL","XRP","DOGE","BNB","ADA","AVAX"]:
    rows={}
    start=int(time.mktime((2021,6,1,0,0,0,0,0,0)))
    t=start
    while t<now:
        end=min(t+300*86400,now)
        for x in get(f"https://indodax.com/tradingview/history_v2?symbol={c}IDR&tf=1D&from={t}&to={end}"):
            rows[int(x["Time"])]=float(x["Close"])
        t=end; time.sleep(0.4)
    out[c]=rows; print(c,len(rows),min(rows) if rows else None, file=sys.stderr)
json.dump(out,open("closes.json","w"))  # run from research/; closes.json is git-ignored
