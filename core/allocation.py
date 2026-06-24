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

    return 0.0


if __name__ == "__main__":
    for s in [85, 90, 95, 100, 110, 120]:
        print(s, get_allocation_weight(s))
