from flask import Flask, jsonify, render_template
import os, math, statistics, urllib.request, json

app=Flask(__name__)
SYMBOLS=["CVKMD","ALTINS1","ASTOR","KTLEV"]
# Optional upstream BIST service. Set BIST_API_URL and BIST_API_KEY on Render.
API_URL=os.getenv("BIST_API_URL","")
API_KEY=os.getenv("BIST_API_KEY","")

def get_json(url):
    req=urllib.request.Request(url,headers={"User-Agent":"BIST-Personal-Terminal/1.0"})
    if API_KEY: req.add_header("X-API-Key",API_KEY)
    with urllib.request.urlopen(req,timeout=12) as r:
        return json.loads(r.read().decode())

def fetch_quote(sym):
    if not API_URL:
        return {"symbol":sym,"available":False,"reason":"BIST_API_URL ayarlanmadı"}
    try:
        base=API_URL.rstrip("/")
        data=get_json(f"{base}/quote/{sym}")
        return {"symbol":sym,"available":True,**data}
    except Exception as e:
        return {"symbol":sym,"available":False,"reason":str(e)}

def fetch_history(sym):
    if not API_URL: return []
    try:
        base=API_URL.rstrip("/")
        data=get_json(f"{base}/history/{sym}?period=1y&interval=1d")
        return data.get("bars",[])
    except Exception:
        return []

def ema(vals,n):
    if not vals: return []
    k=2/(n+1); out=[vals[0]]
    for x in vals[1:]: out.append(x*k+out[-1]*(1-k))
    return out

def indicators(bars):
    closes=[float(b["close"]) for b in bars if b.get("close") is not None]
    vols=[float(b.get("volume") or 0) for b in bars]
    if len(closes)<30: return {}
    def sma(n): return sum(closes[-n:])/n if len(closes)>=n else None
    d=[closes[i]-closes[i-1] for i in range(1,len(closes))]
    gains=[max(x,0) for x in d][-14:]; losses=[max(-x,0) for x in d][-14:]
    ag=sum(gains)/14; al=sum(losses)/14
    rsi=100 if al==0 else 100-(100/(1+ag/al))
    e12=ema(closes,12); e26=ema(closes,26)
    macd=e12[-1]-e26[-1]
    signal=ema([a-b for a,b in zip(e12[-len(e26):],e26)],9)[-1]
    avgvol=sum(vols[-20:])/20 if len(vols)>=20 else None
    volratio=(vols[-1]/avgvol) if avgvol else None
    ret20=(closes[-1]/closes[-21]-1)*100 if len(closes)>21 else None
    return {"close":closes[-1],"previous_close":closes[-2],"rsi":rsi,
            "sma20":sma(20),"sma50":sma(50),"sma200":sma(200),
            "macd":macd,"macd_signal":signal,"volume":vols[-1],
            "volume_ratio":volratio,"momentum20":ret20}

def score(ind,bist_ret=None):
    if not ind: return {"buy":None,"hold":None,"sell":None,"decision":"VERİ YETERSİZ"}
    buy=hold=sell=0
    reasons=[]
    # Trend 25
    c=ind["close"]; s20=ind["sma20"]; s50=ind["sma50"]; s200=ind["sma200"]
    trend=sum([c>s20 if s20 else False,c>s50 if s50 else False,c>s200 if s200 else False])
    buy+=trend/3*25; sell+=(1-trend/3)*25
    reasons.append(("Trend", "pozitif" if trend>=2 else "zayıf"))
    # RSI 15
    r=ind["rsi"]
    if 52<=r<=68: buy+=15
    elif r<35: buy+=5; hold+=10
    elif r>72: sell+=10; hold+=5
    else: hold+=12
    # MACD 15
    if ind["macd"]>ind["macd_signal"]: buy+=15
    else: sell+=10; hold+=5
    # Volume 10
    vr=ind["volume_ratio"] or 1
    if vr>=1.2: buy+=7 if c>s20 else 0; sell+=3 if c<s20 else 0
    else: hold+=6
    # Momentum 15
    m=ind["momentum20"] or 0
    if m>5: buy+=15
    elif m>0: buy+=9; hold+=6
    elif m<-5: sell+=15
    else: hold+=10
    # Relative strength 10
    if bist_ret is not None and m>bist_ret: buy+=10
    else: hold+=6; sell+=4
    # risk 10
    if r>78 or r<25: sell+=6
    else: hold+=6
    total=buy+hold+sell
    if total<=0: return {"buy":0,"hold":100,"sell":0,"decision":"BEKLE","reasons":reasons}
    buy,hold,sell=[round(x/total*100) for x in (buy,hold,sell)]
    mx=max(buy,hold,sell)
    decision="AL" if mx==buy and buy>=55 else ("SAT" if mx==sell and sell>=55 else "BEKLE")
    return {"buy":buy,"hold":hold,"sell":sell,"decision":decision,"reasons":reasons}

@app.get("/")
def home(): return render_template("index.html")

@app.get("/api/portfolio")
def portfolio():
    raw={}
    for s in SYMBOLS:
        q=fetch_quote(s); h=fetch_history(s); ind=indicators(h)
        raw[s]={"quote":q,"indicators":ind,"score":score(ind)}
    return jsonify(raw)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","10000")))
