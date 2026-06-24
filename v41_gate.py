def v41_decision(ticker, price, sma, rsi):

    # =========================
    # V39 (momentum)
    # =========================
    v39 = 100 if price > sma else 80

    # =========================
    # V40 (structure - calibrated)
    # =========================
    raw_v40 = 0

    if rsi < 40:
        raw_v40 = -50
    elif 40 <= rsi <= 60:
        raw_v40 = 40
    elif 60 < rsi <= 70:
        raw_v40 = 60
    else:
        raw_v40 = -40

    # 🔥 CALIBRATION (IMPORTANT FIX)
    v40 = raw_v40 * 1.25

    # =========================
    # FUSION CORE (balanced)
    # =========================
    fusion = (v39 * 0.45) + (v40 * 0.55)

    # =========================
    # FINAL ACTION (ADJUSTED THRESHOLDS)
    # =========================
    if fusion >= 82:
        action = "BUY"
    elif fusion >= 72:
        action = "WATCH"
    elif fusion >= 62:
        action = "WATCH"
    else:
        action = "REJECT"

    return {
        "ticker": ticker,
        "v39": v39,
        "v40": round(v40, 2),
        "fusion": round(fusion, 2),
        "action": action
    }
