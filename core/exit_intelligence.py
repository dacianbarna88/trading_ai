def get_exit_score(
    current_score,
    news_bias="NEUTRAL",
    forecast_multiplier=1.0,
):
    exit_points = 0

    try:
        current_score = float(current_score)
    except Exception:
        current_score = 0

    if current_score < 80:
        exit_points += 1

    if current_score < 70:
        exit_points += 1

    if str(news_bias).upper() == "NEGATIVE":
        exit_points += 1

    if forecast_multiplier <= 0.75:
        exit_points += 1

    if forecast_multiplier <= 0.50:
        exit_points += 1

    return exit_points


def should_exit_position(
    current_score,
    news_bias="NEUTRAL",
    forecast_multiplier=1.0,
):
    return get_exit_score(
        current_score,
        news_bias,
        forecast_multiplier,
    ) >= 3


if __name__ == "__main__":
    tests = [
        (100, "POSITIVE", 1.0),
        (75, "NEUTRAL", 0.75),
        (65, "NEGATIVE", 0.50),
    ]

    for score, news, forecast in tests:
        print(
            score,
            news,
            forecast,
            "=>",
            should_exit_position(
                score,
                news,
                forecast
            )
        )
