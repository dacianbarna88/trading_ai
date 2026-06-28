"""
Integration Gate Chain Report — Phase IX Sprint IX.5E

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from integration_layer.integration_gate_chain import (
    INTEGRATION_GATE_CHAIN_COMPLETE,
    PROMOTION_GATE_REPORT_PATH,
    build_promotion_gate_chain,
    is_integration_gate_chain_resolved,
    is_integration_gate_chained,
    load_canonical_promotion_gate_report,
)
from integration_layer.integration_report import DEFAULT_JSON_PATH, SAFETY_BANNER

CHAIN_JSON = Path("tae_integration_gate_chain.json")
CHAIN_TXT = Path("tae_integration_gate_chain.txt")

PROTECTED_PATHS = (
    "live_bot.py",
    "dashboard_v2.py",
    "portfolio.csv",
    "config/settings.py",
    "core/trades.py",
    "core/portfolio_prices.py",
)


def _load_integration_gate_report(root: Path) -> dict[str, Any] | None:
    path = root / DEFAULT_JSON_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


@dataclass
class IntegrationGateChainReport:
    safety_banner: str
    before_connection_status: str
    after_connection_status: str
    promotion_gate_source: str
    promotion_gate_source_available: bool
    integration_gate_chain_status: dict[str, Any]
    integration_gate_includes_promotion: bool
    runtime_backlog_resolved: bool
    quick_health_backlog_resolved: bool
    missing_optional_reports: list[str]
    protected_files_unchanged: bool
    verdict: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": 1,
            "schema": "tae_integration_gate_chain",
            "generated_at": self.generated_at.isoformat(),
            "safety_banner": self.safety_banner,
            "verdict": self.verdict,
            "before_connection_status": self.before_connection_status,
            "after_connection_status": self.after_connection_status,
            "promotion_gate_source": self.promotion_gate_source,
            "promotion_gate_source_available": self.promotion_gate_source_available,
            "integration_gate_chain_status": dict(self.integration_gate_chain_status),
            "integration_gate_includes_promotion": self.integration_gate_includes_promotion,
            "runtime_backlog_resolved": self.runtime_backlog_resolved,
            "quick_health_backlog_resolved": self.quick_health_backlog_resolved,
            "missing_optional_reports": list(self.missing_optional_reports),
            "protected_files_unchanged": self.protected_files_unchanged,
        }

    def format_text(self) -> str:
        chain = self.integration_gate_chain_status
        lines = [
            "===== TAE INTEGRATION GATE CHAIN — SPRINT IX.5E =====",
            "",
            f"Safety banner: {self.safety_banner}",
            f"Verdict: {self.verdict}",
            f"Protected files unchanged: {self.protected_files_unchanged}",
            "",
            "===== CONNECTION STATUS =====",
            f"Before: {self.before_connection_status}",
            f"After:  {self.after_connection_status}",
            "",
            f"Promotion gate source: {self.promotion_gate_source}",
            f"Source report available: {self.promotion_gate_source_available}",
            "",
            "===== INTEGRATION GATE CHAIN =====",
            f"  promotion_gate_registered: {chain.get('promotion_gate_registered')}",
            f"  promotion_gate_status: {chain.get('promotion_gate_status')}",
            f"  promotion_gate_source: {chain.get('promotion_gate_source')}",
            f"  promotion_gate_last_refresh: {chain.get('promotion_gate_last_refresh')}",
            f"  integration_gate_status: {chain.get('integration_gate_status')}",
            f"  review_candidate_id: {chain.get('review_candidate_id')}",
            "",
            f"Integration gate report includes promotion chain: "
            f"{self.integration_gate_includes_promotion}",
            f"Runtime backlog resolved: {self.runtime_backlog_resolved}",
            f"Quick Health backlog resolved: {self.quick_health_backlog_resolved}",
            "",
            "===== MISSING OPTIONAL REPORTS =====",
        ]
        if self.missing_optional_reports:
            for item in self.missing_optional_reports:
                lines.append(f"  • {item}")
        else:
            lines.append("  none")
        lines.append("")
        return "\n".join(lines)


class IntegrationGateChainAudit:
    def __init__(self, root: Path | str = Path(".")) -> None:
        self._root = Path(root)

    def run(
        self,
        before_wired: bool,
        protected_ok: bool,
    ) -> IntegrationGateChainReport:
        after_wired = is_integration_gate_chained(self._root)
        promotion_payload = load_canonical_promotion_gate_report(self._root)
        promotion_available = promotion_payload is not None

        integration_payload = _load_integration_gate_report(self._root)
        gate_includes = False
        chain_status = build_promotion_gate_chain(self._root, promotion_payload)
        if integration_payload:
            chain = integration_payload.get("promotion_gate_chain")
            if isinstance(chain, dict) and chain.get("promotion_gate_registered"):
                gate_includes = True
                chain_status = chain

        backlog_resolved = is_integration_gate_chain_resolved(
            self._root,
            integration_payload,
        )

        missing_optional: list[str] = []
        if not promotion_available:
            missing_optional.append(
                f"{PROMOTION_GATE_REPORT_PATH.name} — run promotion gate demo"
            )
        if not integration_payload:
            missing_optional.append(
                f"{DEFAULT_JSON_PATH.name} — run integration gate demo"
            )

        before_status = "WIRED_TO_INTEGRATION_GATE" if before_wired else "NOT_WIRED"
        after_status = "WIRED_TO_INTEGRATION_GATE" if after_wired else "NOT_WIRED"

        if not protected_ok:
            verdict = "INTEGRATION_GATE_CHAIN_FAILED_PROTECTED_FILE_MODIFIED"
        elif not after_wired or not gate_includes:
            verdict = "INTEGRATION_GATE_CHAIN_INCOMPLETE"
        elif not promotion_available:
            verdict = "INTEGRATION_GATE_CHAIN_COMPLETE_WITH_MISSING_SOURCE_REPORT"
        elif (
            chain_status.get("integration_gate_status") == INTEGRATION_GATE_CHAIN_COMPLETE
            and backlog_resolved
        ):
            verdict = "INTEGRATION_GATE_CHAIN_COMPLETE"
        else:
            verdict = "INTEGRATION_GATE_CHAIN_INCOMPLETE"

        return IntegrationGateChainReport(
            safety_banner=SAFETY_BANNER,
            before_connection_status=before_status,
            after_connection_status=after_status,
            promotion_gate_source=str(PROMOTION_GATE_REPORT_PATH.name),
            promotion_gate_source_available=promotion_available,
            integration_gate_chain_status=chain_status,
            integration_gate_includes_promotion=gate_includes,
            runtime_backlog_resolved=backlog_resolved,
            quick_health_backlog_resolved=backlog_resolved,
            missing_optional_reports=missing_optional,
            protected_files_unchanged=protected_ok,
            verdict=verdict,
        )

    def persist(self, report: IntegrationGateChainReport) -> dict[str, Path]:
        json_path = self._root / CHAIN_JSON
        txt_path = self._root / CHAIN_TXT
        json_path.write_text(
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        txt_path.write_text(report.format_text() + "\n", encoding="utf-8")
        return {"chain_json": json_path, "chain_txt": txt_path}


def protected_mtime_snapshot(root: Path) -> dict[str, float]:
    snapshot: dict[str, float] = {}
    for rel in PROTECTED_PATHS:
        full = root / rel
        if full.is_file():
            snapshot[rel] = full.stat().st_mtime
    return snapshot


def verify_protected_unchanged(root: Path, before: dict[str, float]) -> bool:
    for rel, mtime in before.items():
        full = root / rel
        if not full.is_file() or full.stat().st_mtime != mtime:
            return False
    return True
