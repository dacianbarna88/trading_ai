#!/usr/bin/env python3
"""
TAE Strategy Lab adapters — Sprint 2

READ-ONLY façades over existing research / replay / economics owners.
Never runs research pipelines, never writes owner artifacts, never touches LIVE.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from research_core.integration_adapters.base_adapter import read_json_report
from research_core.integration_adapters.strategy_adapter import StrategyAdapter
from tae_parallel_paper_config import PROJECT_ROOT, arm_paths, configured_arms

# Direct paths — do not call paper_economic_attribution.summary_path() (mkdir side effect).
PARALLEL_ROOT = PROJECT_ROOT / "runtime_outputs" / "parallel_paper"
ECONOMIC_SUMMARY = PARALLEL_ROOT / "attribution" / "economic_summary.json"
ECONOMIC_CYCLES = PARALLEL_ROOT / "attribution" / "economic_cycles.json"
CAPITAL_CHALLENGERS = (
    PROJECT_ROOT / "runtime_outputs" / "learning_to_profit" / "capital_challengers.json"
)
CHRONO_REPLAY = PROJECT_ROOT / "tae_chronological_portfolio_replay_results.json"
ROI001_REPORT = PROJECT_ROOT / "tae_roi001_challenger_report.json"
ROI_QUEUE = PROJECT_ROOT / "tae_roi_queue.json"
DAILY_SCORECARD = PROJECT_ROOT / "TAE_DAILY_ECONOMIC_SCORECARD.json"
LEARNING_ATTRIBUTION = PROJECT_ROOT / "tae_learning_economic_attribution.json"
ABLATION_SUMMARY = PROJECT_ROOT / "tae_learning_ablation_summary.json"
WINNER_LIFECYCLE = PROJECT_ROOT / "tae_winner_lifecycle_profiler.json"
CANDIDATE_REGISTRY = PROJECT_ROOT / "tae_candidate_strategy_registry.json"
PROMOTION_GATE = PROJECT_ROOT / "tae_strategy_promotion_gate.json"


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _present(path: Path) -> bool:
    return path.is_file()


def _source(path: Path, owner: str, *, loaded: bool) -> dict[str, Any]:
    return {
        "path": _rel(path),
        "owner": owner,
        "present": _present(path),
        "loaded": loaded,
        "read_only": True,
    }


class ResearchAdapter:
    """Read-only research / candidate / promotion / capital-challenger view."""

    OWNERS = {
        "strategy_evolution": "research_core/strategy_evolution/daily_runner.py",
        "strategy_adapter": "research_core/integration_adapters/strategy_adapter.py",
        "candidate_registry": "research_core/strategy_evolution/candidate_registry.py",
        "promotion_gate": "research_core/strategy_evolution/promotion_gate.py",
        "capital_challengers": "tae_paper_decision_engine.py::capital_challengers.json",
    }

    def load(self) -> dict[str, Any]:
        evolution = StrategyAdapter.load_strategy_state_for_orchestrator(str(PROJECT_ROOT))
        candidates = read_json_report(CANDIDATE_REGISTRY, PROJECT_ROOT)
        gate = read_json_report(PROMOTION_GATE, PROJECT_ROOT)
        challengers = read_json_report(CAPITAL_CHALLENGERS, PROJECT_ROOT)
        return {
            "schema": "tae.strategy_lab.adapter.research.v1",
            "mode": "READ_ONLY",
            "mutates_owners": False,
            "executes_daily_runner": False,
            "auto_promote": False,
            "owners": dict(self.OWNERS),
            "sources": {
                "strategy_evolution_orchestrator": {
                    "owner": self.OWNERS["strategy_adapter"],
                    "api": "StrategyAdapter.load_strategy_state_for_orchestrator",
                    "loaded": evolution is not None,
                    "read_only": True,
                },
                "candidate_registry": _source(
                    CANDIDATE_REGISTRY,
                    self.OWNERS["candidate_registry"],
                    loaded=candidates is not None,
                ),
                "promotion_gate": _source(
                    PROMOTION_GATE,
                    self.OWNERS["promotion_gate"],
                    loaded=gate is not None,
                ),
                "capital_challengers": _source(
                    CAPITAL_CHALLENGERS,
                    self.OWNERS["capital_challengers"],
                    loaded=challengers is not None,
                ),
            },
            "strategy_evolution": {
                "completeness": evolution.get("strategy_state_completeness"),
                "daily_runner_verdict": evolution.get("daily_runner_verdict"),
                "verdict": evolution.get("verdict"),
                "missing_step_reports": evolution.get("missing_step_reports") or [],
                "missing_primary_report": evolution.get("missing_primary_report"),
                "top_ranked_strategy_id": evolution.get("top_ranked_strategy_id"),
                "top_ranked_strategy_score": evolution.get("top_ranked_strategy_score"),
                "promotion_review_candidate_id": evolution.get(
                    "promotion_review_candidate_id"
                ),
            },
            "candidate_registry": {
                "verdict": None if candidates is None else candidates.get("verdict"),
                "baseline_candidate_id": None
                if candidates is None
                else candidates.get("baseline_candidate_id"),
                "candidates": []
                if candidates is None
                else list(candidates.get("candidates") or []),
                "candidate_count": 0
                if candidates is None
                else len(candidates.get("candidates") or []),
            },
            "promotion_gate": {
                "verdict": None if gate is None else gate.get("verdict"),
                "review_candidate_id": None if gate is None else gate.get("review_candidate_id"),
                "entries": [] if gate is None else list(gate.get("entries") or []),
                "auto_promote": False,
                "produces_promotion": False,
            },
            "capital_challengers": {
                "challenger_count": None
                if challengers is None
                else challengers.get("challenger_count"),
                "authorized_count": None
                if challengers is None
                else challengers.get("authorized_count"),
                "live_promotion_allowed": None
                if challengers is None
                else challengers.get("live_promotion_allowed"),
                "challengers": []
                if challengers is None
                else list(challengers.get("challengers") or []),
            },
        }


class ReplayAdapter:
    """Read-only chronological replay + ablation replay pointers."""

    OWNERS = {
        "chronological_replay": "tae_chronological_portfolio_replay.py",
        "ablation_summary": "tae_learning_economic_ablation.py",
    }

    def load(self) -> dict[str, Any]:
        chrono = read_json_report(CHRONO_REPLAY, PROJECT_ROOT)
        ablation = read_json_report(ABLATION_SUMMARY, PROJECT_ROOT)
        replay_block = None
        if isinstance(ablation, dict):
            replay_block = ablation.get("replay")
        return {
            "schema": "tae.strategy_lab.adapter.replay.v1",
            "mode": "READ_ONLY",
            "mutates_owners": False,
            "runs_replay": False,
            "owners": dict(self.OWNERS),
            "sources": {
                "chronological_replay": _source(
                    CHRONO_REPLAY,
                    self.OWNERS["chronological_replay"],
                    loaded=chrono is not None,
                ),
                "ablation_summary": _source(
                    ABLATION_SUMMARY,
                    self.OWNERS["ablation_summary"],
                    loaded=ablation is not None,
                ),
            },
            "chronological": None
            if chrono is None
            else {
                "generated_at": chrono.get("generated_at"),
                "recommendation": chrono.get("recommendation"),
                "reliable_for_promotion": chrono.get("reliable_for_promotion"),
                "reliability": chrono.get("reliability"),
                "promotion_eligibility": chrono.get("promotion_eligibility"),
                "metrics": chrono.get("metrics"),
                "comparisons": chrono.get("comparisons"),
                "economic_evaluations": chrono.get("economic_evaluations"),
                "capital_utilization": chrono.get("capital_utilization"),
            },
            "ablation_replay": replay_block,
            "replay_state": (
                "AVAILABLE"
                if chrono is not None
                else ("ABLATION_ONLY" if replay_block is not None else "MISSING")
            ),
        }


class EconomicsAdapter:
    """Read-only economics: attribution, ROI, scorecard, ablation risk metrics."""

    OWNERS = {
        "paper_economic_attribution": "tae_paper_economic_attribution.py",
        "learning_attribution": "tae_learning_economic_attribution_engine.py",
        "roi001": "tae_roi001_challenger.py",
        "daily_scorecard": "TAE_DAILY_ECONOMIC_SCORECARD.json",
        "equity_metrics": "tae_learning_economic_ablation.equity_metrics",
        "ablation_summary": "tae_learning_ablation_summary.json",
    }

    def load(self) -> dict[str, Any]:
        # Read files directly — never call attribution_dir()/summary_path() (mkdir).
        paper = read_json_report(ECONOMIC_SUMMARY, PROJECT_ROOT)
        learning = read_json_report(LEARNING_ATTRIBUTION, PROJECT_ROOT)
        roi = read_json_report(ROI001_REPORT, PROJECT_ROOT)
        queue = read_json_report(ROI_QUEUE, PROJECT_ROOT)
        scorecard = read_json_report(DAILY_SCORECARD, PROJECT_ROOT)
        ablation = read_json_report(ABLATION_SUMMARY, PROJECT_ROOT)

        arms: dict[str, Any] = {}
        if isinstance(paper, dict):
            for key in ("v1", "v2", "V1", "V2"):
                block = paper.get(key)
                if isinstance(block, dict):
                    arms[key.lower()] = block

        return {
            "schema": "tae.strategy_lab.adapter.economics.v1",
            "mode": "READ_ONLY",
            "mutates_owners": False,
            "invents_formulas": False,
            "owners": dict(self.OWNERS),
            "sources": {
                "paper_economic_summary": _source(
                    ECONOMIC_SUMMARY,
                    self.OWNERS["paper_economic_attribution"],
                    loaded=paper is not None,
                ),
                "learning_attribution": _source(
                    LEARNING_ATTRIBUTION,
                    self.OWNERS["learning_attribution"],
                    loaded=learning is not None,
                ),
                "roi001_report": _source(
                    ROI001_REPORT, self.OWNERS["roi001"], loaded=roi is not None
                ),
                "roi_queue": _source(ROI_QUEUE, self.OWNERS["roi001"], loaded=queue is not None),
                "daily_scorecard": _source(
                    DAILY_SCORECARD,
                    self.OWNERS["daily_scorecard"],
                    loaded=scorecard is not None,
                ),
                "ablation_summary": _source(
                    ABLATION_SUMMARY,
                    self.OWNERS["ablation_summary"],
                    loaded=ablation is not None,
                ),
            },
            "paper_arms": arms,
            "paper_comparison": None if paper is None else paper.get("comparison"),
            "learning_attribution": None
            if learning is None
            else {
                "economic_verdict": learning.get("economic_verdict"),
                "expectancy": learning.get("expectancy"),
                "gross_attributable_pnl": learning.get("gross_attributable_pnl"),
                "economically_material": learning.get("economically_material"),
                "decision_impact_proven": learning.get("decision_impact_proven"),
            },
            "roi001": None
            if roi is None
            else {
                "roi_id": roi.get("roi_id"),
                "verdict": roi.get("verdict"),
                "delta": roi.get("delta"),
                "promotion_checks": roi.get("promotion_checks"),
                "comparisons": roi.get("comparisons"),
                "production_default": roi.get("production_default"),
            },
            "roi_queue": None
            if queue is None
            else {
                "active_roi_id": queue.get("active_roi_id"),
                "active_count": queue.get("active_count"),
                "verdict": queue.get("verdict"),
                "current_number_one": queue.get("current_number_one"),
            },
            "daily_scorecard": None
            if scorecard is None
            else {
                "generated_at": scorecard.get("generated_at"),
                "limitation": scorecard.get("limitation"),
                "row_count": len(scorecard.get("rows") or []),
            },
            "ablation_metrics_on": None
            if ablation is None
            else ablation.get("metrics_on"),
            "ablation_metrics_off": None
            if ablation is None
            else ablation.get("metrics_off"),
        }

    def arm_block(self, arm: str) -> dict[str, Any] | None:
        doc = self.load()
        return (doc.get("paper_arms") or {}).get(str(arm).lower())


class CycleAnalyticsAdapter:
    """Read-only cycle analytics from paper attribution + V2 snapshot (+ lifecycle observe)."""

    OWNERS = {
        "paper_economic_attribution": "tae_paper_economic_attribution.py",
        "v2_accounting_snapshot": "runtime_outputs/parallel_paper/v2/accounting_snapshot.json",
        "winner_lifecycle": "tae_winner_lifecycle_profiler.py",
    }

    def load(self) -> dict[str, Any]:
        paper = read_json_report(ECONOMIC_SUMMARY, PROJECT_ROOT)
        lifecycle = read_json_report(WINNER_LIFECYCLE, PROJECT_ROOT)

        def _arm_from_summary(key: str) -> dict[str, Any] | None:
            if not isinstance(paper, dict):
                return None
            block = paper.get(key) or paper.get(key.upper())
            return block if isinstance(block, dict) else None

        def _snap_eco(snap: dict[str, Any] | None) -> dict[str, Any] | None:
            if not isinstance(snap, dict):
                return None
            eco = snap.get("economic_attribution")
            return eco if isinstance(eco, dict) else None

        arms_out: dict[str, Any] = {}
        sources: dict[str, Any] = {
            "economic_summary": _source(
                ECONOMIC_SUMMARY,
                self.OWNERS["paper_economic_attribution"],
                loaded=paper is not None,
            ),
            "winner_lifecycle": _source(
                WINNER_LIFECYCLE,
                self.OWNERS["winner_lifecycle"],
                loaded=lifecycle is not None,
            ),
        }
        for a in configured_arms():
            aid = a["arm_id"]
            snap_path = arm_paths(aid)["accounting"]
            snap = read_json_report(snap_path, PROJECT_ROOT)
            sources[f"{aid}_accounting_snapshot"] = _source(
                snap_path,
                "research_core/accounting/accounting_snapshot.py",
                loaded=snap is not None,
            )
            arms_out[aid] = {
                "from_summary": _arm_from_summary(aid),
                "from_snapshot": _snap_eco(snap),
                "enabled": bool(a.get("enabled")),
                "policy_binding": a.get("policy_binding"),
            }

        return {
            "schema": "tae.strategy_lab.adapter.cycle_analytics.v1",
            "mode": "READ_ONLY",
            "mutates_owners": False,
            "owners": dict(self.OWNERS),
            "sources": sources,
            "arms": arms_out,
            "winner_lifecycle": None
            if lifecycle is None
            else {
                "global_verdict": lifecycle.get("global_verdict"),
                "mode": lifecycle.get("mode"),
                "read_only": lifecycle.get("read_only"),
                "live_trading_impact": lifecycle.get("live_trading_impact"),
                "provenance_note": "LIVE/shadow profiler; not canonical PAPER arm analytics",
                "profile_count": len(lifecycle.get("profiles") or []),
            },
            "cycles_store_present": ECONOMIC_CYCLES.is_file(),
        }


__all__ = [
    "ResearchAdapter",
    "ReplayAdapter",
    "EconomicsAdapter",
    "CycleAnalyticsAdapter",
    "ECONOMIC_SUMMARY",
    "CHRONO_REPLAY",
    "ROI001_REPORT",
    "CAPITAL_CHALLENGERS",
]
