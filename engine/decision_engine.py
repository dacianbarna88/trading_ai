def decide(price, sma, rsi):

    price = float(price)
    sma = float(sma)
    rsi = float(rsi)

    score = 0

    if price > sma:
        score += 50
    else:
        score += 20

    if rsi < 40:
        score += 30
    elif rsi <= 60:
        score += 10
    else:
        score -= 20

    if score >= 70:
        return {"action": "BUY", "score": score}
    elif score >= 50:
        return {"action": "WATCH", "score": score}
    else:
        return {"action": "REJECT", "score": score}
