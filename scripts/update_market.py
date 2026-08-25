import json
import math
from datetime import datetime, timezone

import borsapy as bp

TICKERS = ["CVKMD", "ALTINS1", "ASTOR", "KTLEV"]


def num(v):
    try:
        x = float(v)
        return None if not math.isfinite(x) else x
    except Exception:
        return None


def rsi(closes, period=14):
    if len(closes) <= period:
        return None
    gains, losses = [], []
    for a, b in zip(closes[-period-1:-1], closes[-period:]):
        d = b - a
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains) / period
    al = sum(losses) / period
    if al == 0:
        return 100.0
    return 100 - (100 / (1 + ag / al))


def ema(values, period):
    if len(values) < period:
        return []
    k = 2 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def sma(values, period):
    return sum(values[-period:]) / period if len(values) >= period else None


def indicators(df):
    closes = [num(x) for x in df["Close"].tolist() if num(x) is not None]
    volumes = [num(x) for x in df["Volume"].tolist()] if "Volume" in df else []
    e12 = ema(closes, 12)
    e26 = ema(closes, 26)
    macd_line = None
    signal = None
    hist = None
    if e12 and e26:
        # Align the two EMA series by their common tail.
        n = min(len(e12), len(e26))
        macds = [a - b for a, b in zip(e12[-n:], e26[-n:])]
        macd_line = macds[-1]
        sigs = ema(macds, 9)
        if sigs:
            signal = sigs[-1]
            hist = macd_line - signal

    avg_vol = sum(volumes[-20:]) / min(20, len(volumes)) if volumes else None
    vol_now = volumes[-1] if volumes else None

    return {
        "rsi14": rsi(closes),
        "sma20": sma(closes, 20),
        "sma50": sma(closes, 50),
        "sma200": sma(closes, 200),
        "macd": macd_line,
        "macd_signal": signal,
        "macd_hist": hist,
        "momentum20": ((closes[-1] / closes[-21]) - 1) * 100 if len(closes) > 21 else None,
        "volume": vol_now,
        "volume_vs_20d": (vol_now / avg_vol) if vol_now and avg_vol else None,
    }


def score(close, ind, day_change):
    # Transparent heuristic score, not a price prediction.
    points = 50.0
    reasons = []

    r = ind.get("rsi14")
    if r is not None:
        if r < 30:
            points += 10; reasons.append("RSI aşırı satım bölgesinde")
        elif r > 70:
            points -= 8; reasons.append("RSI aşırı alım bölgesinde")
        elif r >= 55:
            points += 5; reasons.append("RSI pozitif bölgede")

    s20, s50, s200 = ind.get("sma20"), ind.get("sma50"), ind.get("sma200")
    if s20 and close > s20:
        points += 5; reasons.append("Fiyat SMA20 üzerinde")
    else:
        points -= 4
    if s50 and close > s50:
        points += 5; reasons.append("Fiyat SMA50 üzerinde")
    else:
        points -= 4
    if s200 and close > s200:
        points += 7; reasons.append("Fiyat SMA200 üzerinde")
    else:
        points -= 7

    mh = ind.get("macd_hist")
    if mh is not None:
        if mh > 0:
            points += 7; reasons.append("MACD histogram pozitif")
        else:
            points -= 7; reasons.append("MACD histogram negatif")

    mom = ind.get("momentum20")
    if mom is not None:
        if mom > 5:
            points += 5
        elif mom < -5:
            points -= 5

    if day_change is not None:
        if day_change > 3:
            points += 2
        elif day_change < -3:
            points -= 2

    buy = max(0, min(100, points))
    sell = 100 - buy
    hold = 100 - abs(buy - 50) * 2
    hold = max(0, min(100, hold))

    if buy >= 65:
        decision = "AL"
    elif buy <= 35:
        decision = "SAT"
    else:
        decision = "BEKLE"

    return {
        "buy": round(buy, 1),
        "hold": round(hold, 1),
        "sell": round(sell, 1),
        "decision": decision,
        "reasons": reasons[:6],
    }


def fetch(symbol):
    t = bp.Ticker(symbol)
    info = getattr(t, "fast_info", {}) or {}
    df = t.history(period="1y", interval="1d")
    if df is None or len(df) < 30:
        raise RuntimeError(f"{symbol}: yeterli tarihsel veri alınamadı")

    last = num(df["Close"].iloc[-1])
    prev = num(df["Close"].iloc[-2])
    day_change = ((last / prev) - 1) * 100 if last and prev else None
    ind = indicators(df)

    return {
        "symbol": symbol,
        "quote": {
            "price": last,
            "previous_close": prev,
            "day_change_percent": day_change,
            "volume": ind["volume"],
            "market_cap": num(info.get("market_cap")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "indicators": ind,
        "score": score(last, ind, day_change),
    }


def main():
    result = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "borsapy / TradingView-İş Yatırım kaynakları",
        "delay_note": "Varsayılan BIST verisi yaklaşık 15 dk gecikmeli olabilir.",
        "stocks": {},
    }

    errors = {}
    for symbol in TICKERS:
        try:
            result["stocks"][symbol] = fetch(symbol)
        except Exception as exc:
            errors[symbol] = str(exc)

    result["errors"] = errors

    if not result["stocks"]:
        raise RuntimeError(f"Hiçbir hisse verisi alınamadı: {errors}")

    with open("data/market.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
