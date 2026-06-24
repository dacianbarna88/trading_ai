def calculate_regional_strength(backtest_results):
    strength = {}

    for region, data in backtest_results.items():
        r2 = data.get("2Y", 0)
        r5 = data.get("5Y", 0)
        r10 = data.get("10Y", 0)

        performance_score = (r2 * 0.2) + (r5 * 0.3) + (r10 * 0.5)
        stability_score = min(r2, r5, r10)
        momentum_score = (r2 * 0.5) + (r5 * 0.3) + (r10 * 0.2)

        final_score = (
            performance_score * 0.6
            + stability_score * 0.2
            + momentum_score * 0.2
        )

        strength[region] = round(final_score, 2)

    return strength


def normalize_scores(raw_scores):
    total = sum(raw_scores.values())

    if total <= 0:
        equal = round(100 / len(raw_scores), 2)
        return {k: equal for k in raw_scores}

    return {
        k: round((v / total) * 100, 2)
        for k, v in raw_scores.items()
    }


def apply_allocation_bounds(weights, min_allocations, max_allocations):
    bounded = {}

    for region, value in weights.items():
        minimum = min_allocations.get(region, 0)
        maximum = max_allocations.get(region, 100)
        bounded[region] = max(minimum, min(maximum, value))

    for _ in range(20):
        total = sum(bounded.values())
        diff = round(100 - total, 6)

        if abs(diff) < 0.01:
            break

        if diff > 0:
            candidates = [
                r for r in bounded
                if bounded[r] < max_allocations.get(r, 100)
            ]
        else:
            candidates = [
                r for r in bounded
                if bounded[r] > min_allocations.get(r, 0)
            ]

        if not candidates:
            break

        share = diff / len(candidates)

        for region in candidates:
            minimum = min_allocations.get(region, 0)
            maximum = max_allocations.get(region, 100)
            bounded[region] = max(
                minimum,
                min(maximum, bounded[region] + share)
            )

    rounded = {
        region: round(value, 2)
        for region, value in bounded.items()
    }

    rounding_diff = round(100 - sum(rounded.values()), 2)

    if abs(rounding_diff) >= 0.01:
        target = max(
            rounded,
            key=lambda r: max_allocations.get(r, 100) - rounded[r]
        )
        rounded[target] = round(rounded[target] + rounding_diff, 2)

    return rounded


def recommend_allocation(backtest_results, min_allocations=None, max_allocations=None):
    min_allocations = min_allocations or {
        "US": 45,
        "EU": 15,
        "UK": 5,
    }

    max_allocations = max_allocations or {
        "US": 80,
        "EU": 40,
        "UK": 15,
    }

    strength = calculate_regional_strength(backtest_results)
    raw_allocation = normalize_scores(strength)

    recommended = apply_allocation_bounds(
        raw_allocation,
        min_allocations,
        max_allocations,
    )

    return {
        "strength": strength,
        "raw_allocation": raw_allocation,
        "recommended_allocation": recommended,
    }


if __name__ == "__main__":
    sample = {
        "US": {"2Y": 40.07, "5Y": 86.75, "10Y": 318.84},
        "EU": {"2Y": 39.08, "5Y": 49.98, "10Y": 162.65},
        "UK": {"2Y": 42.72, "5Y": 67.32, "10Y": 125.90},
    }

    result = recommend_allocation(sample)

    print("===== ADAPTIVE ALLOCATION ENGINE =====")
    print("Regional Strength:")
    for region, score in result["strength"].items():
        print(f"{region}: {score}")

    print("\nRaw Allocation:")
    for region, allocation in result["raw_allocation"].items():
        print(f"{region}: {allocation}%")

    print("\nRecommended Allocation:")
    for region, allocation in result["recommended_allocation"].items():
        print(f"{region}: {allocation}%")
