def classify_position(pnl_pct, exit_score, news_bias="NEUTRAL"):
    try:
        pnl_pct = float(pnl_pct)
        exit_score = int(exit_score)
    except Exception:
        return "UNKNOWN"

    news_bias = str(news_bias).upper()

    if exit_score >= 4:
        return "EXIT"

    if exit_score >= 3:
        return "REDUCE"

    if pnl_pct < -5:
        return "WEAK HOLD"

    if news_bias == "NEGATIVE" and pnl_pct < 0:
        return "WEAK HOLD"

    if pnl_pct > 10 and exit_score <= 1:
        return "CORE HOLD"

    return "HOLD"


if __name__ == "__main__":
    tests = [
        (12, 1, "POSITIVE"),
        (2, 2, "NEUTRAL"),
        (-6, 2, "NEUTRAL"),
        (-1, 3, "NEGATIVE"),
        (5, 4, "NEGATIVE"),
    ]

    for t in tests:
        print(t, "=>", classify_position(*t))
