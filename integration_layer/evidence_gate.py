"""
TAE Evidence Integration Gate

PAPER_ONLY | NO_BROKER | NO_EXECUTION

Reads tae_evidence_engine_report.json and decides which evidence items may
progress toward implementation (paper validation only — no live changes).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from integration_layer.integration_report import (
    GateDecision,
    GateStatus,
    IntegrationGateReport,
    IntegrationGateVerdict,
)

logger = logging.getLogger(__name__)

EVIDENCE_ENGINE_REPORT_PATH = Path("tae_evidence_engine_report.json")

ELIGIBILITY_TO_GATE: dict[str, GateStatus] = {
    "NOT_ELIGIBLE": GateStatus.BLOCKED,
    "RESEARCH_ONLY": GateStatus.RESEARCH_HOLD,
    "PAPER_VALIDATION_ELIGIBLE": GateStatus.PAPER_CANDIDATE,
    "DEPLOYMENT_CANDIDATE": GateStatus.DEPLOYMENT_REVIEW_REQUIRED,
}

# Explicit allowlist — only these IDs may become implementation candidates.
IMPLEMENTATION_ALLOWLIST: frozenset[str] = frozenset({"score_100_current_not_defective"})

ENGINE_ALIGNED_VERDICT = "EVIDENCE_ENGINE_SOURCE_OF_TRUTH_ALIGNED"


def _load_evidence_engine_report(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Evidence engine report not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Invalid evidence engine report: {path}")
    return payload


class EvidenceIntegrationGate:
    def __init__(
        self,
        evidence_report_path: Path | str = EVIDENCE_ENGINE_REPORT_PATH,
        allowlist: frozenset[str] | None = None,
    ) -> None:
        self._evidence_report_path = Path(evidence_report_path)
        self._allowlist = allowlist if allowlist is not None else IMPLEMENTATION_ALLOWLIST

    def evaluate(self) -> IntegrationGateReport:
        engine_report = _load_evidence_engine_report(self._evidence_report_path)
        engine_verdict = str(engine_report.get("verdict", ""))
        contradictions = engine_report.get("contradictions", [])
        engine_aligned = (
            engine_verdict == ENGINE_ALIGNED_VERDICT and not contradictions
        )

        items = engine_report.get("evidence_items", [])
        if not isinstance(items, list):
            items = []

        decisions: list[GateDecision] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            decision = self._decide(raw, engine_aligned)
            decisions.append(decision)

        decisions.sort(key=lambda d: d.evidence_id)

        status_counts = {s.value: 0 for s in GateStatus}
        allowed_count = 0
        for d in decisions:
            status_counts[d.gate_status] = status_counts.get(d.gate_status, 0) + 1
            if d.implementation_allowed:
                allowed_count += 1

        return IntegrationGateReport(
            verdict=IntegrationGateVerdict.EVIDENCE_INTEGRATION_GATE_READY,
            evidence_engine_verdict=engine_verdict,
            decisions=decisions,
            allowed_count=allowed_count,
            blocked_count=status_counts.get(GateStatus.BLOCKED.value, 0),
            research_hold_count=status_counts.get(GateStatus.RESEARCH_HOLD.value, 0),
            paper_candidate_count=status_counts.get(GateStatus.PAPER_CANDIDATE.value, 0),
            deployment_review_count=status_counts.get(
                GateStatus.DEPLOYMENT_REVIEW_REQUIRED.value, 0
            ),
            allowlist=sorted(self._allowlist),
        )

    def _decide(self, item: dict, engine_aligned: bool) -> GateDecision:
        evidence_id = str(item.get("evidence_id", ""))
        title = str(item.get("title", ""))
        evidence_status = str(item.get("status", ""))
        eligibility = str(item.get("implementation_eligibility", "NOT_ELIGIBLE"))

        gate_status = ELIGIBILITY_TO_GATE.get(eligibility, GateStatus.BLOCKED)
        block_reason: str | None = None
        allowed = False

        if gate_status == GateStatus.BLOCKED:
            block_reason = "NOT_ELIGIBLE"
        elif gate_status == GateStatus.RESEARCH_HOLD:
            block_reason = "RESEARCH_ONLY"
        elif gate_status == GateStatus.DEPLOYMENT_REVIEW_REQUIRED:
            block_reason = "NOT_ON_IMPLEMENTATION_ALLOWLIST"
        elif gate_status == GateStatus.PAPER_CANDIDATE:
            if evidence_id not in self._allowlist:
                block_reason = "NOT_ON_IMPLEMENTATION_ALLOWLIST"
            elif evidence_status != "CONFIRMED":
                block_reason = f"EVIDENCE_STATUS_{evidence_status}"
            elif not engine_aligned:
                block_reason = "EVIDENCE_ENGINE_NOT_ALIGNED"
            else:
                allowed = True

        return GateDecision(
            evidence_id=evidence_id,
            title=title,
            evidence_status=evidence_status,
            implementation_eligibility=eligibility,
            gate_status=gate_status.value,
            implementation_allowed=allowed,
            block_reason=block_reason,
        )
