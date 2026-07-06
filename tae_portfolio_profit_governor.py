#!/usr/bin/env python3
"""
TAE Portfolio Profit Governor v1 — SHADOW_ONLY / NO_BROKER.

Portfolio-level profit protection VIEW from upstream shadow JSON outputs.
Reads portfolio.csv read-only for position counts — does not modify it.
Does NOT modify live_bot, broker, or execution.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PORTFOLIO_CSV = Path("portfolio.csv")
GOVERNOR_JSON = Path("tae_profit_decision_governor.json")
CONTEXT_JSON = Path("tae_profit_context_engine.json")
LEARNING_JSON = Path("tae_profit_committee_learning.json")
BRAIN_JSON = Path("tae_profit_intelligence_brain.json")
MEMORY_JSON = Path("tae_profit_memory_engine.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
VALIDATION_JSON = Path("tae_profit_protection_validation.json")
SECTOR_SUMMARY = Path("runtime_outputs/sector_intelligence_summary.txt")

OUTPUT_JSON = Path("tae_portfolio_profit_governor.json")
OUTPUT_MD = Path("tae_portfolio_profit_governor.md")

VERDICTS = frozenset(
    {
        "PORTFOLIO_KEEP",
        "PORTFOLIO_NORMAL",
        "PORTFOLIO_WATCH",
        "PORTFOLIO_DEFENSIVE",
        "PORTFOLIO_LOCK_PROFITS",
        "PORTFOLIO_HIGH_RISK",
    }
)

EU_SUFFIXES = (".DE", ".PA", ".AS", ".MI", ".MC", ".SW", ".BR", ".HE", ".VI")
UK_SUFFIX = ".L"
US_SUFFIX = ".US"

HIGH_MISSED_USD = 500.0


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def infer_region(ticker: str) -> str:
    upper = ticker.upper()
    if upper.endswith(UK_SUFFIX):
        return "UK"
    if upper.endswith(US_SUFFIX):
        return "US"
    for suffix in EU_SUFFIXES:
        if upper.endswith(suffix):
            return "EU"
    if "." in upper:
        return "OTHER"
    return "US"


def read_open_positions(portfolio_path: Path) -> dict[str, dict[str, float]]:
    """Read-only FIFO-lite open position scan from portfolio.csv."""
    if not portfolio_path.is_file():
        return {}
    try:
        with portfolio_path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError:
        return {}

    by_ticker: dict[str, list[tuple[str, float, float]]] = {}
    for row in rows:
        ticker = str(row.get("Ticker") or "").upper().strip()
        if not ticker:
            continue
        action = str(row.get("Action") or "").upper()
        shares = _f(row.get("Shares"))
        price = _f(row.get("Price"))
        if shares <= 0:
            continue
        by_ticker.setdefault(ticker, []).append((action, shares, price))

    open_positions: dict[str, dict[str, float]] = {}
    for ticker, events in by_ticker.items():
        buy_shares = sum(s for a, s, _ in events if a == "BUY")
        sell_shares = sum(s for a, s, _ in events if a == "SELL")
        open_shares = buy_shares - sell_shares
        if open_shares <= 1e-9:
            continue
        buy_value = sum(s * p for a, s, p in events if a == "BUY")
        avg_price = buy_value / buy_shares if buy_shares else 0.0
        pnl_pct = _f(
            next(
                (
                    row.get("PnL_%")
                    for row in reversed(rows)
                    if str(row.get("Ticker", "")).upper() == ticker
                ),
                0.0,
            )
        )
        open_positions[ticker] = {
            "shares": round(open_shares, 4),
            "avg_price": round(avg_price, 4),
            "pnl_pct": pnl_pct,
        }
    return open_positions


def parse_sector_summary(text: str) -> dict[str, Any]:
    leader = "UNKNOWN"
    score: float | None = None
    view = "UNKNOWN"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Sector Leader:"):
            leader = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("Sector Score:"):
            score = _f(stripped.split(":", 1)[1].strip(), default=-1.0)
            if score < 0:
                score = None
        elif stripped.startswith("OVERWEIGHT_"):
            view = stripped
        elif stripped.startswith("UNDERWEIGHT_"):
            view = stripped
    risk = "UNKNOWN"
    if leader != "UNKNOWN":
        risk = f"LEADER_{leader.split('(')[0].strip().replace(' ', '_').upper()}"
    return {
        "sector_leader": leader,
        "sector_score": score,
        "sector_view": view,
        "sector_risk_summary": risk,
    }


def posture_counts(ticker_postures: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "protect_shadow_count": 0,
        "trail_shadow_count": 0,
        "watch_shadow_count": 0,
        "keep_winner_count": 0,
        "observe_shadow_count": 0,
    }
    for row in ticker_postures:
        posture = str(row.get("governor_posture") or "")
        if posture == "PROTECT_SHADOW":
            counts["protect_shadow_count"] += 1
        elif posture == "TRAIL_SHADOW":
            counts["trail_shadow_count"] += 1
        elif posture == "WATCH_SHADOW":
            counts["watch_shadow_count"] += 1
        elif posture == "KEEP_WINNER_SHADOW":
            counts["keep_winner_count"] += 1
        elif posture == "OBSERVE_SHADOW":
            counts["observe_shadow_count"] += 1
    return counts


def compute_quality_score(
    *,
    profitable_ratio: float,
    keep_ratio: float,
    avg_governor_score: float,
    missed_per_position: float,
) -> float:
    missed_penalty = min(40.0, missed_per_position / 25.0)
    score = (
        profitable_ratio * 30.0
        + keep_ratio * 25.0
        + (avg_governor_score / 100.0) * 35.0
        + max(0.0, 10.0 - missed_penalty)
    )
    return round(max(0.0, min(100.0, score)), 1)


def compute_at_risk_score(
    *,
    protect_trail_ratio: float,
    watch_ratio: float,
    avg_protection_score: float,
    missed_per_position: float,
) -> float:
    missed_component = min(35.0, missed_per_position / 20.0)
    score = (
        protect_trail_ratio * 40.0
        + watch_ratio * 15.0
        + (avg_protection_score / 100.0) * 25.0
        + missed_component
    )
    return round(max(0.0, min(100.0, score)), 1)


def compute_concentration_score(
    regional_counts: dict[str, int],
    total: int,
    ticker_postures: list[dict[str, Any]],
) -> float:
    if total <= 0:
        return 0.0
    region_shares = [c / total for c in regional_counts.values() if c > 0]
    region_hhi = sum(s * s for s in region_shares) if region_shares else 1.0

    risky = [r for r in ticker_postures if r.get("governor_posture") in {"PROTECT_SHADOW", "TRAIL_SHADOW"}]
    risky_regions: dict[str, int] = {}
    for row in risky:
        region = infer_region(str(row.get("ticker", "")))
        risky_regions[region] = risky_regions.get(region, 0) + 1
    risky_concentration = max(risky_regions.values()) / max(len(risky), 1) if risky else 0.0

    score = region_hhi * 55.0 + risky_concentration * 45.0
    return round(max(0.0, min(100.0, score)), 1)


def compute_portfolio_verdict(metrics: dict[str, Any]) -> str:
    n = metrics["total_positions"]
    if n <= 0:
        return "PORTFOLIO_NORMAL"

    keep = metrics["keep_winner_count"]
    protect = metrics["protect_shadow_count"]
    trail = metrics["trail_shadow_count"]
    watch = metrics["watch_shadow_count"]
    missed = metrics["aggregate_missed_usd"]

    risky = protect + trail + watch
    protect_trail = protect + trail

    if risky / n >= 0.5:
        return "PORTFOLIO_HIGH_RISK"
    if missed >= HIGH_MISSED_USD and protect_trail >= 2:
        return "PORTFOLIO_LOCK_PROFITS"
    if protect_trail / n >= 0.30:
        return "PORTFOLIO_DEFENSIVE"
    if keep >= n / 2 and protect_trail <= 1:
        return "PORTFOLIO_KEEP"
    if watch >= 2 or protect_trail >= 1:
        return "PORTFOLIO_WATCH"
    return "PORTFOLIO_NORMAL"


def build_explanation(
    verdict: str,
    metrics: dict[str, Any],
    regional: dict[str, int],
    sector: dict[str, Any],
) -> str:
    n = metrics["total_positions"]
    parts = [
        f"SHADOW_ONLY portfolio governor: {n} positions, verdict={verdict}.",
        (
            f"Postures — keep={metrics['keep_winner_count']}, "
            f"protect={metrics['protect_shadow_count']}, trail={metrics['trail_shadow_count']}, "
            f"watch={metrics['watch_shadow_count']}."
        ),
        (
            f"Scores — quality={metrics['portfolio_profit_quality_score']}, "
            f"at_risk={metrics['portfolio_profit_at_risk_score']}, "
            f"concentration={metrics['concentration_risk_score']}."
        ),
        f"Aggregate missed USD={metrics['aggregate_missed_usd']:.2f}.",
        f"Regional mix: US={regional.get('US', 0)}, EU={regional.get('EU', 0)}, "
        f"UK={regional.get('UK', 0)}, OTHER={regional.get('OTHER', 0)}.",
    ]
    if sector.get("sector_risk_summary") != "UNKNOWN":
        parts.append(f"Sector context: {sector.get('sector_risk_summary')}.")
    parts.append("NO BUY / NO SELL — observation VIEW only.")
    return " ".join(parts)


def build_portfolio_report() -> dict[str, Any]:
    source_paths = {
        "portfolio.csv": PORTFOLIO_CSV,
        "tae_profit_decision_governor.json": GOVERNOR_JSON,
        "tae_profit_context_engine.json": CONTEXT_JSON,
        "tae_profit_committee_learning.json": LEARNING_JSON,
        "tae_profit_intelligence_brain.json": BRAIN_JSON,
        "tae_profit_memory_engine.json": MEMORY_JSON,
        "tae_profit_protection_shadow.json": SHADOW_JSON,
        "tae_profit_protection_validation.json": VALIDATION_JSON,
        "runtime_outputs/sector_intelligence_summary.txt": SECTOR_SUMMARY,
    }

    sources_loaded: dict[str, bool] = {}
    payloads: dict[str, dict[str, Any] | None] = {}
    for key, path in source_paths.items():
        if key.endswith(".txt"):
            sources_loaded[key] = path.is_file()
            payloads[key] = None
            continue
        if key == "portfolio.csv":
            sources_loaded[key] = path.is_file()
            payloads[key] = None
            continue
        data, ok = load_json(path)
        sources_loaded[key] = ok
        payloads[key] = data

    governor = payloads["tae_profit_decision_governor.json"]
    context = payloads["tae_profit_context_engine.json"]
    shadow = payloads["tae_profit_protection_shadow.json"]
    validation = payloads["tae_profit_protection_validation.json"]

    ticker_postures = list((governor or {}).get("ticker_postures") or [])
    open_positions = read_open_positions(PORTFOLIO_CSV)

    portfolio_tickers = set(open_positions) | {str(r.get("ticker", "")).upper() for r in ticker_postures}
    portfolio_tickers.discard("")

    counts = posture_counts(ticker_postures)
    total_positions = len(ticker_postures) if ticker_postures else len(portfolio_tickers)

    profitable = 0
    losing = 0
    for row in ticker_postures:
        pct = _f(row.get("current_pct"))
        if pct > 0:
            profitable += 1
        elif pct < 0:
            losing += 1
    if not ticker_postures and open_positions:
        for info in open_positions.values():
            pct = info.get("pnl_pct", 0.0)
            if pct > 0:
                profitable += 1
            elif pct < 0:
                losing += 1

    shadow_summary = (shadow or {}).get("global_summary") or {}
    aggregate_missed = _f(shadow_summary.get("total_missed_opportunity"))
    if not aggregate_missed:
        aggregate_missed = sum(
            _f(p.get("missed_opportunity_usd")) for p in (shadow or {}).get("positions") or []
        )

    avg_governor = _f(((governor or {}).get("global_summary") or {}).get("average_governor_score"))
    avg_protection = 0.0
    prot_scores = [_f(r.get("pdc_protection_score")) for r in ticker_postures if r.get("pdc_protection_score") is not None]
    if prot_scores:
        avg_protection = sum(prot_scores) / len(prot_scores)

    n = max(total_positions, 1)
    missed_per = aggregate_missed / n
    profitable_ratio = profitable / n
    keep_ratio = counts["keep_winner_count"] / n
    protect_trail_ratio = (counts["protect_shadow_count"] + counts["trail_shadow_count"]) / n
    watch_ratio = counts["watch_shadow_count"] / n

    quality_score = compute_quality_score(
        profitable_ratio=profitable_ratio,
        keep_ratio=keep_ratio,
        avg_governor_score=avg_governor,
        missed_per_position=missed_per,
    )
    at_risk_score = compute_at_risk_score(
        protect_trail_ratio=protect_trail_ratio,
        watch_ratio=watch_ratio,
        avg_protection_score=avg_protection,
        missed_per_position=missed_per,
    )

    regional_counts = {"US": 0, "EU": 0, "UK": 0, "OTHER": 0}
    for ticker in portfolio_tickers:
        regional_counts[infer_region(ticker)] = regional_counts.get(infer_region(ticker), 0) + 1

    sector_info: dict[str, Any] = {"sector_risk_summary": "UNKNOWN"}
    if SECTOR_SUMMARY.is_file():
        try:
            sector_info = parse_sector_summary(SECTOR_SUMMARY.read_text(encoding="utf-8"))
        except OSError:
            pass
    elif (context or {}).get("market_snapshot", {}).get("sector_leader"):
        leader = (context or {})["market_snapshot"]["sector_leader"]
        sector_info = {
            "sector_leader": leader.get("leader", "UNKNOWN"),
            "sector_score": leader.get("score"),
            "sector_view": "FROM_CONTEXT_ENGINE",
            "sector_risk_summary": f"LEADER_{str(leader.get('leader', 'UNKNOWN')).split('(')[0].strip().replace(' ', '_').upper()}",
        }

    context_sector_labels: dict[str, int] = {}
    for row in (context or {}).get("tickers") or []:
        label = str(((row.get("context_factors") or {}).get("sector_context")) or "UNKNOWN")
        context_sector_labels[label] = context_sector_labels.get(label, 0) + 1

    concentration_score = compute_concentration_score(regional_counts, n, ticker_postures)

    metrics = {
        "total_positions": total_positions,
        "profitable_positions": profitable,
        "losing_positions": losing,
        **counts,
        "aggregate_missed_usd": round(aggregate_missed, 2),
        "portfolio_profit_quality_score": quality_score,
        "portfolio_profit_at_risk_score": at_risk_score,
        "concentration_risk_score": concentration_score,
    }

    portfolio_verdict = compute_portfolio_verdict(metrics)

    risky_sorted = sorted(
        ticker_postures,
        key=lambda r: (r.get("governor_score", 100), -_f(r.get("pdc_protection_score"))),
    )
    keep_sorted = sorted(
        [r for r in ticker_postures if r.get("governor_posture") == "KEEP_WINNER_SHADOW"],
        key=lambda r: r.get("governor_score", 0),
        reverse=True,
    )

    if not governor:
        final_status = "PPG_NOT_READY"
    elif total_positions >= 3:
        final_status = "PPG_SHADOW_READY_FOR_OBSERVATION"
    else:
        final_status = "PPG_SHADOW_NEEDS_MORE_DATA"

    explanation = build_explanation(portfolio_verdict, metrics, regional_counts, sector_info)

    return {
        "schema": "tae_portfolio_profit_governor",
        "version": "v1",
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "no_broker": True,
        "no_execution": True,
        "view_type": "MATERIALIZED_VIEW",
        "governor_note": "Portfolio-level profit VIEW — no live orders; execution remains live_bot.py",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": sources_loaded,
        "safety_mode": {
            "shadow_only": True,
            "no_broker": True,
            "no_live_execution_change": True,
            "portfolio_csv_modified": False,
        },
        "portfolio_verdict": portfolio_verdict,
        "final_status": final_status,
        "metrics": metrics,
        "regional_risk_summary": regional_counts,
        "sector_risk_summary": sector_info,
        "context_sector_labels": context_sector_labels,
        "top_5_risky_tickers": [
            {
                "ticker": r["ticker"],
                "governor_score": r.get("governor_score"),
                "governor_posture": r.get("governor_posture"),
                "final_shadow_recommendation": r.get("final_shadow_recommendation"),
                "pdc_protection_score": r.get("pdc_protection_score"),
            }
            for r in risky_sorted[:5]
        ],
        "top_5_keep_winners": [
            {
                "ticker": r["ticker"],
                "governor_score": r.get("governor_score"),
                "profit_context_score": r.get("profit_context_score"),
                "pce_context_verdict": r.get("pce_context_verdict"),
            }
            for r in keep_sorted[:5]
        ],
        "validation_verdict": (validation or {}).get("verdict"),
        "pdg_verdict": ((governor or {}).get("global_summary") or {}).get("final_verdict"),
        "explanation": explanation,
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    metrics = report["metrics"]
    regional = report.get("regional_risk_summary") or {}
    sector = report.get("sector_risk_summary") or {}

    lines = [
        "# TAE Portfolio Profit Governor v1",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**Portfolio verdict:** {report['portfolio_verdict']}",
        f"**Final status:** {report['final_status']}",
        "",
        "> **NO BUY / NO SELL — SHADOW_ONLY portfolio profit VIEW**",
        "",
        report.get("governor_note", ""),
        "",
        "## Safety mode",
        "",
        "- SHADOW_ONLY: **true**",
        "- NO_BROKER: **true**",
        "- NO_LIVE_EXECUTION_CHANGE: **true**",
        "- portfolio.csv modified: **false**",
        "",
        "## Portfolio metrics",
        "",
        f"- Total positions: **{metrics['total_positions']}**",
        f"- Profitable: **{metrics['profitable_positions']}**",
        f"- Losing: **{metrics['losing_positions']}**",
        f"- Keep winner: **{metrics['keep_winner_count']}**",
        f"- Protect shadow: **{metrics['protect_shadow_count']}**",
        f"- Trail shadow: **{metrics['trail_shadow_count']}**",
        f"- Watch shadow: **{metrics['watch_shadow_count']}**",
        f"- Observe shadow: **{metrics['observe_shadow_count']}**",
        f"- Aggregate missed USD: **{metrics['aggregate_missed_usd']}**",
        f"- Profit quality score: **{metrics['portfolio_profit_quality_score']}**",
        f"- Profit at risk score: **{metrics['portfolio_profit_at_risk_score']}**",
        f"- Concentration risk score: **{metrics['concentration_risk_score']}**",
        "",
        "## Regional risk summary",
        "",
        "| region | positions |",
        "| --- | --- |",
    ]
    for region in ("US", "EU", "UK", "OTHER"):
        lines.append(f"| {region} | {regional.get(region, 0)} |")

    lines.extend(
        [
            "",
            "## Sector risk summary",
            "",
            f"- Leader: **{sector.get('sector_leader', 'UNKNOWN')}**",
            f"- Score: **{sector.get('sector_score', 'UNKNOWN')}**",
            f"- View: **{sector.get('sector_view', 'UNKNOWN')}**",
            f"- Summary: **{sector.get('sector_risk_summary', 'UNKNOWN')}**",
            "",
            "## Top 5 risky tickers",
            "",
            "| ticker | governor score | posture | final rec | protect score |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for row in report.get("top_5_risky_tickers") or []:
        lines.append(
            f"| {row['ticker']} | {row.get('governor_score')} | {row.get('governor_posture')} | "
            f"{row.get('final_shadow_recommendation')} | {row.get('pdc_protection_score')} |"
        )

    lines.extend(
        [
            "",
            "## Top 5 keep winners",
            "",
            "| ticker | governor score | context score | PCE verdict |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report.get("top_5_keep_winners") or []:
        lines.append(
            f"| {row['ticker']} | {row.get('governor_score')} | {row.get('profit_context_score')} | "
            f"{row.get('pce_context_verdict')} |"
        )

    lines.extend(
        [
            "",
            "## Sources loaded",
            "",
        ]
    )
    for key, loaded in sorted((report.get("sources_loaded") or {}).items()):
        mark = "✅" if loaded else "❌"
        lines.append(f"- {mark} {key}")

    lines.extend(["", "## Explanation", "", report.get("explanation", ""), ""])

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD


def print_summary(report: dict[str, Any]) -> None:
    metrics = report["metrics"]
    print("===== TAE PORTFOLIO PROFIT GOVERNOR v1 =====")
    print("Mode: SHADOW_ONLY — no live orders")
    print("Portfolio verdict:", report["portfolio_verdict"])
    print("Final status:", report["final_status"])
    print("Positions:", metrics["total_positions"])
    print("Quality / at-risk / concentration:", metrics["portfolio_profit_quality_score"], metrics["portfolio_profit_at_risk_score"], metrics["concentration_risk_score"])
    print("Missed USD:", metrics["aggregate_missed_usd"])
    print(
        "Keep / protect / trail / watch:",
        metrics["keep_winner_count"],
        metrics["protect_shadow_count"],
        metrics["trail_shadow_count"],
        metrics["watch_shadow_count"],
    )


def main() -> int:
    report = build_portfolio_report()
    write_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
