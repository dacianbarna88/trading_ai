from pathlib import Path


SUMMARY_FILE = "historical_pattern_summary.txt"


def get_historical_risk_mode():
    path = Path(SUMMARY_FILE)

    if not path.exists():
        return "NORMAL"

    text = path.read_text()

    for line in text.splitlines():
        if line.startswith("Risk Mode:"):
            mode = line.split(":", 1)[1].strip().upper()
            if mode in ["AGGRESSIVE", "NORMAL", "CAUTIOUS", "DEFENSIVE"]:
                return mode

    return "NORMAL"


def get_risk_multiplier():
    mode = get_historical_risk_mode()

    if mode == "AGGRESSIVE":
        return 1.25
    if mode == "CAUTIOUS":
        return 0.5
    if mode == "DEFENSIVE":
        return 0.25

    return 1.0


def get_position_limit_multiplier():
    mode = get_historical_risk_mode()

    if mode == "CAUTIOUS":
        return 0.75
    if mode == "DEFENSIVE":
        return 0.5

    return 1.0


if __name__ == "__main__":
    print("Risk Mode:", get_historical_risk_mode())
    print("Risk Multiplier:", get_risk_multiplier())
    print("Position Limit Multiplier:", get_position_limit_multiplier())
