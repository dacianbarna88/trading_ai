from config.settings import MIN_SCORE_TO_BUY
from core.historical_risk import get_historical_risk_mode
from core.forecast_risk import get_forecast_multiplier


def get_dynamic_min_score_to_buy():
    score = MIN_SCORE_TO_BUY
    risk_mode = get_historical_risk_mode()
    forecast_multiplier = get_forecast_multiplier()

    if risk_mode == "CAUTIOUS":
        score += 5

    if risk_mode == "DEFENSIVE":
        score += 10

    if forecast_multiplier <= 0.75:
        score += 5

    if forecast_multiplier <= 0.5:
        score += 10

    return min(score, 110)


if __name__ == "__main__":
    print("Dynamic MIN_SCORE_TO_BUY:", get_dynamic_min_score_to_buy())
