# companies/scoring.py
import pandas as pd
import pandas_ta as ta   # pip install pandas-ta

def band(score: float) -> str:
    if score < 25: return "Strong Avoid"
    if score < 50: return "Neutral / Avoid"
    if score < 75: return "Buy / Accumulate"
    return "Strong Buy"

def compute_master_score(prices_qs):
    df = pd.DataFrame(list(prices_qs.values("date", "open_price", "high_price",
                                            "low_price", "close_price", "volume"))).sort_values("date")
    if len(df) < 200:
        return None  # not enough history

    c = df["close_price"].astype(float)
    df["rsi"] = ta.rsi(c, 14)
    macd = ta.macd(c)
    df["macd"], df["macd_sig"] = macd.iloc[:, 0], macd.iloc[:, 2]
    df["sma50"], df["sma200"] = c.rolling(50).mean(), c.rolling(200).mean()
    df["vol_ratio"] = df["volume"] / df["volume"].rolling(20).mean()
    last = df.iloc[-1]

    trend = (100 if last.close_price > last.sma200 else 0) * .5 + (100 if last.sma50 > last.sma200 else 0) * .5
    parts = {
        "trend": trend,
        "momentum": float(last.rsi),
        "macd": 100 if last.macd > last.macd_sig else 0,
        "volume": min(float(last.vol_ratio) * 50, 100),
    }
    weights = {"trend": .35, "momentum": .25, "macd": .20, "volume": .20}
    score = round(sum(parts[k] * weights[k] for k in parts), 1)
    return {"score": score, "band": band(score), "components": parts, "date": last.date}