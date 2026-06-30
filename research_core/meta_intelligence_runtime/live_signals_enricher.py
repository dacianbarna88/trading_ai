"""Live signals meta intelligence enricher + unified runtime score."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

META_COLUMNS = (
    "Meta_Score",
    "Meta_Confidence",
    "Meta_Health",
    "Meta_Strategy_Rank",
    "Meta_Ecosystem_Status",
    "Meta_Recommendation",
    "Meta_Context",
    "Unified_Runtime_Score",
)

ARTIFACT_FILES = {
    "meta_intelligence": "tae_meta_intelligence.json",
    "strategy_ranking": "tae_continuous_strategy_ranking.json",
    "strategy_registry": "tae_candidate_strategy_registry.json",
    "orchestrator": "tae_ecosystem_orchestrator.json",
    "full_ecosystem_run": "tae_full_ecosystem_run.json",
    "ecosystem_review": "tae_full_ecosystem_review.json",
    "quick_health": "tae_quick_health_check.json",
    "performance_audit": "tae_strategic_performance_audit.json",
    "historical_analysis": "tae_historical_results_analysis.json",
    "advisory_index": "tae_advisory_index.json",
    "learning_runtime": "tae_learning_runtime.json",
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _extract_verdict(payload: dict[str, Any] | None) -> str | None:
    if not payload:
        return None
    for key in ("verdict", "final_verdict", "dominant_status"):
        val = payload.get(key)
        if val:
            return str(val)
    final = payload.get("J_final_verdict") or {}
    if isinstance(final, dict) and final.get("ecosystem_verdict"):
        return str(final["ecosystem_verdict"])
    return None


@dataclass
class MetaContext:
    meta_score: float | None
    meta_confidence: float | None
    meta_health: str
    strategy_rank: int | None
    top_strategy_id: str | None
    ecosystem_status: str
    recommendation: str
    orchestrator_verdict: str | None
    quick_health_verdict: str | None
    advisory_index_status: str | None
    learning_health_score: float | None
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> MetaContext:
        root = Path(root)
        artifacts_loaded = {
            name: (root / fname).is_file() for name, fname in ARTIFACT_FILES.items()
        }

        meta = _load_json(root / ARTIFACT_FILES["meta_intelligence"]) or {}
        obs = meta.get("strategic_observations") or {}
        confidence_block = obs.get("overall_ecosystem_confidence") or {}
        composite = _parse_float(confidence_block.get("composite_score"))
        meta_score = round(composite * 100, 2) if composite is not None else None
        label = str(confidence_block.get("confidence_label") or "UNKNOWN")
        meta_confidence = meta_score
        if label == "HIGH" and meta_confidence is not None:
            meta_confidence = min(100.0, meta_confidence + 2.0)
        elif label == "LOW" and meta_confidence is not None:
            meta_confidence = max(0.0, meta_confidence - 10.0)

        runtime_health = obs.get("runtime_health_summary") or {}
        meta_health = str(
            runtime_health.get("health_status")
            or (_load_json(root / ARTIFACT_FILES["quick_health"]) or {}).get("verdict")
            or "UNKNOWN"
        )

        ranking = _load_json(root / ARTIFACT_FILES["strategy_ranking"]) or {}
        rankings = list(ranking.get("rankings") or [])
        strategy_rank = None
        top_strategy_id = None
        if rankings and isinstance(rankings[0], dict):
            top_strategy_id = str(rankings[0].get("candidate_id") or "")
            strategy_rank = rankings[0].get("rank")
            if strategy_rank is None:
                strategy_rank = 1

        highest = obs.get("highest_quality_strategy") or {}
        if not top_strategy_id:
            top_strategy_id = str(highest.get("candidate_id") or "N/A")

        review = _load_json(root / ARTIFACT_FILES["ecosystem_review"]) or {}
        ecosystem_status = (
            _extract_verdict(review)
            or str(meta.get("verdict") or "UNKNOWN")
        )

        recommendation = str(
            highest.get("decision")
            or meta.get("verdict")
            or "OBSERVE"
        )
        promos = obs.get("promotion_candidates") or []
        if promos and isinstance(promos[0], dict):
            recommendation = f"{recommendation}|TOP={promos[0].get('candidate_id')}"

        orchestrator = _load_json(root / ARTIFACT_FILES["orchestrator"]) or {}
        quick = _load_json(root / ARTIFACT_FILES["quick_health"]) or {}
        advisory_index = _load_json(root / ARTIFACT_FILES["advisory_index"]) or {}
        learning = _load_json(root / ARTIFACT_FILES["learning_runtime"]) or {}
        learning_score = _parse_float(
            (learning.get("advisory_summary") or {}).get("learning_health_score")
        )

        return cls(
            meta_score=meta_score,
            meta_confidence=meta_confidence,
            meta_health=meta_health,
            strategy_rank=int(strategy_rank) if strategy_rank is not None else None,
            top_strategy_id=top_strategy_id,
            ecosystem_status=str(ecosystem_status),
            recommendation=recommendation,
            orchestrator_verdict=_extract_verdict(orchestrator),
            quick_health_verdict=str(quick.get("verdict") or ""),
            advisory_index_status=str(advisory_index.get("dominant_status") or advisory_index.get("verdict") or ""),
            learning_health_score=learning_score,
            artifacts_loaded=artifacts_loaded,
        )

    def _layer_score(self, ctx: dict[str, Any], key: str) -> float | None:
        return _parse_float(ctx.get(key))

    def compute_unified_score(self, ctx: dict[str, Any]) -> float:
        weights: list[tuple[float | None, float]] = [
            (self._layer_score(ctx, "Score"), 0.22),
            (self._layer_score(ctx, "Historical_Confidence"), 0.12),
            (self._layer_score(ctx, "Research_Confidence"), 0.12),
            (self._layer_score(ctx, "Committee_Confidence"), 0.12),
            (self._layer_score(ctx, "Allocation_Score"), 0.12),
            (self.meta_score, 0.18),
            (self.learning_health_score, 0.06),
            (self._layer_score(ctx, "Allocation_Confidence"), 0.06),
        ]
        total_w = 0.0
        weighted = 0.0
        for value, weight in weights:
            if value is None:
                continue
            weighted += value * weight
            total_w += weight
        if total_w <= 0:
            return _parse_float(ctx.get("Score")) or 0.0
        return round(weighted / total_w, 2)

    def enrich_ticker(self, ticker: str, signal: str = "", score: Any = None, row: dict | None = None) -> dict[str, Any]:
        ctx = row or {}
        if score is None:
            score = ctx.get("Score")

        ticker_score = self.meta_score or 50.0
        signal_u = str(signal or ctx.get("Signal") or "").upper()
        if signal_u == "STRONG BUY" and self.meta_confidence and self.meta_confidence >= 80:
            ticker_score = min(100.0, ticker_score + 3.0)
        elif signal_u == "TAKE PROFIT":
            ticker_score = max(0.0, ticker_score - 2.0)

        unified = self.compute_unified_score({**ctx, "Score": score})

        ctx_parts = [
            f"meta_score={ticker_score}",
            f"ecosystem={self.ecosystem_status}",
            f"health={self.meta_health}",
            f"strategy={self.top_strategy_id}",
            f"rank={self.strategy_rank}",
            f"recommendation={self.recommendation}",
            f"unified={unified}",
        ]
        if signal:
            ctx_parts.append(f"signal={signal}")
        if score is not None:
            ctx_parts.append(f"score={score}")

        return {
            "Meta_Score": round(ticker_score, 2),
            "Meta_Confidence": self.meta_confidence,
            "Meta_Health": self.meta_health,
            "Meta_Strategy_Rank": self.strategy_rank,
            "Meta_Ecosystem_Status": self.ecosystem_status,
            "Meta_Recommendation": self.recommendation,
            "Meta_Context": "; ".join(ctx_parts),
            "Unified_Runtime_Score": unified,
        }

    def advisory_summary(self) -> dict[str, Any]:
        return {
            "meta_summary": (
                f"score={self.meta_score} health={self.meta_health} "
                f"ecosystem={self.ecosystem_status} strategy={self.top_strategy_id}"
            ),
            "meta_confidence": self.meta_confidence,
            "meta_health": self.meta_health,
            "ecosystem_health": self.ecosystem_status,
            "strategy_rank": self.strategy_rank,
            "top_strategy_id": self.top_strategy_id,
            "recommendation": self.recommendation,
            "orchestrator_verdict": self.orchestrator_verdict,
            "quick_health_verdict": self.quick_health_verdict,
            "advisory_index_status": self.advisory_index_status,
            "artifacts_loaded": self.artifacts_loaded,
        }


def enrich_live_signals_file(
    root: Path | str = ".",
    *,
    signals_path: str = "live_signals.csv",
) -> dict[str, Any]:
    root = Path(root)
    path = root / signals_path
    if not path.is_file():
        return {"ok": False, "error": f"Missing {signals_path}", "rows": 0}

    ctx = MetaContext.load(root)
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"ok": False, "error": "Empty live_signals.csv", "rows": 0}

    fieldnames = list(rows[0].keys())
    for col in META_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    enriched = 0
    strong_buy_meta: list[dict[str, Any]] = []
    unified_candidates: list[dict[str, Any]] = []

    for row in rows:
        ticker = str(row.get("Ticker") or "").upper()
        enrichment = ctx.enrich_ticker(
            ticker,
            signal=str(row.get("Signal") or ""),
            score=row.get("Score"),
            row=row,
        )
        row.update(enrichment)
        enriched += 1
        unified_candidates.append(
            {
                "ticker": ticker,
                "unified_runtime_score": enrichment.get("Unified_Runtime_Score"),
                "meta_score": enrichment.get("Meta_Score"),
                "signal": row.get("Signal"),
            }
        )
        if str(row.get("Signal", "")).upper() == "STRONG BUY":
            strong_buy_meta.append({"ticker": ticker, **enrichment})

    unified_candidates.sort(
        key=lambda x: _parse_float(x.get("unified_runtime_score")) or 0,
        reverse=True,
    )
    strong_buy_meta.sort(
        key=lambda x: _parse_float(x.get("Meta_Score")) or 0,
        reverse=True,
    )

    advisory = ctx.advisory_summary()
    advisory["top_unified_candidates"] = unified_candidates[:10]
    advisory["top_meta_candidates"] = [
        {
            "ticker": c["ticker"],
            "meta_score": c.get("Meta_Score"),
            "meta_confidence": c.get("Meta_Confidence"),
            "unified_runtime_score": c.get("Unified_Runtime_Score"),
        }
        for c in strong_buy_meta[:10]
    ]
    unified_scores = [_parse_float(c.get("unified_runtime_score")) for c in unified_candidates]
    unified_scores = [v for v in unified_scores if v is not None]
    advisory["unified_runtime_score_summary"] = {
        "count": len(unified_scores),
        "max": max(unified_scores) if unified_scores else None,
        "avg": round(sum(unified_scores) / len(unified_scores), 2) if unified_scores else None,
    }

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    strong_buy = sum(1 for r in rows if str(r.get("Signal", "")).upper() == "STRONG BUY")
    return {
        "ok": True,
        "rows": len(rows),
        "enriched": enriched,
        "strong_buy_count": strong_buy,
        "strong_buy_meta_summary": strong_buy_meta[:10],
        "advisory_summary": advisory,
        "artifacts_loaded": ctx.artifacts_loaded,
    }
