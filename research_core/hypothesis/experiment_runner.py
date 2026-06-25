"""
Experiment runner — test UNTESTED hypotheses against historical research CSVs.

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Foundation only — structured cohort filtering, not live trading or signal generation.
"""

from __future__ import annotations

import csv
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.hypothesis.experiment_result import ExperimentResult, ExperimentStatus
from research_core.hypothesis.hypothesis_model import Hypothesis, HypothesisStatus, SAFETY_MODE
from research_core.hypothesis.hypothesis_registry import HypothesisRegistry

logger = logging.getLogger(__name__)

DEFAULT_RESULTS_PATH = Path("tae_experiment_results.json")
DEFAULT_ENSEMBLE_PATH = Path("edge_ensemble_signal_scores.csv")
DEFAULT_V18_PATH = Path("context_v18_signal_features.csv")
FORWARD_RETURN_COL = "Forward_Return_60d"
MIN_SAMPLE_SIZE = 5
SCHEMA_VERSION = 1
SCHEMA_NAME = "tae_experiment_results"


@dataclass
class ResearchDataLoader:
    """Load historical research rows from project CSV files — stdlib csv only."""

    ensemble_path: Path = DEFAULT_ENSEMBLE_PATH
    v18_path: Path = DEFAULT_V18_PATH
    _rows: list[dict[str, str]] = field(default_factory=list, init=False)
    _load_error: str | None = field(default=None, init=False)

    def load(self) -> bool:
        if self._rows:
            return True
        rows, error = self._read_csv(self.ensemble_path)
        if rows:
            self._rows = rows
            return True
        rows_v18, error_v18 = self._read_csv(self.v18_path)
        if rows_v18:
            self._rows = rows_v18
            return True
        self._load_error = error or error_v18 or "No research CSV data available."
        return False

    @property
    def row_count(self) -> int:
        return len(self._rows)

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def _read_csv(self, path: Path) -> tuple[list[dict[str, str]], str | None]:
        if not path.is_file():
            return [], f"Missing file: {path}"
        try:
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = [dict(row) for row in reader]
            if not rows:
                return [], f"Empty file: {path}"
            return rows, None
        except (OSError, csv.Error) as exc:
            return [], f"Failed to read {path}: {exc}"

    def rows_matching(self, hypothesis: Hypothesis) -> list[dict[str, str]]:
        if not self._rows:
            self.load()
        matched: list[dict[str, str]] = []
        for row in self._rows:
            if _row_matches_conditions(row, hypothesis.conditions):
                matched.append(row)
        return matched


class ExperimentResultsStore:
    """JSON persistence for experiment results."""

    def __init__(self, path: Path | None = None, auto_load: bool = True) -> None:
        self._path = path or DEFAULT_RESULTS_PATH
        self._results: dict[str, ExperimentResult] = {}
        self._sequence: int = 0
        self._loaded_at_startup = False
        if auto_load:
            self._loaded_at_startup = self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def loaded_at_startup(self) -> bool:
        return self._loaded_at_startup

    def count(self) -> int:
        return len(self._results)

    def list_all(self) -> list[ExperimentResult]:
        return sorted(self._results.values(), key=lambda r: r.tested_at)

    def get_by_hypothesis(self, hypothesis_id: str) -> list[ExperimentResult]:
        return [r for r in self._results.values() if r.hypothesis_id == hypothesis_id]

    def next_id(self) -> str:
        self._sequence += 1
        return f"exp_s51_{self._sequence:05d}"

    def add(self, result: ExperimentResult) -> ExperimentResult:
        self._results[result.experiment_id] = result
        return result

    def load(self) -> bool:
        if not self._path.is_file():
            return False
        try:
            raw = self._path.read_text(encoding="utf-8")
            payload = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Experiment results unreadable (%s): %s", self._path, exc)
            return False

        if not isinstance(payload, dict) or payload.get("schema") != SCHEMA_NAME:
            return False

        self._sequence = int(payload.get("sequence", 0))
        items = payload.get("results", [])
        if not isinstance(items, list):
            return False

        restored: dict[str, ExperimentResult] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            result = ExperimentResult.from_dict(item)
            if result is not None:
                restored[result.experiment_id] = result

        self._results = restored
        if self._sequence < len(restored):
            self._sequence = len(restored)
        return True

    def persist(self) -> Path:
        payload = {
            "version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "sequence": self._sequence,
            "result_count": len(self._results),
            "results": [r.to_dict() for r in self.list_all()],
        }
        self._path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return self._path

    def format_summary(self) -> str:
        if not self._results:
            return "Experiment results empty."
        lines = ["===== EXPERIMENT RESULTS =====", ""]
        for result in self.list_all():
            lines.append(f"  {result.summary_line()}")
            if result.notes:
                lines.append(f"    notes: {result.notes[:120]}")
        lines.append("")
        return "\n".join(lines)


