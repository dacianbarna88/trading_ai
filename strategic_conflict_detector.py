import csv
import json
from pathlib import Path

REGION_MAP = {
    "SPY": "US",
    "QQQ": "US",
    "AAPL": "US",
    "MSFT": "US",
    "NVDA": "US",
    "AMD": "US",
    "UNH": "US",
    "CRM": "US",
    "ADBE": "US",
    "NOW": "US",
    "DIA": "US",
    "MRK": "US",
    "V": "US",
    "PANW": "US",
    "CRWD": "US",
    "CAT": "US",
    "CSCO": "US",
    "IBM": "US",
    "INTC": "US",

    "ALV.DE": "EU",
    "SIE.DE": "EU",
    "SAP.DE": "EU",
    "AIR.PA": "EU",
    "MC.PA": "EU",

    "HSBA.L": "UK",
    "ULVR.L": "UK",
    "SHEL.L": "UK",
    "BP.L": "UK",
    "AZN.L": "UK",
}

def load_signals():
    path = Path("live_signals.csv")
    if not path.exists():
        return []

    with path.open() as f:
        return list(csv.DictReader(f))

def load_gap():
    path = Path("allocation_gap_analysis.json")
    if not path.exists():
        return {}

    return json.loads(path.read_text())

def detect_conflicts():
    signals = load_signals()
    gap = load_gap()

    conflicts = []

    for row in signals:
        ticker = row.get("Ticker", "")
        signal = row.get("Signal", "")
        score = float(row.get("Score", 0) or 0)

        region = REGION_MAP.get(ticker, "UNKNOWN")

        if region == "UNKNOWN":
            continue

        region_action = gap.get(region, {}).get("action", "HOLD")
        region_gap = gap.get(region, {}).get("gap", 0)

        conflict_type = None
        conflict_level = "LOW"

        if signal == "STRONG BUY" and region_action == "DECREASE":
            conflict_type = "SHORT_TERM_BUY_VS_STRATEGIC_DECREASE"
            conflict_level = "HIGH"

        elif signal in ["WAIT", "TAKE PROFIT"] and region_action == "INCREASE":
            conflict_type = "WEAK_SIGNAL_VS_STRATEGIC_INCREASE"
            conflict_level = "MEDIUM"

        if conflict_type:
            conflicts.append({
                "ticker": ticker,
                "region": region,
                "signal": signal,
                "score": score,
                "region_action": region_action,
                "region_gap": region_gap,
                "conflict_type": conflict_type,
                "conflict_level": conflict_level,
            })

    return conflicts

if __name__ == "__main__":
    conflicts = detect_conflicts()

    lines = [
        "===== STRATEGIC CONFLICT DETECTOR =====",
        "",
        f"Total Conflicts: {len(conflicts)}",
        "",
    ]

    if conflicts:
        for item in conflicts:
            lines.append(
                f"{item['ticker']} | {item['region']} | "
                f"Signal {item['signal']} | Score {item['score']} | "
                f"Region {item['region_action']} {item['region_gap']}% | "
                f"Conflict {item['conflict_level']}"
            )
    else:
        lines.append("No strategic conflicts detected.")

    lines.extend([
        "",
        "Status:",
        "PAPER_ONLY",
        "NO_BROKER",
        "NO_AUTO_EXECUTION",
    ])

    text = "\n".join(lines)

    Path("strategic_conflict_summary.txt").write_text(text)

    print(text)
