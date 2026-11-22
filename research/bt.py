import json, math
D=json.load(open("closes.json"))
COINS=["BTC","ETH","SOL","XRP","DOGE"]
days=sorted(set.intersection(*[set(map(int,D[c])) for c in COINS]))
start=int(1640995200)  # 2022-01-01
px={c:[D[c][str(t)] for t in days] for c in COINS}
idx0=next(i for i,t in enumerate(days) if t>=start)
COST=0.0032; LB=21

def vol(c,i,n=60):
    r=[math.log(px[c][k]/px[c][k-1]) for k in range(i-n+1,i+1)]
    m=sum(r)/n; return math.sqrt(sum((x-m)**2 for x in r)/(n-1))*math.sqrt(365)

def run(target_fn, band=0.5, lag=1, coins=COINS):
    eq=1.0; w={c:0.0 for c in coins}; curve=[]; turn=0
    for i in range(idx0, len(days)):
        # mark to market
        if i>idx0:
            g=sum(w[c]*(px[c][i]/px[c][i-1]-1) for c in coins)
            eq*=1+g
            tot=1+g
            for c in coins: w[c]=w[c]*(px[c][i]/px[c][i-1])/tot
        tgt=target_fn(i-lag+1 if lag else i)  # signal from close i-lag+... (lag=1: uses close i-1? see below)
        for c in coins:
            cur,t=w[c],tgt.get(c,0.0)
            if t==0 and cur>0: trade=cur
            elif t>0 and abs(t-cur)>band*t: trade=abs(t-cur)
            else: continue
            eq*=1-COST*trade; turn+=trade; w[c]=t
        curve.append(eq)
    return curve, turn

def eth_only(i):  return {"ETH":1.0 if px["ETH"][i-1]/px["ETH"][i-1-LB]>1 else 0.0}
def ew(i):        return {c:(1/len(COINS) if px[c][i-1]/px[c][i-1-LB]>1 else 0.0) for c in COINS}
def vt(i):
    t={c:(min(0.06/vol(c,i-1),0.25) if px[c][i-1]/px[c][i-1-LB]>1 else 0.0) for c in COINS}
    s=sum(t.values()); return {c:v/s for c,v in t.items()} if s>1 else t
def hold_btc(i):  return {"BTC":1.0}

def stats(name,curve,turn):
    n=len(curve); yrs=n/365
    cagr=curve[-1]**(1/yrs)-1
    peak=0; mdd=0
    for x in curve: peak=max(peak,x); mdd=min(mdd,x/peak-1)
    r=[curve[k]/curve[k-1]-1 for k in range(1,n)]; m=sum(r)/len(r); sd=math.sqrt(sum((x-m)**2 for x in r)/(len(r)-1))
    yr={}
    for k,t in enumerate(days[idx0:]):
        y=1970+t//31557600; yr.setdefault(int(y),[]).append(curve[k])
    ys=[]; prev=1.0
    for y in sorted(yr): ys.append(f"{y}:{yr[y][-1]/prev-1:+.0%}"); prev=yr[y][-1]
    print(f"{name:28s} CAGR {cagr:+6.1%}  Sharpe {m/sd*math.sqrt(365):5.2f}  MaxDD {mdd:6.1%}  turnover/yr {turn/yrs:5.1f}  | "+" ".join(ys))

print("Indodax IDR daily closes, 2022-01-01 →", __import__('datetime').datetime.utcfromtimestamp(days[-1]).date(), f"cost {COST:.2%}/trade, signal from yesterday's close")
stats("ETH-only TSMOM (current)",*run(eth_only,band=0))
stats("5-coin equal-weight TSMOM",*run(ew))
stats("5-coin vol-target (trial)",*run(vt))
stats("BTC buy & hold",*run(hold_btc,band=0))
eh=run(lambda i:{"ETH":1.0},band=0); stats("ETH buy & hold",*eh)
