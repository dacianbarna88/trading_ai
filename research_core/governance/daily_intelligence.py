"""
Daily intelligence collector — Phase V Sprint A5

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Aggregates TAE ecosystem artifacts into one executive governance report.
Read-only — does not modify live bot, config, portfolio, or execution paths.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.governance.governance_report import (
    ComponentHealth,
    DailyIntelligenceReport,
    DailyIntelligenceStore,
    HealthStatus,
)

logger = logging.getLogger(__name__)

NOT_AVAILABLE = "NOT_AVAILABLE"

INPUT_PATHS = {
    "tae_learning_report.json": Path("tae_learning_report.json"),
    "tae_discoveries.json": Path("tae_discoveries.json"),
    "tae_knowledge_candidates.json": Path("tae_knowledge_candidates.json"),
    "tae_strategy_recommendations.json": Path("tae_strategy_recommendations.json"),
    "tae_strategy_evolution_plan.json": Path("tae_strategy_evolution_plan.json"),
    "tae_cross_validation_report.json": Path("tae_cross_validation_report.json"),
    "tae_research_priorities.json": Path("tae_research_priorities.json"),
    "tae_roadmap_status.json": Path("tae_roadmap_status.json"),
    "process_health.json": Path("process_health.json"),
    "bot_status.txt": Path("bot_status.txt"),
    "tae_hypothesis_registry.json": Path("tae_hypothesis_registry.json"),
    "bot_output.log": Path("bot_output.log"),
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Unreadable JSON %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _load_text(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _tail_text(path: Path, max_lines: int = 500) -> str | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
        return "".join(lines[-max_lines:])
    except OSError:
        return None


def _list_items(payload: dict[str, Any] | None, key: str) -> list[Any]:
    if not payload:
        return []
    items = payload.get(key, [])
    return items if isinstance(items, list) else []


def _status_rank(status: HealthStatus) -> int:
    order = {
        HealthStatus.HEALTHY: 0,
        HealthStatus.WARNING: 1,
        HealthStatus.ATTENTION: 2,
        HealthStatus.NOT_AVAILABLE: 3,
    }
    return order.get(status, 3)


def _worst_status(statuses: list[HealthStatus]) -> HealthStatus:
    if not statuses:
        return HealthStatus.NOT_AVAILABLE
    return max(statuses, key=_status_rank)


class DailyIntelligenceCollector:
    """Builds the daily executive intelligence report from TAE artifacts."""

    def __init__(self, store: DailyIntelligenceStore | None = None) -> None:
        self._store = store or DailyIntelligenceStore()
        self._data: dict[str, dict[str, Any] | None] = {}
        self._text: dict[str, str | None] = {}
        self._sources_loaded: dict[str, bool] = {}

    def collect(self, report_date: str | None = None) -> DailyIntelligenceReport:
        self._load_all()
        day = report_date or date.today().isoformat()

        ecosystem = self._build_ecosystem_health()
        research = self._build_research_summary()
        learning = self._build_learning_summary()
        validation = self._build_validation_summary()
        evolution = self._build_strategy_evolution()
        priorities = self._build_priorities()
        trading = self._build_trading_status()
        roadmap = self._build_roadmap_progress()
        issues = self._build_critical_issues(validation, research, evolution)
        executive = self._build_executive_summary(
            ecosystem, research, learning, validation, evolution, trading, issues
        )

        return DailyIntelligenceReport(
            report_date=day,
            ecosystem_health=ecosystem,
            research_summary=research,
            learning_summary=learning,
            validation_summary=validation,
            strategy_evolution=evolution,
            research_priorities=priorities,
            trading_status=trading,
            roadmap_progress=roadmap,
            critical_issues=issues,
            executive_summary=executive,
            sources_loaded=dict(self._sources_loaded),
        )

    def generate_and_persist(self, report_date: str | None = None) -> DailyIntelligenceReport:
        report = self.collect(report_date=report_date)
        self._store.persist(report)
        return report

    def _load_all(self) -> None:
        for name, path in INPUT_PATHS.items():
            if path.suffix == ".json":
                payload = _load_json(path)
                self._data[name] = payload
                self._sources_loaded[name] = payload is not None
            elif name == "bot_output.log":
                text = _tail_text(path)
                self._text[name] = text
                self._sources_loaded[name] = text is not None
            else:
                text = _load_text(path)
                self._text[name] = text
                self._sources_loaded[name] = text is not None

    def _build_ecosystem_health(self) -> dict[str, Any]:
        components: list[ComponentHealth] = []

        learning_ok = self._data.get("tae_learning_report.json") is not None
        hypothesis_ok = self._data.get("tae_hypothesis_registry.json") is not None
        research_status = HealthStatus.HEALTHY if learning_ok and hypothesis_ok else (
            HealthStatus.WARNING if learning_ok or hypothesis_ok else HealthStatus.ATTENTION
        )
        components.append(ComponentHealth(
            "Research Engine",
            research_status,
            "Learning report and hypothesis registry" if research_status == HealthStatus.HEALTHY
            else "Partial research artifacts missing",
        ))

        disc = self._data.get("tae_discoveries.json")
        disc_count = len(_list_items(disc, "discoveries"))
        discovery_status = HealthStatus.HEALTHY if disc_count > 0 else (
            HealthStatus.WARNING if disc else HealthStatus.ATTENTION
        )
        components.append(ComponentHealth(
            "Discovery Engine",
            discovery_status,
            f"{disc_count} discovery(ies) in registry",
        ))

        learning_status = HealthStatus.HEALTHY if learning_ok else HealthStatus.ATTENTION
        components.append(ComponentHealth(
            "Learning Engine",
            learning_status,
            "Meta-learning report available" if learning_ok else "tae_learning_report.json missing",
        ))

        recs = _list_items(self._data.get("tae_strategy_recommendations.json"), "recommendations")
        ki_status = HealthStatus.HEALTHY if recs else (
            HealthStatus.WARNING if self._data.get("tae_strategy_recommendations.json") else HealthStatus.ATTENTION
        )
        components.append(ComponentHealth(
            "Knowledge Integration",
            ki_status,
            f"{len(recs)} strategy recommendation(s)",
        ))

        plans = _list_items(self._data.get("tae_strategy_evolution_plan.json"), "plans")
        evo_status = HealthStatus.HEALTHY if plans else (
            HealthStatus.WARNING if self._data.get("tae_strategy_evolution_plan.json") else HealthStatus.ATTENTION
        )
        components.append(ComponentHealth(
            "Evolution Manager",
            evo_status,
            f"{len(plans)} evolution plan(s) documented",
        ))

        bot_txt = self._text.get("bot_status.txt")
        proc = self._data.get("process_health.json")
        if proc and proc.get("status") == "RUNNING":
            trading_status = HealthStatus.HEALTHY
            trading_detail = f"Bot process health: RUNNING (pid={proc.get('pid', '?')})"
        elif bot_txt == "RUNNING":
            trading_status = HealthStatus.WARNING
            trading_detail = "bot_status.txt RUNNING — process_health not verified"
        elif bot_txt or proc:
            trading_status = HealthStatus.WARNING
            trading_detail = f"bot_status={bot_txt or NOT_AVAILABLE}"
        else:
            trading_status = HealthStatus.NOT_AVAILABLE
            trading_detail = "No bot status artifacts"
        components.append(ComponentHealth("Trading Engine", trading_status, trading_detail))

        ops_status = HealthStatus.HEALTHY if proc or bot_txt else HealthStatus.WARNING
        components.append(ComponentHealth(
            "Operations",
            ops_status,
            "process_supervisor health available" if proc else "process_health.json not found",
        ))

        overall = _worst_status([c.status for c in components])
        return {
            "overall_status": overall.value,
            "components": [c.to_dict() for c in components],
        }

    def _build_research_summary(self) -> dict[str, Any]:
        hyp_payload = self._data.get("tae_hypothesis_registry.json")
        hypotheses = _list_items(hyp_payload, "hypotheses")
        tested = sum(
            1 for h in hypotheses
            if isinstance(h, dict) and str(h.get("status", "")) == "TESTED"
        )

        kc_payload = self._data.get("tae_knowledge_candidates.json")
        candidates = _list_items(kc_payload, "candidates")
        kc_count = len(candidates)

        disc_payload = self._data.get("tae_discoveries.json")
        discoveries = _list_items(disc_payload, "discoveries")
        converted = sum(
            1 for d in discoveries
            if isinstance(d, dict) and str(d.get("status", "")) == "CONVERTED"
        )

        return {
            "hypotheses_total": len(hypotheses) if hypotheses else NOT_AVAILABLE,
            "hypotheses_tested": tested if hypotheses else NOT_AVAILABLE,
            "hypotheses_promoted": kc_count if kc_count else NOT_AVAILABLE,
            "knowledge_candidates": kc_count if kc_count else NOT_AVAILABLE,
            "discoveries": len(discoveries) if discoveries else NOT_AVAILABLE,
            "discoveries_converted": converted if discoveries else NOT_AVAILABLE,
        }

    def _build_learning_summary(self) -> dict[str, Any]:
        payload = self._data.get("tae_learning_report.json")
        if not payload:
            return {k: NOT_AVAILABLE for k in (
                "average_accuracy", "average_forward_return", "learning_confidence",
                "best_organism", "strongest_hypothesis_family",
            )}
        acc = payload.get("average_accuracy")
        return {
            "average_accuracy": round(float(acc), 4) if acc is not None else NOT_AVAILABLE,
            "average_forward_return": payload.get("average_forward_return", NOT_AVAILABLE),
            "learning_confidence": payload.get("learning_confidence", NOT_AVAILABLE),
            "best_organism": payload.get("best_organism", NOT_AVAILABLE),
            "strongest_hypothesis_family": payload.get("strongest_hypothesis_family", NOT_AVAILABLE),
        }

    def _build_validation_summary(self) -> dict[str, Any]:
        payload = self._data.get("tae_cross_validation_report.json")
        if not payload:
            return {
                "cross_regime_consistency": NOT_AVAILABLE,
                "cross_horizon_consistency": NOT_AVAILABLE,
                "cross_region_consistency": NOT_AVAILABLE,
                "validation_gaps": [],
            }

        gaps: list[str] = []
        region = payload.get("cross_region_consistency_summary", NOT_AVAILABLE)
        regime = payload.get("cross_regime_consistency_summary", NOT_AVAILABLE)
        if region == NOT_AVAILABLE or str(region) == NOT_AVAILABLE:
            gaps.append("Regional validation incomplete (Europe/UK NOT_AVAILABLE)")
        if isinstance(regime, str) and regime == NOT_AVAILABLE:
            gaps.append("Cross-regime consistency NOT_AVAILABLE for some candidates")

        follow_ups = payload.get("recommended_follow_up_research", [])
        if isinstance(follow_ups, list):
            for item in follow_ups[:5]:
                gaps.append(str(item))

        return {
            "cross_regime_consistency": regime,
            "cross_horizon_consistency": payload.get("cross_horizon_consistency_summary", NOT_AVAILABLE),
            "cross_region_consistency": region,
            "validation_gaps": gaps,
        }

    def _build_strategy_evolution(self) -> dict[str, Any]:
        rec_payload = self._data.get("tae_strategy_recommendations.json")
        recs = _list_items(rec_payload, "recommendations")
        blocked = sum(
            1 for r in recs
            if isinstance(r, dict) and r.get("recommendation_type") == "BLOCK_FROM_TRADING"
        )

        plan_payload = self._data.get("tae_strategy_evolution_plan.json")
        plans = _list_items(plan_payload, "plans")
        requiring = sum(
            1 for p in plans
            if isinstance(p, dict) and p.get("proposed_change_type") == "VALIDATION_GATE"
        )
        implementation_ready = sum(
            1 for p in plans
            if isinstance(p, dict) and p.get("proposed_change_type") != "VALIDATION_GATE"
        )

        return {
            "recommendations": len(recs) if recs else NOT_AVAILABLE,
            "evolution_plans": len(plans) if plans else NOT_AVAILABLE,
            "implementation_ready": implementation_ready if plans else NOT_AVAILABLE,
            "blocked": blocked if recs else NOT_AVAILABLE,
            "requiring_validation": requiring if plans else NOT_AVAILABLE,
        }

    def _build_priorities(self) -> list[dict[str, Any]]:
        payload = self._data.get("tae_research_priorities.json")
        items = _list_items(payload, "priorities")
        top: list[dict[str, Any]] = []
        for item in items[:5]:
            if not isinstance(item, dict):
                continue
            top.append({
                "rank": item.get("rank"),
                "opportunity_id": item.get("opportunity_id", ""),
                "title": item.get("title", ""),
                "priority_score": item.get("priority_score"),
                "source_id": item.get("source_id", ""),
                "suggested_next_action": str(item.get("suggested_next_action", ""))[:120],
            })
        return top

    def _build_trading_status(self) -> dict[str, Any]:
        bot_status = self._text.get("bot_status.txt") or NOT_AVAILABLE
        proc = self._data.get("process_health.json")
        process_health = NOT_AVAILABLE
        if proc:
            process_health = (
                f"status={proc.get('status', '?')}, pid={proc.get('pid', '?')}, "
                f"cpu={proc.get('cpu', '?')}, memory={proc.get('memory', '?')}"
            )

        market_regime = NOT_AVAILABLE
        log_text = self._text.get("bot_output.log")
        if log_text:
            for line in reversed(log_text.splitlines()):
                if "Market Regime" in line:
                    market_regime = line.strip()[:200]
                    break

        dashboard_status = NOT_AVAILABLE

        return {
            "bot_status": bot_status,
            "dashboard_status": dashboard_status,
            "market_regime": market_regime,
            "process_health": process_health,
        }

    def _build_roadmap_progress(self) -> dict[str, Any]:
        payload = self._data.get("tae_roadmap_status.json")
        if not payload:
            return {
                "maturity_level": NOT_AVAILABLE,
                "completion_pct": NOT_AVAILABLE,
                "completed_capabilities": [],
                "remaining_capabilities": [],
            }
        completed = payload.get("capabilities_completed", [])
        planned = payload.get("capabilities_planned", [])
        if not isinstance(completed, list):
            completed = []
        if not isinstance(planned, list):
            planned = []
        return {
            "maturity_level": payload.get("maturity_level", NOT_AVAILABLE),
            "completion_pct": payload.get("completion_overall_pct", NOT_AVAILABLE),
            "completed_capabilities": list(completed),
            "remaining_capabilities": list(planned),
        }

    def _build_critical_issues(
        self,
        validation: dict[str, Any],
        research: dict[str, Any],
        evolution: dict[str, Any],
    ) -> list[str]:
        issues: list[str] = []

        gaps = validation.get("validation_gaps", [])
        if isinstance(gaps, list):
            for gap in gaps:
                lower = gap.lower()
                if "europe" in lower or "uk" in lower:
                    if "Europe validation missing" not in issues and "europe" in lower:
                        issues.append("Europe validation missing")
                    if "UK validation missing" not in issues and "uk" in lower:
                        issues.append("UK validation missing")
                if "cross-regime" in lower or "regime" in lower:
                    if "Cross-regime incomplete" not in issues:
                        issues.append("Cross-regime incomplete")
                if "regional" in lower and "Missing regional datasets" not in issues:
                    issues.append("Missing regional datasets")

        kc = research.get("knowledge_candidates", 0)
        if isinstance(kc, int) and kc > 0:
            val_payload = self._data.get("tae_cross_validation_report.json")
            if val_payload:
                results = _list_items(val_payload, "candidate_results")
                for item in results:
                    if not isinstance(item, dict):
                        continue
                    regional = item.get("regional_consistency", NOT_AVAILABLE)
                    if regional == NOT_AVAILABLE:
                        cid = item.get("candidate_id", "")
                        if cid and f"Regional gap for {cid}" not in issues:
                            issues.append(f"Regional validation gap for candidate {cid}")

        req_val = evolution.get("requiring_validation", 0)
        if isinstance(req_val, int) and req_val > 0:
            issues.append(
                f"{req_val} evolution plan(s) blocked behind validation gate"
            )

        hyp_total = research.get("hypotheses_total", 0)
        if isinstance(hyp_total, int) and hyp_total == 0:
            issues.append("Hypothesis registry empty or unavailable")

        # Deduplicate preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for issue in issues:
            if issue not in seen:
                seen.add(issue)
                unique.append(issue)
        return unique

    def _build_executive_summary(
        self,
        ecosystem: dict[str, Any],
        research: dict[str, Any],
        learning: dict[str, Any],
        validation: dict[str, Any],
        evolution: dict[str, Any],
        trading: dict[str, Any],
        issues: list[str],
    ) -> list[str]:
        overall = ecosystem.get("overall_status", NOT_AVAILABLE)
        lines = ["TAE DAILY INTELLIGENCE", ""]

        if overall == HealthStatus.HEALTHY.value:
            lines.append("Research ecosystem healthy.")
        elif overall == HealthStatus.WARNING.value:
            lines.append("Research ecosystem operational with warnings.")
        else:
            lines.append("Research ecosystem needs attention.")

        proc = trading.get("process_health", NOT_AVAILABLE)
        bot = trading.get("bot_status", NOT_AVAILABLE)
        if proc != NOT_AVAILABLE and "RUNNING" in str(proc):
            lines.append("Trading infrastructure reports active bot process.")
        elif bot == "RUNNING":
            lines.append("Trading status file indicates bot RUNNING (verify process_health).")
        else:
            lines.append("Trading infrastructure status limited or stopped.")

        kc = research.get("knowledge_candidates", 0)
        disc = research.get("discoveries", 0)
        if isinstance(kc, int) and kc > 0:
            lines.append(f"Knowledge generation operational ({kc} candidates, {disc} discoveries).")
        else:
            lines.append("Knowledge pipeline needs more candidate promotion.")

        impl_ready = evolution.get("implementation_ready", 0)
        if isinstance(impl_ready, int) and impl_ready > 0:
            lines.append(f"{impl_ready} evolution plan(s) ready for human implementation review.")
        else:
            lines.append("No strategy approved for implementation.")

        req_val = evolution.get("requiring_validation", 0)
        if isinstance(req_val, int) and req_val > 0:
            lines.append("Continue cross-regime and regional validation before strategy changes.")

        if issues:
            lines.append(f"Critical attention: {issues[0]}.")
        else:
            lines.append("No critical blocking issues in current artifacts.")

        conf = learning.get("learning_confidence", NOT_AVAILABLE)
        if conf != NOT_AVAILABLE:
            lines.append(f"Learning confidence: {conf} (research meta-score, not trading authorization).")

        lines.append("Human approval still required before any evolution implementation.")
        lines.append("No live trading files modified.")
        return lines[:12]
