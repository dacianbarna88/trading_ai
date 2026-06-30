"""Confidence validation SSOT context — read-only from existing artifacts."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONFIDENCE_COLUMNS = (
    "Confidence_Runtime_Score",
    "Confidence_Runtime_Confidence",
    "Validation_Status",
    "Vote_Accuracy",
    "Adaptive_Weight",
    "Confidence_Context",
)

ARTIFACT_FILES = {
    "validation_rules": "validation_rules.json",
    "validation_rules_summary": "validation_rules_summary.txt",
    "vote_accuracy": "vote_accuracy.csv",
    "vote_accuracy_summary": "vote_accuracy_summary.txt",
    "validation_summary": "automatic_outcome_validation_summary.txt",
    "registry_sync": "registry_sync_summary.txt",
    "learning_automation": "learning_automation_summary.txt",
    "confidence_evolution": "confidence_evolution_summary.txt",
    "weighted_committee": "weighted_committee_summary.txt",
    "adaptive_weights": "adaptive_weights.csv",
    "vote_outcome_registry": "vote_outcome_registry.csv",
    "confidence_runtime": "tae_confidence_runtime.json",
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


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


@dataclass
class ConfidenceContext:
    validation_rules: dict[str, Any] = field(default_factory=dict)
    vote_accuracy_rows: list[dict[str, str]] = field(default_factory=list)
    validation_text: str = ""
    avg_vote_accuracy: float | None = None
    avg_adaptive_weight: float | None = None
    validation_status: str = "UNKNOWN"
    global_confidence_score: float | None = None
    global_confidence_confidence: float | None = None
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> ConfidenceContext:
        root = Path(root)
        artifacts_loaded = {key: (root / name).is_file() for key, name in ARTIFACT_FILES.items()}

        rules: dict[str, Any] = {}
        rules_path = root / ARTIFACT_FILES["validation_rules"]
        if rules_path.is_file():
            try:
                payload = json.loads(rules_path.read_text(encoding="utf-8"))
                rules = payload if isinstance(payload, dict) else {}
            except (json.JSONDecodeError, OSError):
                rules = {}

        vote_rows = _read_csv_rows(root / ARTIFACT_FILES["vote_accuracy"])
        accuracies: list[float] = []
        weights: list[float] = []
        for row in vote_rows:
            acc = _parse_float(row.get("Accuracy_%"))
            if acc is not None and acc > 0:
                accuracies.append(acc)
            wt = _parse_float(row.get("Weight"))
            if wt is not None:
                weights.append(wt)

        if not weights:
            reg_rows = _read_csv_rows(root / ARTIFACT_FILES["vote_outcome_registry"])
            for row in reg_rows:
                wt = _parse_float(row.get("Weight"))
                if wt is not None:
                    weights.append(wt)

        if not weights:
            adapt_rows = _read_csv_rows(root / ARTIFACT_FILES["adaptive_weights"])
            for row in adapt_rows:
                wt = _parse_float(row.get("Weight") or row.get("weight"))
                if wt is not None:
                    weights.append(wt)

        avg_acc = round(sum(accuracies) / len(accuracies), 2) if accuracies else None
        avg_weight = round(sum(weights) / len(weights), 2) if weights else 1.0

        validation_text = _read_text(root / ARTIFACT_FILES["validation_summary"])
        validation_status = "RULES_DEFINED"
        if "READY_FOR_VALIDATION" in validation_text:
            validation_status = "READY_FOR_VALIDATION"
        elif "WAITING" in validation_text:
            validation_status = "WAITING"
        elif rules:
            validation_status = "RULES_DEFINED"

        conf_score = avg_acc if avg_acc is not None else 60.0
        if rules:
            conf_score = min(100.0, conf_score + len(rules) * 2.0)
        conf_confidence = avg_acc if avg_acc is not None else 65.0
        if validation_status == "READY_FOR_VALIDATION":
            conf_confidence = min(100.0, conf_confidence + 5.0)

        return cls(
            validation_rules=rules,
            vote_accuracy_rows=vote_rows,
            validation_text=validation_text,
            avg_vote_accuracy=avg_acc,
            avg_adaptive_weight=avg_weight,
            validation_status=validation_status,
            global_confidence_score=round(conf_score, 2),
            global_confidence_confidence=round(conf_confidence, 2),
            artifacts_loaded=artifacts_loaded,
        )

    def compute_bonuses(self, enrichment: dict[str, Any]) -> dict[str, float]:
        conf_score = _parse_float(enrichment.get("Confidence_Runtime_Score"))
        conf_conf = _parse_float(enrichment.get("Confidence_Runtime_Confidence"))
        vote_acc = _parse_float(enrichment.get("Vote_Accuracy"))
        validation = str(enrichment.get("Validation_Status") or "")

        confidence_bonus = 0.0
        if conf_score is not None and conf_score >= 60:
            confidence_bonus += (conf_score - 50) * 0.012
        if conf_conf is not None and conf_conf >= 65:
            confidence_bonus += (conf_conf - 50) * 0.01
        if vote_acc is not None and vote_acc >= 65:
            confidence_bonus += (vote_acc - 50) * 0.015

        validation_bonus = 0.0
        if validation == "READY_FOR_VALIDATION":
            validation_bonus += 0.4
        elif validation == "RULES_DEFINED":
            validation_bonus += 0.2
        if self.validation_rules:
            validation_bonus += min(0.5, len(self.validation_rules) * 0.05)

        return {
            "confidence_bonus": round(confidence_bonus, 4),
            "validation_bonus": round(validation_bonus, 4),
        }

    def enrich_ticker(self, ticker: str, *, signal: str = "") -> dict[str, Any]:
        score = self.global_confidence_score
        conf = self.global_confidence_confidence
        vote_acc = self.avg_vote_accuracy
        weight = self.avg_adaptive_weight

        ctx_parts = [
            f"ticker={ticker}",
            f"validation={self.validation_status}",
            f"vote_accuracy={vote_acc}",
            f"adaptive_weight={weight}",
            f"rules={len(self.validation_rules)}",
        ]

        enrichment = {
            "Confidence_Runtime_Score": score,
            "Confidence_Runtime_Confidence": conf,
            "Validation_Status": self.validation_status,
            "Vote_Accuracy": vote_acc,
            "Adaptive_Weight": weight,
            "Confidence_Context": "; ".join(ctx_parts),
        }
        enrichment.update(self.compute_bonuses(enrichment))
        return enrichment

    def advisory_summary(self) -> dict[str, Any]:
        top_votes = []
        for row in self.vote_accuracy_rows[:10]:
            top_votes.append(
                {
                    "vote": row.get("Vote"),
                    "accuracy": row.get("Accuracy_%"),
                    "weight": row.get("Weight"),
                }
            )
        return {
            "validation_status": self.validation_status,
            "confidence_score": self.global_confidence_score,
            "confidence_confidence": self.global_confidence_confidence,
            "vote_accuracy_avg": self.avg_vote_accuracy,
            "adaptive_weight_avg": self.avg_adaptive_weight,
            "validation_rules_count": len(self.validation_rules),
            "top_vote_accuracy": top_votes,
            "artifacts_loaded": self.artifacts_loaded,
        }
