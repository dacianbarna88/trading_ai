"""
Trading AI Research Direction Finder V1.6

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
Analyzes existing Momentum research outputs and ranks next research directions.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

SUMMARY_TXT = "research_direction_v16_summary.txt"
RANKINGS_CSV = "research_direction_v16_rankings.csv"

INPUT_FILES = [
    "momentum_v13_contribution.csv",
    "momentum_v13_summary.txt",
    "momentum_v14_trade_paths.csv",
    "momentum_v14_stop_reentry_matrix.csv",
    "momentum_v14_summary.txt",
    "momentum_v15_recovery_matrix.csv",
    "momentum_v15_trade_recovery_paths.csv",
    "momentum_v15_summary.txt",
    "us_expanded_universe.txt",
]


def file_status(root: Path) -> dict[str, bool]:
    return {name: (root / name).exists() for name in INPUT_FILES}


def parse_baseline_section(text: str) -> dict[str, float | None]:
    """Parse metrics from the Baseline (Hold 60, NO_FILTER) block."""
    match = re.search(
        r"--- Baseline \(Hold 60, NO_FILTER\) ---\s*\n"
        r"Trades:\s*([\d.]+)\s*\n"
        r"Win_Rate:\s*([\d.]+)%\s*\n"
        r"Avg_Return:\s*([\d.]+)%\s*\n"
        r"Median_Return:\s*([\d.]+)%\s*\n"
        r"Total_Return:\s*([\d.]+)%\s*\n"
        r"Best_Trade:\s*([\d.]+)%\s*\n"
        r"Worst_Trade:\s*(-?[\d.]+)%\s*\n"
        r"Profit_Factor:\s*([\d.]+)",
        text,
    )
    if not match:
        return {}
    return {
        "trades": float(match.group(1)),
        "win_rate": float(match.group(2)),
        "avg_return": float(match.group(3)),
        "median_return": float(match.group(4)),
        "total_return": float(match.group(5)),
        "best_trade": float(match.group(6)),
        "worst_trade": float(match.group(7)),
        "profit_factor": float(match.group(8)),
    }


def parse_summary_block(path: Path) -> dict[str, str | float | None]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    verdict_match = re.search(
        r"FINAL VERDICT:\s*(\S+)|===== FINAL VERDICT =====\s*\n(\S+)",
        text,
    )
    verdict = None
    if verdict_match:
        verdict = verdict_match.group(1) or verdict_match.group(2)

    baseline = parse_baseline_section(text)
    return {
        "text": text,
        "verdict": verdict,
        "trades": baseline.get("trades"),
        "avg_return": baseline.get("avg_return"),
        "total_return": baseline.get("total_return"),
        "worst_trade": baseline.get("worst_trade"),
        "profit_factor": baseline.get("profit_factor"),
        "win_rate": baseline.get("win_rate"),
    }


def parse_touch_rates(v14_text: str) -> dict[str, float]:
    rates: dict[str, float] = {}
    for match in re.finditer(
        r"Touch\s+(-?\d+)%:\s*([\d.]+)%\s+of trades", v14_text
    ):
        rates[match.group(1)] = float(match.group(2))
    return rates


def parse_concentration(v13_text: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for match in re.finditer(r"Top\s+(\d+):\s*([\d.]+)%", v13_text):
        out[f"top_{match.group(1)}"] = float(match.group(2))
    return out


def load_contribution(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    df = pd.read_csv(path)
    if "Total_Return_Contribution" in df.columns:
        df = df.sort_values("Total_Return_Contribution", ascending=False)
    return df


def load_matrix(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def load_paths(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    return pd.read_csv(path)


def baseline_from_v14(v14_summary: dict) -> dict[str, float]:
    return {
        "trades": v14_summary.get("trades") or 0,
        "avg_return": v14_summary.get("avg_return") or 0.0,
        "total_return": v14_summary.get("total_return") or 0.0,
        "worst_trade": v14_summary.get("worst_trade") or 0.0,
        "profit_factor": v14_summary.get("profit_factor") or 0.0,
        "win_rate": v14_summary.get("win_rate") or 0.0,
    }


def analyze_v14_matrix(df: pd.DataFrame, baseline: dict[str, float]) -> dict:
    improved_avg = df[df["Avg_Return"] > baseline["avg_return"]]
    improved_total = df[df["Total_Return"] > baseline["total_return"]]
    improved_worst = df[df["Worst_Trade"] > baseline["worst_trade"]]
    improved_pf = df[df["Profit_Factor"] >= baseline["profit_factor"]]
    hurt = df[
        (df["Avg_Return"] < baseline["avg_return"])
        & (df["Total_Return"] < baseline["total_return"])
    ]
    conservative = df[
        (df["Worst_Trade"] > baseline["worst_trade"])
        & (df["Profit_Factor"] >= baseline["profit_factor"])
        & (df["Avg_Return"] >= baseline["avg_return"])
    ]
    best_avg = df.loc[df["Avg_Return"].idxmax()]
    return {
        "pairs_tested": len(df),
        "improved_avg_count": len(improved_avg),
        "improved_worst_count": len(improved_worst),
        "hurt_count": len(hurt),
        "conservative_count": len(conservative),
        "best_avg_row": best_avg,
        "best_worst_row": df.loc[df["Worst_Trade"].idxmax()],
        "top_score_row": df.loc[df["Objective_Score"].idxmax()],
    }


def analyze_v15_matrix(df: pd.DataFrame, baseline: dict[str, float]) -> dict:
    improved_avg = df[df["Avg_Return"] > baseline["avg_return"]]
    improved_total = df[df["Total_Return"] > baseline["total_return"]]
    improved_worst = df[df["Worst_Trade"] > baseline["worst_trade"]]
    improved_all_four = df[
        (df["Avg_Return"] > baseline["avg_return"])
        & (df["Total_Return"] > baseline["total_return"])
        & (df["Worst_Trade"] > baseline["worst_trade"])
        & (df["Profit_Factor"] > baseline["profit_factor"])
    ]
    trigger_avg = df.groupby("Recovery_Trigger")["Avg_Return"].mean().sort_values(
        ascending=False
    )
    trigger_worst = df.groupby("Recovery_Trigger")["Worst_Trade"].max().sort_values(
        ascending=False
    )
    dd_avg = df.groupby("Drawdown_Level")["Avg_Return"].mean().sort_values(
        ascending=False
    )
    best_risk = df.loc[df["Worst_Trade"].idxmax()]
    best_score = df.loc[df["Objective_Score"].idxmax()]
    return {
        "systems_tested": len(df),
        "improved_avg_count": len(improved_avg),
        "improved_worst_count": len(improved_worst),
        "quad_improve_count": len(improved_all_four),
        "best_trigger_avg": trigger_avg.index[0] if len(trigger_avg) else "",
        "worst_trigger_avg": trigger_avg.index[-1] if len(trigger_avg) else "",
        "best_dd_avg": int(dd_avg.index[0]) if len(dd_avg) else 0,
        "best_risk_row": best_risk,
        "best_score_row": best_score,
        "trigger_avg": trigger_avg,
        "trigger_worst": trigger_worst,
        "dd_avg": dd_avg,
    }


def format_v14_row(row: pd.Series) -> str:
    return (
        f"Stop={row['Stop_Level']}% Reentry={row['Reentry_Level']}% "
        f"avg={row['Avg_Return']}% worst={row['Worst_Trade']}% PF={row['Profit_Factor']}"
    )


def format_v15_row(row: pd.Series) -> str:
    return (
        f"DD={row['Drawdown_Level']}% Trigger={row['Recovery_Trigger']} "
        f"avg={row['Avg_Return']}% worst={row['Worst_Trade']}% PF={row['Profit_Factor']}"
    )


RESEARCH_DIRECTIONS: list[dict] = [
    {
        "direction": "Recovery Confirmation Research",
        "verdict_key": "RECOVERY_CONFIRMATION_NEXT",
        "next_module": "momentum_recovery_confirmation_v17.py",
        "research_question": (
            "Can multi-bar recovery confirmation (e.g. CLOSE_ABOVE_5DAY_HIGH plus "
            "volume or second-day confirm) improve V1.5 edge while cutting tail risk?"
        ),
        "why_matters": (
            "V1.5 showed recovery re-entry beats baseline avg/total/PF; "
            "5-day high break best improved worst trade; simple triggers already saturate."
        ),
        "files_needed": [
            "momentum_v15_recovery_matrix.csv",
            "momentum_v15_trade_recovery_paths.csv",
            "momentum_v14_trade_paths.csv",
            "us_expanded_universe.txt",
        ],
        "overfitting_risk": "Medium — many trigger combos; need holdout tickers and fewer rules.",
        "base_score": 82,
    },
    {
        "direction": "Loser Avoidance Filter Research",
        "verdict_key": "LOSER_AVOIDANCE_NEXT",
        "next_module": "momentum_loser_avoidance_v17.py",
        "research_question": (
            "Can excluding chronic underperformers (utilities, low-PF tickers) "
            "lift portfolio avg return without destroying diversification?"
        ),
        "why_matters": (
            "V1.3: 34 losing tickers (16%); losers include RIVN, NEE, utilities; "
            "83% tickers profitable — filtering tail may be high leverage."
        ),
        "files_needed": [
            "momentum_v13_contribution.csv",
            "momentum_v14_trade_paths.csv",
            "us_expanded_universe.txt",
        ],
        "overfitting_risk": "Medium-High — ticker blacklist from same 10y window risks hindsight.",
        "base_score": 78,
    },
    {
        "direction": "Drawdown Persistence Research",
        "verdict_key": "DRAWNDOWN_PERSISTENCE_NEXT",
        "next_module": "momentum_drawdown_persistence_v17.py",
        "research_question": (
            "After a -5% to -10% drawdown touch, how long does adverse excursion persist "
            "and does persistence predict recovery success?"
        ),
        "why_matters": (
            "79.9% trades touch -3%, 66.4% touch -5%; V1.4 stop/re-entry hurt edge; "
            "timing recovery needs persistence stats not static levels."
        ),
        "files_needed": [
            "momentum_v14_trade_paths.csv",
            "momentum_v15_trade_recovery_paths.csv",
        ],
        "overfitting_risk": "Low-Medium — descriptive path stats with clear hypotheses.",
        "base_score": 74,
    },
    {
        "direction": "Ticker Cohort Selection Research",
        "verdict_key": "LOSER_AVOIDANCE_NEXT",
        "next_module": "momentum_ticker_cohort_v17.py",
        "research_question": (
            "Do high-contribution cohorts (semis, energy cyclicals) share signal traits "
            "that enable positive cohort tilts?"
        ),
        "why_matters": (
            "Top contributors MU, NVDA, AMD, PLTR cluster in semis/high-beta; "
            "concentration low (Top10=18.97%) but cohort tilts may add edge."
        ),
        "files_needed": [
            "momentum_v13_contribution.csv",
            "momentum_v14_trade_paths.csv",
            "us_expanded_universe.txt",
        ],
        "overfitting_risk": "High — cohort labels from same backtest window.",
        "base_score": 65,
    },
    {
        "direction": "Sector Momentum Research",
        "verdict_key": "SECTOR_MOMENTUM_NEXT",
        "next_module": "momentum_sector_rotation_v17.py",
        "research_question": (
            "Does sector-level momentum alignment improve continuation trade selection "
            "beyond single-ticker 5% gaps?"
        ),
        "why_matters": (
            "Winners cluster semis/energy; losers cluster utilities/staples; "
            "sector filter may explain cohort edge without ticker blacklist."
        ),
        "files_needed": [
            "momentum_v13_contribution.csv",
            "us_expanded_universe.txt",
            "sector map (new lightweight file)",
        ],
        "overfitting_risk": "Medium — sector buckets reduce ticker-specific overfit.",
        "base_score": 70,
    },
    {
        "direction": "Market Regime Filter Research",
        "verdict_key": "REGIME_FILTER_NEXT",
        "next_module": "momentum_regime_filter_v17.py",
        "research_question": (
            "Do SPY trend/volatility regimes explain when momentum continuation "
            "60d holds outperform or fail?"
        ),
        "why_matters": (
            "Baseline edge is strong but worst trade -61.5%; regime gating may "
            "reduce tail risk without per-ticker overfit."
        ),
        "files_needed": [
            "momentum_v14_trade_paths.csv",
            "SPY 10y history (small download)",
        ],
        "overfitting_risk": "Low-Medium — macro regimes fewer parameters than tickers.",
        "base_score": 68,
    },
    {
        "direction": "Buying/Selling Pressure Proxy Research",
        "verdict_key": "MARKET_PRESSURE_NEXT",
        "next_module": "momentum_pressure_proxy_v17.py",
        "research_question": (
            "Do volume surge, close location, or intraday range proxies predict "
            "which 5% gap signals sustain 60d continuation?"
        ),
        "why_matters": (
            "VOLUME_GREEN_RECOVERY helped in V1.5; pressure at signal day untested; "
            "may improve entry quality before drawdown management."
        ),
        "files_needed": [
            "momentum_v15_recovery_matrix.csv",
            "momentum_v14_trade_paths.csv",
            "OHLCV history",
        ],
        "overfitting_risk": "Medium — multiple pressure metrics need pruning.",
        "base_score": 66,
    },
    {
        "direction": "Gap Continuation Research",
        "verdict_key": "RECOVERY_CONFIRMATION_NEXT",
        "next_module": "momentum_gap_continuation_v17.py",
        "research_question": (
            "Is the edge driven by overnight gap vs intraday continuation, "
            "and should entry rules differ for gap-heavy signals?"
        ),
        "why_matters": (
            "Signal is daily gain >=5% with next-open entry; gap anatomy may explain "
            "MAE depth and recovery trigger efficacy."
        ),
        "files_needed": [
            "momentum_v14_trade_paths.csv",
            "OHLCV history",
        ],
        "overfitting_risk": "Medium — gap definitions can be tuned post-hoc.",
        "base_score": 62,
    },
]


def adjust_scores(
    directions: list[dict],
    evidence: dict,
) -> list[dict]:
    v14 = evidence["v14_analysis"]
    v15 = evidence["v15_analysis"]
    v13 = evidence["v13_stats"]
    touch = evidence["touch_rates"]

    adjusted: list[dict] = []
    for d in directions:
        score = float(d["base_score"])
        name = d["direction"]

        if name == "Recovery Confirmation Research":
            score += min(v15.get("quad_improve_count", 0) * 2, 10)
            score += 5 if v15.get("improved_avg_count", 0) > 20 else 0
            best_risk = v15.get("best_risk_row")
            if best_risk is not None and "CLOSE_ABOVE_5DAY" in str(
                best_risk["Recovery_Trigger"]
            ):
                score += 6

        if name == "Loser Avoidance Filter Research":
            score += min(v13.get("losing_tickers", 0) / 2, 8)
            score += 4 if v13.get("pct_profitable", 0) > 80 else 0

        if name == "Drawdown Persistence Research":
            score += 3 if touch.get("-3", 0) > 75 else 0
            score += 4 if v14.get("hurt_count", 0) > v14.get("improved_avg_count", 0) else 0

        if name == "Sector Momentum Research":
            score += 3 if v13.get("top_10_concentration", 100) < 25 else 0

        if name == "Market Regime Filter Research":
            score += 3 if evidence["baseline"]["worst_trade"] < -50 else 0

        if name == "Buying/Selling Pressure Proxy Research":
            trig = v15.get("trigger_avg")
            if trig is not None and "VOLUME_GREEN" in str(trig.index[2]):
                score += 4

        if name == "Ticker Cohort Selection Research":
            score += 2 if v13.get("top_10_concentration", 100) < 30 else 0

        if name == "Gap Continuation Research":
            score += 2

        score = max(1, min(100, round(score)))
        row = dict(d)
        row["priority_score"] = score
        adjusted.append(row)

    adjusted.sort(key=lambda x: x["priority_score"], reverse=True)
    for i, row in enumerate(adjusted, start=1):
        row["rank"] = i
    return adjusted


def pick_verdict(ranked: list[dict], evidence: dict) -> str:
    verdict_scores: dict[str, float] = {
        "DRAWNDOWN_PERSISTENCE_NEXT": 0.0,
        "MARKET_PRESSURE_NEXT": 0.0,
        "SECTOR_MOMENTUM_NEXT": 0.0,
        "REGIME_FILTER_NEXT": 0.0,
        "RECOVERY_CONFIRMATION_NEXT": 0.0,
        "LOSER_AVOIDANCE_NEXT": 0.0,
    }
    for row in ranked:
        key = row["verdict_key"]
        verdict_scores[key] += row["priority_score"] * (1.0 / row["rank"])

    v15 = evidence["v15_analysis"]
    v14 = evidence["v14_analysis"]
    if v15.get("quad_improve_count", 0) > 0:
        verdict_scores["RECOVERY_CONFIRMATION_NEXT"] += 15
    if v14.get("hurt_count", 0) > 50:
        verdict_scores["DRAWNDOWN_PERSISTENCE_NEXT"] += 8
    if evidence["v13_stats"].get("losing_tickers", 0) >= 30:
        verdict_scores["LOSER_AVOIDANCE_NEXT"] += 10

    return max(verdict_scores, key=verdict_scores.get)


def build_evidence(root: Path) -> dict:
    status = file_status(root)
    v13_summary = parse_summary_block(root / "momentum_v13_summary.txt")
    v14_summary = parse_summary_block(root / "momentum_v14_summary.txt")
    v15_summary = parse_summary_block(root / "momentum_v15_summary.txt")

    baseline = baseline_from_v14(v14_summary)
    if not baseline["avg_return"] and v15_summary.get("avg_return"):
        baseline = {
            "trades": v15_summary.get("trades") or 0,
            "avg_return": v15_summary.get("avg_return") or 0.0,
            "total_return": v15_summary.get("total_return") or 0.0,
            "worst_trade": v15_summary.get("worst_trade") or 0.0,
            "profit_factor": v15_summary.get("profit_factor") or 0.0,
            "win_rate": v15_summary.get("win_rate") or 0.0,
        }

    contribution = load_contribution(root / "momentum_v13_contribution.csv")
    v14_matrix = load_matrix(root / "momentum_v14_stop_reentry_matrix.csv")
    v15_matrix = load_matrix(root / "momentum_v15_recovery_matrix.csv")
    v14_paths = load_paths(root / "momentum_v14_trade_paths.csv")
    v15_paths = load_paths(root / "momentum_v15_trade_recovery_paths.csv")

    v13_stats: dict = {}
    if contribution is not None and len(contribution):
        total_col = "Total_Return_Contribution"
        v13_stats["total_tickers"] = len(contribution)
        v13_stats["profitable_tickers"] = int(
            (contribution[total_col] > 0).sum()
        )
        v13_stats["losing_tickers"] = int((contribution[total_col] < 0).sum())
        v13_stats["pct_profitable"] = round(
            v13_stats["profitable_tickers"] / len(contribution) * 100, 2
        )
        v13_stats["top_tickers"] = contribution.head(10)["Ticker"].tolist()
        v13_stats["worst_tickers"] = contribution.nsmallest(10, total_col)["Ticker"].tolist()
        v13_stats["median_ticker_avg"] = round(
            float(contribution["Avg_Return"].median()), 4
        )

    concentration = parse_concentration(v13_summary.get("text", "") or "")
    v13_stats["top_10_concentration"] = concentration.get("top_10", 0.0)

    touch_rates = parse_touch_rates(v14_summary.get("text", "") or "")

    v14_analysis: dict = {}
    if v14_matrix is not None and len(v14_matrix):
        v14_analysis = analyze_v14_matrix(v14_matrix, baseline)

    v15_analysis: dict = {}
    if v15_matrix is not None and len(v15_matrix):
        v15_analysis = analyze_v15_matrix(v15_matrix, baseline)

    mae_stats: dict = {}
    if v14_paths is not None and "MAE" in v14_paths.columns:
        mae = v14_paths["MAE"].astype(float)
        mae_stats = {
            "mean_mae": round(float(mae.mean()), 4),
            "median_mae": round(float(mae.median()), 4),
            "p25_mae": round(float(mae.quantile(0.25)), 4),
            "p75_mae": round(float(mae.quantile(0.75)), 4),
        }

    universe_size = 0
    uni_path = root / "us_expanded_universe.txt"
    if uni_path.exists():
        universe_size = sum(
            1
            for line in uni_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        )

    return {
        "file_status": status,
        "baseline": baseline,
        "v13_summary": v13_summary,
        "v14_summary": v14_summary,
        "v15_summary": v15_summary,
        "v13_stats": v13_stats,
        "touch_rates": touch_rates,
        "v14_analysis": v14_analysis,
        "v15_analysis": v15_analysis,
        "mae_stats": mae_stats,
        "universe_size": universe_size,
        "v14_paths_rows": len(v14_paths) if v14_paths is not None else 0,
        "v15_paths_rows": len(v15_paths) if v15_paths is not None else 0,
    }


def build_rankings_csv(ranked: list[dict]) -> pd.DataFrame:
    rows = []
    for r in ranked:
        rows.append(
            {
                "Rank": r["rank"],
                "Research_Direction": r["direction"],
                "Priority_Score": r["priority_score"],
                "Verdict_Key": r["verdict_key"],
                "Suggested_Next_Module": r["next_module"],
                "Research_Question": r["research_question"],
                "Why_It_Matters": r["why_matters"],
                "Files_Needed": "; ".join(r["files_needed"]),
                "Overfitting_Risk": r["overfitting_risk"],
            }
        )
    return pd.DataFrame(rows)


def build_summary(
    evidence: dict,
    ranked: list[dict],
    verdict: str,
) -> str:
    baseline = evidence["baseline"]
    v13 = evidence["v13_stats"]
    v14 = evidence["v14_analysis"]
    v15 = evidence["v15_analysis"]
    touch = evidence["touch_rates"]
    mae = evidence["mae_stats"]
    status = evidence["file_status"]

    lines = [
        "===== TRADING AI RESEARCH DIRECTION FINDER V1.6 =====",
        "",
        "RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION",
        "",
        "--- Input file availability ---",
    ]
    for name, present in status.items():
        lines.append(f"  {name}: {'FOUND' if present else 'MISSING'}")
    lines.append("")

    lines.append("===== 1. PROVEN FINDINGS SUMMARY =====")
    lines.append("")
    lines.append("--- Baseline momentum edge (V1.3 / V1.4 / V1.5) ---")
    lines.append(
        f"  Trades: {int(baseline['trades'])} | Win rate: {baseline['win_rate']}%"
    )
    lines.append(
        f"  Avg return: {baseline['avg_return']}% | Median ~5.7% | "
        f"Total: {baseline['total_return']}%"
    )
    lines.append(
        f"  Profit factor: {baseline['profit_factor']} | "
        f"Worst trade: {baseline['worst_trade']}%"
    )
    lines.append(
        "  Signal: daily gain >=5%, entry next open, hold 60d close, NO_FILTER."
    )
    lines.append("")

    lines.append("--- Universe diversification (V1.3) ---")
    lines.append(f"  Universe symbols: {evidence['universe_size'] or 'unknown'}")
    if v13:
        lines.append(
            f"  Profitable tickers: {v13.get('profitable_tickers', 'n/a')} "
            f"({v13.get('pct_profitable', 'n/a')}%)"
        )
        lines.append(f"  Losing tickers: {v13.get('losing_tickers', 'n/a')}")
        lines.append(
            f"  Top-10 return concentration: {v13.get('top_10_concentration', 'n/a')}%"
        )
        lines.append(f"  Verdict: {evidence['v13_summary'].get('verdict', 'n/a')}")
    lines.append("")

    lines.append("--- Contribution concentration ---")
    if v13.get("top_tickers"):
        lines.append(f"  Best tickers: {', '.join(v13['top_tickers'][:5])}")
        lines.append(f"  Worst tickers: {', '.join(v13['worst_tickers'][:5])}")
    lines.append("")

    lines.append("--- Stop / re-entry result (V1.4) ---")
    lines.append(f"  Verdict: {evidence['v14_summary'].get('verdict', 'n/a')}")
    if v14:
        lines.append(f"  Pairs tested: {v14.get('pairs_tested', 0)}")
        lines.append(
            f"  Improved avg return: {v14.get('improved_avg_count', 0)} pairs"
        )
        lines.append(
            f"  Improved worst trade: {v14.get('improved_worst_count', 0)} pairs"
        )
        lines.append(f"  Hurt avg+total: {v14.get('hurt_count', 0)} pairs")
        lines.append(
            f"  Conservative winners: {v14.get('conservative_count', 0)} pairs"
        )
        if "best_avg_row" in v14:
            lines.append(f"  Best avg: {format_v14_row(v14['best_avg_row'])}")
    lines.append("")

    lines.append("--- Recovery trigger result (V1.5) ---")
    lines.append(f"  Verdict: {evidence['v15_summary'].get('verdict', 'n/a')}")
    if v15:
        lines.append(f"  Systems tested: {v15.get('systems_tested', 0)}")
        lines.append(
            f"  Improved avg: {v15.get('improved_avg_count', 0)} | "
            f"Quad-improve (avg/total/worst/PF): {v15.get('quad_improve_count', 0)}"
        )
        lines.append(
            f"  Best trigger (avg): {v15.get('best_trigger_avg', 'n/a')} | "
            f"Worst trigger (avg): {v15.get('worst_trigger_avg', 'n/a')}"
        )
        lines.append(f"  Best DD level (avg): {v15.get('best_dd_avg', 'n/a')}%")
        if "best_score_row" in v15:
            lines.append(f"  Top score: {format_v15_row(v15['best_score_row'])}")
        if "best_risk_row" in v15:
            lines.append(f"  Best worst-trade: {format_v15_row(v15['best_risk_row'])}")
    lines.append("")

    lines.append("===== 2. STRONGEST STATISTICAL SIGNALS =====")
    lines.append("")
    if mae:
        lines.append(
            f"  MAE mean: {mae['mean_mae']}% | median: {mae['median_mae']}% | "
            f"P25: {mae['p25_mae']}% | P75: {mae['p75_mae']}%"
        )
    if touch:
        for lvl in ["-3", "-5", "-7", "-10", "-15", "-20"]:
            if lvl in touch:
                lines.append(f"  Touch {lvl}%: {touch[lvl]}% of trades")
    lines.append("")

    if v15 and "trigger_avg" in v15:
        lines.append("  Recovery triggers by avg return:")
        for trig, val in v15["trigger_avg"].head(5).items():
            lines.append(f"    {trig}: {round(val, 4)}%")
        lines.append("  Recovery triggers weakest avg:")
        for trig, val in v15["trigger_avg"].tail(3).items():
            lines.append(f"    {trig}: {round(val, 4)}%")
    lines.append("")

    if v14:
        lines.append("  V1.4 systems that hurt (lower avg AND total vs baseline):")
        lines.append(f"    Count: {v14.get('hurt_count', 0)} of {v14.get('pairs_tested', 0)}")
    lines.append("")

    lines.append("===== 3. RANKED RESEARCH ROADMAP =====")
    lines.append("")
    for r in ranked:
        lines.append(
            f"  #{r['rank']} [{r['priority_score']}/100] {r['direction']}"
        )
        lines.append(f"      Module: {r['next_module']}")
        lines.append(f"      Question: {r['research_question']}")
        lines.append(f"      Overfitting risk: {r['overfitting_risk']}")
        lines.append("")

    top5 = ranked[:5]
    lines.append("===== 4. TOP 5 NEXT EXPERIMENTS =====")
    for r in top5:
        lines.append(
            f"  {r['rank']}. {r['direction']} (score {r['priority_score']})"
        )
    lines.append("")

    recommended = top5[0]
    lines.append("===== RECOMMENDED NEXT EXPERIMENT =====")
    lines.append(f"  Direction: {recommended['direction']}")
    lines.append(f"  Module file: {recommended['next_module']}")
    lines.append(f"  Research question: {recommended['research_question']}")
    lines.append("")
    lines.append("  Why this should be next:")
    lines.append(f"    {recommended['why_matters']}")
    lines.append("")

    lines.append(f"FINAL VERDICT: {verdict}")
    lines.append("")
    lines.append("Verdict mapping:")
    lines.append("  RECOVERY_CONFIRMATION_NEXT — refine V1.5 recovery edge")
    lines.append("  LOSER_AVOIDANCE_NEXT — cut chronic underperformers")
    lines.append("  DRAWNDOWN_PERSISTENCE_NEXT — path timing after drawdown")
    lines.append("  SECTOR_MOMENTUM_NEXT — sector alignment filters")
    lines.append("  REGIME_FILTER_NEXT — macro regime gating")
    lines.append("  MARKET_PRESSURE_NEXT — volume/pressure entry proxies")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    root = Path(".")
    print("===== RESEARCH DIRECTION FINDER V1.6 =====")
    print("RESEARCH_ONLY | PAPER_ONLY | NO_EXECUTION")
    print()

    evidence = build_evidence(root)
    ranked = adjust_scores(RESEARCH_DIRECTIONS, evidence)
    verdict = pick_verdict(ranked, evidence)

    rankings_df = build_rankings_csv(ranked)
    rankings_df.to_csv(RANKINGS_CSV, index=False)

    summary = build_summary(evidence, ranked, verdict)
    Path(SUMMARY_TXT).write_text(summary, encoding="utf-8")

    print(summary)
    print(f"Saved: {RANKINGS_CSV}")
    print(f"Saved: {SUMMARY_TXT}")


if __name__ == "__main__":
    main()
