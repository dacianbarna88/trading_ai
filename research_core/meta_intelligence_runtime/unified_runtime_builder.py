"""Unified Runtime SSOT — consolidates all intelligence layers per ticker."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.committee_runtime.live_signals_enricher import COMMITTEE_COLUMNS
from research_core.historical_intelligence.live_signals_enricher import ENRICHMENT_COLUMNS
from research_core.meta_intelligence_runtime.live_signals_enricher import (
    META_COLUMNS,
    MetaContext,
    _parse_float,
)
from research_core.research_runtime.live_signals_enricher import RESEARCH_COLUMNS
from research_core.strategic_allocation_runtime.live_signals_enricher import ALLOCATION_COLUMNS

OUTPUT_JSON = "tae_unified_runtime.json"

SCANNER_FIELDS = ("Score", "Signal", "Price", "RSI", "SMA50", "Time")
HISTORICAL_PREFIX = "Historical_"
LEARNING_FIELDS = ("Learning_Health_Score", "Learning_Context", "Learning_Verdict")

TICKER_SOURCES: tuple[tuple[str, str], ...] = (
    ("global_opportunity_ranking.csv", "global_ranking"),
    ("global_candidates.csv", "global_candidates"),
    ("multi_market_candidates.csv", "multi_market_scanner"),
    ("watchlist_candidates.csv", "us_market_scanner"),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _pick_prefix(row: dict[str, Any], prefix: str) -> dict[str, Any]:
    return {k: v for k, v in row.items() if k.startswith(prefix) and v not in (None, "")}


def _pick_columns(row: dict[str, Any], columns: tuple[str, ...]) -> dict[str, Any]:
    return {col: row[col] for col in columns if col in row and row[col] not in (None, "")}


def _load_learning_global(root: Path) -> dict[str, Any]:
    payload = _load_json(root / "tae_learning_runtime.json") or {}
    summary = payload.get("advisory_summary") or {}
    return {
        "Learning_Health_Score": summary.get("learning_health_score"),
        "Learning_Verdict": summary.get("learning_verdict") or summary.get("verdict"),
        "Learning_Context": summary.get("learning_summary") or summary.get("summary"),
    }


def _compute_confidence(record: dict[str, Any]) -> float | None:
    candidates: list[tuple[float, float]] = []
    weights = (
        ("Historical_Confidence", 0.15),
        ("Research_Confidence", 0.15),
        ("Committee_Confidence", 0.15),
        ("Allocation_Confidence", 0.15),
        ("Meta_Confidence", 0.25),
        ("Learning_Health_Score", 0.15),
    )
    for key, weight in weights:
        val = _parse_float(record.get(key))
        if val is not None:
            candidates.append((val, weight))
    if not candidates:
        score = _parse_float(record.get("Unified_Runtime_Score"))
        return score
    total_w = sum(w for _, w in candidates)
    if total_w <= 0:
        return None
    return round(sum(v * w for v, w in candidates) / total_w, 2)


def _compute_recommendation(record: dict[str, Any]) -> str:
    unified = _parse_float(record.get("Unified_Runtime_Score")) or 0.0
    confidence = _parse_float(record.get("Unified_Runtime_Confidence")) or 0.0
    signal = str(record.get("Signal") or "").upper()
    committee = str(record.get("Committee_Decision") or "").upper()
    meta_rec = str(record.get("Meta_Recommendation") or "")

    if unified >= 85 and confidence >= 75 and signal == "STRONG BUY":
        return "STRONG_UNIFIED_CANDIDATE"
    if unified >= 70 and confidence >= 65:
        if committee in {"BUY", "BUY_ALIGNED"} or "STRONG" in meta_rec.upper():
            return "FAVORABLE"
    if unified >= 55:
        return "MONITOR"
    if signal == "TAKE PROFIT":
        return "TAKE_PROFIT_CONTEXT"
    if committee in {"SELL", "DEFENSIVE"}:
        return "DEFENSIVE"
    return "NEUTRAL"


def _compute_context(record: dict[str, Any]) -> str:
    parts: list[str] = []
    ticker = record.get("Ticker") or record.get("ticker")
    if ticker:
        parts.append(f"ticker={ticker}")
    for key in (
        "Signal",
        "Scanner_Score",
        "Unified_Runtime_Score",
        "Unified_Runtime_Confidence",
        "Unified_Runtime_Recommendation",
        "Historical_Edge",
        "Research_Confidence",
        "Committee_Decision",
        "Allocation_Score",
        "Meta_Health",
        "Meta_Ecosystem_Status",
    ):
        val = record.get(key)
        if val not in (None, ""):
            parts.append(f"{key}={val}")
    return "; ".join(parts)


def _compute_bonuses(record: dict[str, Any], *, learning_score: float | None) -> dict[str, float]:
    hist_edge = str(record.get("Historical_Edge") or "")
    hist_conf = _parse_float(record.get("Historical_Confidence"))
    historical_bonus = 0.0
    if hist_edge == "POSITIVE":
        historical_bonus += 1.5
    elif hist_edge == "WEAK":
        historical_bonus -= 1.0
    if hist_conf is not None and hist_conf >= 70:
        historical_bonus += (hist_conf - 50) * 0.03

    res_conf = _parse_float(record.get("Research_Confidence"))
    research_bonus = 0.0
    if res_conf is not None and res_conf >= 65:
        research_bonus += (res_conf - 50) * 0.03

    conf = _parse_float(record.get("Committee_Confidence"))
    decision = str(record.get("Committee_Decision") or "").upper()
    committee_bonus = 0.0
    if decision in {"BUY", "BUY_ALIGNED", "ACCUMULATE_US_TECH", "AGGRESSIVE", "NORMAL"}:
        committee_bonus += 2.0
    elif decision in {"SELL", "DEFENSIVE"}:
        committee_bonus -= 3.0
    if conf is not None and conf >= 70:
        committee_bonus += (conf - 50) * 0.04
    if str(record.get("Signal") or "").upper() == "STRONG BUY":
        if decision in {"BUY", "BUY_ALIGNED"}:
            committee_bonus += 2.0
        elif decision == "CONFLICT":
            committee_bonus -= 1.0

    learning_bonus = 0.0
    if learning_score is not None and learning_score >= 60:
        learning_bonus += (learning_score - 50) * 0.02

    alloc_score = _parse_float(record.get("Allocation_Score"))
    alloc_conf = _parse_float(record.get("Allocation_Confidence"))
    allocation_bonus = 0.0
    if alloc_score is not None and alloc_score >= 55:
        allocation_bonus += (alloc_score - 50) * 0.04
    if alloc_conf is not None and alloc_conf >= 70:
        allocation_bonus += (alloc_conf - 50) * 0.02

    meta_score = _parse_float(record.get("Meta_Score"))
    meta_conf = _parse_float(record.get("Meta_Confidence"))
    meta_bonus = 0.0
    if meta_score is not None and meta_score >= 70:
        meta_bonus += (meta_score - 50) * 0.03
    if meta_conf is not None and meta_conf >= 75:
        meta_bonus += (meta_conf - 50) * 0.02
    ecosystem = str(record.get("Meta_Ecosystem_Status") or "")
    if "HEALTHY" in ecosystem.upper():
        meta_bonus += 0.5

    return {
        "historical_bonus": round(historical_bonus, 4),
        "research_bonus": round(research_bonus, 4),
        "committee_bonus": round(committee_bonus, 4),
        "learning_bonus": round(learning_bonus, 4),
        "allocation_bonus": round(allocation_bonus, 4),
        "meta_bonus": round(meta_bonus, 4),
    }


def _build_record_from_row(
    row: dict[str, Any],
    *,
    learning_global: dict[str, Any],
    meta_ctx: MetaContext | None = None,
) -> dict[str, Any]:
    ticker = str(row.get("Ticker") or row.get("ticker") or "").upper()
    record: dict[str, Any] = {"Ticker": ticker}
    record["Scanner_Score"] = _parse_float(row.get("Score"))
    for field in SCANNER_FIELDS:
        if field in row and row[field] not in (None, ""):
            record[field] = row[field]

    record.update(_pick_columns(row, ENRICHMENT_COLUMNS))
    record.update(_pick_columns(row, RESEARCH_COLUMNS))
    record.update(_pick_columns(row, COMMITTEE_COLUMNS))
    record.update(_pick_columns(row, ALLOCATION_COLUMNS))
    record.update(_pick_columns(row, META_COLUMNS))

    record.update({k: v for k, v in learning_global.items() if v not in (None, "")})

    unified = _parse_float(record.get("Unified_Runtime_Score"))
    if unified is None and meta_ctx is not None:
        unified = meta_ctx.compute_unified_score(row)
        record["Unified_Runtime_Score"] = unified

    record["Unified_Runtime_Confidence"] = _compute_confidence(record)
    record["Unified_Runtime_Recommendation"] = _compute_recommendation(record)
    record["Unified_Runtime_Context"] = _compute_context(record)

    learning_score = _parse_float(learning_global.get("Learning_Health_Score"))
    bonuses = _compute_bonuses(record, learning_score=learning_score)
    record.update(bonuses)
    return record


def build_unified_runtime(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    signals_path = root / "live_signals.csv"
    learning_global = _load_learning_global(root)
    meta_ctx = MetaContext.load(root)

    records: dict[str, dict[str, Any]] = {}

    if signals_path.is_file():
        with signals_path.open(encoding="utf-8", errors="replace", newline="") as handle:
            for row in csv.DictReader(handle):
                ticker = str(row.get("Ticker") or "").upper()
                if not ticker:
                    continue
                records[ticker] = _build_record_from_row(
                    dict(row),
                    learning_global=learning_global,
                    meta_ctx=meta_ctx,
                )

    for artifact_name, _source_kind in TICKER_SOURCES:
        for row in _read_csv_rows(root / artifact_name):
            ticker = str(row.get("Ticker") or "").upper()
            if not ticker or ticker in records:
                continue
            partial = dict(row)
            partial.setdefault("Score", row.get("Score") or row.get("Global_Rank_Score"))
            records[ticker] = _build_record_from_row(
                partial,
                learning_global=learning_global,
                meta_ctx=meta_ctx,
            )
            records[ticker]["source_artifact"] = artifact_name

    records_list = sorted(
        records.values(),
        key=lambda r: _parse_float(r.get("Unified_Runtime_Score")) or 0.0,
        reverse=True,
    )

    top_candidates = [
        {
            "ticker": r["Ticker"],
            "unified_runtime_score": r.get("Unified_Runtime_Score"),
            "unified_runtime_confidence": r.get("Unified_Runtime_Confidence"),
            "unified_runtime_recommendation": r.get("Unified_Runtime_Recommendation"),
            "signal": r.get("Signal"),
            "scanner_score": r.get("Scanner_Score"),
        }
        for r in records_list[:15]
    ]

    scores = [
        _parse_float(r.get("Unified_Runtime_Score"))
        for r in records_list
        if _parse_float(r.get("Unified_Runtime_Score")) is not None
    ]
    confidences = [
        _parse_float(r.get("Unified_Runtime_Confidence"))
        for r in records_list
        if _parse_float(r.get("Unified_Runtime_Confidence")) is not None
    ]

    advisory_summary = {
        "ssot": True,
        "record_count": len(records_list),
        "top_unified_candidates": top_candidates[:10],
        "top_candidates": [c["ticker"] for c in top_candidates[:10]],
        "top_scores": [c["unified_runtime_score"] for c in top_candidates[:10]],
        "confidence_summary": {
            "avg": round(sum(confidences) / len(confidences), 2) if confidences else None,
            "max": max(confidences) if confidences else None,
            "count": len(confidences),
        },
        "unified_runtime_score_summary": {
            "count": len(scores),
            "max": max(scores) if scores else None,
            "avg": round(sum(scores) / len(scores), 2) if scores else None,
        },
        "recommendation_distribution": {},
    }
    for r in records_list:
        rec = str(r.get("Unified_Runtime_Recommendation") or "NEUTRAL")
        advisory_summary["recommendation_distribution"][rec] = (
            advisory_summary["recommendation_distribution"].get(rec, 0) + 1
        )

    return {
        "ok": True,
        "ssot": True,
        "generated_at": _utc_now_iso(),
        "records": records,
        "records_list": records_list,
        "advisory_summary": advisory_summary,
        "learning_global": learning_global,
    }


def write_unified_runtime(root: Path | str = ".") -> dict[str, Any]:
    root = Path(root)
    result = build_unified_runtime(root)
    (root / OUTPUT_JSON).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result
