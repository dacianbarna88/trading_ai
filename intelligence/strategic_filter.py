from intelligence.historical_intelligence import get_historical_profile

def evaluate_ticker(ticker, base_score):
    profile = get_historical_profile(ticker)

    if not profile:
        return {
            "ticker": ticker,
            "decision": "DEFER",
            "reason": "NO_HISTORY",
            "final_score": base_score
        }

    ret5 = profile["Return_5Y_%"]
    vol = profile["Volatility_5Y"]

    structural_score = 0

    # LONG-TERM QUALITY FILTER
    if ret5 > 150:
        structural_score += 60
    elif ret5 > 100:
        structural_score += 40
    elif ret5 > 50:
        structural_score += 20
    elif ret5 < 0:
        structural_score -= 40

    # VOLATILITY PENALTY
    if vol > 2.0:
        structural_score -= 10

    final_score = base_score + structural_score

    # DECISION LOGIC
    if final_score >= 150:
        decision = "ALLOW"
    elif final_score >= 120:
        decision = "WATCH"
    else:
        decision = "REJECT"

    return {
        "ticker": ticker,
        "decision": decision,
        "base_score": base_score,
        "structural_score": structural_score,
        "final_score": final_score,
        "return_5y": ret5
    }
