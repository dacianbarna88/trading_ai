#!/usr/bin/env python3
"""
TAE Profit Protection Shadow Engine — SHADOW_ONLY / PAPER_ONLY.

Compares hypothetical profit protection strategies without live execution.
Does NOT modify live_bot, portfolio, or signals.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from tae_intraday_fade_intelligence import fifo_open_positions

PORTFOLIO_FILE = Path("portfolio.csv")
FADE_INTELLIGENCE_JSON = Path("tae_intraday_fade_intelligence.json")
FADE_HISTORY_CSV = Path("runtime_outputs/tae_intraday_fade_history.csv")
DISCOVERY_JSON = Path("tae_intraday_discovery_engine.json")
KNOWLEDGE_BASE_JSON = Path("tae_knowledge_base.json")

OUTPUT_JSON = Path("tae_profit_protection_shadow.json")
OUTPUT_MD = Path("tae_profit_protection_shadow.md")

SHADOW_ACTIONS = frozenset(
    {
        "OBSERVE",
        "TEST_SELL_20",
        "TEST_SELL_30",
        "TEST_TRAILING_1",
        "TEST_TRAILING_1_5",
    }
)


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def confidence_from_observations(observations: int) -> str:
    if observations >= 100:
        return "HIGH"
    if observations >= 30:
        return "MEDIUM"
    return "LOW"


def observation_counts(history_csv: Path) -> dict[str, int]:
    if not history_csv.is_file():
        return {}
    try:
        df = pd.read_csv(history_csv)
    except (OSError, pd.errors.EmptyDataError):
        return {}
    if df.empty or "ticker" not in df.columns:
        return {}
    valid = df[df.get("classification", pd.Series(dtype=str)) != "DATA_UNAVAILABLE"]
    return valid.groupby(valid["ticker"].astype(str).str.upper()).size().to_dict()


def knowledge_prefers_trailing(knowledge: dict[str, Any] | None) -> bool:
    if not knowledge:
        return False
    for rec in knowledge.get("recommendations") or []:
        if rec.get("recommendation") == "TEST_TRAILING_SHADOW":
            return True
    for entry in knowledge.get("entries") or []:
        if entry.get("recommendation") == "TEST_TRAILING_SHADOW":
            return True
        if entry.get("pattern_type") == "BEST_SHADOW_TRAILING":
            return True
    return False


def discovery_best_shadow_by_ticker(discovery: dict[str, Any] | None) -> dict[str, str]:
    if not discovery:
        return {}
    return {
        str(row.get("ticker", "")).upper(): str(row.get("best_shadow_strategy", ""))
        for row in discovery.get("ticker_learning") or []
        if row.get("ticker")
    }


def _shadow_values(position: dict[str, Any]) -> dict[str, float]:
    shadow = position.get("shadow") or {}
    return {
        "sell_20": float(shadow.get("sell_20_at_high_pnl") or 0),
        "sell_30": float(shadow.get("sell_30_at_high_pnl") or 0),
        "trailing_1": float(shadow.get("trailing_1pct_pnl") or 0),
        "trailing_1_5": float(shadow.get("trailing_1_5pct_pnl") or 0),
    }


def trailing_is_best_shadow(
    shadow: dict[str, float],
    discovery_strategy: str | None,
    knowledge_trailing: bool,
) -> bool:
    if discovery_strategy in {"shadow_trailing_1", "shadow_trailing_1_5"}:
        return True
    best_key = max(shadow, key=lambda k: shadow.get(k, float("-inf")))
    if best_key.startswith("trailing"):
        return True
    if knowledge_trailing and shadow.get("trailing_1", 0) > 0:
        return True
    return False


def preferred_trailing_action(shadow: dict[str, float]) -> str:
    if shadow.get("trailing_1", float("-inf")) >= shadow.get("trailing_1_5", float("-inf")):
        return "TEST_TRAILING_1"
    return "TEST_TRAILING_1_5"


def evaluate_protection_signal(
    *,
    high_pct: float,
    current_pct: float,
    drawdown_from_high_pct: float,
    missed_opportunity_usd: float,
    shadow: dict[str, float],
    discovery_strategy: str | None = None,
    knowledge_trailing: bool = False,
) -> tuple[str, str, str]:
    """
    Returns (protection_signal, suggested_shadow_action, reason).
    Priority: PARTIAL_30 > PARTIAL_20 > TRAILING > WATCH > NO_PROTECTION.
    """
    if (
        high_pct >= 5
        and drawdown_from_high_pct <= -1
        and current_pct > -1.5
    ):
        return (
            "PARTIAL_TAKE_PROFIT_SHADOW_30",
            "TEST_SELL_30",
            "SHADOW_ONLY: high_pct>=5 with fade from high; test 30% partial at intraday peak.",
        )

    if (
        high_pct >= 3
        and drawdown_from_high_pct <= -1.5
        and current_pct > -1
    ):
        return (
            "PARTIAL_TAKE_PROFIT_SHADOW_20",
            "TEST_SELL_20",
            "SHADOW_ONLY: high_pct>=3 with >=1.5% fade; test 20% partial at intraday peak.",
        )

    if (
        high_pct >= 2
        and drawdown_from_high_pct <= -1
        and trailing_is_best_shadow(shadow, discovery_strategy, knowledge_trailing)
    ):
        action = preferred_trailing_action(shadow)
        return (
            "TRAILING_PROTECTION_SHADOW",
            action,
            "SHADOW_ONLY: intraday fade with trailing as best shadow strategy.",
        )

    if (
        high_pct >= 2
        and drawdown_from_high_pct <= -1
        and missed_opportunity_usd > 25
    ):
        return (
            "PROFIT_PROTECTION_WATCH",
            "OBSERVE",
            "SHADOW_ONLY: meaningful intraday fade detected; continue observation.",
        )

    return (
        "NO_PROTECTION",
        "OBSERVE",
        "SHADOW_ONLY: no profit protection shadow rule matched.",
    )


def analyze_position(
    position: dict[str, Any],
    *,
    fifo_shares: float | None,
    fifo_avg: float | None,
    obs_count: int,
    discovery_strategy: str | None,
    knowledge_trailing: bool,
) -> dict[str, Any]:
    ticker = str(position.get("ticker", "")).upper()
    shares = float(fifo_shares if fifo_shares is not None else position.get("shares") or 0)
    avg_price = float(fifo_avg if fifo_avg is not None else position.get("avg_price") or 0)

    high_pct = float(position.get("high_pct") or 0)
    current_pct = float(position.get("current_pct") or 0)
    drawdown = float(position.get("drawdown_from_high_pct") or 0)
    missed = float(position.get("missed_opportunity_usd") or 0)
    shadow = _shadow_values(position)

    signal, action, reason = evaluate_protection_signal(
        high_pct=high_pct,
        current_pct=current_pct,
        drawdown_from_high_pct=drawdown,
        missed_opportunity_usd=missed,
        shadow=shadow,
        discovery_strategy=discovery_strategy,
        knowledge_trailing=knowledge_trailing,
    )

    if knowledge_trailing and signal == "PROFIT_PROTECTION_WATCH":
        if trailing_is_best_shadow(shadow, discovery_strategy, knowledge_trailing):
            signal = "TRAILING_PROTECTION_SHADOW"
            action = preferred_trailing_action(shadow)
            reason = "SHADOW_ONLY: knowledge base prioritizes trailing shadow testing."

    return {
        "ticker": ticker,
        "shares": round(shares, 4),
        "avg_price": round(avg_price, 2),
        "current_pct": round(current_pct, 2),
        "high_pct": round(high_pct, 2),
        "drawdown_from_high_pct": round(drawdown, 2),
        "missed_opportunity_usd": round(missed, 2),
        "classification": position.get("classification", "UNKNOWN"),
        "protection_signal": signal,
        "suggested_shadow_action": action,
        "confidence": confidence_from_observations(obs_count),
        "reason": reason,
        "estimated_protected_value_20": round(shadow["sell_20"], 2),
        "estimated_protected_value_30": round(shadow["sell_30"], 2),
        "estimated_trailing_value_1": round(shadow["trailing_1"], 2),
        "estimated_trailing_value_1_5": round(shadow["trailing_1_5"], 2),
        "shadow_only": True,
    }


def build_daily_summary(positions: list[dict[str, Any]]) -> dict[str, Any]:
    totals = {
        "total_positions": len(positions),
        "num_watch": sum(1 for p in positions if p["protection_signal"] == "PROFIT_PROTECTION_WATCH"),
        "num_partial20": sum(
            1 for p in positions if p["protection_signal"] == "PARTIAL_TAKE_PROFIT_SHADOW_20"
        ),
        "num_partial30": sum(
            1 for p in positions if p["protection_signal"] == "PARTIAL_TAKE_PROFIT_SHADOW_30"
        ),
        "num_trailing": sum(
            1 for p in positions if p["protection_signal"] == "TRAILING_PROTECTION_SHADOW"
        ),
        "total_missed_opportunity": round(
            sum(p.get("missed_opportunity_usd", 0) for p in positions), 2
        ),
        "estimated_total_protected_20": round(
            sum(p.get("estimated_protected_value_20", 0) for p in positions), 2
        ),
        "estimated_total_protected_30": round(
            sum(p.get("estimated_protected_value_30", 0) for p in positions), 2
        ),
        "estimated_total_trailing_1": round(
            sum(p.get("estimated_trailing_value_1", 0) for p in positions), 2
        ),
        "estimated_total_trailing_1_5": round(
            sum(p.get("estimated_trailing_value_1_5", 0) for p in positions), 2
        ),
    }

    method_totals = {
        "TEST_SELL_20": totals["estimated_total_protected_20"],
        "TEST_SELL_30": totals["estimated_total_protected_30"],
        "TEST_TRAILING_1": totals["estimated_total_trailing_1"],
        "TEST_TRAILING_1_5": totals["estimated_total_trailing_1_5"],
    }
    best_method = max(method_totals, key=method_totals.get) if positions else "OBSERVE"
    totals["best_shadow_protection_method"] = best_method

    actionable = totals["num_watch"] + totals["num_partial20"] + totals["num_partial30"] + totals["num_trailing"]
    if totals["total_missed_opportunity"] > 300:
        verdict = "SHADOW_ONLY: TAE missed major intraday profit — protection shadow review recommended."
    elif actionable > 0:
        verdict = "SHADOW_ONLY: profit protection signals active — paper simulation only."
    else:
        verdict = "SHADOW_ONLY: no profit protection shadow triggers today."

    totals["verdict"] = verdict
    return totals


def build_profit_protection_report(
    *,
    portfolio_path: Path = PORTFOLIO_FILE,
    fade_intelligence_path: Path = FADE_INTELLIGENCE_JSON,
    history_csv_path: Path = FADE_HISTORY_CSV,
    discovery_path: Path = DISCOVERY_JSON,
    knowledge_path: Path = KNOWLEDGE_BASE_JSON,
) -> dict[str, Any]:
    sources_loaded: dict[str, bool] = {}

    fade_intel, ok = load_json(fade_intelligence_path)
    sources_loaded[str(fade_intelligence_path)] = ok

    discovery, ok_d = load_json(discovery_path)
    sources_loaded[str(discovery_path)] = ok_d

    knowledge, ok_k = load_json(knowledge_path)
    sources_loaded[str(knowledge_path)] = ok_k

    sources_loaded[str(history_csv_path)] = history_csv_path.is_file()
    sources_loaded[str(portfolio_path)] = portfolio_path.is_file()

    fifo_map: dict[str, tuple[float, float]] = {}
    if portfolio_path.is_file():
        try:
            portfolio = pd.read_csv(portfolio_path)
            for ticker, pos in fifo_open_positions(portfolio).items():
                fifo_map[ticker] = (pos.shares, pos.avg_price)
        except OSError:
            pass

    obs_counts = observation_counts(history_csv_path)
    discovery_by_ticker = discovery_best_shadow_by_ticker(discovery)
    knowledge_trailing = knowledge_prefers_trailing(knowledge)

    positions: list[dict[str, Any]] = []
    for row in (fade_intel or {}).get("positions") or []:
        if row.get("classification") == "DATA_UNAVAILABLE":
            continue
        ticker = str(row.get("ticker", "")).upper()
        fifo = fifo_map.get(ticker, (None, None))
        positions.append(
            analyze_position(
                row,
                fifo_shares=fifo[0],
                fifo_avg=fifo[1],
                obs_count=int(obs_counts.get(ticker, 0)),
                discovery_strategy=discovery_by_ticker.get(ticker),
                knowledge_trailing=knowledge_trailing,
            )
        )

    positions.sort(key=lambda p: p.get("missed_opportunity_usd", 0), reverse=True)
    summary = build_daily_summary(positions)

    return {
        "schema": "tae_profit_protection_shadow",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": sources_loaded,
        "knowledge_trailing_priority": knowledge_trailing,
        "positions": positions,
        "daily_summary": summary,
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    summary = report["daily_summary"]
    lines = [
        "# TAE Profit Protection Shadow",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY research**",
        "",
        "## Daily verdict",
        summary["verdict"],
        "",
        "## Summary",
        f"- Positions: **{summary['total_positions']}**",
        f"- Watch: **{summary['num_watch']}** | Partial 20%: **{summary['num_partial20']}** | "
        f"Partial 30%: **{summary['num_partial30']}** | Trailing: **{summary['num_trailing']}**",
        f"- Total missed opportunity: **{summary['total_missed_opportunity']} USD**",
        f"- Best shadow method: **{summary['best_shadow_protection_method']}**",
        "",
        "## Positions",
        "",
        "| ticker | high_pct | current_pct | drawdown | missed_usd | signal | action | confidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for row in report.get("positions") or []:
        lines.append(
            f"| {row['ticker']} | {row['high_pct']} | {row['current_pct']} | "
            f"{row['drawdown_from_high_pct']} | {row['missed_opportunity_usd']} | "
            f"{row['protection_signal']} | {row['suggested_shadow_action']} | {row['confidence']} |"
        )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report["daily_summary"]
    print("===== TAE PROFIT PROTECTION SHADOW =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Positions:", summary["total_positions"])
    print("Missed opportunity:", summary["total_missed_opportunity"])
    print("Watch / Partial20 / Partial30 / Trailing:", summary["num_watch"], summary["num_partial20"], summary["num_partial30"], summary["num_trailing"])
    print("Best shadow method:", summary["best_shadow_protection_method"])
    print("Verdict:", summary["verdict"])


def main() -> int:
    report = build_profit_protection_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
