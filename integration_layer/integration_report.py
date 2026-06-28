"""
TAE Evidence Integration Gate report

PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_JSON_PATH = Path("tae_evidence_integration_gate.json")
DEFAULT_TXT_PATH = Path("tae_evidence_integration_gate.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_evidence_integration_gate"
SAFETY_BANNER = "PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class GateStatus(str, Enum):
    BLOCKED = "BLOCKED"
    RESEARCH_HOLD = "RESEARCH_HOLD"
    PAPER_CANDIDATE = "PAPER_CANDIDATE"
    DEPLOYMENT_REVIEW_REQUIRED = "DEPLOYMENT_REVIEW_REQUIRED"


class IntegrationGateVerdict(str, Enum):
    EVIDENCE_INTEGRATION_GATE_READY = "EVIDENCE_INTEGRATION_GATE_READY"


@dataclass
class GateDecision:
    evidence_id: str
    title: str
    evidence_status: str
    implementation_eligibility: str
    gate_status: str
    implementation_allowed: bool
    block_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "title": self.title,
            "evidence_status": self.evidence_status,
            "implementation_eligibility": self.implementation_eligibility,
            "gate_status": self.gate_status,
            "implementation_allowed": self.implementation_allowed,
            "block_reason": self.block_reason,
        }


@dataclass
class IntegrationGateReport:
    verdict: IntegrationGateVerdict
    evidence_engine_verdict: str
    decisions: list[GateDecision]
    allowed_count: int
    blocked_count: int
    research_hold_count: int
    paper_candidate_count: int
    deployment_review_count: int
    allowlist: list[str]
    promotion_gate_chain: dict[str, Any] | None = None
    sources_loaded: dict[str, bool] = field(default_factory=dict)
    safety_mode: str = SAFETY_BANNER
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "verdict": self.verdict.value,
            "evidence_engine_verdict": self.evidence_engine_verdict,
            "allowlist": list(self.allowlist),
            "allowed_count": self.allowed_count,
            "blocked_count": self.blocked_count,
            "research_hold_count": self.research_hold_count,
            "paper_candidate_count": self.paper_candidate_count,
            "deployment_review_count": self.deployment_review_count,
            "decisions": [d.to_dict() for d in self.decisions],
            "promotion_gate_chain": dict(self.promotion_gate_chain)
            if self.promotion_gate_chain
            else None,
            "sources_loaded": dict(self.sources_loaded),
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE EVIDENCE INTEGRATION GATE =====",
            "",
            f"Siguranță: {self.safety_mode}",
            f"Generat: {self.generated_at.isoformat()}",
            "",
            f"Verdict: {self.verdict.value}",
            f"Evidence Engine verdict: {self.evidence_engine_verdict}",
            f"Allowlist: {', '.join(self.allowlist)}",
            "",
            f"Permise implementare: {self.allowed_count}",
            f"  BLOCKED: {self.blocked_count}",
            f"  RESEARCH_HOLD: {self.research_hold_count}",
            f"  PAPER_CANDIDATE: {self.paper_candidate_count}",
            f"  DEPLOYMENT_REVIEW_REQUIRED: {self.deployment_review_count}",
            "",
        ]
        if self.promotion_gate_chain:
            chain = self.promotion_gate_chain
            lines.extend([
                "===== PROMOTION GATE CHAIN =====",
                f"  promotion_gate_registered: {chain.get('promotion_gate_registered')}",
                f"  promotion_gate_status: {chain.get('promotion_gate_status')}",
                f"  promotion_gate_source: {chain.get('promotion_gate_source')}",
                f"  promotion_gate_last_refresh: {chain.get('promotion_gate_last_refresh')}",
                f"  integration_gate_status: {chain.get('integration_gate_status')}",
                f"  review_candidate_id: {chain.get('review_candidate_id')}",
                "",
            ])
        lines.extend([
            "===== DECIZII GATE =====",
        ])
        for decision in self.decisions:
            allowed = "ALLOWED" if decision.implementation_allowed else "DENIED"
            lines.append(
                f"  [{decision.gate_status}] {decision.evidence_id} — {allowed}"
            )
            lines.append(f"    {decision.title}")
            lines.append(
                f"    Eligibility: {decision.implementation_eligibility} | "
                f"Status: {decision.evidence_status}"
            )
            if decision.block_reason:
                lines.append(f"    Motiv: {decision.block_reason}")
        lines.extend([
            "",
            "===== AVERTISMENT =====",
            "PAPER ONLY — NO EXECUTION",
            "No live trading files were modified",
            "Nu modifică strategie, praguri sau execuție live.",
            "",
        ])
        return "\n".join(lines)


class IntegrationReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: IntegrationGateReport) -> Path:
        self._json_path.write_text(
            json.dumps(
                report.to_dict(),
                indent=2,
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n",
            encoding="utf-8",
        )
        return self._json_path

    def persist_txt(self, report: IntegrationGateReport) -> Path:
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._txt_path
