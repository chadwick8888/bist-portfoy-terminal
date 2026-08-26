import json
import math
from datetime import datetime, timezone

import borsapy as bp

TICKERS = {
    "CVKMD": "CVKMD",
    "ALTINS1": "ALTIN",
    "ASTOR": "ASTOR",
    "KTLEV": "KTLEV",
}


def num(v):
    try:
        x = float(v)
        return None if not math.isfinite(x) else x
    except Exception:
        return None


def attr(obj, *names):
    if obj is None:
        return None
    for name in names:
        try:
            value = getattr(obj, name)
            if value is not None:
                return value
        except Exception:
            pass
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
    volumes = [num(x) for x in df["Volume"].tolist() if num(x) is not None] if "Volume" in df else []

    e12, e26 = ema(closes, 12), ema(closes, 26)
    macd_line = signal = hist = None
    if e12 and e26:
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
        "volume_vs_20d": (vol_now / avg_vol) if vol_now is not None and avg_vol else None,
    }


def score(close, ind, day_change):
    points = 50.0
    reasons = []

    r = ind.get("rsi14")
    if r is not None:
        if r < 30:
            points += 10
            reasons.append("RSI aşırı satım bölgesinde")
        elif r > 70:
            points -= 8
            reasons.append("RSI aşırı alım bölgesinde")
        elif r >= 55:
            points += 5
            reasons.append("RSI pozitif bölgede")

    for key, bonus, label in [
        ("sma20", 5, "Fiyat SMA20 üzerinde"),
        ("sma50", 5, "Fiyat SMA50 üzerinde"),
        ("sma200", 7, "Fiyat SMA200 üzerinde"),
    ]:
        value = ind.get(key)
        if value is not None:
            if close > value:
                points += bonus
                reasons.append(label)
            else:
                points -= 4 if key != "sma200" else 7

    mh = ind.get("macd_hist")
    if mh is not None:
        if mh > 0:
            points += 7
            reasons.append("MACD histogram pozitif")
        else:
            points -= 7
            reasons.append("MACD histogram negatif")

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
    hold = max(0, min(100, 100 - abs(buy - 50) * 2))
    decision = "AL" if buy >= 65 else "SAT" if buy <= 35 else "BEKLE"

    return {
        "buy": round(buy, 1),
        "hold": round(hold, 1),
        "sell": round(sell, 1),
        "decision": decision,
        "reasons": reasons[:6],
    }


def history_rows(df):
    rows = []
    # Keep up to 5 years of daily history for multiple chart ranges.
    for idx, row in df.tail(260).iterrows():
        close = num(row.get("Close"))
        if close is None:
            continue

        def row_num(name):
            try:
                return num(row.get(name))
            except Exception:
                return None

        date_value = str(idx)
        if " " in date_value:
            date_value = date_value.split(" ")[0]

        rows.append({
            "date": date_value[:10],
            "open": row_num("Open"),
            "high": row_num("High"),
            "low": row_num("Low"),
            "close": close,
            "volume": row_num("Volume"),
        })
    return rows


def fetch(display_symbol, provider_symbol):
    ticker = bp.Ticker(provider_symbol)
    info = getattr(ticker, "fast_info", None)

    df = ticker.history(period="5y", interval="1d")
    if df is None or len(df) < 30:
        raise RuntimeError(f"{display_symbol}: yeterli tarihsel veri alınamadı")

    last = num(df["Close"].iloc[-1])
    prev = num(df["Close"].iloc[-2])
    if last is None:
        raise RuntimeError(f"{display_symbol}: son fiyat alınamadı")

    day_change = ((last / prev) - 1) * 100 if prev not in (None, 0) else None
    ind = indicators(df)

    return {
        "symbol": display_symbol,
        "provider_symbol": provider_symbol,
        "quote": {
            "price": last,
            "previous_close": prev,
            "day_change_percent": day_change,
            "volume": ind["volume"],
            "market_cap": num(attr(info, "market_cap")),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "indicators": ind,
        "score": score(last, ind, day_change),
        "history": history_rows(df),
    }


def main():
    result = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "source": "borsapy / TradingView-İş Yatırım kaynakları",
        "delay_note": "BIST verisi sağlayıcıya göre gecikmeli olabilir.",
        "stocks": {},
        "errors": {},
    }

    for display_symbol, provider_symbol in TICKERS.items():
        try:
            result["stocks"][display_symbol] = fetch(display_symbol, provider_symbol)
            print(f"OK: {display_symbol} <- {provider_symbol}")
        except Exception as exc:
            result["errors"][display_symbol] = str(exc)
            print(f"ERROR: {display_symbol} <- {provider_symbol}: {exc}")

    if not result["stocks"]:
        raise RuntimeError(f"Hiçbir hisse verisi alınamadı: {result['errors']}")

    with open("data/market.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(json.dumps({
        "updated": result["updated"],
        "stocks": list(result["stocks"].keys()),
        "errors": result["errors"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
