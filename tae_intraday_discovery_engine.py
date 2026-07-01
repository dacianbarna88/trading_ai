#!/usr/bin/env python3
"""
TAE Intraday Discovery & Learning Engine — SHADOW_ONLY / PAPER_ONLY.

Discovers recurring intraday fade patterns from persistent history.
Does NOT execute trades or modify live_bot.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

HISTORY_CSV = Path("runtime_outputs/tae_intraday_fade_history.csv")
DAILY_SUMMARY_JSON = Path("runtime_outputs/tae_intraday_fade_daily_summary.json")
OUTPUT_JSON = Path("tae_intraday_discovery_engine.json")
OUTPUT_MD = Path("tae_intraday_discovery_engine.md")

MIN_OBSERVATIONS_WARNING = 30
MIN_OBSERVATIONS_PATTERN = 3
SIGNIFICANT_FADE_RATE_THRESHOLD = 0.5
HIGH_FADE_MISSED_USD = 50.0

SHADOW_COLS = [
    "shadow_sell_20",
    "shadow_sell_30",
    "shadow_trailing_1",
    "shadow_trailing_1_5",
]

TRAILING_STRATEGIES = {"shadow_trailing_1", "shadow_trailing_1_5"}
PARTIAL_SELL_STRATEGIES = {"shadow_sell_20", "shadow_sell_30"}

CLASSIFICATIONS = [
    "HOLD",
    "WATCH_INTRADAY_FADE",
    "SIGNIFICANT_INTRADAY_FADE",
    "POTENTIAL_PARTIAL_TAKE_PROFIT",
    "RISK_INTRADAY_LOW",
    "DATA_UNAVAILABLE",
]

RECOMMENDATIONS = [
    "CONTINUE_OBSERVATION",
    "PRIORITIZE_TRACKING",
    "TEST_TRAILING_SHADOW",
    "TEST_PARTIAL_SELL_SHADOW",
    "INSUFFICIENT_DATA",
]


def confidence_level(observations: int) -> str:
    if observations >= 30:
        return "HIGH"
    if observations >= 10:
        return "MEDIUM"
    return "LOW"


def _best_shadow_from_totals(totals: dict[str, float]) -> str | None:
    if not totals:
        return None
    return max(totals, key=totals.get)


def _shadow_totals_from_row(row: pd.Series) -> dict[str, float]:
    totals: dict[str, float] = {}
    for col in SHADOW_COLS:
        val = pd.to_numeric(row.get(col), errors="coerce")
        if pd.notna(val):
            totals[col] = float(val)
    return totals


def load_history_csv(path: Path = HISTORY_CSV) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty:
        return df
    for col in [
        "missed_opportunity_usd",
        "current_pct",
        "high_pct",
        "low_pct",
        "drawdown_from_high_pct",
        *SHADOW_COLS,
    ]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "ticker" in df.columns:
        df["ticker"] = df["ticker"].astype(str).str.upper()
    return df


def load_daily_summaries(path: Path = DAILY_SUMMARY_JSON) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("summaries", []))


def compute_dataset_health(df: pd.DataFrame) -> dict[str, Any]:
    valid = df[df["classification"] != "DATA_UNAVAILABLE"] if not df.empty and "classification" in df.columns else df
    observations = len(df)
    unique_days = int(df["date"].nunique()) if not df.empty and "date" in df.columns else 0
    unique_tickers = int(df["ticker"].nunique()) if not df.empty and "ticker" in df.columns else 0

    if observations == 0:
        quality = "EMPTY"
    elif "classification" in df.columns:
        unavailable = int((df["classification"] == "DATA_UNAVAILABLE").sum())
        unavailable_rate = unavailable / observations
        if unavailable_rate > 0.5:
            quality = "POOR"
        elif unavailable_rate > 0.2:
            quality = "PARTIAL"
        else:
            quality = "GOOD"
    else:
        quality = "UNKNOWN"

    return {
        "observations": observations,
        "valid_observations": len(valid),
        "unique_days": unique_days,
        "unique_tickers": unique_tickers,
        "data_quality": quality,
        "minimum_sample_warning": observations < MIN_OBSERVATIONS_WARNING,
    }


def compute_ticker_learning(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "ticker" not in df.columns:
        return []

    valid = df[df["classification"] != "DATA_UNAVAILABLE"].copy()
    if valid.empty:
        return []

    results: list[dict[str, Any]] = []
    for ticker, group in valid.groupby("ticker"):
        obs = len(group)
        sig_count = int((group["classification"] == "SIGNIFICANT_INTRADAY_FADE").sum())
        partial_count = int((group["classification"] == "POTENTIAL_PARTIAL_TAKE_PROFIT").sum())
        risk_count = int((group["classification"] == "RISK_INTRADAY_LOW").sum())

        shadow_totals = {col: float(group[col].fillna(0).sum()) for col in SHADOW_COLS if col in group.columns}
        best_shadow = _best_shadow_from_totals(shadow_totals)

        results.append(
            {
                "ticker": ticker,
                "observations": obs,
                "avg_missed_opportunity": round(float(group["missed_opportunity_usd"].mean()), 2),
                "total_missed_opportunity": round(float(group["missed_opportunity_usd"].sum()), 2),
                "significant_fade_count": sig_count,
                "significant_fade_rate": round(sig_count / obs, 4) if obs else 0.0,
                "potential_partial_take_profit_count": partial_count,
                "risk_intraday_low_count": risk_count,
                "avg_current_pct": round(float(group["current_pct"].mean()), 2),
                "avg_high_pct": round(float(group["high_pct"].mean()), 2),
                "avg_drawdown_from_high_pct": round(float(group["drawdown_from_high_pct"].mean()), 2),
                "best_shadow_strategy": best_shadow,
                "shadow_totals": {k: round(v, 2) for k, v in shadow_totals.items()},
                "confidence": confidence_level(obs),
            }
        )

    results.sort(key=lambda row: row["total_missed_opportunity"], reverse=True)
    return results


def compute_classification_learning(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty or "classification" not in df.columns:
        return []

    valid = df[df["classification"] != "DATA_UNAVAILABLE"].copy()
    results: list[dict[str, Any]] = []

    for label in CLASSIFICATIONS:
        if label == "DATA_UNAVAILABLE":
            continue
        group = valid[valid["classification"] == label]
        if group.empty:
            continue

        shadow_totals = {col: float(group[col].fillna(0).sum()) for col in SHADOW_COLS if col in group.columns}
        results.append(
            {
                "classification": label,
                "count": len(group),
                "avg_missed_opportunity": round(float(group["missed_opportunity_usd"].mean()), 2),
                "avg_current_pct": round(float(group["current_pct"].mean()), 2),
                "avg_high_pct": round(float(group["high_pct"].mean()), 2),
                "best_shadow_strategy": _best_shadow_from_totals(shadow_totals),
                "shadow_totals": {k: round(v, 2) for k, v in shadow_totals.items()},
            }
        )

    results.sort(key=lambda row: row["count"], reverse=True)
    return results


def compute_daily_learning(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not summaries:
        return []

    daily: list[dict[str, Any]] = []
    for row in summaries:
        shadow_map = {
            "shadow_sell_20": float(row.get("shadow_sell20_total", 0) or 0),
            "shadow_sell_30": float(row.get("shadow_sell30_total", 0) or 0),
            "shadow_trailing_1": float(row.get("shadow_trailing1_total", 0) or 0),
            "shadow_trailing_1_5": float(row.get("shadow_trailing15_total", 0) or 0),
        }
        daily.append(
            {
                "date": row.get("date"),
                "total_missed_opportunity": row.get("total_missed_opportunity"),
                "total_current_unrealized": row.get("total_current_unrealized"),
                "total_theoretical_high": row.get("total_theoretical_high"),
                "best_shadow_strategy": _best_shadow_from_totals(shadow_map),
                "shadow_totals": {k: round(v, 2) for k, v in shadow_map.items()},
                "verdict": row.get("verdict"),
            }
        )

    daily.sort(key=lambda row: str(row.get("date", "")))
    return daily


def _pattern(
    *,
    pattern_id: str,
    pattern_type: str,
    scope: str,
    subject: str,
    observations: int,
    metric: str,
    value: Any,
    confidence: str,
    recommendation: str,
) -> dict[str, Any]:
    return {
        "id": pattern_id,
        "pattern_type": pattern_type,
        "scope": scope,
        "subject": subject,
        "observations": observations,
        "metric": metric,
        "value": value,
        "confidence": confidence,
        "recommendation": recommendation,
    }


def discover_patterns(
    health: dict[str, Any],
    ticker_learning: list[dict[str, Any]],
    daily_learning: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    patterns: list[dict[str, Any]] = []
    pid = 0

    if health.get("minimum_sample_warning"):
        pid += 1
        patterns.append(
            _pattern(
                pattern_id=f"P{pid:03d}",
                pattern_type="LOW_CONFIDENCE_INSUFFICIENT_SAMPLE",
                scope="dataset",
                subject="all",
                observations=health["observations"],
                metric="observations",
                value=health["observations"],
                confidence="LOW",
                recommendation="INSUFFICIENT_DATA",
            )
        )

    global_shadow: dict[str, float] = {col: 0.0 for col in SHADOW_COLS}
    for day in daily_learning:
        for col, val in day.get("shadow_totals", {}).items():
            global_shadow[col] = global_shadow.get(col, 0.0) + float(val)

    best_global = _best_shadow_from_totals(global_shadow)
    if best_global:
        pid += 1
        if best_global in TRAILING_STRATEGIES:
            ptype = "BEST_SHADOW_TRAILING"
            rec = "TEST_TRAILING_SHADOW"
        elif best_global in PARTIAL_SELL_STRATEGIES:
            ptype = "BEST_SHADOW_PARTIAL_SELL"
            rec = "TEST_PARTIAL_SELL_SHADOW"
        else:
            ptype = "BEST_SHADOW_TRAILING"
            rec = "TEST_TRAILING_SHADOW"

        patterns.append(
            _pattern(
                pattern_id=f"P{pid:03d}",
                pattern_type=ptype,
                scope="portfolio",
                subject=best_global,
                observations=health["observations"],
                metric="cumulative_shadow_pnl_usd",
                value=round(global_shadow[best_global], 2),
                confidence=confidence_level(health["observations"]),
                recommendation=rec,
            )
        )

    for ticker_row in ticker_learning:
        ticker = ticker_row["ticker"]
        obs = ticker_row["observations"]
        conf = ticker_row["confidence"]

        if (
            obs >= MIN_OBSERVATIONS_PATTERN
            and ticker_row["significant_fade_rate"] > SIGNIFICANT_FADE_RATE_THRESHOLD
        ):
            pid += 1
            patterns.append(
                _pattern(
                    pattern_id=f"P{pid:03d}",
                    pattern_type="REPEATED_SIGNIFICANT_FADE",
                    scope="ticker",
                    subject=ticker,
                    observations=obs,
                    metric="significant_fade_rate",
                    value=ticker_row["significant_fade_rate"],
                    confidence=conf,
                    recommendation="PRIORITIZE_TRACKING",
                )
            )

        if obs >= MIN_OBSERVATIONS_PATTERN and ticker_row["risk_intraday_low_count"] >= 2:
            rate = ticker_row["risk_intraday_low_count"] / obs
            pid += 1
            patterns.append(
                _pattern(
                    pattern_id=f"P{pid:03d}",
                    pattern_type="REPEATED_RISK_INTRADAY_LOW",
                    scope="ticker",
                    subject=ticker,
                    observations=obs,
                    metric="risk_intraday_low_count",
                    value=ticker_row["risk_intraday_low_count"],
                    confidence=conf,
                    recommendation="PRIORITIZE_TRACKING",
                )
            )
            _ = rate

        if (
            obs >= 2
            and ticker_row["avg_missed_opportunity"] >= HIGH_FADE_MISSED_USD
        ) or (
            obs >= MIN_OBSERVATIONS_PATTERN
            and ticker_row["total_missed_opportunity"]
            >= max((t["total_missed_opportunity"] for t in ticker_learning), default=0) * 0.5
        ):
            pid += 1
            patterns.append(
                _pattern(
                    pattern_id=f"P{pid:03d}",
                    pattern_type="HIGH_FADE_TICKER",
                    scope="ticker",
                    subject=ticker,
                    observations=obs,
                    metric="total_missed_opportunity",
                    value=ticker_row["total_missed_opportunity"],
                    confidence=conf,
                    recommendation="PRIORITIZE_TRACKING",
                )
            )

    return patterns


def generate_recommendations(
    health: dict[str, Any],
    patterns: list[dict[str, Any]],
    ticker_learning: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recs: list[dict[str, Any]] = []

    if health.get("minimum_sample_warning"):
        recs.append(
            {
                "recommendation": "INSUFFICIENT_DATA",
                "scope": "dataset",
                "subject": "all",
                "reason": f"Only {health['observations']} observations; need {MIN_OBSERVATIONS_WARNING}+ for reliable learning.",
                "mode": "SHADOW_ONLY",
            }
        )

    pattern_recs = {p["recommendation"] for p in patterns if p.get("recommendation")}
    for rec_type in ("TEST_TRAILING_SHADOW", "TEST_PARTIAL_SELL_SHADOW", "PRIORITIZE_TRACKING"):
        if rec_type in pattern_recs:
            subjects = [p["subject"] for p in patterns if p.get("recommendation") == rec_type]
            recs.append(
                {
                    "recommendation": rec_type,
                    "scope": "pattern",
                    "subject": ", ".join(sorted(set(subjects))[:5]),
                    "reason": f"Detected from {rec_type.lower().replace('_', ' ')} patterns.",
                    "mode": "SHADOW_ONLY",
                }
            )

    if not recs:
        recs.append(
            {
                "recommendation": "CONTINUE_OBSERVATION",
                "scope": "dataset",
                "subject": "all",
                "reason": "Accumulate more intraday fade history before shadow strategy testing.",
                "mode": "SHADOW_ONLY",
            }
        )
    elif health["observations"] >= MIN_OBSERVATIONS_PATTERN and not health.get("minimum_sample_warning"):
        recs.append(
            {
                "recommendation": "CONTINUE_OBSERVATION",
                "scope": "dataset",
                "subject": "all",
                "reason": "Dataset growing; maintain daily fade intelligence runs.",
                "mode": "SHADOW_ONLY",
            }
        )

    top_tickers = [t["ticker"] for t in ticker_learning[:3]]
    if top_tickers and not any(r["recommendation"] == "PRIORITIZE_TRACKING" for r in recs):
        recs.append(
            {
                "recommendation": "PRIORITIZE_TRACKING",
                "scope": "ticker",
                "subject": ", ".join(top_tickers),
                "reason": "Highest cumulative missed intraday opportunity.",
                "mode": "SHADOW_ONLY",
            }
        )

    return recs


def build_discovery_report(
    history_csv: Path = HISTORY_CSV,
    daily_json: Path = DAILY_SUMMARY_JSON,
) -> dict[str, Any]:
    df = load_history_csv(history_csv)
    summaries = load_daily_summaries(daily_json)

    health = compute_dataset_health(df)
    ticker_learning = compute_ticker_learning(df)
    classification_learning = compute_classification_learning(df)
    daily_learning = compute_daily_learning(summaries)
    patterns = discover_patterns(health, ticker_learning, daily_learning)
    recommendations = generate_recommendations(health, patterns, ticker_learning)

    return {
        "schema": "tae_intraday_discovery_engine",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "inputs": {
            "history_csv": str(history_csv),
            "daily_summary_json": str(daily_json),
        },
        "dataset_health": health,
        "ticker_learning": ticker_learning,
        "classification_learning": classification_learning,
        "daily_learning": daily_learning,
        "patterns": patterns,
        "recommendations": recommendations,
    }


def write_discovery_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    health = report["dataset_health"]
    lines = [
        "# TAE Intraday Discovery Engine",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        "",
        "## Dataset health",
        f"- Observations: **{health['observations']}**",
        f"- Unique days: **{health['unique_days']}**",
        f"- Unique tickers: **{health['unique_tickers']}**",
        f"- Data quality: **{health['data_quality']}**",
        f"- Minimum sample warning: **{health['minimum_sample_warning']}**",
        "",
        "## Top tickers by missed opportunity",
    ]

    for row in report.get("ticker_learning", [])[:10]:
        lines.append(
            f"- **{row['ticker']}**: total missed {row['total_missed_opportunity']} USD, "
            f"sig fade rate {row['significant_fade_rate']}, confidence {row['confidence']}"
        )

    lines.extend(["", "## Patterns discovered"])
    for pattern in report.get("patterns", []):
        lines.append(
            f"- `{pattern['pattern_type']}` [{pattern['subject']}]: "
            f"{pattern['metric']}={pattern['value']} (confidence {pattern['confidence']})"
        )

    lines.extend(["", "## Recommendations (SHADOW_ONLY)"])
    for rec in report.get("recommendations", []):
        lines.append(f"- **{rec['recommendation']}** — {rec['reason']}")

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    health = report["dataset_health"]
    print("===== TAE INTRADAY DISCOVERY ENGINE (SHADOW) =====")
    print("Observations:", health["observations"])
    print("Unique days:", health["unique_days"])
    print("Unique tickers:", health["unique_tickers"])
    print("Data quality:", health["data_quality"])
    if health["minimum_sample_warning"]:
        print("WARNING: insufficient sample (<30 observations)")
    print("Patterns:", len(report.get("patterns", [])))
    print("Recommendations:", len(report.get("recommendations", [])))
    for rec in report.get("recommendations", [])[:3]:
        print(" -", rec["recommendation"])


def main() -> int:
    report = build_discovery_report()
    write_discovery_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
