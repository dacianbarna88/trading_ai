from pathlib import Path
import pandas as pd


def read_text(path):
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text()


def main():

    risk_mode = "UNKNOWN"
    global_state = "UNKNOWN"
    rotation_bias = "UNKNOWN"
    top_opportunity = "NONE"
    horizon_text = read_text("strategic_horizon_summary.txt")

    regime_text = read_text("regime_forecast_summary.txt")

    if "Historical Risk:" in regime_text:
        for line in regime_text.splitlines():
            if "Historical Risk:" in line:
                risk_mode = line.split(":")[-1].strip()

    cross_text = read_text("cross_market_regime_summary.txt")

    if "Global State:" in cross_text:
        for line in cross_text.splitlines():
            if "Global State:" in line:
                global_state = line.split(":")[-1].strip()

    rotation_text = read_text("market_rotation_summary.txt")

    if "Market Rotation Bias:" in rotation_text:
        for line in rotation_text.splitlines():
            if "Market Rotation Bias:" in line:
                rotation_bias = line.split(":")[-1].strip()

    if Path("global_candidates.csv").exists():
        df = pd.read_csv("global_candidates.csv")

        if not df.empty:
            top_opportunity = str(df.iloc[0]["Ticker"])

    allocation_text = ""

    if Path("strategic_allocations.csv").exists():
        alloc = pd.read_csv("strategic_allocations.csv")

        allocation_text = " | ".join(
            [
                f'{r["Market"]} {r["Allocation_%"]}%'
                for _, r in alloc.iterrows()
            ]
        )

    elif Path("global_allocations.csv").exists():
        alloc = pd.read_csv("global_allocations.csv")

        allocation_text = " | ".join(
            [
                f'{r["Market"]} {r["Allocation_%"]}%'
                for _, r in alloc.iterrows()
            ]
        )

    recommendation = "WAIT"

    if (
        risk_mode in ["NORMAL", "AGGRESSIVE"]
        and global_state == "GLOBAL_RISK_ON"
    ):
        recommendation = "AGGRESSIVE BUYING"

    elif (
        global_state == "GLOBAL_RISK_OFF"
        or risk_mode == "CAUTIOUS"
    ):
        recommendation = "SELECTIVE BUYING"

    lines = [
        "STRATEGIC INVESTMENT COMMITTEE",
        "==============================",
        "",
        f"Historical Risk: {risk_mode}",
        f"Cross Market State: {global_state}",
        f"Market Rotation: {rotation_bias}",
        "",
        "Strategic Horizon:",
        horizon_text,
        "",
        f"Capital Allocation: {allocation_text}",
        "",
        f"Top Opportunity: {top_opportunity}",
        "",
        f"Final Recommendation: {recommendation}",
    ]

    Path(
        "strategic_decision_summary.txt"
    ).write_text("\n".join(lines))

    pd.DataFrame(
        [{
            "Historical_Risk": risk_mode,
            "Cross_Market_State": global_state,
            "Market_Rotation": rotation_bias,
            "Strategic_Horizon": horizon_text,
            "Top_Opportunity": top_opportunity,
            "Recommendation": recommendation,
        }]
    ).to_csv(
        "strategic_decision.csv",
        index=False
    )

    print("\n".join(lines))


if __name__ == "__main__":
    main()
