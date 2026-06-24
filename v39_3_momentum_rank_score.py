import pandas as pd
import yfinance as yf

signals = pd.read_csv("archive/v35_6_buy_execution_fix_stable/live_signals.csv")

rows = []

for _, row in signals.iterrows():
    if str(row["Signal"]).upper() != "STRONG BUY":
        continue

    ticker = row["Ticker"]
    price = float(row["Price"])
    sma50 = float(row["SMA50"])
    rsi = float(row["RSI"])
    base_score = float(row["Score"])

    try:
        data = yf.download(
            ticker,
            period="2mo",
            auto_adjust=False,
            progress=False,
        )

        if data.empty:
            continue

        if len(data.columns.names) > 1:
            data.columns = data.columns.droplevel(1)

        close = pd.to_numeric(data["Close"], errors="coerce").dropna()
        volume = pd.to_numeric(data["Volume"], errors="coerce").dropna()

        if len(close) < 21:
            continue

        current = float(close.iloc[-1])
        ret_1d = ((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) * 100
        ret_5d = ((close.iloc[-1] - close.iloc[-6]) / close.iloc[-6]) * 100
        ret_20d = ((close.iloc[-1] - close.iloc[-21]) / close.iloc[-21]) * 100

        avg_vol_20 = volume.tail(20).mean()
        vol_ratio = volume.iloc[-1] / avg_vol_20 if avg_vol_20 else 0

    except Exception:
        continue

    distance_sma_pct = ((price - sma50) / sma50) * 100 if sma50 else 0

    rsi_quality = 0
    if 52 <= rsi <= 60:
        rsi_quality = 20
    elif 48 <= rsi < 52:
        rsi_quality = 10
    elif 60 < rsi <= 65:
        rsi_quality = 10

    sma_quality = 0
    if 3 <= distance_sma_pct <= 8:
        sma_quality = 20
    elif 1 <= distance_sma_pct < 3:
        sma_quality = 10
    elif 8 < distance_sma_pct <= 12:
        sma_quality = 10

    momentum_quality = 0
    if ret_5d > 2:
        momentum_quality += 20
    elif ret_5d > 1:
        momentum_quality += 10

    if ret_20d > 5:
        momentum_quality += 20
    elif ret_20d > 2:
        momentum_quality += 10

    volume_quality = 0
    if vol_ratio > 1.5:
        volume_quality = 20
    elif vol_ratio > 1.0:
        volume_quality = 10

    rank_score = (
        base_score
        + rsi_quality
        + sma_quality
        + momentum_quality
        + volume_quality
    )

    rows.append({
        "Ticker": ticker,
        "Base_Score": int(base_score),
        "RSI": round(rsi, 2),
        "Dist_SMA50_%": round(distance_sma_pct, 2),
        "Ret_1D_%": round(ret_1d, 2),
        "Ret_5D_%": round(ret_5d, 2),
        "Ret_20D_%": round(ret_20d, 2),
        "Vol_Ratio": round(vol_ratio, 2),
        "RSI_Q": rsi_quality,
        "SMA_Q": sma_quality,
        "Momentum_Q": momentum_quality,
        "Volume_Q": volume_quality,
        "Rank_Score": round(rank_score, 2),
    })

out = pd.DataFrame(rows)
out = out.sort_values(
    ["Rank_Score", "Base_Score", "Ret_5D_%"],
    ascending=[False, False, False]
)

print("===== V39.3 MOMENTUM RANK SCORE =====")
print(out.to_string(index=False))

out.to_csv("momentum_rank_score.csv", index=False)
print("")
print("Saved: momentum_rank_score.csv")
