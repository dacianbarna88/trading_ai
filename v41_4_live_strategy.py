from v41_gate import v41_decision

def v41_live_decision(ticker, price, sma, rsi):

    res = v41_decision(ticker, price, sma, rsi)

    v39 = res["v39"]
    v40 = res["v40"]
    fusion = res["fusion"]

    # ------------------------
    # FINAL POLICY LAYER
    # ------------------------

    if fusion >= 85:
        action = "BUY"

    elif fusion >= 75:
        action = "HOLD"

    elif fusion >= 60:
        action = "WATCH"

    else:
        action = "REJECT"

    # special downgrade rule
    if v40 < 0:
        action = "REDUCE"

    return {
        "ticker": ticker,
        "v39": v39,
        "v40": v40,
        "fusion": fusion,
        "action": action
    }
