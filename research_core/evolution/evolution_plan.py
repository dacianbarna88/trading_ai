"""
Evolution plan model — Phase V Sprint A4

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Auditable strategy evolution plans — not live config or execution changes.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from research_core.constants import RESEARCH_SAFETY_BANNER

logger = logging.getLogger(__name__)

DEFAULT_EVOLUTION_PLAN_PATH = Path("tae_strategy_evolution_plan.json")
DEFAULT_EVOLUTION_NOTICE_PATH = Path("tae_strategy_evolution_notice.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_strategy_evolution_plan"


class ProposedChangeType(str, Enum):
    RESEARCH_WEIGHT_ADJUSTMENT = "RESEARCH_WEIGHT_ADJUSTMENT"
    OBSERVATION_TRACKING = "OBSERVATION_TRACKING"
    VALIDATION_GATE = "VALIDATION_GATE"
    PAPER_ONLY_TRIAL = "PAPER_ONLY_TRIAL"


class ImplementationStatus(str, Enum):
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    IMPLEMENTED = "IMPLEMENTED"


@dataclass
class EvolutionPlanEntry:
    plan_id: str
    source_recommendation_id: str
    proposed_change_type: ProposedChangeType
    proposed_target: str
    proposed_change: str
    rationale: str
    expected_benefit: str
    risk_assessment: str
    rollback_plan: str
    human_approval_required: bool = True
    implementation_status: ImplementationStatus = ImplementationStatus.NOT_IMPLEMENTED
    safety_mode: str = RESEARCH_SAFETY_BANNER
    confidence: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if isinstance(self.proposed_change_type, str):
            self.proposed_change_type = ProposedChangeType(self.proposed_change_type)
        if isinstance(self.implementation_status, str):
            self.implementation_status = ImplementationStatus(self.implementation_status)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "source_recommendation_id": self.source_recommendation_id,
            "proposed_change_type": self.proposed_change_type.value,
            "proposed_target": self.proposed_target,
            "proposed_change": self.proposed_change,
            "rationale": self.rationale,
            "expected_benefit": self.expected_benefit,
            "risk_assessment": self.risk_assessment,
            "rollback_plan": self.rollback_plan,
            "human_approval_required": self.human_approval_required,
            "implementation_status": self.implementation_status.value,
            "safety_mode": self.safety_mode,
            "confidence": round(self.confidence, 2),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvolutionPlanEntry | None:
        try:
            created = data.get("created_at")
            if created:
                dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = datetime.now(timezone.utc)

            change_type = str(
                data.get("proposed_change_type", ProposedChangeType.OBSERVATION_TRACKING.value)
            )
            try:
                proposed_change_type = ProposedChangeType(change_type)
            except ValueError:
                proposed_change_type = ProposedChangeType.OBSERVATION_TRACKING

            impl = str(data.get("implementation_status", ImplementationStatus.NOT_IMPLEMENTED.value))
            try:
                implementation_status = ImplementationStatus(impl)
            except ValueError:
                implementation_status = ImplementationStatus.NOT_IMPLEMENTED

            return cls(
                plan_id=str(data["plan_id"]),
                source_recommendation_id=str(data.get("source_recommendation_id", "")),
                proposed_change_type=proposed_change_type,
                proposed_target=str(data.get("proposed_target", "")),
                proposed_change=str(data.get("proposed_change", "")),
                rationale=str(data.get("rationale", "")),
                expected_benefit=str(data.get("expected_benefit", "")),
                risk_assessment=str(data.get("risk_assessment", "")),
                rollback_plan=str(data.get("rollback_plan", "")),
                human_approval_required=bool(data.get("human_approval_required", True)),
                implementation_status=implementation_status,
                safety_mode=str(data.get("safety_mode", RESEARCH_SAFETY_BANNER)),
                confidence=float(data.get("confidence", 0)),
                created_at=dt,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def summary_line(self) -> str:
        return (
            f"{self.plan_id} | {self.proposed_change_type.value} | "
            f"confidence={self.confidence:.1f} | {self.source_recommendation_id}"
        )


@dataclass
class EvolutionPlanResult:
    recommendations_loaded: int
    recommendations_eligible: int
    recommendations_blocked: int
    plans_generated: int
    plans_skipped_duplicate: int
    plans: list[EvolutionPlanEntry]
    highest_confidence_plan: EvolutionPlanEntry | None
    validation_gated_plans: list[EvolutionPlanEntry]
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = RESEARCH_SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "recommendations_loaded": self.recommendations_loaded,
            "recommendations_eligible": self.recommendations_eligible,
            "recommendations_blocked": self.recommendations_blocked,
            "plans_generated": self.plans_generated,
            "plans_skipped_duplicate": self.plans_skipped_duplicate,
            "highest_confidence_plan_id": (
                self.highest_confidence_plan.plan_id if self.highest_confidence_plan else ""
            ),
            "validation_gated_plan_count": len(self.validation_gated_plans),
            "sources_loaded": dict(self.sources_loaded),
            "plans": [p.to_dict() for p in self.plans],
        }

    def format_report(self) -> str:
        lines = [
            "===== TAE STRATEGY EVOLUTION PLAN =====",
            "",
            f"Safety: {self.safety_mode}",
            f"Generated: {self.generated_at.isoformat()}",
            "",
            f"Recommendations loaded: {self.recommendations_loaded}",
            f"Recommendations eligible (not BLOCK_FROM_TRADING): {self.recommendations_eligible}",
            f"Recommendations blocked (BLOCK_FROM_TRADING): {self.recommendations_blocked}",
            f"Plans generated (this run): {self.plans_generated}",
            f"Duplicates skipped (this run): {self.plans_skipped_duplicate}",
            f"Total plans in store: {len(self.plans)}",
            "",
            "Sources loaded:",
        ]
        for name, ok in sorted(self.sources_loaded.items()):
            lines.append(f"  {name}: {'yes' if ok else 'no'}")
        lines.append("")

        if self.highest_confidence_plan:
            hc = self.highest_confidence_plan
            lines.append("Highest-confidence plan:")
            lines.append(f"  {hc.summary_line()}")
            lines.append(f"  target: {hc.proposed_target[:100]}")
            lines.append("")

        lines.append(
            f"Plans requiring validation gate: {len(self.validation_gated_plans)}"
        )
        for plan in self.validation_gated_plans:
            lines.append(f"  - {plan.plan_id}: {plan.proposed_change_type.value}")
        lines.append("")

        lines.append("All evolution plans:")
        for plan in self.plans:
            lines.append(f"  {plan.summary_line()}")
            lines.append(
                f"    human_approval_required={plan.human_approval_required} "
                f"implementation_status={plan.implementation_status.value}"
            )
        lines.append("")
        lines.append("Evolution plans only — no live bot or config changes applied.")
        lines.append("")
        return "\n".join(lines)

    def actionable_plans(self) -> list[EvolutionPlanEntry]:
        """Plans ready for implementation review (not blocked behind validation gate)."""
        return [
            p for p in self.plans
            if p.proposed_change_type != ProposedChangeType.VALIDATION_GATE
        ]

    def format_human_notice(self, live_files_unchanged: bool = True) -> str:
        """Human-readable notice for project owner — Romanian-friendly plain language."""
        lines = [
            "===== TAE — NOTIFICARE EVOLUȚIE STRATEGIE =====",
            "",
            f"Generat: {self.generated_at.isoformat()}",
            f"Mod sigur: {self.safety_mode}",
            "",
            f"Număr planuri de evoluție documentate: {len(self.plans)}",
            f"Planuri noi în această rulare: {self.plans_generated}",
            "",
        ]

        actionable = self.actionable_plans()
        has_documented = len(self.plans) > 0

        if not has_documented:
            lines.extend(self._format_no_plans_notice())
        else:
            lines.extend(self._format_documented_plans_notice(actionable))

        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "NOT IMPLEMENTED — HUMAN APPROVAL REQUIRED",
            "",
            "===== CONFIRMARE SIGURANȚĂ =====",
        ])
        if live_files_unchanged:
            lines.append("No live trading files were modified")
            lines.append(
                "(live_bot.py, config/settings.py, dashboard_v2.py, portfolio.csv — neatinse)"
            )
        else:
            lines.append(
                "Verificare necesară: unele fișiere de trading live ar putea fi modificate."
            )

        lines.append("")
        lines.append(
            "Acest mesaj este doar pentru revizuire umană — nu autorizează broker sau execuție."
        )
        lines.append("")
        return "\n".join(lines)

    def _format_no_plans_notice(self) -> list[str]:
        lines = [
            "No strategy evolution is ready for implementation review.",
            "Nu există planuri de evoluție documentate în acest moment.",
            "",
            "Ce lipsește (evidence):",
        ]
        missing = self._missing_evidence_items()
        if missing:
            for item in missing:
                lines.append(f"  - {item}")
        else:
            lines.append("  - Nu s-au putut determina lacunele — verificați artefactele de research.")
        return lines

    def _format_documented_plans_notice(self, actionable: list[EvolutionPlanEntry]) -> list[str]:
        lines: list[str] = []
        hc = self.highest_confidence_plan

        if hc is not None:
            lines.append("Propunere cu cea mai mare încredere (highest-confidence):")
            lines.append(f"  ID plan: {hc.plan_id}")
            lines.append(f"  Încredere (confidence): {hc.confidence:.1f}")
            lines.append(f"  Tip schimbare: {_change_type_plain(hc.proposed_change_type)}")
            lines.append("")
            lines.append("Rezumat schimbare propusă:")
            lines.append(f"  {hc.proposed_change}")
            lines.append("")
            lines.append("Baza evidenței (evidence basis):")
            lines.append(f"  {hc.rationale[:400]}")
            lines.append("")
            lines.append("Status validare:")
            lines.append(f"  {_validation_status_plain(hc)}")
            lines.append("")
            lines.append("Note de risc:")
            lines.append(f"  {hc.risk_assessment[:400]}")
            lines.append("")
            lines.append("Plan de revenire (rollback):")
            lines.append(f"  {hc.rollback_plan[:300]}")
            lines.append("")

        if not actionable:
            lines.extend([
                "===== STATUS IMPLEMENTARE =====",
                "No strategy evolution is ready for implementation review.",
                "Niciun plan este pregătit pentru revizuire de implementare.",
                "",
                "Planurile documentate necesită validare suplimentară înainte de orice schimbare:",
            ])
            for plan in self.validation_gated_plans:
                lines.append(f"  - {plan.plan_id} ({plan.proposed_target})")
            lines.append("")
            lines.append("Ce lipsește (evidence):")
            missing = self._missing_evidence_items()
            for item in missing:
                lines.append(f"  - {item}")
        else:
            lines.extend([
                "===== PLANURI PREGĂTITE PENTRU REVIZUIRE =====",
                f"Planuri acționabile pentru revizuire: {len(actionable)}",
            ])
            for plan in actionable:
                lines.append(
                    f"  - {plan.plan_id}: {_change_type_plain(plan.proposed_change_type)} "
                    f"(confidence={plan.confidence:.1f})"
                )

        return lines

    def _missing_evidence_items(self) -> list[str]:
        items: list[str] = []

        for name, ok in sorted(self.sources_loaded.items()):
            if not ok:
                items.append(f"Artefact lipsă: {name}")

        if self.recommendations_loaded == 0:
            items.append("tae_strategy_recommendations.json — fără recomandări de strategie")
        if self.recommendations_eligible == 0 and self.recommendations_loaded > 0:
            items.append(
                "Toate recomandările sunt BLOCK_FROM_TRADING — nimic eligibil pentru plan"
            )

        if self.validation_gated_plans:
            items.append(
                "Validare cross-regime incompletă pentru unele candidați "
                "(regime_consistency NOT_AVAILABLE)"
            )
            items.append(
                "Validare regională Europe/UK NOT_AVAILABLE — CSV-uri regionale "
                "legate de ipoteză necesare"
            )
            items.append(
                "Prioritate research: închideți gap-urile de validare înainte de "
                "orice schimbare de strategie"
            )

        if not self.sources_loaded.get("tae_cross_validation_report.json", False):
            items.append("tae_cross_validation_report.json — rulare validare cross-regime (D6)")
        if not self.sources_loaded.get("tae_learning_report.json", False):
            items.append("tae_learning_report.json — raport learning pentru context")
        if not self.sources_loaded.get("tae_research_priorities.json", False):
            items.append("tae_research_priorities.json — priorități research pentru context")

        return items

    def write_human_notice(
        self,
        path: Path | None = None,
        live_files_unchanged: bool = True,
    ) -> Path:
        notice_path = path or DEFAULT_EVOLUTION_NOTICE_PATH
        notice_path.write_text(
            self.format_human_notice(live_files_unchanged=live_files_unchanged) + "\n",
            encoding="utf-8",
        )
        return notice_path


def _change_type_plain(change_type: ProposedChangeType) -> str:
    labels = {
        ProposedChangeType.RESEARCH_WEIGHT_ADJUSTMENT: (
            "Ajustare greutate research (paper only, nu live bot)"
        ),
        ProposedChangeType.OBSERVATION_TRACKING: (
            "Monitorizare sub observație (fără schimbare live)"
        ),
        ProposedChangeType.VALIDATION_GATE: (
            "Poartă de validare — validare necesară înainte de orice schimbare"
        ),
        ProposedChangeType.PAPER_ONLY_TRIAL: (
            "Trial paper only — revizuire înainte de orice expunere"
        ),
    }
    return labels.get(change_type, change_type.value)


def _validation_status_plain(plan: EvolutionPlanEntry) -> str:
    if plan.proposed_change_type == ProposedChangeType.VALIDATION_GATE:
        return (
            "Validare incompletă — candidatul necesită teste cross-regime și regionale "
            "înainte de revizuire de implementare. "
            f"Status plan: {plan.implementation_status.value}."
        )
    return (
        f"Validare documentată în research — plan în revizuire umană. "
        f"Status: {plan.implementation_status.value}."
    )


class EvolutionPlanStore:
    """JSON persistence for strategy evolution plans — stdlib only."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_EVOLUTION_PLAN_PATH
        self._plans: dict[str, EvolutionPlanEntry] = {}
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def loaded_at_startup(self) -> bool:
        return self._loaded_at_startup

    def list_all(self) -> list[EvolutionPlanEntry]:
        return sorted(self._plans.values(), key=lambda p: p.created_at)

    def get(self, plan_id: str) -> EvolutionPlanEntry | None:
        return self._plans.get(plan_id)

    def has_recommendation(self, source_recommendation_id: str) -> bool:
        return any(
            p.source_recommendation_id == source_recommendation_id for p in self._plans.values()
        )

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Evolution plan unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict):
            return False
        if payload.get("schema") != SCHEMA_NAME:
            return False

        items = payload.get("plans", [])
        if not isinstance(items, list):
            return False

        self._plans.clear()
        for item in items:
            if not isinstance(item, dict):
                continue
            entry = EvolutionPlanEntry.from_dict(item)
            if entry is not None:
                self._plans[entry.plan_id] = entry
        return True

    def merge_new(self, plans: list[EvolutionPlanEntry]) -> tuple[int, int]:
        added = 0
        skipped = 0
        for plan in plans:
            if plan.plan_id in self._plans:
                skipped += 1
                continue
            if self.has_recommendation(plan.source_recommendation_id):
                skipped += 1
                continue
            self._plans[plan.plan_id] = plan
            added += 1
        return added, skipped

    def persist(self, result: EvolutionPlanResult | None = None) -> Path:
        if result is not None:
            payload = result.to_dict()
            payload["plans"] = [p.to_dict() for p in self.list_all()]
        else:
            payload = {
                "version": SCHEMA_VERSION,
                "schema": SCHEMA_NAME,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "safety_mode": RESEARCH_SAFETY_BANNER,
                "plans": [p.to_dict() for p in self.list_all()],
            }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path
