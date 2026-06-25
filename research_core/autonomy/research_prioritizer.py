"""
Research prioritizer — Phase V Sprint A1 autonomous research ordering.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Decides which research opportunity to investigate next — does not run experiments,
generate hypotheses, or modify discoveries/rankings.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from research_core.autonomy.prioritization_report import (
    PrioritizationReport,
    ResearchPriorityEntry,
)
from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.discovery.discovery_registry import DEFAULT_REGISTRY_PATH as DISCOVERIES_PATH
from research_core.hypothesis.hypothesis_model import HypothesisStatus
from research_core.hypothesis.hypothesis_registry import DEFAULT_REGISTRY_PATH as HYPOTHESIS_PATH
from research_core.hypothesis.experiment_runner import DEFAULT_RESULTS_PATH as EXPERIMENTS_PATH
from research_core.hypothesis.knowledge_candidate import DEFAULT_CANDIDATES_PATH
from research_core.learning.learning_report import DEFAULT_REPORT_PATH as LEARNING_PATH
from research_core.validation.validation_report import DEFAULT_REPORT_PATH as VALIDATION_PATH

logger = logging.getLogger(__name__)

EFFORT_SCORE = {"LOW": 15.0, "MEDIUM": 35.0, "HIGH": 55.0}
VALUE_SCORE = {"LOW": 25.0, "MEDIUM": 55.0, "HIGH": 80.0}


@dataclass
class _OpportunityDraft:
    opportunity_id: str
    source_type: str
    source_id: str
    title: str
    why_it_matters: str
    suggested_next_action: str
    novelty: float = 50.0
    evidence_quality: float = 50.0
    robustness: float = 50.0
    validation_gap_score: float = 0.0
    information_gain: float = 50.0
    duplicate_risk: float = 0.0
    research_cost: float = 35.0
    scientific_value: str = "MEDIUM"
    effort: str = "MEDIUM"


class ResearchPrioritizer:
    """
    Evaluates pending research opportunities from TAE intelligence artifacts.
    Sprint A1 — prioritization only, no execution paths.
    """

    def __init__(self) -> None:
        self._sources: dict[str, bool] = {}
        self._data: dict[str, Any] = {}

    def prioritize(self) -> PrioritizationReport:
        self._load_all_sources()
        drafts = self._collect_opportunities()
        entries = [self._score_opportunity(d) for d in drafts]
        entries.sort(key=lambda e: (-e.priority_score, e.opportunity_id))

        for idx, entry in enumerate(entries, start=1):
            entry.rank = idx

        if not entries:
            return PrioritizationReport(
                opportunities_evaluated=0,
                top_opportunity_id="",
                highest_information_gain_id="",
                recommended_next_experiment="Run discovery engine and hypothesis pipeline to seed opportunities.",
                top_ranking_reason="No pending research opportunities found in loaded artifacts.",
                priorities=[],
                sources_loaded=self._sources,
            )

        top = entries[0]
        highest_ig = max(entries, key=lambda e: e.expected_information_gain)

        return PrioritizationReport(
            opportunities_evaluated=len(entries),
            top_opportunity_id=top.opportunity_id,
            highest_information_gain_id=highest_ig.opportunity_id,
            recommended_next_experiment=top.suggested_next_action,
            top_ranking_reason=self._ranking_reason(top),
            priorities=entries,
            sources_loaded=self._sources,
        )

    def _load_all_sources(self) -> None:
        paths = {
            "tae_discoveries.json": DISCOVERIES_PATH,
            "tae_hypothesis_registry.json": HYPOTHESIS_PATH,
            "tae_experiment_results.json": EXPERIMENTS_PATH,
            "tae_knowledge_candidates.json": DEFAULT_CANDIDATES_PATH,
            "tae_cross_validation_report.json": VALIDATION_PATH,
            "tae_learning_report.json": LEARNING_PATH,
        }
        for name, path in paths.items():
            payload, ok = self._load_json(path)
            self._data[name] = payload
            self._sources[name] = ok

    def _load_json(self, path: Path) -> tuple[Any, bool]:
        if not path.is_file():
            return {}, False
        try:
            raw = path.read_text(encoding="utf-8")
            return json.loads(raw), True
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Unreadable %s: %s", path, exc)
            return {}, False

    def _collect_opportunities(self) -> list[_OpportunityDraft]:
        drafts: list[_OpportunityDraft] = []
        seen_titles: set[str] = set()

        drafts.extend(self._from_discoveries(seen_titles))
        drafts.extend(self._from_untested_hypotheses(seen_titles))
        drafts.extend(self._from_validation_gaps(seen_titles))
        drafts.extend(self._from_learning_insights(seen_titles))
        drafts.extend(self._from_discovery_follow_ups(seen_titles))
        return drafts

    def _from_discoveries(self, seen: set[str]) -> list[_OpportunityDraft]:
        payload = self._data.get("tae_discoveries.json", {})
        items = payload.get("discoveries", []) if isinstance(payload, dict) else []
        out: list[_OpportunityDraft] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", ""))
            if status != "NEW":
                continue
            did = str(item.get("discovery_id", ""))
            title = str(item.get("title", ""))
            if title in seen:
                continue
            seen.add(title)

            out.append(
                _OpportunityDraft(
                    opportunity_id=f"prio_{did}",
                    source_type="DISCOVERY",
                    source_id=did,
                    title=title,
                    why_it_matters=str(item.get("description", ""))[:300],
                    suggested_next_action=str(item.get("suggested_next_step", "")),
                    novelty=float(item.get("novelty_score", 50)),
                    evidence_quality=float(item.get("confidence", 50)),
                    validation_gap_score=40.0,
                    information_gain=min(90.0, float(item.get("novelty_score", 50)) + 20),
                    duplicate_risk=10.0,
                    research_cost=EFFORT_SCORE["LOW"],
                    scientific_value="MEDIUM",
                    effort="LOW",
                )
            )
        return out

    def _from_discovery_follow_ups(self, seen: set[str]) -> list[_OpportunityDraft]:
        payload = self._data.get("tae_discoveries.json", {})
        items = payload.get("discoveries", []) if isinstance(payload, dict) else []
        out: list[_OpportunityDraft] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            if str(item.get("status", "")) not in ("CONVERTED", "LINKED"):
                continue
            did = str(item.get("discovery_id", ""))
            title = f"Follow-up: {item.get('title', '')}"
            if title in seen:
                continue
            seen.add(title)
            category = str(item.get("category", ""))
            effort = "HIGH" if category == "CROSS_REGIME_ANOMALY" else "MEDIUM"

            out.append(
                _OpportunityDraft(
                    opportunity_id=f"prio_follow_{did}",
                    source_type="DISCOVERY_FOLLOW_UP",
                    source_id=did,
                    title=title[:120],
                    why_it_matters=(
                        f"Converted discovery {did} has outstanding research step: "
                        f"{item.get('description', '')[:200]}"
                    ),
                    suggested_next_action=str(item.get("suggested_next_step", "")),
                    novelty=float(item.get("novelty_score", 50)) * 0.7,
                    evidence_quality=float(item.get("confidence", 50)),
                    robustness=55.0,
                    validation_gap_score=50.0 if category == "CROSS_REGIME_ANOMALY" else 25.0,
                    information_gain=70.0 if category == "CROSS_REGIME_ANOMALY" else 55.0,
                    duplicate_risk=25.0,
                    research_cost=EFFORT_SCORE[effort],
                    scientific_value="HIGH" if category == "CROSS_REGIME_ANOMALY" else "MEDIUM",
                    effort=effort,
                )
            )
        return out

    def _from_untested_hypotheses(self, seen: set[str]) -> list[_OpportunityDraft]:
        payload = self._data.get("tae_hypothesis_registry.json", {})
        items = payload.get("hypotheses", []) if isinstance(payload, dict) else []
        out: list[_OpportunityDraft] = []

        for item in items:
            if not isinstance(item, dict):
                continue
            status = str(item.get("status", ""))
            if status not in (
                HypothesisStatus.UNTESTED.value,
                HypothesisStatus.INSUFFICIENT_DATA.value,
            ):
                continue
            hid = str(item.get("hypothesis_id", ""))
            title = str(item.get("title", ""))
            if title in seen:
                continue
            seen.add(title)

            out.append(
                _OpportunityDraft(
                    opportunity_id=f"prio_hyp_{hid}",
                    source_type="HYPOTHESIS",
                    source_id=hid,
                    title=title[:120],
                    why_it_matters=(
                        f"Hypothesis {hid} is {status} — experiment would advance "
                        "research pipeline without execution."
                    ),
                    suggested_next_action=(
                        f"Run Sprint 5.1 experiment runner on {hid} (research cohort only)."
                    ),
                    novelty=45.0,
                    evidence_quality=float(item.get("confidence", 50)),
                    information_gain=65.0,
                    research_cost=EFFORT_SCORE["MEDIUM"],
                    scientific_value="MEDIUM",
                    effort="MEDIUM",
                )
            )
        return out

    def _from_validation_gaps(self, seen: set[str]) -> list[_OpportunityDraft]:
        payload = self._data.get("tae_cross_validation_report.json", {})
        out: list[_OpportunityDraft] = []

        follow_ups = payload.get("recommended_follow_up_research", [])
        if isinstance(follow_ups, list):
            for idx, note in enumerate(follow_ups, start=1):
                if not isinstance(note, str):
                    continue
                lower = note.lower()
                if "discipline" in lower or "authorize" in lower or "does not authorize" in lower:
                    continue
                title = str(note)[:120]
                if title in seen:
                    continue
                seen.add(title)
                effort = "HIGH" if "cross-regime" in note.lower() else "MEDIUM"
                out.append(
                    _OpportunityDraft(
                        opportunity_id=f"prio_val_{idx:03d}",
                        source_type="VALIDATION_GAP",
                        source_id=f"cross_validation_{idx}",
                        title=title,
                        why_it_matters=(
                            "Cross-validation (Sprint D6) identified a robustness gap "
                            "requiring further research."
                        ),
                        suggested_next_action=note,
                        novelty=60.0,
                        evidence_quality=70.0,
                        robustness=40.0,
                        validation_gap_score=85.0,
                        information_gain=80.0 if "cross-regime" in note.lower() else 60.0,
                        duplicate_risk=5.0,
                        research_cost=EFFORT_SCORE[effort],
                        scientific_value="HIGH",
                        effort=effort,
                    )
                )

        results = payload.get("candidate_results", [])
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                cid = str(item.get("candidate_id", ""))
                regime = item.get("regime_consistency", "NOT_AVAILABLE")
                region = item.get("regional_consistency", "NOT_AVAILABLE")
                if regime != "NOT_AVAILABLE" and region != "NOT_AVAILABLE":
                    continue
                title = f"Validation gap: {cid}"
                if title in seen:
                    continue
                seen.add(title)
                out.append(
                    _OpportunityDraft(
                        opportunity_id=f"prio_cand_{cid}",
                        source_type="VALIDATION_GAP",
                        source_id=cid,
                        title=title,
                        why_it_matters=str(item.get("validation_notes", ""))[:300],
                        suggested_next_action=(
                            f"Close validation gaps for knowledge candidate {cid} "
                            "(regime/region dimensions)."
                        ),
                        novelty=55.0,
                        evidence_quality=float(item.get("robustness_score", 50)),
                        robustness=float(item.get("robustness_score", 50))
                        if isinstance(item.get("robustness_score"), (int, float))
                        else 50.0,
                        validation_gap_score=75.0,
                        information_gain=72.0,
                        duplicate_risk=15.0,
                        research_cost=EFFORT_SCORE["MEDIUM"],
                        scientific_value="MEDIUM",
                        effort="MEDIUM",
                    )
                )
        return out

    def _from_learning_insights(self, seen: set[str]) -> list[_OpportunityDraft]:
        payload = self._data.get("tae_learning_report.json", {})
        lessons = payload.get("key_lessons_learned", [])
        out: list[_OpportunityDraft] = []

        if not isinstance(lessons, list):
            return out

        for idx, lesson in enumerate(lessons, start=1):
            if not isinstance(lesson, str):
                continue
            lower = lesson.lower()
            if "does not authorize" in lower or "research-only meta-learning" in lower:
                continue
            if "duplicate" not in lower and "regime" not in lower and "knowledge candidate" not in lower:
                continue
            title = f"Learning insight #{idx}"
            if title in seen:
                continue
            seen.add(title)

            info_gain = 65.0
            if "duplicate" in lower:
                info_gain = 45.0
            if "regime" in lower:
                info_gain = 75.0

            out.append(
                _OpportunityDraft(
                    opportunity_id=f"prio_learn_{idx:03d}",
                    source_type="LEARNING_INSIGHT",
                    source_id=f"lesson_{idx}",
                    title=title,
                    why_it_matters=lesson[:300],
                    suggested_next_action=self._action_from_lesson(lesson),
                    novelty=50.0,
                    evidence_quality=float(payload.get("learning_confidence", 50)),
                    information_gain=info_gain,
                    duplicate_risk=30.0 if "duplicate" in lower else 10.0,
                    research_cost=EFFORT_SCORE["MEDIUM"],
                    scientific_value="MEDIUM",
                    effort="MEDIUM",
                )
            )
        return out

    def _action_from_lesson(self, lesson: str) -> str:
        lower = lesson.lower()
        if "duplicate" in lower:
            return "De-duplicate hypothesis titles before next experiment batch (research hygiene)."
        if "regime" in lower:
            return "Schedule cross-regime cohort research for BULL/BEAR/NEUTRAL — not execution."
        if "knowledge candidate" in lower:
            return "Review knowledge candidate pipeline output and queue next validation sprint."
        return "Investigate meta-learning insight in next research council cycle."

    def _score_opportunity(self, draft: _OpportunityDraft) -> ResearchPriorityEntry:
        factors = {
            "novelty": draft.novelty,
            "evidence_quality": draft.evidence_quality,
            "robustness": draft.robustness,
            "validation_gaps": draft.validation_gap_score,
            "expected_information_gain": draft.information_gain,
            "duplicate_risk_penalty": draft.duplicate_risk,
            "research_cost_penalty": draft.research_cost,
        }

        score = (
            draft.novelty * 0.12
            + draft.evidence_quality * 0.18
            + draft.robustness * 0.10
            + draft.validation_gap_score * 0.22
            + draft.information_gain * 0.28
            - draft.duplicate_risk * 0.12
            - draft.research_cost * 0.14
        )
        score = max(0.0, min(100.0, score))

        return ResearchPriorityEntry(
            opportunity_id=draft.opportunity_id,
            source_type=draft.source_type,
            source_id=draft.source_id,
            title=draft.title,
            priority_score=round(score, 2),
            why_it_matters=draft.why_it_matters,
            estimated_scientific_value=draft.scientific_value,
            estimated_effort=draft.effort,
            suggested_next_action=draft.suggested_next_action,
            expected_information_gain=draft.information_gain,
            scoring_factors=factors,
        )

    def _ranking_reason(self, top: ResearchPriorityEntry) -> str:
        factors = top.scoring_factors
        return (
            f"{top.opportunity_id} ranked first with priority {top.priority_score:.1f} "
            f"(info_gain={factors.get('expected_information_gain', 0):.0f}, "
            f"validation_gaps={factors.get('validation_gaps', 0):.0f}, "
            f"evidence={factors.get('evidence_quality', 0):.0f}) — "
            "prioritization only, not execution."
        )
