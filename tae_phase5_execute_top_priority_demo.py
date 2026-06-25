"""
TAE Phase V Sprint A2 — Execute Top Research Priority

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Executes only the top priority from tae_research_priorities.json.
Focused follow-up validation — not trading or execution.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.autonomy.prioritization_report import DEFAULT_PRIORITIES_PATH
from research_core.constants import RESEARCH_SAFETY_BANNER
from research_core.validation.cross_regime_validator import (
    MULTI_HORIZON_PATH,
    CrossRegimeValidator,
)
from research_core.validation.validation_report import NOT_AVAILABLE

EXECUTION_REPORT_PATH = Path("tae_top_priority_execution.json")
CROSS_VALIDATION_PATH = Path("tae_cross_validation_report.json")
SUMMARY_TXT = "tae_phase5_execute_top_priority_summary.txt"


@dataclass
class ExecutionResult:
    selected_priority: dict[str, Any]
    candidate_tested: str
    gap_addressed: str
    result_summary: str
    robustness_before: float | str
    robustness_after: float
    robustness_improved: bool
    remains_unavailable: list[str]
    follow_up_validation: dict[str, Any] = field(default_factory=dict)
    safety_mode: str = RESEARCH_SAFETY_BANNER
    executed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "tae_top_priority_execution",
            "executed_at": self.executed_at.isoformat(),
            "safety_mode": self.safety_mode,
            "selected_priority": self.selected_priority,
            "candidate_tested": self.candidate_tested,
            "gap_addressed": self.gap_addressed,
            "result_summary": self.result_summary,
            "robustness_before": self.robustness_before,
            "robustness_after": round(self.robustness_after, 2),
            "robustness_improved": self.robustness_improved,
            "remains_unavailable": list(self.remains_unavailable),
            "follow_up_validation": self.follow_up_validation,
        }

    def format_report(self) -> str:
        lines = [
            "===== TAE PHASE V SPRINT A2 — EXECUTE TOP PRIORITY =====",
            "",
            RESEARCH_SAFETY_BANNER,
            "Focused research execution — NOT trading or broker actions.",
            "",
            "===== SELECTED PRIORITY =====",
            f"  opportunity_id: {self.selected_priority.get('opportunity_id', '')}",
            f"  rank: #{self.selected_priority.get('rank', 1)}",
            f"  priority_score: {self.selected_priority.get('priority_score', 0)}",
            f"  source_type: {self.selected_priority.get('source_type', '')}",
            f"  source_id: {self.selected_priority.get('source_id', '')}",
            f"  title: {self.selected_priority.get('title', '')}",
            f"  suggested_action: {self.selected_priority.get('suggested_next_action', '')}",
            "",
            f"Candidate tested: {self.candidate_tested}",
            f"Gap addressed: {self.gap_addressed}",
            "",
            "===== RESULT =====",
            self.result_summary,
            "",
            f"Robustness before: {self.robustness_before}",
            f"Robustness after:  {self.robustness_after:.2f}",
            f"Robustness improved: {self.robustness_improved}",
            "",
            "Remains unavailable:",
        ]
        if self.remains_unavailable:
            for item in self.remains_unavailable:
                lines.append(f"  - {item}")
        else:
            lines.append("  (none)")
        lines.append("")
        if self.follow_up_validation:
            lines.append("Follow-up validation detail:")
            for key, val in self.follow_up_validation.items():
                lines.append(f"  {key}: {val}")
            lines.append("")
        lines.append("No broker. No execution. No live bot.")
        lines.append("")
        return "\n".join(lines)


def _load_priorities() -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    if not DEFAULT_PRIORITIES_PATH.is_file():
        return None, []
    try:
        payload = json.loads(DEFAULT_PRIORITIES_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, []
    if not isinstance(payload, dict):
        return None, []
    priorities = payload.get("priorities", [])
    if not isinstance(priorities, list) or not priorities:
        return payload, []
    return payload, priorities


def _prior_baseline(candidate_id: str) -> tuple[float | str, dict[str, Any]]:
    if not CROSS_VALIDATION_PATH.is_file():
        return NOT_AVAILABLE, {}
    try:
        payload = json.loads(CROSS_VALIDATION_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return NOT_AVAILABLE, {}
    for item in payload.get("candidate_results", []):
        if isinstance(item, dict) and item.get("candidate_id") == candidate_id:
            score = item.get("robustness_score", NOT_AVAILABLE)
            return score, item
    return NOT_AVAILABLE, {}


def _load_market_reference() -> dict[str, dict[str, str]]:
    refs: dict[str, dict[str, str]] = {}
    if not MULTI_HORIZON_PATH.is_file():
        return refs
    try:
        with MULTI_HORIZON_PATH.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                market = str(row.get("Market", "")).upper()
                if market == "US":
                    refs["US"] = dict(row)
                elif market == "EU":
                    refs["Europe"] = dict(row)
                elif market == "UK":
                    refs["UK"] = dict(row)
    except (OSError, csv.Error):
        pass
    return refs


def _execute_validation_gap(candidate_id: str, priority: dict[str, Any]) -> ExecutionResult:
    prior_score, prior_detail = _prior_baseline(candidate_id)
    validator = CrossRegimeValidator()
    validation = validator.validate_candidate_by_id(candidate_id)

    if validation is None:
        return ExecutionResult(
            selected_priority=priority,
            candidate_tested=candidate_id,
            gap_addressed="Validation could not run — candidate not found.",
            result_summary="No candidate located in knowledge registry.",
            robustness_before=prior_score,
            robustness_after=0.0,
            robustness_improved=False,
            remains_unavailable=["Candidate registry lookup failed."],
        )

    remains: list[str] = []
    if validation.regional_consistency is None:
        remains.append("Europe: NOT_AVAILABLE (no hypothesis-linked regional signal CSV)")
        remains.append("UK: NOT_AVAILABLE (no hypothesis-linked regional signal CSV)")
    if validation.regime_consistency is None:
        remains.append("Cross-regime consistency: NOT_AVAILABLE")

    gap_parts: list[str] = []
    if prior_detail.get("regional_consistency") == NOT_AVAILABLE:
        gap_parts.append("regional validation (Europe/UK)")
    if prior_detail.get("regime_consistency") == NOT_AVAILABLE:
        gap_parts.append("regime consistency")
    gap_addressed = (
        "Focused re-validation for " + ", ".join(gap_parts)
        if gap_parts
        else "Focused follow-up validation per top priority"
    )

    refs = _load_market_reference()
    follow_up: dict[str, Any] = {
        "regime_slices": {
            k: v.to_dict() for k, v in validation.regime_slices.items()
        },
        "horizon_slices": {
            k: v.to_dict() for k, v in validation.horizon_slices.items()
        },
        "region_slices": {
            k: v.to_dict() for k, v in validation.region_slices.items()
        },
    }
    if refs:
        follow_up["market_reference_returns"] = {
            region: {
                "return_2y": row.get("Return_2Y_%", NOT_AVAILABLE),
                "return_5y": row.get("Return_5Y_%", NOT_AVAILABLE),
                "return_10y": row.get("Return_10Y_%", NOT_AVAILABLE),
            }
            for region, row in refs.items()
        }
        follow_up["reference_note"] = (
            "Market reference returns are contextual benchmarks only — "
            "not hypothesis-linked candidate validation."
        )

    us_slice = validation.region_slices.get("US")
    regime_evaluated = [
        r for r, s in validation.regime_slices.items() if s.status == "EVALUATED"
    ]

    result_summary = (
        f"Re-validated {candidate_id}. "
        f"Regimes evaluated: {', '.join(regime_evaluated) or 'none'}. "
        f"US n={us_slice.sample_size if us_slice else 0}, "
        f"accuracy={us_slice.accuracy:.2%}, "
        f"avg_return={us_slice.avg_forward_return:.2f}%. "
        "Regional Europe/UK remain NOT_AVAILABLE without linked CSVs."
        if us_slice and us_slice.accuracy is not None
        else (
            f"Re-validated {candidate_id} ({validation.title[:60]}). "
            "Insufficient US cohort metrics."
        )
    )

    before_f = float(prior_score) if isinstance(prior_score, (int, float)) else 0.0
    after_f = validation.robustness_score
    improved = after_f > before_f if isinstance(prior_score, (int, float)) else False

    if validation.regional_consistency is None and refs:
        gap_addressed += " — US cohort re-confirmed; reference market data loaded for context"

    return ExecutionResult(
        selected_priority=priority,
        candidate_tested=candidate_id,
        gap_addressed=gap_addressed,
        result_summary=result_summary,
        robustness_before=prior_score,
        robustness_after=after_f,
        robustness_improved=improved,
        remains_unavailable=remains,
        follow_up_validation=follow_up,
    )


def run_execute_top_priority() -> ExecutionResult:
    print("===== TAE PHASE V SPRINT A2 — EXECUTE TOP PRIORITY =====")
    print(RESEARCH_SAFETY_BANNER)
    print("Executes single top research priority — not trading.")
    print("No broker. No live bot. No order execution.")
    print()

    meta, priorities = _load_priorities()
    if not priorities:
        result = ExecutionResult(
            selected_priority={},
            candidate_tested="",
            gap_addressed="",
            result_summary="No priorities loaded from tae_research_priorities.json.",
            robustness_before=NOT_AVAILABLE,
            robustness_after=0.0,
            robustness_improved=False,
            remains_unavailable=["tae_research_priorities.json missing or empty."],
        )
        print(result.format_report())
        return result

    top = priorities[0]
    print(f"Loaded priorities: {DEFAULT_PRIORITIES_PATH}")
    print(f"Top priority: {top.get('opportunity_id')} (score={top.get('priority_score')})")
    print()

    source_type = str(top.get("source_type", ""))
    source_id = str(top.get("source_id", ""))

    if source_type == "VALIDATION_GAP" and source_id.startswith("kn_"):
        result = _execute_validation_gap(source_id, top)
    else:
        result = ExecutionResult(
            selected_priority=top,
            candidate_tested=source_id,
            gap_addressed="Top priority is not a candidate validation gap.",
            result_summary=(
                f"Priority type '{source_type}' deferred — Sprint A2 executes "
                "VALIDATION_GAP for knowledge candidates only."
            ),
            robustness_before=NOT_AVAILABLE,
            robustness_after=0.0,
            robustness_improved=False,
            remains_unavailable=[f"Execution path for {source_type} not implemented in A2."],
        )

    EXECUTION_REPORT_PATH.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = result.format_report()
    print(report)

    Path(SUMMARY_TXT).write_text(report + "\n", encoding="utf-8")
    print(f"Saved: {EXECUTION_REPORT_PATH}")
    print(f"Saved: {SUMMARY_TXT}")

    return result


def main() -> None:
    run_execute_top_priority()


if __name__ == "__main__":
    main()
