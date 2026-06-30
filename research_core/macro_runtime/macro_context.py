"""Macro intelligence SSOT context — read-only from existing artifacts."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MACRO_COLUMNS = (
    "Macro_Runtime_Score",
    "Macro_Runtime_Confidence",
    "Macro_Regime",
    "Interest_Rate_Context",
    "Inflation_Context",
)

ARTIFACT_FILES = {
    "macro_snapshot": "macro_intelligence/macro_snapshot.json",
    "economic_regime": "economic_regime_summary.txt",
    "rate_intelligence": "rate_intelligence_summary.txt",
    "inflation_intelligence": "inflation_intelligence_summary.txt",
    "macro_committee": "macro_committee_summary.txt",
    "macro_runtime": "tae_macro_runtime.json",
}


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _extract_verdict(text: str, label: str) -> str:
    match = re.search(rf"{re.escape(label)}:\s*(\S+)", text)
    return match.group(1) if match else "UNKNOWN"


def _verdict_score(verdict: str, bullish: tuple[str, ...], bearish: tuple[str, ...]) -> float:
    v = str(verdict or "").upper()
    if any(b in v for b in bullish):
        return 75.0
    if any(b in v for b in bearish):
        return 42.0
    return 55.0


@dataclass
class MacroContext:
    macro_snapshot: dict[str, Any] = field(default_factory=dict)
    economic_regime_text: str = ""
    rate_text: str = ""
    inflation_text: str = ""
    macro_committee_text: str = ""
    macro_regime: str = "UNKNOWN"
    rate_context: str = "UNKNOWN"
    inflation_context: str = "UNKNOWN"
    macro_verdict: str = "UNKNOWN"
    macro_confidence: float | None = None
    global_macro_score: float | None = None
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> MacroContext:
        root = Path(root)
        artifacts_loaded = {key: (root / name).is_file() for key, name in ARTIFACT_FILES.items()}

        snapshot = {}
        snap_path = root / ARTIFACT_FILES["macro_snapshot"]
        if snap_path.is_file():
            try:
                payload = json.loads(snap_path.read_text(encoding="utf-8"))
                snapshot = payload if isinstance(payload, dict) else {}
            except (json.JSONDecodeError, OSError):
                snapshot = {}

        economic_regime_text = _read_text(root / ARTIFACT_FILES["economic_regime"])
        rate_text = _read_text(root / ARTIFACT_FILES["rate_intelligence"])
        inflation_text = _read_text(root / ARTIFACT_FILES["inflation_intelligence"])
        committee_text = _read_text(root / ARTIFACT_FILES["macro_committee"])

        regime = _extract_verdict(economic_regime_text, "Economic Regime")
        if regime == "UNKNOWN" and "EXPANSION" in economic_regime_text:
            regime = "EXPANSION"
        elif "RECESSION_RISK" in economic_regime_text:
            regime = "RECESSION_RISK"

        rate_ctx = "UNKNOWN"
        for token in ("RATE_TAILWIND", "RATE_HEADWIND", "RATE_NEUTRAL"):
            if token in rate_text:
                rate_ctx = token
                break

        infl_ctx = "UNKNOWN"
        for token in ("DISINFLATION", "INFLATION_PRESSURE", "INFLATION_STABLE"):
            if token in inflation_text:
                infl_ctx = token
                break

        macro_verdict = "MACRO_NEUTRAL"
        for token in ("MACRO_BULLISH", "MACRO_BEARISH", "MACRO_NEUTRAL"):
            if token in committee_text:
                macro_verdict = token
                break

        conf_match = re.search(r"Confidence:\s*([\d.]+)%", committee_text)
        macro_confidence = _parse_float(conf_match.group(1)) if conf_match else None
        if macro_confidence is None or macro_confidence <= 0:
            macro_confidence = _verdict_score(
                macro_verdict,
                ("BULLISH", "TAILWIND", "EXPANSION"),
                ("BEARISH", "HEADWIND", "RECESSION"),
            )

        base = _verdict_score(macro_verdict, ("BULLISH",), ("BEARISH",))
        global_score = round(min(100.0, base * 0.7 + macro_confidence * 0.3), 2)

        return cls(
            macro_snapshot=snapshot,
            economic_regime_text=economic_regime_text,
            rate_text=rate_text,
            inflation_text=inflation_text,
            macro_committee_text=committee_text,
            macro_regime=regime,
            rate_context=rate_ctx,
            inflation_context=infl_ctx,
            macro_verdict=macro_verdict,
            macro_confidence=macro_confidence,
            global_macro_score=global_score,
            artifacts_loaded=artifacts_loaded,
        )

    def compute_bonuses(self, enrichment: dict[str, Any]) -> dict[str, float]:
        macro_score = _parse_float(enrichment.get("Macro_Runtime_Score"))
        macro_conf = _parse_float(enrichment.get("Macro_Runtime_Confidence"))
        verdict = str(enrichment.get("Macro_Regime") or "")

        macro_bonus = 0.0
        if macro_score is not None and macro_score >= 60:
            macro_bonus += (macro_score - 50) * 0.015
        if macro_conf is not None and macro_conf >= 65:
            macro_bonus += (macro_conf - 50) * 0.01
        if "BULLISH" in str(enrichment.get("Interest_Rate_Context") or ""):
            macro_bonus += 0.25
        elif "BEARISH" in str(enrichment.get("Inflation_Context") or ""):
            macro_bonus -= 0.15
        if "EXPANSION" in verdict.upper():
            macro_bonus += 0.3

        return {"macro_bonus": round(macro_bonus, 4)}

    def enrich_ticker(self, ticker: str, *, signal: str = "") -> dict[str, Any]:
        score = self.global_macro_score
        conf = self.macro_confidence
        if str(signal or "").upper() == "STRONG BUY" and "BULLISH" in self.macro_verdict:
            score = round(min(100.0, (score or 55) + 2.0), 2) if score is not None else 77.0

        enrichment = {
            "Macro_Runtime_Score": score,
            "Macro_Runtime_Confidence": conf,
            "Macro_Regime": self.macro_regime,
            "Interest_Rate_Context": self.rate_context,
            "Inflation_Context": self.inflation_context,
        }
        enrichment.update(self.compute_bonuses(enrichment))
        return enrichment

    def advisory_summary(self) -> dict[str, Any]:
        return {
            "macro_verdict": self.macro_verdict,
            "macro_regime": self.macro_regime,
            "macro_confidence": self.macro_confidence,
            "macro_score": self.global_macro_score,
            "interest_rate_context": self.rate_context,
            "inflation_context": self.inflation_context,
            "snapshot_present": bool(self.macro_snapshot),
            "artifacts_loaded": self.artifacts_loaded,
        }
