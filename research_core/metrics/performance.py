"""Performance metrics for research candidates."""

from __future__ import annotations

import numpy as np


def profit_factor(returns: np.ndarray) -> float:
    wins = returns[returns > 0]
    losses = returns[returns < 0]
    gross_loss = abs(losses.sum())
    if gross_loss == 0:
        return float(wins.sum()) if wins.sum() > 0 else 0.0
    return float(wins.sum() / gross_loss)


def compute_metrics(returns: np.ndarray, baseline: dict) -> dict:
    if len(returns) == 0:
        return {
            "Trades": 0,
            "Win_Rate": None,
            "Avg_Return": None,
            "Median_Return": None,
            "Total_Return": None,
            "Profit_Factor": None,
            "Worst_Trade": None,
            "Avg_Winner": None,
            "Avg_Loser": None,
            "Return_Stdev": None,
            "Lift_vs_Baseline_Avg": None,
            "Lift_vs_Baseline_WinRate": None,
        }

    winners = returns[returns > 0]
    losers = returns[returns < 0]
    avg_ret = float(returns.mean())
    win_rate = float((returns > 0).mean() * 100.0)
    return {
        "Trades": len(returns),
        "Win_Rate": round(win_rate, 2),
        "Avg_Return": round(avg_ret, 4),
        "Median_Return": round(float(np.median(returns)), 4),
        "Total_Return": round(float(returns.sum()), 4),
        "Profit_Factor": round(profit_factor(returns), 4),
        "Worst_Trade": round(float(returns.min()), 4),
        "Avg_Winner": round(float(winners.mean()), 4) if len(winners) else 0.0,
        "Avg_Loser": round(float(losers.mean()), 4) if len(losers) else 0.0,
        "Return_Stdev": round(float(returns.std(ddof=0)), 4) if len(returns) > 1 else 0.0,
        "Lift_vs_Baseline_Avg": round(avg_ret - baseline["Avg_Return"], 4),
        "Lift_vs_Baseline_WinRate": round(win_rate - baseline["Win_Rate"], 2),
    }
