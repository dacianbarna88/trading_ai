"""
Confidence recalibrator — Phase VI Sprint B4

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Recalibrates TAE research confidence after accounting integrity fix — read-only analysis.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.recalibration.recalibration_report import (
    CandidateRecalibration,
    ConfidenceRecalibrationReport,
    ConfidenceStability,
    EcosystemMetrics,
    PortfolioAccountingComparison,
    RecalibrationStore,
)

logger = logging.getLogger(__name__)

PORTFOLIO_PATH = Path("portfolio.csv")
LEARNING_REPORT_PATH = Path("tae_learning_report.json")
DISCOVERIES_PATH = Path("tae_discoveries.json")
KNOWLEDGE_CANDIDATES_PATH = Path("tae_knowledge_candidates.json")
CROSS_VALIDATION_PATH = Path("tae_cross_validation_report.json")
RESEARCH_PRIORITIES_PATH = Path("tae_research_priorities.json")
STRATEGY_RECOMMENDATIONS_PATH = Path("tae_strategy_recommendations.json")
EVOLUTION_PLAN_PATH = Path("tae_strategy_evolution_plan.json")
IMPLEMENTATION_PATCH_PATH = Path("tae_implementation_patch.json")
PATCH_REVIEW_PATH = Path("tae_patch_review.json")
EVIDENCE_HISTORY_PATH = Path("tae_evidence_history.json")
EVIDENCE_GAP_PATH = Path("tae_evidence_gap_report.json")
STRATEGIC_PERFORMANCE_PATH = Path("tae_strategic_performance_audit.json")
ACCOUNTING_INTEGRITY_PATH = Path("tae_accounting_integrity_audit.json")

ALL_SOURCE_PATHS = (
    PORTFOLIO_PATH,
    LEARNING_REPORT_PATH,
    DISCOVERIES_PATH,
    KNOWLEDGE_CANDIDATES_PATH,
    CROSS_VALIDATION_PATH,
    RESEARCH_PRIORITIES_PATH,
    STRATEGY_RECOMMENDATIONS_PATH,
    EVOLUTION_PLAN_PATH,
    IMPLEMENTATION_PATCH_PATH,
    PATCH_REVIEW_PATH,
    EVIDENCE_HISTORY_PATH,
    EVIDENCE_GAP_PATH,
    STRATEGIC_PERFORMANCE_PATH,
    ACCOUNTING_INTEGRITY_PATH,
)

# Small trust restoration after accounting fix — research cross-validation unaffected.
ACCOUNTING_TRUST_BOOST = 2.5
EVIDENCE_SCORE_TRUST_BOOST = 0.8
STABILITY_THRESHOLD = 0.5
EUROPE_UK_BLOCKER = "Europe/UK regional validation missing"


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _load_portfolio_sells(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    rows: list[dict[str, str]] = []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                if str(row.get("Action", "")).upper() == "SELL":
                    rows.append(dict(row))
    except OSError as exc:
        logger.warning("Could not read portfolio %s: %s", path, exc)
    return rows


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _confidence_stability(delta: float) -> ConfidenceStability:
    if delta > STABILITY_THRESHOLD:
        return ConfidenceStability.INCREASED
    if delta < -STABILITY_THRESHOLD:
        return ConfidenceStability.DECREASED
    return ConfidenceStability.UNCHANGED


def _composite_rank_score(confidence: float, evidence_score: float) -> float:
    """Blend gap/recommendation confidence with evidence score (0–100 scale)."""
    normalized_evidence = min(100.0, evidence_score * 4.0)
    return confidence * 0.65 + normalized_evidence * 0.35


def _has_europe_uk_gap(blocking_items: list[str], missing_evidence: list[Any]) -> bool:
    if EUROPE_UK_BLOCKER in blocking_items:
        return True
    for item in missing_evidence:
        text = ""
        if isinstance(item, dict):
            text = str(item.get("description", "")) + str(item.get("gap_id", ""))
        else:
            text = str(item)
        if "Europe" in text or "UK" in text:
            return True
    return False


class ConfidenceRecalibrator:
    """Read-only recalibration of TAE research confidence after accounting fix."""

    def __init__(
        self,
        store: RecalibrationStore | None = None,
        source_paths: dict[str, Path] | None = None,
    ) -> None:
        self._store = store or RecalibrationStore()
        self._paths = {
            "portfolio": PORTFOLIO_PATH,
            "learning_report": LEARNING_REPORT_PATH,
            "discoveries": DISCOVERIES_PATH,
            "knowledge_candidates": KNOWLEDGE_CANDIDATES_PATH,
            "cross_validation": CROSS_VALIDATION_PATH,
            "research_priorities": RESEARCH_PRIORITIES_PATH,
            "strategy_recommendations": STRATEGY_RECOMMENDATIONS_PATH,
            "evolution_plan": EVOLUTION_PLAN_PATH,
            "implementation_patch": IMPLEMENTATION_PATCH_PATH,
            "patch_review": PATCH_REVIEW_PATH,
            "evidence_history": EVIDENCE_HISTORY_PATH,
            "evidence_gap": EVIDENCE_GAP_PATH,
            "strategic_performance": STRATEGIC_PERFORMANCE_PATH,
            "accounting_integrity": ACCOUNTING_INTEGRITY_PATH,
        }
        if source_paths:
            self._paths.update(source_paths)
        self._sources_loaded: dict[str, bool] = {}
        self._artifacts: dict[str, dict[str, Any] | None] = {}

    def recalibrate(self) -> ConfidenceRecalibrationReport:
        self._load_all_sources()
        accounting = self._build_accounting_comparison()
        candidates = self._recalibrate_candidates(accounting)
        ecosystem = self._build_ecosystem_metrics(candidates, accounting)
        next_action = self._next_research_action(candidates, ecosystem)

        report = ConfidenceRecalibrationReport(
            accounting_comparison=accounting,
            candidates=candidates,
            ecosystem=ecosystem,
            next_recommended_research_action=next_action,
            sources_loaded=dict(self._sources_loaded),
            generated_at=datetime.now(timezone.utc),
        )
        self._store.persist(report)
        self._store.persist_txt(report)
        return report

    def _load_all_sources(self) -> None:
        for key, path in self._paths.items():
            if key == "portfolio":
                loaded = path.is_file()
                self._artifacts[key] = {"path": str(path)} if loaded else None
            else:
                payload = _load_json(path)
                self._artifacts[key] = payload
                loaded = payload is not None
            self._sources_loaded[key] = loaded

    def _build_accounting_comparison(self) -> PortfolioAccountingComparison:
        perf = self._artifacts.get("strategic_performance") or {}
        audit = self._artifacts.get("accounting_integrity") or {}
        portfolio_sells = _load_portfolio_sells(self._paths["portfolio"])

        legacy_pnl = _safe_float(
            (perf.get("performance") or {}).get("all_history_realized_pnl")
        )
        legacy_win_rate = _safe_float((perf.get("trade_quality") or {}).get("win_rate"))

        sell_validations = audit.get("sell_validations") or []
        corrected_pnl = sum(_safe_float(s.get("recorded_pnl")) for s in sell_validations)
        corrected_closed = len(sell_validations) or max(len(portfolio_sells), 1)
        corrected_wins = sum(
            1 for s in sell_validations if _safe_float(s.get("recorded_pnl")) > 0
        )
        corrected_win_rate = (corrected_wins / corrected_closed) * 100.0

        portfolio_csv_pnl = sum(_safe_float(r.get("PnL")) for r in portfolio_sells)
        portfolio_matches_audit = abs(portfolio_csv_pnl - corrected_pnl) < 1.0

        legacy_high = self._estimate_legacy_high_severity(
            portfolio_sells, sell_validations, audit
        )
        corrected_high = int(audit.get("high_severity_count", 0))

        notable: list[str] = []
        for focus in audit.get("focus_ticker_audits") or []:
            ticker = focus.get("ticker", "")
            if ticker in ("GS", "ULVR.L", "AAPL", "SIE.DE"):
                for sv in focus.get("sell_validations") or []:
                    pnl = _safe_float(sv.get("recorded_pnl"))
                    reason = sv.get("reason", "")
                    notable.append(f"{ticker}: {reason} → PnL corect {pnl:+.2f}")

        perf_loser = (perf.get("trade_quality") or {}).get("biggest_loser") or {}
        if perf_loser.get("ticker") == "GS" and _safe_float(perf_loser.get("pnl")) < 0:
            notable.append(
                "GS: concluzie legacy 'cel mai mare pierzător' (-909.57) invalidă — "
                "gain real +547.99"
            )

        if not portfolio_matches_audit:
            notable.append(
                f"portfolio.csv încă reflectă PnL legacy ({portfolio_csv_pnl:+.2f}) — "
                f"audit contabil folosește valori corecte ({corrected_pnl:+.2f})"
            )

        conclusions_affected = (
            abs(legacy_pnl - corrected_pnl) > 50.0
            or legacy_high > corrected_high
            or not portfolio_matches_audit
        )

        return PortfolioAccountingComparison(
            legacy_realized_pnl=legacy_pnl,
            corrected_realized_pnl=corrected_pnl,
            realized_pnl_delta=corrected_pnl - legacy_pnl,
            legacy_win_rate=legacy_win_rate,
            corrected_win_rate=corrected_win_rate,
            legacy_high_severity_anomalies=legacy_high,
            corrected_high_severity_anomalies=corrected_high,
            conclusions_affected=conclusions_affected,
            notable_corrections=notable,
        )

    def _estimate_legacy_high_severity(
        self,
        portfolio_sells: list[dict[str, str]],
        sell_validations: list[dict[str, Any]],
        audit: dict[str, Any],
    ) -> int:
        """Estimate pre-fix HIGH anomalies by comparing portfolio.csv vs audit."""
        audit_by_key: dict[tuple[str, str], float] = {}
        for sv in sell_validations:
            key = (sv.get("ticker", ""), sv.get("date", "")[:10])
            audit_by_key[key] = _safe_float(sv.get("recorded_pnl"))

        high = 0
        for row in portfolio_sells:
            ticker = row.get("Ticker", "")
            date = row.get("Date", "")[:10]
            recorded = _safe_float(row.get("PnL"))
            expected = audit_by_key.get((ticker, date))
            if expected is None:
                continue
            if abs(recorded - expected) > 1.0:
                reason = row.get("Reason", "")
                profit_reason = "PROFIT" in reason.upper() or "TAKE PROFIT" in reason.upper()
                loss_reason = "STOP LOSS" in reason.upper() or "LOSS" in reason.upper()
                sign_flip = (recorded < 0 < expected) or (recorded > 0 > expected)
                if sign_flip or (profit_reason and recorded < 0) or (loss_reason and recorded > 0):
                    high += 1
        if high == 0 and audit.get("anomalies_found", 0):
            medium = int(audit.get("medium_severity_count", 0))
            return int(audit.get("anomalies_found", 0)) - medium
        return high

    def _recalibrate_candidates(
        self, accounting: PortfolioAccountingComparison
    ) -> list[CandidateRecalibration]:
        gap_payload = self._artifacts.get("evidence_gap") or {}
        gap_analyses = {
            a["candidate_id"]: a for a in gap_payload.get("analyses") or []
        }
        dossiers = {
            d["candidate_id"]: d
            for d in (self._artifacts.get("evidence_history") or {}).get("dossiers") or []
        }
        candidates_meta = {
            c["candidate_id"]: c
            for c in (self._artifacts.get("knowledge_candidates") or {}).get("candidates") or []
        }
        rec_by_candidate: dict[str, dict[str, Any]] = {}
        for rec in (self._artifacts.get("strategy_recommendations") or {}).get(
            "recommendations"
        ) or []:
            cid = rec.get("source_candidate_id")
            if cid:
                rec_by_candidate[cid] = rec

        patch_reviews = {
            r.get("source_candidate_id"): r
            for r in (self._artifacts.get("patch_review") or {}).get("reviews") or []
        }

        candidate_ids = sorted(
            set(gap_analyses) | set(dossiers) | set(candidates_meta),
            key=lambda cid: -_composite_rank_score(
                _safe_float((gap_analyses.get(cid) or {}).get("current_confidence")),
                _safe_float((dossiers.get(cid) or {}).get("current_evidence_score")),
            ),
        )

        interim: list[dict[str, Any]] = []
        for cid in candidate_ids:
            gap = gap_analyses.get(cid, {})
            dossier = dossiers.get(cid, {})
            meta = candidates_meta.get(cid, {})
            rec = rec_by_candidate.get(cid, {})
            review = patch_reviews.get(cid, {})

            old_confidence = _safe_float(
                gap.get("current_confidence"), _safe_float(rec.get("confidence"), 50.0)
            )
            old_evidence = _safe_float(dossier.get("current_evidence_score"), 0.0)
            old_readiness = str(
                gap.get("current_readiness")
                or dossier.get("implementation_readiness")
                or "NOT_READY"
            )

            blocking = list(gap.get("blocking_items") or [])
            missing = list(gap.get("missing_evidence") or [])
            europe_uk_gap = _has_europe_uk_gap(blocking, missing)

            recal_confidence = min(100.0, old_confidence + ACCOUNTING_TRUST_BOOST)
            recal_evidence = round(old_evidence + EVIDENCE_SCORE_TRUST_BOOST, 2)
            conf_delta = recal_confidence - old_confidence

            if accounting.conclusions_affected:
                accounting_impact = (
                    "INDIRECT — integritate date portofoliu restaurată; "
                    "concluzii performanță strategică invalidate"
                )
            else:
                accounting_impact = "NONE — fără impact detectat pe candidat"

            recal_readiness = "NOT_READY"
            if europe_uk_gap:
                recal_readiness = "NOT_READY"
            elif old_readiness == "READY_FOR_SANDBOX_REVIEW":
                recal_readiness = "READY_FOR_SANDBOX_REVIEW"

            perf_dep = self._recommendation_depended_on_performance(rec, review)
            requires_review = accounting.conclusions_affected or perf_dep
            downgrade = ""
            if requires_review:
                downgrade = "REQUIRE_REVIEW — audit performanță afectat de bug contabil"

            interim.append(
                {
                    "candidate_id": cid,
                    "title": str(
                        meta.get("title") or gap.get("title") or dossier.get("title") or cid
                    ),
                    "old_confidence": old_confidence,
                    "recalibrated_confidence": recal_confidence,
                    "old_evidence_score": old_evidence,
                    "recalibrated_evidence_score": recal_evidence,
                    "old_readiness": old_readiness,
                    "recalibrated_readiness": recal_readiness,
                    "accounting_impact": accounting_impact,
                    "confidence_delta": conf_delta,
                    "evidence_score_delta": recal_evidence - old_evidence,
                    "confidence_stability": _confidence_stability(conf_delta),
                    "requires_review": requires_review,
                    "validation_gaps_remain": europe_uk_gap,
                    "recommendation_downgrade": downgrade,
                    "rank_score_before": _composite_rank_score(old_confidence, old_evidence),
                    "rank_score_after": _composite_rank_score(
                        recal_confidence, recal_evidence
                    ),
                }
            )

        interim.sort(key=lambda x: -x["rank_score_before"])
        rank_before = {item["candidate_id"]: idx + 1 for idx, item in enumerate(interim)}
        interim.sort(key=lambda x: -x["rank_score_after"])
        rank_after = {item["candidate_id"]: idx + 1 for idx, item in enumerate(interim)}

        results: list[CandidateRecalibration] = []
        for item in interim:
            cid = item["candidate_id"]
            results.append(
                CandidateRecalibration(
                    candidate_id=cid,
                    title=item["title"],
                    old_confidence=item["old_confidence"],
                    recalibrated_confidence=item["recalibrated_confidence"],
                    old_evidence_score=item["old_evidence_score"],
                    recalibrated_evidence_score=item["recalibrated_evidence_score"],
                    old_readiness=item["old_readiness"],
                    recalibrated_readiness=item["recalibrated_readiness"],
                    accounting_impact=item["accounting_impact"],
                    confidence_delta=item["confidence_delta"],
                    evidence_score_delta=item["evidence_score_delta"],
                    confidence_stability=item["confidence_stability"],
                    requires_review=item["requires_review"],
                    rank_before=rank_before[cid],
                    rank_after=rank_after[cid],
                    validation_gaps_remain=item["validation_gaps_remain"],
                    recommendation_downgrade=item["recommendation_downgrade"],
                )
            )
        return sorted(results, key=lambda c: c.rank_before)

    def _recommendation_depended_on_performance(
        self, rec: dict[str, Any], review: dict[str, Any]
    ) -> bool:
        if not rec:
            return False
        summary = str(rec.get("evidence_summary", "")) + str(rec.get("validation_summary", ""))
        if any(kw in summary.lower() for kw in ("portfolio", "realized", "pnl", "win rate")):
            return True
        scores = review.get("scores") or {}
        if _safe_float(scores.get("statistical_confidence_score")) > 0:
            return True
        return False

    def _build_ecosystem_metrics(
        self,
        candidates: list[CandidateRecalibration],
        accounting: PortfolioAccountingComparison,
    ) -> EcosystemMetrics:
        if not candidates:
            return EcosystemMetrics(
                average_old_confidence=0.0,
                average_recalibrated_confidence=0.0,
                average_confidence_delta=0.0,
                ranking_changed=False,
                top_candidate_before="",
                top_candidate_after="",
                top_candidate_unchanged=True,
                conclusions_affected_by_accounting=accounting.conclusions_affected,
                recommendations_requiring_review=0,
                patches_still_blocked=0,
                evolution_plans_still_gated=0,
                all_implementation_not_ready=True,
                implementation_readiness_summary=(
                    "Niciun candidat — implementare NOT_READY by default"
                ),
            )

        n = len(candidates)
        avg_old = sum(c.old_confidence for c in candidates) / n
        avg_new = sum(c.recalibrated_confidence for c in candidates) / n
        avg_delta = sum(c.confidence_delta for c in candidates) / n

        top_before = min(candidates, key=lambda c: c.rank_before).candidate_id
        top_after = min(candidates, key=lambda c: c.rank_after).candidate_id
        ranking_changed = any(c.rank_before != c.rank_after for c in candidates)

        recs_review = sum(1 for c in candidates if c.requires_review)

        patch_payload = self._artifacts.get("patch_review") or {}
        patches_blocked = int(patch_payload.get("require_more_evidence", 0))
        if patches_blocked == 0:
            patches_blocked = sum(
                1
                for r in patch_payload.get("reviews") or []
                if r.get("verdict") == "REQUIRE_MORE_EVIDENCE"
            )

        evo_payload = self._artifacts.get("evolution_plan") or {}
        evo_gated = int(evo_payload.get("validation_gated_plan_count", 0))
        if evo_gated == 0:
            evo_gated = sum(
                1
                for p in evo_payload.get("plans") or []
                if p.get("proposed_change_type") == "VALIDATION_GATE"
            )

        all_not_ready = all(
            c.recalibrated_readiness == "NOT_READY" for c in candidates
        )
        europe_blocked = all(c.validation_gaps_remain for c in candidates)

        if europe_blocked and all_not_ready:
            readiness_summary = (
                "Toate candidatelor rămân NOT_READY — validare Europe/UK lipsă "
                "continuă să blocheze implementarea indiferent de recalibrarea confidence."
            )
        elif all_not_ready:
            readiness_summary = "Toate candidatelor rămân NOT_READY după recalibrare."
        else:
            readiness_summary = "Unele candidat(e) proiectate READY — verificare umană necesară."

        return EcosystemMetrics(
            average_old_confidence=avg_old,
            average_recalibrated_confidence=avg_new,
            average_confidence_delta=avg_delta,
            ranking_changed=ranking_changed,
            top_candidate_before=top_before,
            top_candidate_after=top_after,
            top_candidate_unchanged=top_before == top_after,
            conclusions_affected_by_accounting=accounting.conclusions_affected,
            recommendations_requiring_review=recs_review,
            patches_still_blocked=patches_blocked,
            evolution_plans_still_gated=evo_gated,
            all_implementation_not_ready=all_not_ready,
            implementation_readiness_summary=readiness_summary,
        )

    def _next_research_action(
        self,
        candidates: list[CandidateRecalibration],
        ecosystem: EcosystemMetrics,
    ) -> str:
        gap_payload = self._artifacts.get("evidence_gap") or {}
        top_id = ecosystem.top_candidate_after or gap_payload.get(
            "highest_information_gain_candidate_id", "kn_d5_00002"
        )
        return (
            f"1. Închide gap-urile Europe/UK pentru {top_id} "
            f"(prioritate #1 — singurul candidat cu cel mai mare information gain).\n"
            f"2. Re-rulează cross-validation regională cu date ensemble Europe/UK.\n"
            f"3. Nu promova patch-uri sau planuri evolution până când "
            f"validation_gated_plan_count={ecosystem.evolution_plans_still_gated} "
            f"și patch review REQUIRE_MORE_EVIDENCE={ecosystem.patches_still_blocked} "
            f"sunt rezolvate.\n"
            f"4. Opțional: re-aplică corecția portfolio.csv (--apply) pentru aliniere "
            f"fișier cu audit contabil — fără impact pe readiness research."
        )
