"""
Regional validation gap closure — Phase VI Sprint B5 / IX.2C validation feeder

RESEARCH_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Attempts Europe/UK regional validation for kn_d5_00002 using existing project data.
Validation feeder — not a competing strategy pipeline; official conclusions via Daily Runner.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.hypothesis.experiment_runner import (
    DEFAULT_ENSEMBLE_PATH,
    FORWARD_RETURN_COL,
    ResearchDataLoader,
    _row_matches_conditions,
)
from research_core.hypothesis.hypothesis_registry import HypothesisRegistry
from research_core.regional_validation.regional_validation_report import (
    DataAcquisitionItem,
    DatasetKind,
    ReadinessProjection,
    RegionalDatasetStatus,
    RegionalSliceResult,
    RegionalValidationReport,
    RegionalValidationStore,
    NOT_AVAILABLE,
    TARGET_CANDIDATE_ID,
)
from research_core.validation.cross_regime_validator import (
    MIN_SLICE_SAMPLE,
    MULTI_HORIZON_PATH,
    REGIONAL_STRENGTH_PATH,
    REGIMES,
)
from research_core.strategy_evolution.pipeline_integration import pipeline_reference

logger = logging.getLogger(__name__)

PIPELINE_ROLE = "VALIDATION_FEEDER"

RECALIBRATION_PATH = Path("tae_confidence_recalibration.json")
EVIDENCE_GAP_PATH = Path("tae_evidence_gap_report.json")
CROSS_VALIDATION_PATH = Path("tae_cross_validation_report.json")
KNOWLEDGE_CANDIDATES_PATH = Path("tae_knowledge_candidates.json")

REQUIRED_ENSEMBLE_COLUMNS = (
    "Ticker",
    "Signal_Date",
    "Market_Regime",
    FORWARD_RETURN_COL,
)

OPTIONAL_ENSEMBLE_COLUMNS = (
    "Win",
    "Edge_Consensus_Score",
    "Matching_Edge_Count",
    "Daily_Gain_Pct",
    "Volume_Ratio",
)

EXPECTED_HYPOTHESIS_LINKED_PATHS: dict[str, list[Path]] = {
    "Europe": [
        Path("edge_ensemble_signal_scores_europe.csv"),
        Path("research_data/europe/edge_ensemble_signal_scores.csv"),
        Path("data_outputs/europe_ensemble_signal_scores.csv"),
        Path("edge_ensemble_europe_signal_scores.csv"),
    ],
    "UK": [
        Path("edge_ensemble_signal_scores_uk.csv"),
        Path("research_data/uk/edge_ensemble_signal_scores.csv"),
        Path("data_outputs/uk_ensemble_signal_scores.csv"),
        Path("edge_ensemble_uk_signal_scores.csv"),
    ],
}

REFERENCE_DATASETS: dict[str, Path] = {
    "regional_strength": REGIONAL_STRENGTH_PATH,
    "multi_horizon_backtest": MULTI_HORIZON_PATH,
    "us_ensemble_baseline": DEFAULT_ENSEMBLE_PATH,
}

EUROPE_TICKER_SUFFIXES = (".DE", ".PA", ".AS", ".MI", ".MC", ".SW", ".VI", ".BR")
UK_TICKER_SUFFIXES = (".L",)


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        return [], []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = list(reader.fieldnames or [])
            rows = [dict(row) for row in reader]
        return rows, fieldnames
    except (OSError, csv.Error) as exc:
        logger.warning("Could not read CSV %s: %s", path, exc)
        return [], []


def _missing_columns(fieldnames: list[str]) -> list[str]:
    present = {c.strip() for c in fieldnames}
    return [col for col in REQUIRED_ENSEMBLE_COLUMNS if col not in present]


def _safe_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ticker_region(ticker: str) -> str | None:
    upper = ticker.upper()
    for suffix in UK_TICKER_SUFFIXES:
        if upper.endswith(suffix):
            return "UK"
    for suffix in EUROPE_TICKER_SUFFIXES:
        if upper.endswith(suffix):
            return "Europe"
    return None


def _slice_metrics(label: str, cohort: list[dict[str, str]]) -> RegionalSliceResult:
    region, regime = label.split("_", 1) if "_" in label else (label, "")

    if len(cohort) < MIN_SLICE_SAMPLE:
        status = NOT_AVAILABLE if len(cohort) == 0 else "INSUFFICIENT_SAMPLE"
        return RegionalSliceResult(
            slice_id=label,
            region=region,
            regime=regime,
            status=status,
            sample_size=len(cohort),
            reason=(
                f"Sample insuficient ({len(cohort)} < {MIN_SLICE_SAMPLE})"
                if cohort
                else "Niciun rând în cohortă"
            ),
        )

    wins = 0
    losses = 0
    returns: list[float] = []
    for row in cohort:
        forward = _safe_float(row.get(FORWARD_RETURN_COL))
        if forward is None:
            win_raw = row.get("Win", "")
            if str(win_raw).lower() == "true":
                wins += 1
            elif str(win_raw).lower() == "false":
                losses += 1
            continue
        returns.append(forward)
        if forward > 0:
            wins += 1
        elif forward < 0:
            losses += 1

    decided = wins + losses
    if decided == 0:
        return RegionalSliceResult(
            slice_id=label,
            region=region,
            regime=regime,
            status=NOT_AVAILABLE,
            sample_size=len(cohort),
            reason="Niciun outcome Win/Loss sau Forward_Return evaluabil",
        )

    accuracy = wins / decided
    avg_ret = sum(returns) / len(returns) if returns else 0.0
    return RegionalSliceResult(
        slice_id=label,
        region=region,
        regime=regime,
        status="EVALUATED",
        sample_size=len(cohort),
        accuracy=accuracy,
        avg_forward_return=avg_ret,
        data_source="hypothesis_linked_regional_csv",
    )


class RegionalGapClosureAnalyzer:
    """Read-only regional gap closure for kn_d5_00002."""

    def __init__(
        self,
        candidate_id: str = TARGET_CANDIDATE_ID,
        store: RegionalValidationStore | None = None,
    ) -> None:
        self._candidate_id = candidate_id
        self._store = store or RegionalValidationStore()
        self._sources_loaded: dict[str, bool] = {}
        self._artifacts: dict[str, dict[str, Any] | None] = {}
        self._hypotheses = HypothesisRegistry()
        self._data_loader = ResearchDataLoader()

    def analyze(self) -> RegionalValidationReport:
        self._load_sources()
        candidate = self._get_candidate()
        cross_val = self._get_cross_validation()
        gap_analysis = self._get_gap_analysis()

        source_hypothesis_id = str(
            candidate.get("source_hypothesis_id", "")
            if candidate
            else cross_val.get("source_hypothesis_id", "")
        )
        title = str(
            candidate.get("title", "")
            if candidate
            else cross_val.get("title", "Unknown")
        )

        datasets_found, datasets_missing = self._discover_datasets()
        slice_results = self._evaluate_slices(datasets_found, source_hypothesis_id)

        completed = sum(1 for s in slice_results if s.status == "EVALUATED")
        not_available = sum(
            1 for s in slice_results if s.status in (NOT_AVAILABLE, "INSUFFICIENT_SAMPLE")
        )

        us_status = self._us_baseline_status(cross_val)
        remaining_blockers = self._remaining_blockers(gap_analysis, slice_results)
        readiness, rationale = self._project_readiness(
            completed, not_available, remaining_blockers
        )
        checklist = self._build_acquisition_checklist(source_hypothesis_id)

        report = RegionalValidationReport(
            candidate_id=self._candidate_id,
            source_hypothesis_id=source_hypothesis_id,
            title=title,
            datasets_found=datasets_found,
            datasets_missing=datasets_missing,
            slice_results=slice_results,
            validations_completed=completed,
            validations_not_available=not_available,
            us_baseline_status=us_status,
            readiness_projection=readiness,
            readiness_rationale=rationale,
            remaining_blockers=remaining_blockers,
            data_acquisition_checklist=checklist,
            sources_loaded=dict(self._sources_loaded),
            pipeline_reference={
                **pipeline_reference(),
                "pipeline_role": PIPELINE_ROLE,
                "validation_feeder": True,
            },
            generated_at=datetime.now(timezone.utc),
        )
        self._store.persist(report)
        self._store.persist_txt(report)
        return report

    def _load_sources(self) -> None:
        paths = {
            "recalibration": RECALIBRATION_PATH,
            "evidence_gap": EVIDENCE_GAP_PATH,
            "cross_validation": CROSS_VALIDATION_PATH,
            "knowledge_candidates": KNOWLEDGE_CANDIDATES_PATH,
        }
        for key, path in paths.items():
            payload = _load_json(path)
            self._artifacts[key] = payload
            self._sources_loaded[key] = payload is not None

        self._hypotheses.load()
        self._sources_loaded["hypothesis_registry"] = self._hypotheses.count() > 0
        self._data_loader.load()
        self._sources_loaded[str(DEFAULT_ENSEMBLE_PATH)] = self._data_loader.row_count > 0

        for name, path in REFERENCE_DATASETS.items():
            self._sources_loaded[f"reference:{name}"] = path.is_file()

    def _get_candidate(self) -> dict[str, Any]:
        payload = self._artifacts.get("knowledge_candidates") or {}
        for cand in payload.get("candidates") or []:
            if cand.get("candidate_id") == self._candidate_id:
                return cand
        return {}

    def _get_cross_validation(self) -> dict[str, Any]:
        payload = self._artifacts.get("cross_validation") or {}
        for result in payload.get("candidate_results") or []:
            if result.get("candidate_id") == self._candidate_id:
                return result
        return {}

    def _get_gap_analysis(self) -> dict[str, Any]:
        payload = self._artifacts.get("evidence_gap") or {}
        for analysis in payload.get("analyses") or []:
            if analysis.get("candidate_id") == self._candidate_id:
                return analysis
        return {}

    def _discover_datasets(self) -> tuple[list[RegionalDatasetStatus], list[RegionalDatasetStatus]]:
        found: list[RegionalDatasetStatus] = []
        missing: list[RegionalDatasetStatus] = []

        for region, paths in EXPECTED_HYPOTHESIS_LINKED_PATHS.items():
            region_found = False
            for path in paths:
                if not path.is_file():
                    missing.append(
                        RegionalDatasetStatus(
                            path=str(path),
                            region=region,
                            kind=DatasetKind.MISSING,
                            found=False,
                            columns_missing=list(REQUIRED_ENSEMBLE_COLUMNS),
                            notes="Fișier hypothesis-linked regional absent",
                        )
                    )
                    continue

                rows, fieldnames = _read_csv(path)
                missing_cols = _missing_columns(fieldnames)
                if missing_cols:
                    found.append(
                        RegionalDatasetStatus(
                            path=str(path),
                            region=region,
                            kind=DatasetKind.INCOMPLETE,
                            found=True,
                            row_count=len(rows),
                            columns_present=fieldnames,
                            columns_missing=missing_cols,
                            notes="Fișier prezent dar coloane obligatorii lipsă — nu se estimează",
                        )
                    )
                    region_found = True
                    break

                hypothesis = self._hypotheses.get(
                    self._get_candidate().get("source_hypothesis_id", "")
                )
                matched = 0
                if hypothesis is not None:
                    matched = sum(
                        1 for row in rows if _row_matches_conditions(row, hypothesis.conditions)
                    )

                found.append(
                    RegionalDatasetStatus(
                        path=str(path),
                        region=region,
                        kind=DatasetKind.HYPOTHESIS_LINKED,
                        found=True,
                        row_count=len(rows),
                        columns_present=fieldnames,
                        columns_missing=[],
                        notes=(
                            f"Schema validă; {matched} rânduri match hypothesis filters"
                            if hypothesis
                            else "Schema validă; hypothesis filter indisponibil"
                        ),
                    )
                )
                region_found = True
                break

            if not region_found:
                pass  # all paths logged as missing

        for name, path in REFERENCE_DATASETS.items():
            if not path.is_file():
                continue
            rows, fieldnames = _read_csv(path)
            kind = DatasetKind.REFERENCE_ONLY
            region = "US" if name == "us_ensemble_baseline" else "context"
            note = ""
            if name == "multi_horizon_backtest":
                note = "Benchmark ETF returns — nu validează candidatul hypothesis-linked"
            elif name == "regional_strength":
                note = "Agregat regional strength — fără cohortă Forward_Return per semnal"
            elif name == "us_ensemble_baseline":
                note = "Cohortă US deja evaluată în cross-validation — nu înlocuiește Europe/UK"
            found.append(
                RegionalDatasetStatus(
                    path=str(path),
                    region=region,
                    kind=kind,
                    found=True,
                    row_count=len(rows),
                    columns_present=fieldnames,
                    notes=note,
                )
            )

        scanned = self._scan_project_csvs_for_regional_ensemble()
        for status in scanned:
            if status.kind == DatasetKind.HYPOTHESIS_LINKED and status.found:
                if not any(
                    f.path == status.path and f.kind == DatasetKind.HYPOTHESIS_LINKED
                    for f in found
                ):
                    found.append(status)

        return found, missing

    def _scan_project_csvs_for_regional_ensemble(self) -> list[RegionalDatasetStatus]:
        """Scan workspace CSVs for unexpected regional ensemble candidates."""
        results: list[RegionalDatasetStatus] = []
        skip = {
            str(DEFAULT_ENSEMBLE_PATH),
            "portfolio.csv",
            "live_signals.csv",
        }
        root = Path(".")
        for path in sorted(root.glob("**/*.csv")):
            rel = str(path)
            if rel in skip or "data_cache" in rel or "data_outputs" in rel:
                continue
            rows, fieldnames = _read_csv(path)
            if not rows or _missing_columns(fieldnames):
                continue

            europe_rows = [r for r in rows if _ticker_region(r.get("Ticker", "")) == "Europe"]
            uk_rows = [r for r in rows if _ticker_region(r.get("Ticker", "")) == "UK"]
            if not europe_rows and not uk_rows:
                continue

            if europe_rows:
                results.append(
                    RegionalDatasetStatus(
                        path=rel,
                        region="Europe",
                        kind=DatasetKind.INCOMPLETE,
                        found=True,
                        row_count=len(europe_rows),
                        columns_present=fieldnames,
                        notes=(
                            "CSV scan: conține tickere Europe cu schema ensemble parțială — "
                            "verifică linkage hypothesis și acoperire regim"
                        ),
                    )
                )
            if uk_rows:
                results.append(
                    RegionalDatasetStatus(
                        path=rel,
                        region="UK",
                        kind=DatasetKind.INCOMPLETE,
                        found=True,
                        row_count=len(uk_rows),
                        columns_present=fieldnames,
                        notes=(
                            "CSV scan: conține tickere UK cu schema ensemble parțială — "
                            "verifică linkage hypothesis"
                        ),
                    )
                )
        return results

    def _evaluate_slices(
        self,
        datasets_found: list[RegionalDatasetStatus],
        source_hypothesis_id: str,
    ) -> list[RegionalSliceResult]:
        results: list[RegionalSliceResult] = []
        hypothesis = self._hypotheses.get(source_hypothesis_id)

        regional_data: dict[str, list[dict[str, str]]] = {}
        for ds in datasets_found:
            if ds.kind != DatasetKind.HYPOTHESIS_LINKED:
                continue
            rows, _ = _read_csv(Path(ds.path))
            hypothesis_rows = rows
            if hypothesis is not None:
                hypothesis_rows = [
                    r for r in rows if _row_matches_conditions(r, hypothesis.conditions)
                ]
            regional_data[ds.region] = hypothesis_rows

        for region in ("Europe", "UK"):
            cohort = regional_data.get(region, [])
            data_source = ""
            for ds in datasets_found:
                if ds.region == region and ds.kind == DatasetKind.HYPOTHESIS_LINKED:
                    data_source = ds.path
                    break

            for regime in REGIMES:
                slice_id = f"{region}_{regime}"
                if not cohort:
                    results.append(
                        RegionalSliceResult(
                            slice_id=slice_id,
                            region=region,
                            regime=regime,
                            status=NOT_AVAILABLE,
                            reason=(
                                f"Lipsește fișier hypothesis-linked regional pentru {region}. "
                                f"Necesar: edge_ensemble_signal_scores_{region.lower()}.csv "
                                f"cu coloane {', '.join(REQUIRED_ENSEMBLE_COLUMNS)}"
                            ),
                        )
                    )
                    continue

                regime_cohort = [
                    r
                    for r in cohort
                    if str(r.get("Market_Regime", "")).upper() == regime
                ]
                slice_result = _slice_metrics(slice_id, regime_cohort)
                slice_result.data_source = data_source
                if slice_result.status != "EVALUATED":
                    slice_result.reason = (
                        slice_result.reason
                        or f"Cohortă {region}/{regime} insuficientă sau neevaluabilă"
                    )
                results.append(slice_result)

        return results

    def _us_baseline_status(self, cross_val: dict[str, Any]) -> str:
        region_slices = cross_val.get("region_slices") or {}
        us = region_slices.get("US") if isinstance(region_slices, dict) else None
        if isinstance(us, dict):
            return str(us.get("status", NOT_AVAILABLE))
        return NOT_AVAILABLE

    def _remaining_blockers(
        self,
        gap_analysis: dict[str, Any],
        slice_results: list[RegionalSliceResult],
    ) -> list[str]:
        blockers = list(gap_analysis.get("blocking_items") or [])

        regional_open = [
            s.slice_id
            for s in slice_results
            if s.status != "EVALUATED"
        ]
        if regional_open:
            blockers.insert(
                0,
                f"Europe/UK regional validation incomplete ({len(regional_open)}/6 slices NOT_AVAILABLE)",
            )

        deduped: list[str] = []
        seen: set[str] = set()
        for item in blockers:
            key = item.strip()
            if key and key not in seen:
                seen.add(key)
                deduped.append(key)
        return deduped

    def _project_readiness(
        self,
        completed: int,
        not_available: int,
        remaining_blockers: list[str],
    ) -> tuple[ReadinessProjection, str]:
        total_slices = 6
        if completed == total_slices:
            other_blockers = [
                b for b in remaining_blockers if "Europe/UK" not in b and "Europe " not in b
            ]
            if not other_blockers:
                return (
                    ReadinessProjection.READY_FOR_SANDBOX_REVIEW,
                    "Toate slice-urile regionale evaluate — blocaje non-regionale eliminate.",
                )
            return (
                ReadinessProjection.TOWARD_SANDBOX_REVIEW,
                f"Validare regională completă ({completed}/{total_slices}), "
                f"dar alte blocaje rămân: {len(other_blockers)}.",
            )

        return (
            ReadinessProjection.NOT_READY,
            f"Validare regională incompletă: {completed}/{total_slices} EVALUATED, "
            f"{not_available} NOT_AVAILABLE. "
            "Readiness NU poate avanza spre READY_FOR_SANDBOX_REVIEW fără "
            "hypothesis-linked CSV-uri Europe/UK.",
        )

    def _build_acquisition_checklist(
        self, source_hypothesis_id: str
    ) -> list[DataAcquisitionItem]:
        items: list[DataAcquisitionItem] = []
        for region in ("Europe", "UK"):
            filename = f"edge_ensemble_signal_scores_{region.lower()}.csv"
            items.append(
                DataAcquisitionItem(
                    item_id=f"acq_{region.lower()}_ensemble",
                    priority="HIGH",
                    description=(
                        f"Generați cohortă ensemble {region} pentru {source_hypothesis_id} "
                        f"(/ {self._candidate_id}) folosind același pipeline ca "
                        f"{DEFAULT_ENSEMBLE_PATH} — research only."
                    ),
                    required_file=filename,
                    required_columns=list(REQUIRED_ENSEMBLE_COLUMNS),
                    optional_columns=list(OPTIONAL_ENSEMBLE_COLUMNS),
                )
            )

        items.extend([
            DataAcquisitionItem(
                item_id="acq_regime_labels",
                priority="HIGH",
                description=(
                    "Asigurați etichete Market_Regime (BULL/BEAR/NEUTRAL) pe fiecare rând "
                    "regional — aceeași metodologie ca ensemble US."
                ),
                required_file="(coloană în CSV regional)",
                required_columns=["Market_Regime"],
            ),
            DataAcquisitionItem(
                item_id="acq_forward_outcomes",
                priority="HIGH",
                description=(
                    "Includeți Forward_Return_60d sau Win pentru fiecare semnal regional "
                    "— fără estimare sau imputare."
                ),
                required_file="(coloană în CSV regional)",
                required_columns=[FORWARD_RETURN_COL, "Win"],
            ),
            DataAcquisitionItem(
                item_id="acq_hypothesis_filters",
                priority="MEDIUM",
                description=(
                    f"Aplicați filtrele hypothesis {source_hypothesis_id} "
                    "(organism dominance / discovery conditions) la cohorta regională."
                ),
                required_file="tae_hypothesis_registry.json",
                required_columns=["Edge_Consensus_Score", "Matching_Edge_Count"],
                optional_columns=["Matching_Rules_Sample"],
            ),
            DataAcquisitionItem(
                item_id="acq_minimum_sample",
                priority="MEDIUM",
                description=(
                    f"Minim {MIN_SLICE_SAMPLE} rânduri per slice region×regim "
                    "pentru status EVALUATED."
                ),
                required_file="(acoperire cohortă)",
                required_columns=["Ticker", "Signal_Date"],
            ),
            DataAcquisitionItem(
                item_id="acq_revalidation",
                priority="MEDIUM",
                description=(
                    "După adăugarea CSV-urilor, re-rulați CrossRegimeValidator.validate_candidate_by_id "
                    f"('{self._candidate_id}') — research only."
                ),
                required_file="tae_cross_validation_report.json",
                required_columns=[],
            ),
        ])
        return items