class ExperimentRunner:
    """
    Runs defensive historical cohort tests for UNTESTED hypotheses.
    Sprint 5.1 foundation — does not emit trade signals.
    """

    def __init__(
        self,
        registry: HypothesisRegistry | None = None,
        results_store: ExperimentResultsStore | None = None,
        data_loader: ResearchDataLoader | None = None,
    ) -> None:
        self._registry = registry or HypothesisRegistry()
        self._results = results_store or ExperimentResultsStore()
        self._data = data_loader or ResearchDataLoader()

    @property
    def registry(self) -> HypothesisRegistry:
        return self._registry

    @property
    def results_store(self) -> ExperimentResultsStore:
        return self._results

    def run_untested(self) -> list[ExperimentResult]:
        untested = self._registry.list_untested()
        produced: list[ExperimentResult] = []

        if not untested:
            return produced

        data_ok = self._data.load()
        for hypothesis in untested:
            if not data_ok:
                result = self._insufficient_data_result(
                    hypothesis,
                    self._data.load_error or "Research data not loaded.",
                )
            else:
                result = self._run_single(hypothesis)

            self._results.add(result)
            produced.append(result)
            self._apply_hypothesis_status(hypothesis, result)

        return produced

    def _run_single(self, hypothesis: Hypothesis) -> ExperimentResult:
        if FORWARD_RETURN_COL not in (self._data._rows[0] if self._data._rows else {}):
            return self._insufficient_data_result(
                hypothesis,
                f"Column {FORWARD_RETURN_COL} missing from research data.",
            )

        cohort = self._data.rows_matching(hypothesis)
        if len(cohort) < MIN_SAMPLE_SIZE:
            return self._insufficient_data_result(
                hypothesis,
                f"Cohort size {len(cohort)} below minimum {MIN_SAMPLE_SIZE}.",
                sample_size=len(cohort),
            )

        wins = 0
        losses = 0
        neutral = 0
        returns: list[float] = []

        for row in cohort:
            forward = _safe_float(row.get(FORWARD_RETURN_COL))
            if forward is None:
                neutral += 1
                continue
            returns.append(forward)
            if forward > 0:
                wins += 1
            elif forward < 0:
                losses += 1
            else:
                neutral += 1

        decided = wins + losses
        if decided == 0:
            return self._insufficient_data_result(
                hypothesis,
                "No decisive forward returns in matched cohort.",
                sample_size=len(cohort),
                neutral=neutral,
            )

        accuracy = wins / decided
        avg_return = sum(returns) / len(returns) if returns else 0.0

        notes = (
            f"Cohort from historical research CSV ({len(cohort)} rows). "
            f"Forward column: {FORWARD_RETURN_COL}. "
            "Research-only cohort test — not a trade signal."
        )

        return ExperimentResult(
            experiment_id=self._results.next_id(),
            hypothesis_id=hypothesis.hypothesis_id,
            hypothesis_title=hypothesis.title,
            sample_size=len(cohort),
            wins=wins,
            losses=losses,
            neutral=neutral,
            accuracy=round(accuracy, 4),
            avg_forward_return=round(avg_return, 4),
            horizon=hypothesis.horizon,
            status=ExperimentStatus.TESTED,
            notes=notes,
            safety_mode=SAFETY_MODE,
        )

    def _insufficient_data_result(
        self,
        hypothesis: Hypothesis,
        reason: str,
        sample_size: int = 0,
        neutral: int = 0,
    ) -> ExperimentResult:
        return ExperimentResult(
            experiment_id=self._results.next_id(),
            hypothesis_id=hypothesis.hypothesis_id,
            hypothesis_title=hypothesis.title,
            sample_size=sample_size,
            wins=0,
            losses=0,
            neutral=neutral,
            accuracy=0.0,
            avg_forward_return=0.0,
            horizon=hypothesis.horizon,
            status=ExperimentStatus.INSUFFICIENT_DATA,
            notes=reason,
            safety_mode=SAFETY_MODE,
        )

    def _apply_hypothesis_status(self, hypothesis: Hypothesis, result: ExperimentResult) -> None:
        if result.status == ExperimentStatus.INSUFFICIENT_DATA:
            hypothesis.status = HypothesisStatus.INSUFFICIENT_DATA
        else:
            hypothesis.status = HypothesisStatus.TESTED


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _momentum_proxy(row: dict[str, str]) -> float:
    gain = _safe_float(row.get("Daily_Gain_Pct")) or 0.0
    consensus = _safe_float(row.get("Edge_Consensus_Score")) or 0.0
    return min(100.0, gain * 9.0 + consensus * 0.25)


