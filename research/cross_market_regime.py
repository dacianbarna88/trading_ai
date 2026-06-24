from pathlib import Path
import pandas as pd

INPUT_FILE = "global_candidates.csv"
OUTPUT_FILE = "cross_market_regime.csv"
SUMMARY_FILE = "cross_market_regime_summary.txt"


def classify_market(avg_score):
    if avg_score >= 70:
        return "BULL"
    if avg_score >= 50:
        return "NEUTRAL"
    if avg_score >= 30:
        return "WEAK"
    return "BEAR"


def main():
    path = Path(INPUT_FILE)

    if not path.exists():
        print("Lipsește global_candidates.csv")
        return

    df = pd.read_csv(path)
    df["Score"] = pd.to_numeric(df["Score"], errors="coerce").fillna(0)

    regime = (
        df.groupby("Market")["Score"]
        .mean()
        .reset_index(name="Avg_Score")
    )

    regime["Regime"] = regime["Avg_Score"].apply(classify_market)
    regime.to_csv(OUTPUT_FILE, index=False)

    lines = ["Cross Market Regime Summary", "==========================="]

    for _, row in regime.iterrows():
        lines.append(
            f'{row["Market"]}: {row["Regime"]} ({row["Avg_Score"]:.1f})'
        )

    bull_count = int((regime["Regime"] == "BULL").sum())
    weak_count = int(regime["Regime"].isin(["WEAK", "BEAR"]).sum())

    if bull_count >= 2:
        global_state = "GLOBAL_RISK_ON"
    elif weak_count >= 2:
        global_state = "GLOBAL_RISK_OFF"
    else:
        global_state = "MIXED_GLOBAL"

    lines.append("")
    lines.append(f"Global State: {global_state}")

    Path(SUMMARY_FILE).write_text("\\n".join(lines))

    print("\\n".join(lines))


if __name__ == "__main__":
    main()
