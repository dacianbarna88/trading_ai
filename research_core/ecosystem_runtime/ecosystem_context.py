"""Ecosystem / evidence / daily intelligence SSOT context — read-only from existing artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ECOSYSTEM_COLUMNS = (
    "Ecosystem_Run_Status",
    "Ecosystem_Orchestrator_Status",
    "Evidence_Score",
    "Evidence_Confidence",
    "Evidence_Gate",
    "Daily_Intelligence_Score",
    "Daily_Intelligence_Confidence",
    "Daily_Intelligence_Context",
)

ARTIFACT_FILES = {
    "full_ecosystem_run": "tae_full_ecosystem_run.json",
    "orchestrator": "tae_ecosystem_orchestrator.json",
    "evidence_engine": "tae_evidence_engine_report.json",
    "evidence_gate": "tae_evidence_integration_gate.json",
    "daily_intelligence": "tae_daily_intelligence_report.json",
    "ecosystem_runtime": "tae_ecosystem_runtime.json",
    "legacy_daily_intel": "daily_intelligence_report.txt",
}


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _verdict_score(verdict: str, ok_markers: tuple[str, ...]) -> float:
    v = str(verdict or "").upper()
    if any(m in v for m in ok_markers):
        return 75.0
    if "READY" in v or "ALIGNED" in v or "HEALTHY" in v:
        return 70.0
    if "WARNING" in v or "PARTIAL" in v:
        return 55.0
    if "BLOCKED" in v or "FAIL" in v:
        return 40.0
    return 60.0


@dataclass
class EcosystemContext:
    full_ecosystem_run: dict[str, Any] = field(default_factory=dict)
    orchestrator: dict[str, Any] = field(default_factory=dict)
    evidence_engine: dict[str, Any] = field(default_factory=dict)
    evidence_gate: dict[str, Any] = field(default_factory=dict)
    daily_intelligence: dict[str, Any] = field(default_factory=dict)
    legacy_daily_intel_present: bool = False
    global_evidence_score: float | None = None
    global_evidence_confidence: float | None = None
    global_daily_score: float | None = None
    global_daily_confidence: float | None = None
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> EcosystemContext:
        root = Path(root)
        artifacts_loaded = {key: (root / name).is_file() for key, name in ARTIFACT_FILES.items()}

        full_ecosystem_run = _load_json(root / ARTIFACT_FILES["full_ecosystem_run"]) or {}
        orchestrator = _load_json(root / ARTIFACT_FILES["orchestrator"]) or {}
        evidence_engine = _load_json(root / ARTIFACT_FILES["evidence_engine"]) or {}
        evidence_gate = _load_json(root / ARTIFACT_FILES["evidence_gate"]) or {}
        daily_intelligence = _load_json(root / ARTIFACT_FILES["daily_intelligence"]) or {}
        legacy_daily_intel_present = (root / ARTIFACT_FILES["legacy_daily_intel"]).is_file()

        confirmed = _parse_float(evidence_engine.get("confirmed_count")) or 0.0
        registry = _parse_float(evidence_engine.get("registry_item_count")) or 0.0
        if registry > 0:
            evidence_score = round(min(100.0, (confirmed / registry) * 100.0), 2)
        else:
            evidence_score = _verdict_score(
                str(evidence_engine.get("verdict") or ""),
                ("ALIGNED", "INITIALIZED"),
            )

        conf_reg = evidence_engine.get("confidence_registration") or {}
        conf_report = conf_reg.get("confidence_report") or {}
        evidence_confidence = _parse_float(conf_report.get("average_recalibrated_confidence"))
        if evidence_confidence is None:
            evidence_confidence = evidence_score

        learning = daily_intelligence.get("learning_summary") or {}
        daily_score = _parse_float(learning.get("learning_confidence"))
        if daily_score is None:
            eco_health = daily_intelligence.get("ecosystem_health") or {}
            if str(eco_health.get("overall_status") or "").upper() == "HEALTHY":
                daily_score = 75.0
            else:
                daily_score = 60.0

        validation = daily_intelligence.get("validation_summary") or {}
        daily_confidence = _parse_float(validation.get("cross_regime_consistency"))
        if daily_confidence is None:
            daily_confidence = _parse_float(validation.get("cross_horizon_consistency"))
        if daily_confidence is None:
            daily_confidence = daily_score

        return cls(
            full_ecosystem_run=full_ecosystem_run,
            orchestrator=orchestrator,
            evidence_engine=evidence_engine,
            evidence_gate=evidence_gate,
            daily_intelligence=daily_intelligence,
            legacy_daily_intel_present=legacy_daily_intel_present,
            global_evidence_score=evidence_score,
            global_evidence_confidence=round(evidence_confidence, 2),
            global_daily_score=round(daily_score, 2) if daily_score is not None else None,
            global_daily_confidence=round(daily_confidence, 2) if daily_confidence is not None else None,
            artifacts_loaded=artifacts_loaded,
        )

    def _ecosystem_run_status(self) -> str:
        return str(
            self.full_ecosystem_run.get("verdict")
            or self.orchestrator.get("verdict")
            or "NOT_AVAILABLE"
        )

    def _orchestrator_status(self) -> str:
        return str(self.orchestrator.get("verdict") or "NOT_AVAILABLE")

    def _evidence_gate_status(self) -> str:
        return str(self.evidence_gate.get("verdict") or "NOT_AVAILABLE")

    def _daily_context(self, ticker: str) -> str:
        eco = self.daily_intelligence.get("ecosystem_health") or {}
        parts = [
            f"ticker={ticker}",
            f"ecosystem_run={self._ecosystem_run_status()}",
            f"orchestrator={self._orchestrator_status()}",
            f"evidence={self.evidence_engine.get('verdict')}",
            f"gate={self._evidence_gate_status()}",
            f"daily_health={eco.get('overall_status')}",
            f"legacy_runner={self.legacy_daily_intel_present}",
        ]
        return "; ".join(parts)

    def compute_bonuses(self, enrichment: dict[str, Any]) -> dict[str, float]:
        eco_run = str(enrichment.get("Ecosystem_Run_Status") or "")
        orch = str(enrichment.get("Ecosystem_Orchestrator_Status") or "")
        ev_score = _parse_float(enrichment.get("Evidence_Score"))
        ev_conf = _parse_float(enrichment.get("Evidence_Confidence"))
        gate = str(enrichment.get("Evidence_Gate") or "")
        di_score = _parse_float(enrichment.get("Daily_Intelligence_Score"))
        di_conf = _parse_float(enrichment.get("Daily_Intelligence_Confidence"))

        ecosystem_bonus = 0.0
        if "READY" in eco_run.upper():
            ecosystem_bonus += 0.5
        if "READY" in orch.upper():
            ecosystem_bonus += 0.5

        evidence_bonus = 0.0
        if ev_score is not None and ev_score >= 65:
            evidence_bonus += (ev_score - 50) * 0.015
        if ev_conf is not None and ev_conf >= 70:
            evidence_bonus += (ev_conf - 50) * 0.01
        if "READY" in gate.upper():
            evidence_bonus += 0.25
        allowed = _parse_float(self.evidence_gate.get("allowed_count")) or 0.0
        if allowed > 0:
            evidence_bonus += min(0.5, allowed * 0.15)

        daily_intelligence_bonus = 0.0
        if di_score is not None and di_score >= 65:
            daily_intelligence_bonus += (di_score - 50) * 0.01
        if di_conf is not None and di_conf >= 70:
            daily_intelligence_bonus += (di_conf - 50) * 0.008
        eco_health = self.daily_intelligence.get("ecosystem_health") or {}
        if str(eco_health.get("overall_status") or "").upper() == "HEALTHY":
            daily_intelligence_bonus += 0.3

        return {
            "ecosystem_bonus": round(ecosystem_bonus, 4),
            "evidence_bonus": round(evidence_bonus, 4),
            "daily_intelligence_bonus": round(daily_intelligence_bonus, 4),
        }

    def enrich_ticker(self, ticker: str, *, signal: str = "") -> dict[str, Any]:
        ticker = ticker.upper()
        ev_score = self.global_evidence_score
        ev_conf = self.global_evidence_confidence
        di_score = self.global_daily_score
        di_conf = self.global_daily_confidence

        if str(signal or "").upper() == "STRONG BUY":
            if ev_score is not None:
                ev_score = round(min(100.0, ev_score + 2.0), 2)
            if di_score is not None:
                di_score = round(min(100.0, di_score + 1.5), 2)

        enrichment = {
            "Ecosystem_Run_Status": self._ecosystem_run_status(),
            "Ecosystem_Orchestrator_Status": self._orchestrator_status(),
            "Evidence_Score": ev_score,
            "Evidence_Confidence": ev_conf,
            "Evidence_Gate": self._evidence_gate_status(),
            "Daily_Intelligence_Score": di_score,
            "Daily_Intelligence_Confidence": di_conf,
            "Daily_Intelligence_Context": self._daily_context(ticker),
        }
        enrichment.update(self.compute_bonuses(enrichment))
        return enrichment

    def advisory_summary(self) -> dict[str, Any]:
        top_evidence: list[dict[str, Any]] = []
        for decision in self.evidence_gate.get("decisions") or []:
            if not isinstance(decision, dict):
                continue
            gate_status = str(decision.get("gate_status") or "")
            if gate_status in {"PAPER_CANDIDATE", "DEPLOYMENT_REVIEW_REQUIRED"} or decision.get(
                "implementation_allowed"
            ):
                top_evidence.append(
                    {
                        "evidence_id": decision.get("evidence_id"),
                        "title": decision.get("title"),
                        "gate_status": gate_status,
                        "implementation_allowed": decision.get("implementation_allowed"),
                    }
                )
        top_evidence = top_evidence[:10]

        top_daily: list[dict[str, Any]] = []
        for item in self.daily_intelligence.get("research_priorities") or []:
            if isinstance(item, dict):
                top_daily.append(
                    {
                        "rank": item.get("rank"),
                        "title": item.get("title"),
                        "priority_score": item.get("priority_score"),
                        "source_id": item.get("source_id"),
                    }
                )
        top_daily = top_daily[:10]

        eco_health = self.daily_intelligence.get("ecosystem_health") or {}
        return {
            "ecosystem_run_status": self._ecosystem_run_status(),
            "orchestrator_status": self._orchestrator_status(),
            "evidence_verdict": self.evidence_engine.get("verdict"),
            "evidence_gate": self._evidence_gate_status(),
            "evidence_score": self.global_evidence_score,
            "evidence_confidence": self.global_evidence_confidence,
            "evidence_allowed_count": self.evidence_gate.get("allowed_count"),
            "evidence_paper_candidates": self.evidence_gate.get("paper_candidate_count"),
            "daily_intelligence_score": self.global_daily_score,
            "daily_intelligence_confidence": self.global_daily_confidence,
            "daily_ecosystem_health": eco_health.get("overall_status"),
            "legacy_daily_runner_present": self.legacy_daily_intel_present,
            "top_evidence_candidates": top_evidence,
            "top_daily_intelligence_candidates": top_daily,
            "artifacts_loaded": self.artifacts_loaded,
        }
