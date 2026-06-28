"""
Meta Evolution Engine — Phase X Sprint X.2B

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION | RECOMMENDATION_ONLY

Evidence-based evolution advisor above Meta Intelligence.
Reads canonical reports only — advisory output for human review.
Does not execute promotions, retirements, or strategy changes.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from research_core.meta_intelligence.meta_evolution_report import (
    ALLOWED_ACTION,
    EvolutionRecommendation,
    MetaEvolutionReport,
    MetaEvolutionVerdict,
    RecommendationCategory,
)
from research_core.meta_intelligence.meta_intelligence_constants import (
    BASELINE_CANDIDATE_ID,
    PROTECTED_PATHS,
)

logger = logging.getLogger(__name__)

EVOLUTION_CANONICAL_INPUTS: dict[str, Path] = {
    "meta_intelligence": Path("tae_meta_intelligence.json"),
    "strategy_evolution_daily_runner": Path("tae_strategy_evolution_daily_runner.json"),
    "continuous_strategy_ranking": Path("tae_continuous_strategy_ranking.json"),
    "candidate_strategy_registry": Path("tae_candidate_strategy_registry.json"),
    "parallel_paper_validation": Path("tae_parallel_paper_validation.json"),
    "paper_tracking_log": Path("tae_paper_tracking_log.json"),
    "strategic_performance_audit": Path("tae_strategic_performance_audit.json"),
    "daily_intelligence_report": Path("tae_daily_intelligence_report.json"),
    "runtime_foundation": Path("tae_runtime_foundation.json"),
}

MIN_REQUIRED_INPUTS = 7
MIN_TRADES_FOR_PROMOTION_REVIEW = 20


class MetaEvolutionEngine:
    """Produces evidence-based evolution recommendations from canonical reports."""

    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)
        self._payloads: dict[str, dict[str, Any] | None] = {}
        self._sources_loaded: dict[str, bool] = {}
        self._warnings: list[str] = []
        self._rec_counter = 0

    def analyze(self) -> MetaEvolutionReport:
        before_mtimes = self._snapshot_mtimes()
        self._load_all()
        after_mtimes = self._snapshot_mtimes()
        protected_ok = self._mtimes_unchanged(before_mtimes, after_mtimes)

        loaded_count = sum(1 for loaded in self._sources_loaded.values() if loaded)
        meta = self._payloads.get("meta_intelligence") or {}
        meta_verdict = str(meta.get("verdict", "")) if meta else None

        recommendations = self._build_recommendations()
        if not recommendations:
            recommendations = [self._make_recommendation(
                category=RecommendationCategory.NO_ACTION,
                target="ecosystem",
                evidence=["tae_meta_intelligence.json"],
                confidence=0.75,
                rationale=(
                    "Ecosystem stable with no urgent evolution actions identified. "
                    "Continue daily Full Ecosystem Run and paper tracking."
                ),
                risk_level="LOW",
                human_review=False,
            )]

        summary = self._summarize(recommendations)
        verdict = self._determine_verdict(loaded_count, meta)

        if not protected_ok:
            self._warnings.append("Protected file mtimes changed during meta evolution analysis")

        return MetaEvolutionReport(
            verdict=verdict,
            recommendations=recommendations,
            sources_loaded=dict(self._sources_loaded),
            sources_loaded_count=loaded_count,
            meta_intelligence_verdict=meta_verdict,
            recommendation_summary=summary,
            warnings=list(self._warnings),
            protected_files_unchanged=protected_ok,
        )

    def _load_all(self) -> None:
        for name, rel_path in EVOLUTION_CANONICAL_INPUTS.items():
            payload = self._load_json(rel_path)
            self._payloads[name] = payload
            self._sources_loaded[name] = payload is not None
            if payload is None:
                self._warnings.append(f"Missing canonical input: {rel_path.name}")

    def _build_recommendations(self) -> list[EvolutionRecommendation]:
        recs: list[EvolutionRecommendation] = []

        meta = self._payloads.get("meta_intelligence") or {}
        if not meta:
            return recs

        obs = meta.get("strategic_observations") or {}
        daily_runner = self._payloads.get("strategy_evolution_daily_runner") or {}
        ranking = self._payloads.get("continuous_strategy_ranking") or {}
        registry = self._payloads.get("candidate_strategy_registry") or {}
        validation = self._payloads.get("parallel_paper_validation") or {}
        paper_tracking = self._payloads.get("paper_tracking_log") or {}
        performance = self._payloads.get("strategic_performance_audit") or {}
        governance = self._payloads.get("daily_intelligence_report") or {}
        runtime = self._payloads.get("runtime_foundation") or {}

        rankings = self._list_items(ranking, "rankings")
        validations = self._list_items(validation, "validations")
        tracking_entries = self._list_items(paper_tracking, "entries")
        candidates = self._list_items(registry, "candidates")

        review_id = daily_runner.get("promotion_review_candidate_id")
        meta_confidence = (obs.get("overall_ecosystem_confidence") or {}).get(
            "composite_score", 0.7
        )

        recs.extend(self._recommend_promote_or_continue(
            obs, daily_runner, review_id, rankings, tracking_entries, meta_confidence
        ))
        recs.extend(self._recommend_retire_or_freeze(obs, rankings, tracking_entries))
        recs.extend(self._recommend_investigate(
            obs, rankings, validations, performance, meta_confidence
        ))
        recs.extend(self._recommend_data_quality(governance, runtime, meta))
        recs.extend(self._recommend_new_experiments(candidates, obs, meta_confidence))

        return self._dedupe_recommendations(recs)

    def _recommend_promote_or_continue(
        self,
        obs: dict[str, Any],
        daily_runner: dict[str, Any],
        review_id: str | None,
        rankings: list[dict[str, Any]],
        tracking_entries: list[dict[str, Any]],
        meta_confidence: float,
    ) -> list[EvolutionRecommendation]:
        recs: list[EvolutionRecommendation] = []
        ranking_by_id = {
            item.get("candidate_id"): item
            for item in rankings
            if isinstance(item, dict)
        }

        if review_id:
            rank_item = ranking_by_id.get(review_id, {})
            recs.append(self._make_recommendation(
                category=RecommendationCategory.PROMOTE_CANDIDATE,
                target=str(review_id),
                evidence=[
                    "tae_meta_intelligence.json",
                    "tae_strategy_evolution_daily_runner.json",
                    "tae_continuous_strategy_ranking.json",
                ],
                confidence=min(float(meta_confidence) * 0.95, 0.99),
                rationale=(
                    f"Daily runner flagged {review_id} for promotion review. "
                    "Human review required before any promotion decision."
                ),
                risk_level="HIGH",
                human_review=True,
            ))

        for promo in obs.get("promotion_candidates") or []:
            if not isinstance(promo, dict):
                continue
            cid = promo.get("candidate_id")
            if not cid or cid == review_id:
                continue
            trades_needed = int(promo.get("trades_needed") or 0)
            current_trades = int(promo.get("current_trades") or 0)
            score = float(promo.get("ranking_score") or 0)

            if current_trades >= MIN_TRADES_FOR_PROMOTION_REVIEW and score >= 0.85:
                recs.append(self._make_recommendation(
                    category=RecommendationCategory.PROMOTE_CANDIDATE,
                    target=str(cid),
                    evidence=[
                        "tae_meta_intelligence.json",
                        "tae_paper_tracking_log.json",
                        "tae_parallel_paper_validation.json",
                    ],
                    confidence=min(score * float(meta_confidence), 0.95),
                    rationale=(
                        f"{cid} reached {current_trades} trades with ranking score "
                        f"{score:.4f}. Schedule human promotion review — advisory only."
                    ),
                    risk_level="HIGH",
                    human_review=True,
                ))
            elif trades_needed > 0:
                recs.append(self._make_recommendation(
                    category=RecommendationCategory.CONTINUE_PAPER_TRACKING,
                    target=str(cid),
                    evidence=[
                        "tae_meta_intelligence.json",
                        "tae_paper_tracking_log.json",
                        "tae_strategy_evolution_daily_runner.json",
                    ],
                    confidence=min(score * float(meta_confidence) * 0.9, 0.9),
                    rationale=(
                        f"Continue paper tracking for {cid}: {current_trades} trades recorded, "
                        f"{trades_needed} more needed before promotion sample threshold."
                    ),
                    risk_level="LOW",
                    human_review=True,
                ))

        for entry in tracking_entries:
            if not isinstance(entry, dict):
                continue
            cid = entry.get("candidate_id")
            if cid == BASELINE_CANDIDATE_ID:
                continue
            if str(entry.get("tracking_status", "")) != "TRACKING_ACTIVE":
                continue
            if any(r.target_strategy_or_module == cid for r in recs):
                continue
            recs.append(self._make_recommendation(
                category=RecommendationCategory.CONTINUE_PAPER_TRACKING,
                target=str(cid),
                evidence=["tae_paper_tracking_log.json", "tae_meta_intelligence.json"],
                confidence=min(float(meta_confidence) * 0.85, 0.85),
                rationale=(
                    f"Active paper tracking for {cid} — maintain PAPER_ONLY observation "
                    "until validation sample is sufficient."
                ),
                risk_level="LOW",
                human_review=True,
            ))

        return recs

    def _recommend_retire_or_freeze(
        self,
        obs: dict[str, Any],
        rankings: list[dict[str, Any]],
        tracking_entries: list[dict[str, Any]],
    ) -> list[EvolutionRecommendation]:
        recs: list[EvolutionRecommendation] = []
        ranking_by_id = {
            item.get("candidate_id"): item
            for item in rankings
            if isinstance(item, dict)
        }

        for retire in obs.get("retirement_candidates") or []:
            if not isinstance(retire, dict):
                continue
            cid = retire.get("candidate_id")
            if not cid:
                continue
            rank_item = ranking_by_id.get(cid, {})
            score = float(retire.get("ranking_score") or rank_item.get("ranking_score") or 0)
            recs.append(self._make_recommendation(
                category=RecommendationCategory.RETIRE_OR_FREEZE_CANDIDATE,
                target=str(cid),
                evidence=[
                    "tae_meta_intelligence.json",
                    "tae_continuous_strategy_ranking.json",
                    "tae_paper_tracking_log.json",
                ],
                confidence=max(0.55, min(1.0 - score, 0.85)),
                rationale=(
                    f"Consider freezing or retiring {cid}: {retire.get('reason', 'weak metrics')}. "
                    "Human review required — no automatic retirement."
                ),
                risk_level="MEDIUM",
                human_review=True,
            ))

        for entry in tracking_entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("tracking_status", "")) != "BLOCKED":
                continue
            cid = entry.get("candidate_id")
            if not cid or any(
                r.target_strategy_or_module == cid
                and r.category == RecommendationCategory.RETIRE_OR_FREEZE_CANDIDATE.value
                for r in recs
            ):
                continue
            recs.append(self._make_recommendation(
                category=RecommendationCategory.RETIRE_OR_FREEZE_CANDIDATE,
                target=str(cid),
                evidence=["tae_paper_tracking_log.json", "tae_meta_intelligence.json"],
                confidence=0.7,
                rationale=(
                    f"{cid} is BLOCKED in paper tracking ({entry.get('tracking_note', '')}). "
                    "Review for freeze/retirement or redesign experiment."
                ),
                risk_level="MEDIUM",
                human_review=True,
            ))

        return recs

    def _recommend_investigate(
        self,
        obs: dict[str, Any],
        rankings: list[dict[str, Any]],
        validations: list[dict[str, Any]],
        performance: dict[str, Any],
        meta_confidence: float,
    ) -> list[EvolutionRecommendation]:
        recs: list[EvolutionRecommendation] = []

        weakest = obs.get("weakest_strategy") or {}
        if isinstance(weakest, dict):
            cid = weakest.get("candidate_id")
            delta = None
            for item in rankings:
                if isinstance(item, dict) and item.get("candidate_id") == cid:
                    delta = item.get("delta_vs_baseline_total_pnl")
                    break
            if cid and cid != BASELINE_CANDIDATE_ID and isinstance(delta, (int, float)) and delta < 0:
                recs.append(self._make_recommendation(
                    category=RecommendationCategory.INVESTIGATE_UNDERPERFORMANCE,
                    target=str(cid),
                    evidence=[
                        "tae_meta_intelligence.json",
                        "tae_continuous_strategy_ranking.json",
                        "tae_parallel_paper_validation.json",
                    ],
                    confidence=min(float(meta_confidence) * 0.8, 0.8),
                    rationale=(
                        f"{cid} underperforms baseline by {delta:.2f} total PnL. "
                        "Investigate rule definition and sample quality before further tracking."
                    ),
                    risk_level="MEDIUM",
                    human_review=True,
                ))

        perf = performance.get("trade_quality") or {}
        if isinstance(perf, dict):
            pf = perf.get("profit_factor")
            if isinstance(pf, (int, float)) and float(pf) < 1.0:
                recs.append(self._make_recommendation(
                    category=RecommendationCategory.INVESTIGATE_UNDERPERFORMANCE,
                    target=BASELINE_CANDIDATE_ID,
                    evidence=[
                        "tae_strategic_performance_audit.json",
                        "tae_meta_intelligence.json",
                    ],
                    confidence=0.75,
                    rationale=(
                        f"Live baseline profit factor {float(pf):.4f} below 1.0 in strategic "
                        "performance audit. Investigate live execution quality — review only."
                    ),
                    risk_level="MEDIUM",
                    human_review=True,
                ))

        for val in validations:
            if not isinstance(val, dict):
                continue
            cid = val.get("candidate_id")
            if cid == BASELINE_CANDIDATE_ID:
                continue
            if (
                val.get("validation_status") == "INSUFFICIENT_SAMPLE"
                and not val.get("beats_baseline_total_pnl")
                and float(val.get("delta_vs_baseline_total_pnl") or 0) < -50
            ):
                if any(r.target_strategy_or_module == cid for r in recs):
                    continue
                recs.append(self._make_recommendation(
                    category=RecommendationCategory.INVESTIGATE_UNDERPERFORMANCE,
                    target=str(cid),
                    evidence=[
                        "tae_parallel_paper_validation.json",
                        "tae_meta_intelligence.json",
                    ],
                    confidence=0.65,
                    rationale=(
                        f"{cid} shows insufficient sample with material negative baseline delta. "
                        "Investigate before allocating more paper tracking capacity."
                    ),
                    risk_level="MEDIUM",
                    human_review=True,
                ))

        return recs

    def _recommend_data_quality(
        self,
        governance: dict[str, Any],
        runtime: dict[str, Any],
        meta: dict[str, Any],
    ) -> list[EvolutionRecommendation]:
        recs: list[EvolutionRecommendation] = []

        critical_count = len(governance.get("critical_issues") or [])
        gov_summary = (meta.get("strategic_observations") or {}).get("governance_summary") or {}
        if isinstance(gov_summary, dict):
            critical_count = max(
                critical_count,
                int(gov_summary.get("critical_issues_count") or 0),
            )

        if critical_count >= 5:
            recs.append(self._make_recommendation(
                category=RecommendationCategory.IMPROVE_DATA_QUALITY,
                target="governance/research_pipeline",
                evidence=[
                    "tae_daily_intelligence_report.json",
                    "tae_meta_intelligence.json",
                ],
                confidence=0.7,
                rationale=(
                    f"Governance reports {critical_count} critical issues (regional validation, "
                    "legacy data gaps). Improve evidence and validation data quality before "
                    "strategy evolution decisions."
                ),
                risk_level="LOW",
                human_review=True,
            ))

        health_issues = runtime.get("health_issues") or []
        if isinstance(health_issues, list) and health_issues:
            recs.append(self._make_recommendation(
                category=RecommendationCategory.IMPROVE_DATA_QUALITY,
                target="runtime/state_sources",
                evidence=["tae_runtime_foundation.json", "tae_meta_intelligence.json"],
                confidence=0.72,
                rationale=(
                    f"Runtime reports {len(health_issues)} health issue(s). "
                    "Refresh canonical JSON artifacts via Full Ecosystem Run."
                ),
                risk_level="LOW",
                human_review=True,
            ))

        loaded_count = sum(self._sources_loaded.values())
        if loaded_count < len(EVOLUTION_CANONICAL_INPUTS):
            recs.append(self._make_recommendation(
                category=RecommendationCategory.IMPROVE_DATA_QUALITY,
                target="canonical_reports",
                evidence=["tae_meta_evolution.json"],
                confidence=0.8,
                rationale=(
                    f"Only {loaded_count}/{len(EVOLUTION_CANONICAL_INPUTS)} evolution inputs loaded. "
                    "Run tae_full_ecosystem_run.py to regenerate missing canonical reports."
                ),
                risk_level="LOW",
                human_review=True,
            ))

        return recs

    def _recommend_new_experiments(
        self,
        candidates: list[dict[str, Any]],
        obs: dict[str, Any],
        meta_confidence: float,
    ) -> list[EvolutionRecommendation]:
        recs: list[EvolutionRecommendation] = []
        non_baseline = [
            c for c in candidates
            if isinstance(c, dict) and c.get("candidate_id") != BASELINE_CANDIDATE_ID
        ]
        if len(non_baseline) <= 2:
            maturity = (obs.get("system_maturity") or {}).get("maturity_level", "")
            recs.append(self._make_recommendation(
                category=RecommendationCategory.LAUNCH_NEW_EXPERIMENT,
                target="simulation_lab/strategy_evolution",
                evidence=[
                    "tae_candidate_strategy_registry.json",
                    "tae_meta_intelligence.json",
                ],
                confidence=min(float(meta_confidence) * 0.75, 0.78),
                rationale=(
                    f"Only {len(non_baseline)} non-baseline candidate(s) in registry. "
                    f"System maturity {maturity} — consider launching new simulation "
                    "experiments to broaden strategy search space."
                ),
                risk_level="LOW",
                human_review=True,
            ))
        return recs

    def _make_recommendation(
        self,
        category: RecommendationCategory,
        target: str,
        evidence: list[str],
        confidence: float,
        rationale: str,
        risk_level: str,
        human_review: bool,
    ) -> EvolutionRecommendation:
        self._rec_counter += 1
        return EvolutionRecommendation(
            recommendation_id=f"MEV-{self._rec_counter:03d}",
            category=category.value,
            target_strategy_or_module=target,
            evidence_sources=evidence,
            confidence_score=max(0.0, min(confidence, 1.0)),
            rationale=rationale,
            risk_level=risk_level,
            required_human_review=human_review,
            allowed_action=ALLOWED_ACTION,
        )

    @staticmethod
    def _dedupe_recommendations(
        recs: list[EvolutionRecommendation],
    ) -> list[EvolutionRecommendation]:
        seen: set[tuple[str, str]] = set()
        unique: list[EvolutionRecommendation] = []
        for rec in recs:
            key = (rec.category, rec.target_strategy_or_module)
            if key in seen:
                continue
            seen.add(key)
            unique.append(rec)
        return unique

    @staticmethod
    def _summarize(recs: list[EvolutionRecommendation]) -> dict[str, int]:
        summary: dict[str, int] = {}
        for rec in recs:
            summary[rec.category] = summary.get(rec.category, 0) + 1
        return summary

    def _determine_verdict(
        self,
        loaded_count: int,
        meta: dict[str, Any],
    ) -> MetaEvolutionVerdict:
        if not meta or loaded_count < MIN_REQUIRED_INPUTS:
            return MetaEvolutionVerdict.META_EVOLUTION_INSUFFICIENT_DATA

        if self._warnings or loaded_count < len(EVOLUTION_CANONICAL_INPUTS):
            return MetaEvolutionVerdict.META_EVOLUTION_READY_WITH_WARNINGS

        meta_verdict = str(meta.get("verdict", ""))
        if meta_verdict.endswith("INSUFFICIENT_DATA"):
            return MetaEvolutionVerdict.META_EVOLUTION_READY_WITH_WARNINGS

        return MetaEvolutionVerdict.META_EVOLUTION_READY

    @staticmethod
    def _list_items(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
        items = payload.get(key, [])
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def _load_json(self, path: Path) -> dict[str, Any] | None:
        full = self._root / path
        if not full.is_file():
            return None
        try:
            payload = json.loads(full.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read %s: %s", path, exc)
            return None
        return payload if isinstance(payload, dict) else None

    def _snapshot_mtimes(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for path in PROTECTED_PATHS:
            full = self._root / path
            if full.is_file():
                out[str(path)] = full.stat().st_mtime
        return out

    @staticmethod
    def _mtimes_unchanged(before: dict[str, float], after: dict[str, float]) -> bool:
        for key, mtime in before.items():
            if key not in after or after[key] != mtime:
                return False
        return True
