#!/usr/bin/env python3
"""
TAE Intraday Fade History Recorder — SHADOW_ONLY / PAPER_ONLY.

Persists daily fade intelligence observations for statistical learning.
Does NOT execute trades or modify live_bot.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from tae_artifact_paths import generated_report
from typing import Any

import pandas as pd

RUNTIME_DIR = Path("runtime_outputs")
HISTORY_CSV = RUNTIME_DIR / "tae_intraday_fade_history.csv"
HISTORY_JSON = RUNTIME_DIR / "tae_intraday_fade_history.json"
DAILY_SUMMARY_JSON = RUNTIME_DIR / "tae_intraday_fade_daily_summary.json"
SUMMARY_MD = generated_report("tae_intraday_fade_history_summary.md")

POSITION_COLUMNS = [
    "date",
    "timestamp",
    "run_id",
    "ticker",
    "shares",
    "avg_price",
    "open",
    "high",
    "low",
    "current",
    "current_pct",
    "high_pct",
    "low_pct",
    "missed_opportunity_usd",
    "drawdown_from_high_pct",
    "classification",
    "shadow_sell_20",
    "shadow_sell_30",
    "shadow_trailing_1",
    "shadow_trailing_1_5",
]

SUMMARY_COLUMNS = [
    "date",
    "timestamp",
    "run_id",
    "total_current_unrealized",
    "total_theoretical_high",
    "total_missed_opportunity",
    "shadow_sell20_total",
    "shadow_sell30_total",
    "shadow_trailing1_total",
    "shadow_trailing15_total",
    "num_hold",
    "num_watch_intraday_fade",
    "num_significant_intraday_fade",
    "num_potential_partial_take_profit",
    "num_risk_intraday_low",
    "verdict",
]

CLASSIFICATION_BUCKETS = [
    "HOLD",
    "WATCH_INTRADAY_FADE",
    "SIGNIFICANT_INTRADAY_FADE",
    "POTENTIAL_PARTIAL_TAKE_PROFIT",
    "RISK_INTRADAY_LOW",
]

SHADOW_STRATEGIES = [
    ("shadow_sell_20", "sell_20_at_high_pnl"),
    ("shadow_sell_30", "sell_30_at_high_pnl"),
    ("shadow_trailing_1", "trailing_1pct_pnl"),
    ("shadow_trailing_1_5", "trailing_1_5pct_pnl"),
]


def make_run_id(report: dict[str, Any]) -> str:
    if report.get("run_id"):
        return str(report["run_id"])
    generated = report.get("generated_at")
    if generated:
        return str(generated).replace(":", "").replace("-", "")
    return datetime.now().strftime("%Y%m%dT%H%M%S") + uuid.uuid4().hex[:8]


def _parse_report_timestamp(report: dict[str, Any]) -> tuple[str, str]:
    generated = report.get("generated_at", datetime.now().isoformat(timespec="seconds"))
    try:
        dt = datetime.fromisoformat(str(generated))
    except ValueError:
        dt = datetime.now()
    return dt.date().isoformat(), dt.isoformat(timespec="seconds")


def position_row_from_report(
    position: dict[str, Any],
    *,
    date: str,
    timestamp: str,
    run_id: str,
) -> dict[str, Any]:
    shadow = position.get("shadow") or {}
    return {
        "date": date,
        "timestamp": timestamp,
        "run_id": run_id,
        "ticker": position["ticker"],
        "shares": position.get("shares"),
        "avg_price": position.get("avg_price"),
        "open": position.get("open_price"),
        "high": position.get("high"),
        "low": position.get("low"),
        "current": position.get("current"),
        "current_pct": position.get("current_pct"),
        "high_pct": position.get("high_pct"),
        "low_pct": position.get("low_pct"),
        "missed_opportunity_usd": position.get("missed_opportunity_usd"),
        "drawdown_from_high_pct": position.get("drawdown_from_high_pct"),
        "classification": position.get("classification"),
        "shadow_sell_20": shadow.get("sell_20_at_high_pnl"),
        "shadow_sell_30": shadow.get("sell_30_at_high_pnl"),
        "shadow_trailing_1": shadow.get("trailing_1pct_pnl"),
        "shadow_trailing_1_5": shadow.get("trailing_1_5pct_pnl"),
    }


def daily_summary_from_report(
    report: dict[str, Any],
    *,
    date: str,
    timestamp: str,
    run_id: str,
) -> dict[str, Any]:
    totals = report.get("totals") or {}
    positions = report.get("positions") or []
    seen: set[str] = set()
    unique_positions: list[dict[str, Any]] = []
    for row in positions:
        ticker = str(row.get("ticker", "")).upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        unique_positions.append(row)

    counts = {key: 0 for key in CLASSIFICATION_BUCKETS}
    for row in unique_positions:
        label = row.get("classification")
        if label in counts:
            counts[label] += 1

    return {
        "date": date,
        "timestamp": timestamp,
        "run_id": run_id,
        "total_current_unrealized": totals.get("total_current_unrealized_usd", 0),
        "total_theoretical_high": totals.get("total_at_high_usd", 0),
        "total_missed_opportunity": totals.get("total_missed_opportunity_usd", 0),
        "shadow_sell20_total": totals.get("total_shadow_sell_20_at_high_usd", 0),
        "shadow_sell30_total": totals.get("total_shadow_sell_30_at_high_usd", 0),
        "shadow_trailing1_total": totals.get("total_shadow_trailing_1pct_usd", 0),
        "shadow_trailing15_total": totals.get("total_shadow_trailing_1_5pct_usd", 0),
        "num_hold": counts["HOLD"],
        "num_watch_intraday_fade": counts["WATCH_INTRADAY_FADE"],
        "num_significant_intraday_fade": counts["SIGNIFICANT_INTRADAY_FADE"],
        "num_potential_partial_take_profit": counts["POTENTIAL_PARTIAL_TAKE_PROFIT"],
        "num_risk_intraday_low": counts["RISK_INTRADAY_LOW"],
        "verdict": report.get("daily_verdict", ""),
    }


def dedupe_position_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep one row per ticker within a run."""
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("ticker", "")).upper()
        if not ticker or ticker in seen:
            continue
        seen.add(ticker)
        unique.append(row)
    return unique


