from pathlib import Path
import pandas as pd

def main():

    df = pd.read_csv("global_candidates.csv")

    ranking = []

    for _, row in df.iterrows():

        score = float(row.get("Score", 0))

        market = str(row.get("Market", ""))

        if str(row.get("Market_Open", False)).upper() == "TRUE":
            score += 10

        if market == "EU":
            score += 10
        elif market == "UK":
            score += 5

        rotation_txt = Path("market_rotation_summary.txt").read_text() if Path("market_rotation_summary.txt").exists() else ""
        if f"Market Rotation Bias: EUROPE" in rotation_txt and market == "EU":
            score += 10
        if f"Market Rotation Bias: UK" in rotation_txt and market == "UK":
            score += 10
        if f"Market Rotation Bias: USA" in rotation_txt and market == "US":
            score += 10

        strategic_txt = Path("strategic_decision_summary.txt").read_text() if Path("strategic_decision_summary.txt").exists() else ""
        if "Final Recommendation: SELECTIVE BUYING" in strategic_txt and str(row.get("Exit_Warning", False)).upper() != "TRUE":
            score += 5

        if str(row.get("Signal", "")) == "STRONG BUY":
            score += 20

        if str(row.get("Exit_Warning", False)).upper() == "TRUE":
            score -= 15

        ranking.append(score)

    df["Global_Rank_Score"] = ranking

    df = df.sort_values(
        "Global_Rank_Score",
        ascending=False
    )

    df.to_csv(
        "global_opportunity_ranking.csv",
        index=False
    )

    print()
    print("===== GLOBAL OPPORTUNITY RANKING =====")

    print(
        df[
            [
                "Market",
                "Ticker",
                "Global_Rank_Score",
                "Score",
                "Signal",
                "Market_Open"
            ]
        ].head(20).to_string(index=False)
    )

if __name__ == "__main__":
    main()
