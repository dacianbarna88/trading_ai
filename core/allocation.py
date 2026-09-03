def get_allocation_weight(score):
    try:
        score = float(score)
    except Exception:
        return 0.0

    if score >= 110:
        return 1.5

    if score >= 100:
        return 1.25

    if score >= 95:
        return 1.0

    if score >= 90:
        return 0.75

    # Below 90 was previously always 0.0, silently zeroing out every trade
    # for scores in [MIN_SCORE_TO_BUY, 90) after live_bot.py's MIN_SCORE_TO_BUY
    # was relaxed to 60 (commit 15d63b5) without updating this function —
    # a STRONG BUY logged as "BUY permis" would invest $0 with no trace.
    # These tiers extend the same increasing-weight-with-score shape below
    # 90 so a relaxed threshold actually sizes weaker-but-passing signals
    # smaller, instead of silently sizing them at zero.
    if score >= 80:
        return 0.5

    if score >= 70:
        return 0.35

    if score >= 60:
        return 0.25

    return 0.0


if __name__ == "__main__":
    for s in [55, 60, 70, 80, 85, 90, 95, 100, 110, 120]:
        print(s, get_allocation_weight(s))