def load_history_records(path: Path = HISTORY_JSON) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("records", []))


def load_daily_summaries(path: Path = DAILY_SUMMARY_JSON) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("summaries", []))


def run_id_exists(run_id: str, records: list[dict[str, Any]]) -> bool:
    return any(str(row.get("run_id")) == run_id for row in records)


def append_history(
    report: dict[str, Any],
    *,
    history_json: Path = HISTORY_JSON,
    history_csv: Path = HISTORY_CSV,
    daily_summary_json: Path = DAILY_SUMMARY_JSON,
) -> dict[str, Any]:
    """Append one fade intelligence run to persistent history."""
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    run_id = make_run_id(report)
    date, timestamp = _parse_report_timestamp(report)

    existing_records = load_history_records(history_json)
    if run_id_exists(run_id, existing_records):
        return {
            "appended": False,
            "reason": "duplicate_run_id",
            "run_id": run_id,
            "records_added": 0,
            "summaries_added": 0,
        }

    position_rows = [
        position_row_from_report(row, date=date, timestamp=timestamp, run_id=run_id)
        for row in report.get("positions", [])
    ]
    position_rows = dedupe_position_rows(position_rows)
    daily_summary = daily_summary_from_report(
        report, date=date, timestamp=timestamp, run_id=run_id
    )

    existing_summaries = load_daily_summaries(daily_summary_json)
    if any(str(row.get("run_id")) == run_id for row in existing_summaries):
        return {
            "appended": False,
            "reason": "duplicate_run_id",
            "run_id": run_id,
            "records_added": 0,
            "summaries_added": 0,
        }

    all_records = existing_records + position_rows
    all_summaries = existing_summaries + [daily_summary]

    history_json.write_text(
        json.dumps(
            {
                "schema": "tae_intraday_fade_history",
                "mode": "SHADOW_ONLY",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "records": all_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    daily_summary_json.write_text(
        json.dumps(
            {
                "schema": "tae_intraday_fade_daily_summary",
                "mode": "SHADOW_ONLY",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "summaries": all_summaries,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    df = pd.DataFrame(all_records, columns=POSITION_COLUMNS)
    df.to_csv(history_csv, index=False)

    return {
        "appended": True,
        "reason": "ok",
        "run_id": run_id,
        "records_added": len(position_rows),
        "summaries_added": 1,
    }


def record_fade_report(report: dict[str, Any]) -> dict[str, Any]:
    """Public entry point used by tae_intraday_fade_intelligence."""
    return append_history(report)


def build_aggregate_summary(
    records: list[dict[str, Any]] | None = None,
    summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    records = records if records is not None else load_history_records()
    summaries = summaries if summaries is not None else load_daily_summaries()

    valid = [
        row
        for row in records
        if row.get("classification") != "DATA_UNAVAILABLE"
        and row.get("missed_opportunity_usd") is not None
    ]

    shadow_totals: dict[str, float] = {}
    if summaries:
        summary_df = pd.DataFrame(summaries)
        for col in [
            "shadow_sell20_total",
            "shadow_sell30_total",
            "shadow_trailing1_total",
            "shadow_trailing15_total",
        ]:
            if col in summary_df.columns:
                shadow_totals[col] = round(
                    pd.to_numeric(summary_df[col], errors="coerce").fillna(0).sum(), 2
                )

    best_shadow_strategy = None
    if shadow_totals:
        best_key = max(shadow_totals, key=shadow_totals.get)
        best_shadow_strategy = {
            "strategy": best_key,
            "total_usd": shadow_totals[best_key],
            "all_strategy_totals": shadow_totals,
        }

    if not valid:
        return {
            "number_of_observations": len(records),
            "number_of_days_observed": len({row.get("date") for row in records if row.get("date")}),
            "top_tickers_by_missed_opportunity": [],
            "top_tickers_by_significant_fade_count": [],
            "average_missed_opportunity_per_ticker": [],
            "best_shadow_strategy": best_shadow_strategy,
            "classification_totals": {key: 0 for key in CLASSIFICATION_BUCKETS},
        }

    df = pd.DataFrame(valid)
    df["missed_opportunity_usd"] = pd.to_numeric(df["missed_opportunity_usd"], errors="coerce").fillna(0)

    top_missed = (
        df.groupby("ticker", as_index=False)["missed_opportunity_usd"]
        .sum()
        .sort_values("missed_opportunity_usd", ascending=False)
        .head(10)
        .to_dict(orient="records")
    )

    sig = df[df["classification"] == "SIGNIFICANT_INTRADAY_FADE"]
    top_sig = (
        sig.groupby("ticker")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(10)
        .to_dict(orient="records")
        if not sig.empty
        else []
    )

    avg_missed = (
        df.groupby("ticker", as_index=False)["missed_opportunity_usd"]
        .mean()
        .sort_values("missed_opportunity_usd", ascending=False)
        .head(10)
        .rename(columns={"missed_opportunity_usd": "avg_missed_opportunity_usd"})
        .to_dict(orient="records")
    )

    classification_totals = {
        key: int((df["classification"] == key).sum()) for key in CLASSIFICATION_BUCKETS
    }

    days_observed = len({row.get("date") for row in records if row.get("date")})

    return {
        "number_of_observations": len(records),
        "number_of_days_observed": days_observed,
        "top_tickers_by_missed_opportunity": top_missed,
        "top_tickers_by_significant_fade_count": top_sig,
        "average_missed_opportunity_per_ticker": avg_missed,
        "best_shadow_strategy": best_shadow_strategy,
        "classification_totals": classification_totals,
    }


def write_summary_markdown(
    aggregate: dict[str, Any],
    path: Path = SUMMARY_MD,
) -> Path:
    lines = [
        "# TAE Intraday Fade History Summary",
        "",
        f"**Generated:** {datetime.now().isoformat(timespec='seconds')}",
        "**Mode:** SHADOW_ONLY — no live trading impact",
        "",
        "## Overview",
        f"- Observations: **{aggregate['number_of_observations']}**",
        f"- Days observed: **{aggregate['number_of_days_observed']}**",
        "",
        "## Classification totals",
    ]
    for key, value in aggregate.get("classification_totals", {}).items():
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Top tickers by total missed opportunity"])
    for row in aggregate.get("top_tickers_by_missed_opportunity", []):
        lines.append(f"- {row['ticker']}: {row['missed_opportunity_usd']:.2f} USD")

    lines.extend(["", "## Top tickers by SIGNIFICANT_INTRADAY_FADE count"])
    for row in aggregate.get("top_tickers_by_significant_fade_count", []):
        lines.append(f"- {row['ticker']}: {row['count']}")

    lines.extend(["", "## Average missed opportunity per ticker (top 10)"])
    for row in aggregate.get("average_missed_opportunity_per_ticker", []):
        lines.append(f"- {row['ticker']}: {row['avg_missed_opportunity_usd']:.2f} USD")

    best = aggregate.get("best_shadow_strategy")
    lines.extend(["", "## Best shadow strategy (cumulative)"])
    if best:
        lines.append(f"- **{best['strategy']}**: {best['total_usd']:.2f} USD")
        for strategy, total in best.get("all_strategy_totals", {}).items():
            lines.append(f"  - {strategy}: {total:.2f} USD")
    else:
        lines.append("- No shadow history yet.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main() -> int:
    aggregate = build_aggregate_summary()
    write_summary_markdown(aggregate)
    print("===== TAE INTRADAY FADE HISTORY SUMMARY =====")
    print("Observations:", aggregate["number_of_observations"])
    print("Days observed:", aggregate["number_of_days_observed"])
    if aggregate.get("best_shadow_strategy"):
        best = aggregate["best_shadow_strategy"]
        print("Best shadow strategy:", best["strategy"], best["total_usd"])
    print("Wrote:", SUMMARY_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
