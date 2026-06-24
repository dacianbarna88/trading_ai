import random

last_prices = {}

def get_data(ticker):

    if ticker not in last_prices:
        last_prices[ticker] = round(random.uniform(95, 105), 2)

    change_pct = random.uniform(-0.8, 0.8)
    new_price = last_prices[ticker] * (1 + change_pct / 100)
    last_prices[ticker] = round(new_price, 2)

    return {
        "price": last_prices[ticker],
        "sma": 100,
        "rsi": round(random.uniform(30, 80), 2)
    }
