def exit_decide(pnl, rsi):

    if pnl >= 5:
        return "SELL"

    if pnl <= -3:
        return "STOP"

    if rsi > 75:
        return "REDUCE"

    return "HOLD"
