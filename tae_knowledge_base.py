#!/usr/bin/env python3
"""
TAE Knowledge Base — read-only consolidation VIEW (X.KNOWLEDGE-1A).

Materialized view over existing authoritative sources.
Does NOT execute trades or modify live_bot.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

INTRADAY_DISCOVERY_JSON = Path("tae_intraday_discovery_engine.json")
EVIDENCE_REPORT_JSON = Path("tae_evidence_engine_report.json")
LEARNING_MEMORY_JSON = Path("tae_runtime_learning_memory.json")
FADE_HISTORY_CSV = Path("runtime_outputs/tae_intraday_fade_history.csv")
FADE_DAILY_SUMMARY_JSON = Path("runtime_outputs/tae_intraday_fade_daily_summary.json")
KNOWLEDGE_CANDIDATES_JSON = Path("tae_knowledge_candidates.json")
DISCOVERY_RANKINGS_JSON = Path("tae_discovery_hypothesis_rankings.json")

OUTPUT_JSON = Path("tae_knowledge_base.json")
OUTPUT_MD = Path("tae_knowledge_base.md")
OUTPUT_SUMMARY_MD = Path("tae_knowledge_summary.md")

SHADOW_RECOMMENDATIONS = frozenset(
    {
        "CONTINUE_OBSERVATION",
        "PRIORITIZE_TRACKING",
        "TEST_TRAILING_SHADOW",
        "TEST_PARTIAL_SELL_SHADOW",
        "INSUFFICIENT_DATA",
    }
)

FORBIDDEN_RECOMMENDATIONS = frozenset({"BUY", "SELL", "STOP", "TAKE_PROFIT"})


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def load_fade_history(path: Path) -> tuple[pd.DataFrame, bool]:
    if not path.is_file():
        return pd.DataFrame(), False
    try:
        return pd.read_csv(path), True
    except (OSError, pd.errors.EmptyDataError):
        return pd.DataFrame(), False


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip().lower()).strip("_") or "unknown"


def _dedupe_key(entry: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(entry.get("source", "")),
        str(entry.get("subject", "")),
        str(entry.get("pattern_type", "")),
    )


def assign_status_confidence(
    *,
    source: str,
    observations: int,
    upstream_status: str | None = None,
    intraday: bool = False,
    sample_insufficient: bool = False,
) -> tuple[str, str]:
    if upstream_status == "RETIRED" or upstream_status == "REJECTED":
        return "RETIRED", "LOW"
    if upstream_status == "CONFIRMED" and not intraday:
        return "CONFIRMED", "HIGH"

    if intraday or sample_insufficient:
        if observations < 30:
            return "EXPERIMENTAL", "LOW"
        if observations < 100:
            return "LEARNING", "MEDIUM"
        return "CONFIRMED", "HIGH"

    if observations >= 100:
        return "CONFIRMED", "HIGH"
    if observations >= 30:
        return "LEARNING", "MEDIUM"
    return "EXPERIMENTAL", "LOW"


def sanitize_recommendation(value: str | None) -> str:
    rec = str(value or "CONTINUE_OBSERVATION").upper()
    if rec in FORBIDDEN_RECOMMENDATIONS:
        return "CONTINUE_OBSERVATION"
    if rec in SHADOW_RECOMMENDATIONS:
        return rec
    if "TRAILING" in rec:
        return "TEST_TRAILING_SHADOW"
    if "PARTIAL" in rec:
        return "TEST_PARTIAL_SELL_SHADOW"
    if "INSUFFICIENT" in rec or "DATA" in rec:
        return "INSUFFICIENT_DATA"
    if "PRIORITIZE" in rec or "TRACK" in rec:
        return "PRIORITIZE_TRACKING"
    return "CONTINUE_OBSERVATION"


def make_entry(
    *,
    entry_id: str,
    title: str,
    description: str,
    source: str,
    source_file: str,
    category: str,
    subject: str,
    pattern_type: str,
    first_seen: str,
    last_seen: str,
    observations: int,
    confidence: str,
    status: str,
    recommendation: str,
    metrics: dict[str, Any] | None = None,
    evidence_refs: list[str] | None = None,
    trend: str = "NEW",
) -> dict[str, Any]:
    return {
        "id": entry_id,
        "title": title,
        "description": description,
        "source": source,
        "source_file": source_file,
        "category": category,
        "subject": subject,
        "pattern_type": pattern_type,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "observations": observations,
        "confidence": confidence,
        "trend": trend,
        "status": status,
        "evidence_refs": evidence_refs or [],
        "metrics": metrics or {},
        "recommendation": sanitize_recommendation(recommendation),
        "shadow_only": True,
    }


def normalize_intraday_discovery(
    data: dict[str, Any],
    source_file: str,
) -> list[dict[str, Any]]:
    generated = str(data.get("generated_at", datetime.now().isoformat(timespec="seconds")))
    entries: list[dict[str, Any]] = []

    for pattern in data.get("patterns") or []:
        obs = int(pattern.get("observations") or 0)
        status, confidence = assign_status_confidence(
            source="intraday_discovery",
            observations=obs,
            intraday=True,
        )
        subject = str(pattern.get("subject", "all"))
        ptype = str(pattern.get("pattern_type", "UNKNOWN"))
        entries.append(
            make_entry(
                entry_id=f"kb_intraday_{pattern.get('id', _slug(ptype + subject))}",
                title=f"Intraday: {ptype.replace('_', ' ').title()}",
                description=f"{pattern.get('metric', 'metric')}={pattern.get('value')} (scope={pattern.get('scope')})",
                source="intraday_discovery",
                source_file=source_file,
                category="intraday_fade",
                subject=subject,
                pattern_type=ptype,
                first_seen=generated,
                last_seen=generated,
                observations=obs,
                confidence=confidence,
                status=status,
                recommendation=str(pattern.get("recommendation", "CONTINUE_OBSERVATION")),
                metrics={
                    "metric": pattern.get("metric"),
                    "value": pattern.get("value"),
                    "scope": pattern.get("scope"),
                },
                evidence_refs=[f"{source_file}#patterns/{pattern.get('id')}"],
            )
        )

    for row in data.get("ticker_learning") or []:
        ticker = str(row.get("ticker", ""))
        if not ticker:
            continue
        obs = int(row.get("observations") or 0)
        status, confidence = assign_status_confidence(
            source="intraday_discovery",
            observations=obs,
            intraday=True,
        )
        entries.append(
            make_entry(
                entry_id=f"kb_intraday_ticker_{_slug(ticker)}",
                title=f"Intraday fade learning: {ticker}",
                description=(
                    f"Total missed opportunity {row.get('total_missed_opportunity')} USD; "
                    f"significant fade rate {row.get('significant_fade_rate')}"
                ),
                source="intraday_discovery",
                source_file=source_file,
                category="intraday_fade",
                subject=ticker,
                pattern_type="TICKER_FADE_LEARNING",
                first_seen=generated,
                last_seen=generated,
                observations=obs,
                confidence=confidence,
                status=status,
                recommendation="PRIORITIZE_TRACKING"
                if float(row.get("total_missed_opportunity") or 0) > 50
                else "CONTINUE_OBSERVATION",
                metrics={
                    "total_missed_opportunity": row.get("total_missed_opportunity"),
                    "significant_fade_rate": row.get("significant_fade_rate"),
                    "best_shadow_strategy": row.get("best_shadow_strategy"),
                },
                evidence_refs=[f"{source_file}#ticker_learning/{ticker}"],
            )
        )

    return entries


def normalize_evidence_report(
    data: dict[str, Any],
    source_file: str,
) -> list[dict[str, Any]]:
    generated = str(data.get("generated_at", datetime.now().isoformat(timespec="seconds")))
    entries: list[dict[str, Any]] = []

    for item in data.get("evidence_items") or []:
        eid = str(item.get("evidence_id", "unknown"))
        upstream = str(item.get("status", "INCONCLUSIVE")).upper()
        if upstream == "CONFIRMED":
            status, confidence = "CONFIRMED", "HIGH"
        elif upstream == "REJECTED":
            status, confidence = "RETIRED", "LOW"
        else:
            status, confidence = "LEARNING", "MEDIUM"

        metrics = dict(item.get("supporting_metrics") or {})
        obs = int(metrics.get("sells_analyzed") or metrics.get("legacy_closed_freeze_100_plus_trades") or 1)

        entries.append(
            make_entry(
                entry_id=f"kb_evidence_{_slug(eid)}",
                title=str(item.get("title", eid)),
                description=str(item.get("conclusion", "")),
                source="evidence_engine",
                source_file=source_file,
                category="evidence",
                subject=eid,
                pattern_type="EVIDENCE_CONFIRMED" if upstream == "CONFIRMED" else "EVIDENCE_LEARNING",
                first_seen=str(item.get("registered_at") or generated),
                last_seen=generated,
                observations=obs,
                confidence=confidence,
                status=status,
                recommendation="CONTINUE_OBSERVATION",
                metrics=metrics,
                evidence_refs=[str(item.get("source_ref", source_file))],
            )
        )

    return entries


def normalize_learning_memory(
    data: dict[str, Any],
    source_file: str,
) -> list[dict[str, Any]]:
    generated = str(data.get("generated_at", datetime.now().isoformat(timespec="seconds")))
    entries: list[dict[str, Any]] = []

    top = data.get("top_ranked_strategy")
    if top:
        entries.append(
            make_entry(
                entry_id=f"kb_learning_top_{_slug(str(top))}",
                title=f"Top ranked paper strategy: {top}",
                description=f"Ranking score {data.get('top_ranking_score')}",
                source="learning_memory",
                source_file=source_file,
                category="strategy_learning",
                subject=str(top),
                pattern_type="TOP_RANKED_STRATEGY",
                first_seen=generated,
                last_seen=generated,
                observations=int(data.get("strategy_candidates_count") or 1),
                confidence="MEDIUM",
                status="LEARNING",
                recommendation="CONTINUE_OBSERVATION",
                metrics={"top_ranking_score": data.get("top_ranking_score")},
                evidence_refs=[source_file],
            )
        )

    for track in data.get("paper_tracking_needs") or []:
        cid = str(track.get("candidate_id", "unknown"))
        obs = int(track.get("current_trades") or 0)
        insufficient = bool(track.get("sample_insufficient"))
        status, confidence = assign_status_confidence(
            source="learning_memory",
            observations=obs,
            sample_insufficient=insufficient,
        )
        entries.append(
            make_entry(
                entry_id=f"kb_learning_track_{_slug(cid)}",
                title=f"Paper tracking: {cid}",
                description=str(track.get("tracking_note", "")),
                source="learning_memory",
                source_file=source_file,
                category="strategy_learning",
                subject=cid,
                pattern_type="PAPER_TRACKING",
                first_seen=generated,
                last_seen=generated,
                observations=obs,
                confidence=confidence,
                status=status,
                recommendation="INSUFFICIENT_DATA" if insufficient else "CONTINUE_OBSERVATION",
                metrics={
                    "tracking_status": track.get("tracking_status"),
                    "trades_needed": track.get("trades_needed"),
                },
                evidence_refs=[source_file],
            )
        )

    for conflict in data.get("conflict_warnings") or []:
        cid = str(conflict.get("conflict_id", "conflict"))
        entries.append(
            make_entry(
                entry_id=f"kb_learning_conflict_{_slug(cid)}",
                title=f"Learning conflict: {cid}",
                description=str(conflict.get("description", "")),
                source="learning_memory",
                source_file=source_file,
                category="strategy_learning",
                subject=cid,
                pattern_type="LEARNING_CONFLICT",
                first_seen=generated,
                last_seen=generated,
                observations=1,
                confidence="LOW",
                status="LEARNING",
                recommendation="CONTINUE_OBSERVATION",
                metrics={"risk_level": conflict.get("risk_level"), "precedence": conflict.get("precedence")},
                evidence_refs=[source_file],
            )
        )

    return entries


def normalize_knowledge_candidates(
    data: dict[str, Any],
    source_file: str,
) -> list[dict[str, Any]]:
    saved = str(data.get("saved_at", datetime.now().isoformat(timespec="seconds")))
    entries: list[dict[str, Any]] = []

    for cand in data.get("candidates") or []:
        cid = str(cand.get("candidate_id", "unknown"))
        obs = int(cand.get("sample_size") or 0)
        upstream = str(cand.get("status", "CANDIDATE")).upper()
        if upstream in {"REJECTED", "ARCHIVED"}:
            status, confidence = "RETIRED", "LOW"
        else:
            status, confidence = assign_status_confidence(
                source="knowledge_candidates",
                observations=obs,
            )
        entries.append(
            make_entry(
                entry_id=f"kb_candidate_{_slug(cid)}",
                title=str(cand.get("title", cid)),
                description=str(cand.get("evidence_summary", "")),
                source="knowledge_candidates",
                source_file=source_file,
                category="knowledge_candidate",
                subject=cid,
                pattern_type="KNOWLEDGE_CANDIDATE",
                first_seen=str(cand.get("created_at") or saved),
                last_seen=saved,
                observations=obs,
                confidence=confidence,
                status=status,
                recommendation="CONTINUE_OBSERVATION",
                metrics={
                    "quality_score": cand.get("quality_score"),
                    "accuracy": cand.get("accuracy"),
                    "robustness_label": cand.get("robustness_label"),
                },
                evidence_refs=[str(cand.get("source_hypothesis_id", ""))],
            )
        )

    return entries


def normalize_discovery_rankings(
    data: dict[str, Any],
    source_file: str,
) -> list[dict[str, Any]]:
    saved = str(data.get("saved_at", datetime.now().isoformat(timespec="seconds")))
    entries: list[dict[str, Any]] = []

    for row in data.get("discovery_rankings") or []:
        hid = str(row.get("hypothesis_id", "unknown"))
        obs = int(row.get("sample_size") or 0)
        status, confidence = assign_status_confidence(
            source="discovery_hypothesis",
            observations=obs,
        )
        entries.append(
            make_entry(
                entry_id=f"kb_discovery_{_slug(hid)}",
                title=str(row.get("title", hid)),
                description=f"Rank #{row.get('rank')} discovery hypothesis",
                source="discovery_hypothesis",
                source_file=source_file,
                category="discovery",
                subject=hid,
                pattern_type="DISCOVERY_HYPOTHESIS",
                first_seen=saved,
                last_seen=saved,
                observations=obs,
                confidence=confidence,
                status=status,
                recommendation="CONTINUE_OBSERVATION",
                metrics={
                    "quality_score": row.get("quality_score"),
                    "accuracy": row.get("accuracy"),
                    "recommendation": row.get("recommendation"),
                },
                evidence_refs=[source_file],
            )
        )

    return entries


def normalize_fade_history_metadata(
    df: pd.DataFrame,
    source_file: str,
    daily_summary: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if df.empty:
        return []

    now = datetime.now().isoformat(timespec="seconds")
    obs = len(df)
    status, confidence = assign_status_confidence(
        source="intraday_discovery",
        observations=obs,
        intraday=True,
    )
    missed_total = 0.0
    if "missed_opportunity_usd" in df.columns:
        missed_total = float(pd.to_numeric(df["missed_opportunity_usd"], errors="coerce").fillna(0).sum())

    return [
        make_entry(
            entry_id="kb_intraday_history_dataset",
            title="Intraday fade history dataset",
            description=f"{obs} historical observations across fade intelligence runs",
            source="intraday_fade_history",
            source_file=source_file,
            category="intraday_fade",
            subject="portfolio",
            pattern_type="FADE_HISTORY_DATASET",
            first_seen=str(df["date"].min()) if "date" in df.columns and not df["date"].empty else now,
            last_seen=str(df["date"].max()) if "date" in df.columns and not df["date"].empty else now,
            observations=obs,
            confidence=confidence,
            status=status,
            recommendation="INSUFFICIENT_DATA" if obs < 30 else "CONTINUE_OBSERVATION",
            metrics={
                "unique_tickers": int(df["ticker"].nunique()) if "ticker" in df.columns else 0,
                "unique_days": int(df["date"].nunique()) if "date" in df.columns else 0,
                "total_missed_opportunity_usd": round(missed_total, 2),
                "daily_runs": len((daily_summary or {}).get("summaries") or []),
            },
            evidence_refs=[source_file],
        )
    ]


def dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in entries:
        key = _dedupe_key(entry)
        if key not in merged:
            merged[key] = entry
            continue
        existing = merged[key]
        existing["observations"] = max(int(existing.get("observations") or 0), int(entry.get("observations") or 0))
        existing["last_seen"] = max(str(existing.get("last_seen", "")), str(entry.get("last_seen", "")))
        refs = set(existing.get("evidence_refs") or [])
        refs.update(entry.get("evidence_refs") or [])
        existing["evidence_refs"] = sorted(refs)
        for mk, mv in (entry.get("metrics") or {}).items():
            if mk not in existing.get("metrics", {}):
                existing.setdefault("metrics", {})[mk] = mv
    return list(merged.values())


def summarize_entries(entries: list[dict[str, Any]]) -> dict[str, Any]:
    by_status: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_trend: dict[str, int] = {}

    for entry in entries:
        by_status[entry.get("status", "UNKNOWN")] = by_status.get(entry.get("status", "UNKNOWN"), 0) + 1
        by_confidence[entry.get("confidence", "UNKNOWN")] = by_confidence.get(entry.get("confidence", "UNKNOWN"), 0) + 1
        by_source[entry.get("source", "UNKNOWN")] = by_source.get(entry.get("source", "UNKNOWN"), 0) + 1
        by_trend[entry.get("trend", "UNKNOWN")] = by_trend.get(entry.get("trend", "UNKNOWN"), 0) + 1

    return {
        "entries_total": len(entries),
        "by_status": by_status,
        "by_confidence": by_confidence,
        "by_source": by_source,
        "by_trend": by_trend,
    }


def build_knowledge_base(
    *,
    intraday_discovery: Path = INTRADAY_DISCOVERY_JSON,
    evidence_report: Path = EVIDENCE_REPORT_JSON,
    learning_memory: Path = LEARNING_MEMORY_JSON,
    fade_history: Path = FADE_HISTORY_CSV,
    fade_daily_summary: Path = FADE_DAILY_SUMMARY_JSON,
    knowledge_candidates: Path = KNOWLEDGE_CANDIDATES_JSON,
    discovery_rankings: Path = DISCOVERY_RANKINGS_JSON,
) -> dict[str, Any]:
    sources_loaded: dict[str, bool] = {}
    entries: list[dict[str, Any]] = []

    intraday_data, ok = load_json(intraday_discovery)
    sources_loaded[str(intraday_discovery)] = ok
    if intraday_data:
        entries.extend(normalize_intraday_discovery(intraday_data, str(intraday_discovery)))

    evidence_data, ok = load_json(evidence_report)
    sources_loaded[str(evidence_report)] = ok
    if evidence_data:
        entries.extend(normalize_evidence_report(evidence_data, str(evidence_report)))

    learning_data, ok = load_json(learning_memory)
    sources_loaded[str(learning_memory)] = ok
    if learning_data:
        entries.extend(normalize_learning_memory(learning_data, str(learning_memory)))

    fade_df, ok = load_fade_history(fade_history)
    sources_loaded[str(fade_history)] = ok
    daily_data, daily_ok = load_json(fade_daily_summary)
    sources_loaded[str(fade_daily_summary)] = daily_ok
    if ok:
        entries.extend(
            normalize_fade_history_metadata(fade_df, str(fade_history), daily_data)
        )

    candidates_data, ok = load_json(knowledge_candidates)
    sources_loaded[str(knowledge_candidates)] = ok
    if candidates_data:
        entries.extend(normalize_knowledge_candidates(candidates_data, str(knowledge_candidates)))

    rankings_data, ok = load_json(discovery_rankings)
    sources_loaded[str(discovery_rankings)] = ok
    if rankings_data:
        entries.extend(normalize_discovery_rankings(rankings_data, str(discovery_rankings)))

    entries = dedupe_entries(entries)
    summary = summarize_entries(entries)

    recommendations: list[dict[str, Any]] = []
    if summary["entries_total"] == 0:
        recommendations.append(
            {
                "recommendation": "INSUFFICIENT_DATA",
                "reason": "No upstream knowledge sources loaded.",
                "mode": "SHADOW_ONLY",
            }
        )
    else:
        rec_counts: dict[str, int] = {}
        for entry in entries:
            rec = entry.get("recommendation", "CONTINUE_OBSERVATION")
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
        for rec, count in sorted(rec_counts.items(), key=lambda x: -x[1])[:5]:
            recommendations.append(
                {
                    "recommendation": rec,
                    "reason": f"Derived from {count} knowledge entries.",
                    "mode": "SHADOW_ONLY",
                }
            )

    return {
        "schema": "tae_knowledge_base",
        "version": 1,
        "mode": "SHADOW_ONLY",
        "live_trading_impact": "NONE",
        "view_type": "MATERIALIZED_VIEW",
        "ssot_note": "Upstream source files remain authoritative; this file is a read-only consolidation.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "sources_loaded": sources_loaded,
        "summary": summary,
        "entries": entries,
        "recommendations": recommendations,
    }


def _entries_table(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return "_No entries._\n"
    cols = ["id", "subject", "pattern_type", "status", "confidence", "trend", "recommendation"]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for row in entries:
        lines.append("| " + " | ".join(str(row.get(c, "")) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def write_knowledge_outputs(report: dict[str, Any]) -> tuple[Path, Path, Path]:
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    entries = report.get("entries") or []
    active = [e for e in entries if e.get("status") == "CONFIRMED"]
    experimental = [e for e in entries if e.get("status") == "EXPERIMENTAL"]
    growing = [e for e in entries if e.get("status") == "LEARNING" and e.get("trend") in {"NEW", "IMPROVING"}]
    needs_data = [e for e in entries if e.get("recommendation") == "INSUFFICIENT_DATA"]
    declining = [e for e in entries if e.get("trend") == "DECLINING" or e.get("status") == "RETIRED"]

    base_md = [
        "# TAE Knowledge Base",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {report['mode']} — {report['live_trading_impact']}",
        f"**View type:** {report['view_type']}",
        "",
        report["ssot_note"],
        "",
        "## Active Knowledge (CONFIRMED)",
        _entries_table(active),
        "## Experimental Knowledge",
        _entries_table(experimental),
        "## Growing Patterns (LEARNING)",
        _entries_table(growing),
        "## Needs More Data",
        _entries_table(needs_data),
        "## Retired / Declining",
        _entries_table(declining),
        "",
        "## Summary counts",
        json.dumps(report.get("summary", {}), indent=2),
    ]
    OUTPUT_MD.write_text("\n".join(base_md) + "\n", encoding="utf-8")

    summary = report.get("summary") or {}
    top = sorted(entries, key=lambda e: (e.get("confidence") != "HIGH", e.get("observations", 0)), reverse=False)[:10]
    summary_lines = [
        "# TAE Knowledge Summary",
        "",
        f"**Generated:** {report['generated_at']}",
        "**NO BUY/SELL — RESEARCH ONLY**",
        "",
        f"- Total entries: **{summary.get('entries_total', 0)}**",
        f"- By status: {summary.get('by_status', {})}",
        f"- By confidence: {summary.get('by_confidence', {})}",
        f"- By source: {summary.get('by_source', {})}",
        "",
        "## Top entries",
    ]
    for row in top:
        summary_lines.append(
            f"- **{row.get('title')}** [{row.get('status')}/{row.get('confidence')}] — {row.get('recommendation')}"
        )
    summary_lines.extend(["", "## Recommendations (SHADOW_ONLY)"])
    for rec in report.get("recommendations") or []:
        summary_lines.append(f"- **{rec.get('recommendation')}** — {rec.get('reason')}")

    OUTPUT_SUMMARY_MD.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    return OUTPUT_JSON, OUTPUT_MD, OUTPUT_SUMMARY_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report.get("summary") or {}
    print("===== TAE KNOWLEDGE BASE (VIEW) =====")
    print("Entries:", summary.get("entries_total", 0))
    print("By status:", summary.get("by_status", {}))
    print("Sources loaded:", sum(1 for v in (report.get("sources_loaded") or {}).values() if v))
    print("View type:", report.get("view_type"))


def main() -> int:
    report = build_knowledge_base()
    write_knowledge_outputs(report)
    print_summary(report)
    print("Wrote:", OUTPUT_JSON, OUTPUT_MD, OUTPUT_SUMMARY_MD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
