from pathlib import Path

INPUT_FILE = "strategic_conflict_summary.txt"
OUTPUT_FILE = "conflict_position_sizing_summary.txt"


def sizing_for_level(level):
    if level == "HIGH":
        return 50
    if level == "MEDIUM":
        return 75
    return 100


def parse_conflicts():
    path = Path(INPUT_FILE)

    if not path.exists():
        return []

    conflicts = []

    for line in path.read_text().splitlines():
        if "| " not in line or "Conflict" not in line:
            continue

        parts = [p.strip() for p in line.split("|")]

        if len(parts) < 6:
            continue

        ticker = parts[0]
        region = parts[1]
        signal = parts[2].replace("Signal", "").strip()
        score = parts[3].replace("Score", "").strip()
        region_action = parts[4].replace("Region", "").strip()
        conflict_level = parts[5].replace("Conflict", "").strip()

        suggested_size = sizing_for_level(conflict_level)

        conflicts.append({
            "ticker": ticker,
            "region": region,
            "signal": signal,
            "score": score,
            "region_action": region_action,
            "conflict_level": conflict_level,
            "suggested_size_pct": suggested_size,
        })

    return conflicts


if __name__ == "__main__":
    conflicts = parse_conflicts()

    lines = [
        "===== CONFLICT-AWARE POSITION SIZING =====",
        "",
        f"Total Conflict Positions: {len(conflicts)}",
        "",
    ]

    if conflicts:
        for item in conflicts:
            lines.append(
                f"{item['ticker']} | {item['region']} | "
                f"Signal {item['signal']} | "
                f"Region {item['region_action']} | "
                f"Conflict {item['conflict_level']} | "
                f"Suggested Size {item['suggested_size_pct']}%"
            )
    else:
        lines.append("No conflict-based sizing adjustments.")

    lines.extend([
        "",
        "Sizing Rules:",
        "HIGH conflict = 50%",
        "MEDIUM conflict = 75%",
        "LOW/no conflict = 100%",
        "",
        "Status:",
        "PAPER_ONLY",
        "NO_BROKER",
        "NO_AUTO_EXECUTION",
    ])

    text = "\n".join(lines)

    Path(OUTPUT_FILE).write_text(text)

    print(text)
