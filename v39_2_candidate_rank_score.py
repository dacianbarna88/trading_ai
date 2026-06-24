import pandas as pd

signals = pd.read_csv("archive/v35_6_buy_execution_fix_stable/live_signals.csv")

rows = []

for _, row in signals.iterrows():
    if str(row["Signal"]).upper() != "STRONG BUY":
        continue

    price = float(row["Price"])
    sma50 = float(row["SMA50"])
    rsi = float(row["RSI"])
    score = float(row["Score"])

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

    rank_score = score + rsi_quality + sma_quality

    rows.append({
        "Ticker": row["Ticker"],
        "Base_Score": int(score),
        "RSI": round(rsi, 2),
        "Distance_SMA50_%": round(distance_sma_pct, 2),
        "RSI_Quality": rsi_quality,
        "SMA_Quality": sma_quality,
        "Rank_Score": round(rank_score, 2),
    })

out = pd.DataFrame(rows)
out = out.sort_values(
    ["Rank_Score", "Base_Score"],
    ascending=[False, False]
)

print("===== V39.2 CANDIDATE RANK SCORE =====")
print(out.to_string(index=False))

out.to_csv("candidate_rank_score.csv", index=False)
print("")
print("Saved: candidate_rank_score.csv")
