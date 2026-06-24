from pathlib import Path
import csv

BASE_EFFECTIVE_RISK = 0.375
MIN_RISK = 0.25
MAX_RISK = 0.75

def clamp(value):
    return max(MIN_RISK, min(MAX_RISK, value))

def read_bot_regime():
    path = Path("bot_output.log")
    if not path.exists():
        return "UNKNOWN"
    lines = path.read_text(errors="ignore").splitlines()
    for line in reversed(lines):
        if "Market Regime activ:" in line:
            return line.split("Market Regime activ:", 1)[1].strip()
    return "UNKNOWN"

def read_latest_signals():
    path = Path("live_signals.csv")
    if not path.exists():
        return []
    with path.open() as f:
        return list(csv.DictReader(f))

def read_portfolio_open_pnl():
    path = Path("portfolio.csv")
    if not path.exists():
        return 0.0
    total = 0.0
    with path.open() as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        if row.get("Action") == "BUY":
            try:
                total += float(row.get("PnL", 0) or 0)
            except Exception:
                pass
    return round(total, 2)

def calculate_suggested_risk():
    regime = read_bot_regime()
    signals = read_latest_signals()
    open_pnl = read_portfolio_open_pnl()
    qqq = next((s for s in signals if s.get("Ticker") == "QQQ"), {})
    spy = next((s for s in signals if s.get("Ticker") == "SPY"), {})
    strong_buy_count = sum(1 for s in signals if s.get("Signal") == "STRONG BUY")
    suggested = BASE_EFFECTIVE_RISK
    reasons = []
    if regime == "BULL":
        suggested += 0.075
        reasons.append("Market regime is BULL")
    if qqq.get("Signal") == "STRONG BUY":
        suggested += 0.05
        reasons.append("QQQ is STRONG BUY")
    if spy.get("Signal") == "STRONG BUY":
        suggested += 0.05
        reasons.append("SPY is STRONG BUY")
    if strong_buy_count >= 4:
        suggested += 0.05
        reasons.append("At least 4 STRONG BUY signals")
    if open_pnl > 0:
        suggested += 0.05
        reasons.append("Open PnL is positive")
    suggested = round(clamp(suggested), 3)
    return {
        "base_effective_risk": BASE_EFFECTIVE_RISK,
        "suggested_risk": suggested,
        "risk_delta": round(suggested - BASE_EFFECTIVE_RISK, 3),
        "market_regime": regime,
        "strong_buy_count": strong_buy_count,
        "open_pnl": open_pnl,
        "reasons": reasons,
    }

if __name__ == "__main__":
    result = calculate_suggested_risk()
    output = []
    output.append("===== ADAPTIVE STRATEGIC RISK =====")
    output.append("")
    output.append(f"Base Effective Risk: {result["base_effective_risk"]}")
    output.append(f"Suggested Risk: {result["suggested_risk"]}")
    output.append(f"Risk Delta: {result["risk_delta"]}")
    output.append("")
    output.append(f"Market Regime: {result["market_regime"]}")
    output.append(f"Strong Buy Count: {result["strong_buy_count"]}")
    output.append(f"Open PnL: {result["open_pnl"]}")
    output.append("")
    output.append("Reasons:")
    for reason in result["reasons"]:
        output.append(f"- {reason}")
    output.append("")
    output.append("Status:")
    output.append("PAPER_ONLY")
    output.append("NO_BROKER")
    output.append("NO_AUTO_EXECUTION")
    text = "\n".join(output)
    Path("adaptive_strategic_risk_summary.txt").write_text(text)
    print(text)