def _row_matches_conditions(row: dict[str, str], conditions: dict[str, Any]) -> bool:
    regime = conditions.get("market_regime")
    if regime:
        row_regime = str(row.get("Market_Regime", "NEUTRAL")).upper()
        if row_regime != str(regime).upper():
            return False

    momentum_gte = conditions.get("momentum_confidence_gte")
    if momentum_gte is not None:
        if _momentum_proxy(row) < float(momentum_gte):
            return False

    evidence_gte = conditions.get("evidence_confidence_gte")
    if evidence_gte is not None:
        consensus = _safe_float(row.get("Edge_Consensus_Score"))
        if consensus is None or consensus < float(evidence_gte):
            return False

    context_gte = conditions.get("context_confidence_gte")
    if context_gte is not None:
        rsi = _safe_float(row.get("RSI_14")) or _safe_float(row.get("RSI14"))
        if rsi is None:
            return False
        proxy = min(100.0, max(0.0, 100.0 - abs(50.0 - rsi)))
        if proxy < float(context_gte):
            return False

    collective_gte = conditions.get("collective_confidence_gte")
    if collective_gte is not None:
        consensus = _safe_float(row.get("Edge_Consensus_Score")) or 0.0
        if consensus < float(collective_gte):
            return False

    trust_weighted_gte = conditions.get("trust_weighted_confidence_gte")
    if trust_weighted_gte is not None and momentum_gte is None and evidence_gte is None:
        consensus = _safe_float(row.get("Edge_Consensus_Score")) or 0.0
        gain = _safe_float(row.get("Daily_Gain_Pct")) or 0.0
        proxy = min(100.0, consensus * 0.6 + gain * 4.0)
        if proxy < float(trust_weighted_gte) - 10.0:
            return False

    impulse = conditions.get("impulse_strength")
    if impulse == "elevated":
        gain = _safe_float(row.get("Daily_Gain_Pct")) or 0.0
        if gain < 7.0:
            return False
    elif impulse == "strong_burst":
        gain = _safe_float(row.get("Daily_Gain_Pct")) or 0.0
        vol = _safe_float(row.get("Volume_Ratio")) or 0.0
        if gain < 10.0 or vol < 2.0:
            return False

    return True
