import json, urllib.request, time, sys
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent":"Mozilla/5.0"}), timeout=30) as r: return json.load(r)
snap=json.load(open("snapshot.json"))
pairs=[p for p in snap["pairs"] if p["base_currency"]=="idr"]
now=int(time.time()); t0=1577836800  # 2020-01-01
out={}
for i,p in enumerate(pairs):
    sym=p["symbol"]
    for a in range(3):
        try:
            out[p["traded_currency"]]=get(f"https://indodax.com/tradingview/history_v2?symbol={sym}&tf=1D&from={t0}&to={now}"); break
        except Exception as e:
            time.sleep(3*(a+1))
    time.sleep(0.36)  # stay under 180 req/min
    if i%50==0: print(i, sym, len(out.get(p["traded_currency"],[])), flush=True)
json.dump(out,open("history_all.json","w"))
print("done", len(out))
