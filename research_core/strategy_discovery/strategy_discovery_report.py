"""
Strategy Discovery report — Phase X Sprint X.3A

ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

DEFAULT_JSON_PATH = Path("tae_strategy_discovery.json")
DEFAULT_TXT_PATH = Path("tae_strategy_discovery.txt")
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_strategy_discovery"
DISCOVERY_SAFETY_BANNER = "ANALYSIS_ONLY | RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION"


class StrategyDiscoveryVerdict(str, Enum):
    STRATEGY_DISCOVERY_FOUNDATION_READY = "STRATEGY_DISCOVERY_FOUNDATION_READY"
    STRATEGY_DISCOVERY_READY_WITH_WARNINGS = "STRATEGY_DISCOVERY_READY_WITH_WARNINGS"
    STRATEGY_DISCOVERY_INSUFFICIENT_FEATURES = "STRATEGY_DISCOVERY_INSUFFICIENT_FEATURES"


class DiscoveryCandidateStatus(str, Enum):
    DISCOVERY_ONLY = "DISCOVERY_ONLY"


class RiskProfile(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class DiscoveryCandidate:
    discovery_id: str
    entry_rule: str
    exit_rule: str
    market_filter: str
    holding_period: int
    risk_profile: str
    confidence_seed: float
    feature_vector: list[str]
    status: DiscoveryCandidateStatus = DiscoveryCandidateStatus.DISCOVERY_ONLY

    def to_dict(self) -> dict[str, Any]:
        return {
            "discovery_id": self.discovery_id,
            "entry": self.entry_rule,
            "exit": self.exit_rule,
            "market": self.market_filter,
            "holding": self.holding_period,
            "risk": self.risk_profile,
            "confidence_seed": self.confidence_seed,
            "feature_vector": list(self.feature_vector),
            "status": self.status.value,
        }


@dataclass
class StrategyDiscoveryReport:
    verdict: StrategyDiscoveryVerdict
    candidates: list[DiscoveryCandidate]
    feature_library: dict[str, Any]
    hypothesis_count: int
    candidate_count: int
    average_confidence_seed: float
    warnings: list[str] = field(default_factory=list)
    protected_files_unchanged: bool = True
    safety_mode: str = DISCOVERY_SAFETY_BANNER
    research_only: bool = True
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "generated_at": self.generated_at.isoformat(),
            "safety_mode": self.safety_mode,
            "research_only": self.research_only,
            "verdict": self.verdict.value,
            "hypothesis_count": self.hypothesis_count,
            "candidate_count": self.candidate_count,
            "average_confidence_seed": self.average_confidence_seed,
            "feature_library_summary": self.feature_library.get("counts", {}),
            "discovery_registry": [candidate.to_dict() for candidate in self.candidates],
            "warnings": list(self.warnings),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        lines = [
            "===== TAE STRATEGY DISCOVERY ENGINE — SPRINT X.3A =====",
            "",
            f"Safety banner: {self.safety_mode}",
            "Mode: RESEARCH_ONLY",
            f"Verdict: {self.verdict.value}",
            f"Generated: {self.generated_at.isoformat()}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== FEATURE LIBRARY =====",
        ]

        counts = self.feature_library.get("counts", {})
        lines.append(f"  Entry features: {counts.get('entry', 0)}")
        lines.append(f"  Exit features: {counts.get('exit', 0)}")
        lines.append(f"  Filter features: {counts.get('filter', 0)}")
        lines.append(f"  Holding periods: {counts.get('holding', 0)}")
        lines.append("")
        lines.extend(
            [
                "===== DISCOVERY SUMMARY =====",
                f"  Hypotheses generated: {self.hypothesis_count}",
                f"  Candidates built: {self.candidate_count}",
                f"  Average confidence seed: {self.average_confidence_seed:.4f}",
                "",
                "===== SAMPLE CANDIDATES (first 10) =====",
            ]
        )

        for candidate in self.candidates[:10]:
            lines.extend(
                [
                    f"[{candidate.discovery_id}] {candidate.entry_rule} → {candidate.exit_rule}",
                    f"  Market: {candidate.market_filter} | Holding: {candidate.holding_period}d",
                    f"  Risk: {candidate.risk_profile} | Confidence: {candidate.confidence_seed:.4f}",
                    f"  Status: {candidate.status.value}",
                    "",
                ]
            )

        if len(self.candidates) > 10:
            lines.append(f"  ... and {len(self.candidates) - 10} more candidates in registry")
            lines.append("")

        lines.append("===== RISK PROFILE DISTRIBUTION =====")
        risk_counts: dict[str, int] = {}
        for candidate in self.candidates:
            risk_counts[candidate.risk_profile] = risk_counts.get(candidate.risk_profile, 0) + 1
        for risk, count in sorted(risk_counts.items()):
            lines.append(f"  {risk}: {count}")

        if self.warnings:
            lines.extend(["", "===== WARNINGS ====="])
            for warning in self.warnings:
                lines.append(f"  • {warning}")

        return "\n".join(lines)


class StrategyDiscoveryReportStore:
    def __init__(
        self,
        json_path: Path | None = None,
        txt_path: Path | None = None,
    ) -> None:
        self._json_path = json_path or DEFAULT_JSON_PATH
        self._txt_path = txt_path or DEFAULT_TXT_PATH

    def persist(self, report: StrategyDiscoveryReport) -> tuple[Path, Path]:
        self._json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self._txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return self._json_path, self._txt_path
