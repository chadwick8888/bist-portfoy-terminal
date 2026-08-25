import json, math, os, urllib.request, datetime, statistics

SYMS=["CVKMD","ALTINS1","ASTOR","KTLEV"]
# Yahoo Finance symbols for Borsa Istanbul.
TICKERS={s:s+".IS" for s in SYMS}
TICKERS["BIST100"]="XU100.IS"

def fetch(ticker):
    url=f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=1y&interval=1d&events=history"
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
    with urllib.request.urlopen(req,timeout=20) as r: j=json.loads(r.read())
    res=j["chart"]["result"][0]; q=res["indicators"]["quote"][0]
    ts=res["timestamp"]; bars=[]
    for i,t in enumerate(ts):
        c=q["close"][i]
        if c is not None: bars.append({"t":t,"open":q["open"][i],"high":q["high"][i],"low":q["low"][i],"close":c,"volume":q["volume"][i] or 0})
    return bars

def ema(a,n):
    if not a:return []
    k=2/(n+1); out=[a[0]]
    for x in a[1:]:out.append(x*k+out[-1]*(1-k))
    return out

def calc(bars,bist_mom=0):
    c=[float(x["close"]) for x in bars]; v=[float(x["volume"]) for x in bars]
    if len(c)<30:return {},{"buy":None,"hold":None,"sell":None,"decision":"VERİ YETERSİZ","reasons":["En az 30 günlük veri gerekli."]}
    def sma(n): return sum(c[-n:])/n if len(c)>=n else None
    d=[c[i]-c[i-1] for i in range(1,len(c))]
    g=[max(x,0) for x in d[-14:]]; l=[max(-x,0) for x in d[-14:]]
    ag=sum(g)/14; al=sum(l)/14; rsi=100 if al==0 else 100-100/(1+ag/al)
    e12,e26=ema(c,12),ema(c,26); mac=[a-b for a,b in zip(e12[-len(e26):],e26)]
    macd=mac[-1]; sig=ema(mac,9)[-1]
    avgv=sum(v[-20:])/20; vr=v[-1]/avgv if avgv else 1
    mom=(c[-1]/c[-21]-1)*100
    ind={"rsi":rsi,"sma20":sma(20),"sma50":sma(50),"sma200":sma(200),"macd":macd,"macd_signal":sig,"volume":v[-1],"volume_ratio":vr,"momentum20":mom}
    buy=hold=sell=0; reasons=[]
    trend=sum(c[-1]>z for z in [ind["sma20"],ind["sma50"],ind["sma200"]])
    buy+=trend/3*25; sell+=(1-trend/3)*25; reasons.append(("Trend","pozitif" if trend>=2 else "zayıf"))
    if 52<=rsi<=68: buy+=15; reasons.append(("RSI","pozitif bölge"))
    elif rsi>72: sell+=10; hold+=5; reasons.append(("RSI","aşırı alım riski"))
    elif rsi<35: buy+=5; hold+=10; reasons.append(("RSI","zayıf/tepki ihtimali"))
    else: hold+=12; reasons.append(("RSI","nötr"))
    if macd>sig:buy+=15;reasons.append(("MACD","pozitif"))
    else:sell+=10;hold+=5;reasons.append(("MACD","negatif"))
    if vr>=1.2:
        (buy if c[-1]>ind["sma20"] else sell); buy+=7 if c[-1]>ind["sma20"] else 0; sell+=3 if c[-1]<ind["sma20"] else 0
        reasons.append(("Hacim","ortalamanın üzerinde"))
    else:hold+=6;reasons.append(("Hacim","normal"))
    if mom>5:buy+=15
    elif mom>0:buy+=9;hold+=6
    elif mom<-5:sell+=15
    else:hold+=10
    if mom>bist_mom:buy+=10;reasons.append(("Relatif güç","BIST'ten güçlü"))
    else:hold+=6;sell+=4;reasons.append(("Relatif güç","BIST'ten zayıf"))
    if rsi>78 or rsi<25:sell+=6
    else:hold+=6
    total=buy+hold+sell
    vals=[round(x/total*100) for x in (buy,hold,sell)]
    # normalize rounding to 100
    vals[vals.index(max(vals))]+=100-sum(vals)
    b,h,s=vals; decision="AL" if b>=55 and b==max(vals) else ("SAT" if s>=55 and s==max(vals) else "BEKLE")
    return ind,{"buy":b,"hold":h,"sell":s,"decision":decision,"reasons":reasons}

def main():
    bist=fetch(TICKERS["BIST100"]); bc=[x["close"] for x in bist]; bm=(bc[-1]/bc[-21]-1)*100 if len(bc)>21 else 0
    out={"updated":datetime.datetime.now(datetime.timezone.utc).isoformat()}
    for s in SYMS:
        bars=fetch(TICKERS[s]); ind,sc=calc(bars,bm)
        last,prev=bars[-1],bars[-2]
        out[s]={"quote":{"close":last["close"],"previous_close":prev["close"],"change_pct":(last["close"]/prev["close"]-1)*100,"open":last["open"],"high":last["high"],"low":last["low"]},"indicators":ind,"score":sc}
    os.makedirs("data",exist_ok=True)
    with open("data/market.json","w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2)
if __name__=="__main__":main()
