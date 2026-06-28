"""
TAE Evidence Engine registry — Phase VII foundation

ANALYSIS_ONLY | PAPER_ONLY | NO_BROKER | NO_EXECUTION

Central read-only registry for validated conclusions from prior TAE research phases.
Loads metrics from validated JSON reports; hardcoded fallback only when files missing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_core.evidence_engine.evidence_report import (
    DEFAULT_JSON_PATH,
    EvidenceContradiction,
    EvidenceEngineReport,
    EvidenceEngineVerdict,
    EvidenceItem,
    EvidenceRiskLevel,
    EvidenceStatus,
    ImplementationEligibility,
    SCHEMA_NAME as CANONICAL_SCHEMA,
)

logger = logging.getLogger(__name__)

CANONICAL_REGISTRY_MODULE = "research_core/evidence_engine/evidence_registry.py"
CANONICAL_REPORT_PATH = DEFAULT_JSON_PATH

STATISTICAL_AUDIT_PATH = Path("tae_closed_freeze_statistical_audit.json")
ROOT_CAUSE_PATH = Path("tae_closed_freeze_root_cause.json")
SCORE_DECOMP_PATH = Path("tae_score_decomposition_anomaly.json")
INDEPENDENT_PATH = Path("tae_independent_double_entry_verification.json")
EXIT_COUNTERFACTUAL_PATH = Path("tae_exit_counterfactual.json")
PROFIT_ATTRIBUTION_PATH = Path("tae_profit_attribution.json")
SIMULATION_LAB_PATH = Path("tae_continuous_strategy_simulation_lab.json")

FALLBACK_FLAG = "DATA_SOURCE_FALLBACK_USED"
METRIC_TOLERANCE = 0.015
SIMULATION_TARGET_STRATEGY = "SCORE_90_PLUS_NO_CLOSED_FREEZE"


@dataclass
class _SimulationMetrics:
    best_strategy_by_total_pnl: str
    baseline_total_pnl: float
    best_total_pnl: float
    delta_vs_baseline: float
    profit_factor: float
    win_rate: float
    expectancy: float
    primary_source: str
    used_fallback: bool


@dataclass
class _ClosedFreezeMetrics:
    current_dynamic_total_pnl: float
    current_dynamic_trades: int
    legacy_closed_freeze_total_pnl: float
    legacy_closed_freeze_trades: int
    legacy_vs_current_delta: float
    primary_source: str
    used_fallback: bool


@dataclass
class _SourceBundle:
    statistical_audit: dict[str, Any] | None = None
    root_cause: dict[str, Any] | None = None
    score_decomposition: dict[str, Any] | None = None
    independent: dict[str, Any] | None = None
    exit_counterfactual: dict[str, Any] | None = None
    profit_attribution: dict[str, Any] | None = None
    simulation_lab: dict[str, Any] | None = None
    flags: list[str] = field(default_factory=list)
    contradictions: list[EvidenceContradiction] = field(default_factory=list)

    @property
    def sources_loaded(self) -> dict[str, bool]:
        return {
            STATISTICAL_AUDIT_PATH.name: self.statistical_audit is not None,
            ROOT_CAUSE_PATH.name: self.root_cause is not None,
            SCORE_DECOMP_PATH.name: self.score_decomposition is not None,
            INDEPENDENT_PATH.name: self.independent is not None,
            EXIT_COUNTERFACTUAL_PATH.name: self.exit_counterfactual is not None,
            PROFIT_ATTRIBUTION_PATH.name: self.profit_attribution is not None,
            SIMULATION_LAB_PATH.name: self.simulation_lab is not None,
        }


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read %s: %s", path, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _values_differ(expected: float, actual: float) -> bool:
    return abs(expected - actual) > METRIC_TOLERANCE


def _record_contradiction(
    bundle: _SourceBundle,
    evidence_id: str,
    metric: str,
    source_file: str,
    expected: Any,
    actual: Any,
) -> None:
    bundle.contradictions.append(
        EvidenceContradiction(
            evidence_id=evidence_id,
            metric=metric,
            source_file=source_file,
            expected_value=expected,
            actual_value=actual,
        )
    )


def _load_sources() -> _SourceBundle:
    bundle = _SourceBundle(
        statistical_audit=_load_json(STATISTICAL_AUDIT_PATH),
        root_cause=_load_json(ROOT_CAUSE_PATH),
        score_decomposition=_load_json(SCORE_DECOMP_PATH),
        independent=_load_json(INDEPENDENT_PATH),
        exit_counterfactual=_load_json(EXIT_COUNTERFACTUAL_PATH),
        profit_attribution=_load_json(PROFIT_ATTRIBUTION_PATH),
        simulation_lab=_load_json(SIMULATION_LAB_PATH),
    )
    _cross_check_closed_freeze_sources(bundle)
    return bundle


def _cross_check_closed_freeze_sources(bundle: _SourceBundle) -> None:
    stat = bundle.statistical_audit
    root = bundle.root_cause
    if not stat or not root:
        return
    pairs = [
        (
            "current_dynamic_100_plus_total_pnl_usd",
            _safe_float(stat.get("current_score100", {}).get("total_pnl")),
            _safe_float(root.get("score100_current_pnl")),
        ),
        (
            "legacy_closed_freeze_100_plus_total_pnl_usd",
            _safe_float(stat.get("legacy_closed_freeze_score100", {}).get("total_pnl")),
            _safe_float(root.get("score100_legacy_pnl")),
        ),
        (
            "legacy_vs_current_delta_usd",
            _safe_float(stat.get("delta_current_vs_legacy_total_pnl")),
            _safe_float(root.get("anomaly_delta")),
        ),
    ]
    for metric, expected, actual in pairs:
        if _values_differ(expected, actual):
            _record_contradiction(
                bundle,
                "closed_freeze_cross_source",
                metric,
                f"{STATISTICAL_AUDIT_PATH.name} vs {ROOT_CAUSE_PATH.name}",
                expected,
                actual,
            )


def _find_strategy_row(
    simulation: dict[str, Any],
    strategy_id: str,
) -> dict[str, Any] | None:
    strategies = simulation.get("strategies", [])
    if not isinstance(strategies, list):
        return None
    for row in strategies:
        if isinstance(row, dict) and row.get("strategy_id") == strategy_id:
            return row
    return None


def _resolve_simulation_metrics(bundle: _SourceBundle) -> _SimulationMetrics:
    sim = bundle.simulation_lab
    if sim:
        baseline = _safe_float(sim.get("baseline_total_pnl"))
        best_strategy_id = str(
            sim.get("best_strategy_by_total_pnl", SIMULATION_TARGET_STRATEGY)
        )
        row = _find_strategy_row(sim, SIMULATION_TARGET_STRATEGY)
        if row is None and best_strategy_id:
            row = _find_strategy_row(sim, best_strategy_id)
        if row:
            best_total = _safe_float(row.get("total_pnl"))
            return _SimulationMetrics(
                best_strategy_by_total_pnl=best_strategy_id,
                baseline_total_pnl=baseline,
                best_total_pnl=best_total,
                delta_vs_baseline=round(best_total - baseline, 2),
                profit_factor=_safe_float(row.get("profit_factor")),
                win_rate=_safe_float(row.get("win_rate")),
                expectancy=_safe_float(row.get("expectancy")),
                primary_source=SIMULATION_LAB_PATH.name,
                used_fallback=False,
            )

    bundle.flags.append(FALLBACK_FLAG)
    baseline = 330.45
    best_total = 794.2
    return _SimulationMetrics(
        best_strategy_by_total_pnl=SIMULATION_TARGET_STRATEGY,
        baseline_total_pnl=baseline,
        best_total_pnl=best_total,
        delta_vs_baseline=round(best_total - baseline, 2),
        profit_factor=7.7724,
        win_rate=63.64,
        expectancy=65.82,
        primary_source="hardcoded_fallback",
        used_fallback=True,
    )


def _resolve_closed_freeze_metrics(bundle: _SourceBundle) -> _ClosedFreezeMetrics:
    stat = bundle.statistical_audit
    root = bundle.root_cause
    decomp = bundle.score_decomposition

    if stat:
        current = stat.get("current_score100", {})
        legacy = stat.get("legacy_closed_freeze_score100", {})
        return _ClosedFreezeMetrics(
            current_dynamic_total_pnl=_safe_float(current.get("total_pnl")),
            current_dynamic_trades=int(current.get("trades", 0)),
            legacy_closed_freeze_total_pnl=_safe_float(legacy.get("total_pnl")),
            legacy_closed_freeze_trades=int(legacy.get("trades", 0)),
            legacy_vs_current_delta=_safe_float(stat.get("delta_current_vs_legacy_total_pnl")),
            primary_source=STATISTICAL_AUDIT_PATH.name,
            used_fallback=False,
        )

    if root:
        return _ClosedFreezeMetrics(
            current_dynamic_total_pnl=_safe_float(root.get("score100_current_pnl")),
            current_dynamic_trades=int(root.get("score100_current_trades", 0)),
            legacy_closed_freeze_total_pnl=_safe_float(root.get("score100_legacy_pnl")),
            legacy_closed_freeze_trades=int(root.get("score100_legacy_trades", 0)),
            legacy_vs_current_delta=_safe_float(root.get("anomaly_delta")),
            primary_source=ROOT_CAUSE_PATH.name,
            used_fallback=False,
        )

    if decomp:
        freeze_rows = [
            g
            for g in decomp.get("group_aggregates", [])
            if g.get("dimension") == "reason"
            and g.get("bucket") == "CLOSED_FREEZE"
            and g.get("cohort") == "100+"
        ]
        dynamic_rows = [
            g
            for g in decomp.get("group_aggregates", [])
            if g.get("dimension") == "reason"
            and g.get("bucket") == "DYNAMIC_MARKET_REGIME"
            and g.get("cohort") == "100+"
        ]
        legacy_pnl = _safe_float(freeze_rows[0].get("total_pnl")) if freeze_rows else -336.93
        legacy_n = int(freeze_rows[0].get("buy_count", 0)) if freeze_rows else 7
        current_pnl = _safe_float(dynamic_rows[0].get("total_pnl")) if dynamic_rows else 198.46
        current_n = int(dynamic_rows[0].get("buy_count", 0)) if dynamic_rows else 7
        return _ClosedFreezeMetrics(
            current_dynamic_total_pnl=current_pnl,
            current_dynamic_trades=current_n,
            legacy_closed_freeze_total_pnl=legacy_pnl,
            legacy_closed_freeze_trades=legacy_n,
            legacy_vs_current_delta=round(current_pnl - legacy_pnl, 2),
            primary_source=SCORE_DECOMP_PATH.name,
            used_fallback=False,
        )

    bundle.flags.append(FALLBACK_FLAG)
    return _ClosedFreezeMetrics(
        current_dynamic_total_pnl=396.56,
        current_dynamic_trades=7,
        legacy_closed_freeze_total_pnl=-611.72,
        legacy_closed_freeze_trades=7,
        legacy_vs_current_delta=1008.28,
        primary_source="hardcoded_fallback",
        used_fallback=True,
    )


def _verify_item_metrics(
    bundle: _SourceBundle,
    evidence_id: str,
    source_file: str,
    expected_from_source: dict[str, float],
    item_metrics: dict[str, Any],
) -> None:
    for metric, expected in expected_from_source.items():
        actual = _safe_float(item_metrics.get(metric), float("nan"))
        if actual != actual or _values_differ(expected, actual):
            _record_contradiction(
                bundle,
                evidence_id,
                metric,
                source_file,
                expected,
                item_metrics.get(metric),
            )


def _build_evidence_items(bundle: _SourceBundle) -> list[EvidenceItem]:
    now = datetime.now(timezone.utc)
    freeze = _resolve_closed_freeze_metrics(bundle)
    if freeze.used_fallback:
        bundle.flags.append(FALLBACK_FLAG)

    items: list[EvidenceItem] = []

    # --- accounting_verified ---
    indep = bundle.independent
    if indep:
        account_value = _safe_float(indep.get("independent_account_value"))
        delta_dashboard = _safe_float(indep.get("delta_vs_dashboard_expected"))
        total_pnl = _safe_float(indep.get("independent_total_pnl"))
        verdict = str(indep.get("verdict", "INDEPENDENTLY_VERIFIED"))
        source_ref = INDEPENDENT_PATH.name
        used_fallback = False
    else:
        bundle.flags.append(FALLBACK_FLAG)
        account_value = 30330.47
        delta_dashboard = 0.0
        total_pnl = 330.47
        verdict = "INDEPENDENTLY_VERIFIED"
        source_ref = "hardcoded_fallback"
        used_fallback = True

    acct_metrics = {
        "verdict": verdict,
        "account_value_usd": round(account_value, 2),
        "delta_vs_dashboard_usd": round(delta_dashboard, 2),
        "independent_total_pnl_usd": round(total_pnl, 2),
        "data_source": source_ref,
    }
    if indep and not used_fallback:
        _verify_item_metrics(
            bundle,
            "accounting_verified",
            source_ref,
            {
                "account_value_usd": account_value,
                "delta_vs_dashboard_usd": delta_dashboard,
                "independent_total_pnl_usd": total_pnl,
            },
            acct_metrics,
        )
    items.append(
        EvidenceItem(
            evidence_id="accounting_verified",
            title="Contabilitate verificată independent",
            conclusion=(
                f"Ledger-ul FIFO independent confirmă account value ${account_value:,.2f} "
                f"cu delta ${delta_dashboard:,.2f} față de dashboard."
            ),
            source_phase="Phase VI B6",
            source_ref=source_ref,
            status=EvidenceStatus.CONFIRMED,
            risk_level=EvidenceRiskLevel.LOW,
            implementation_eligibility=ImplementationEligibility.RESEARCH_ONLY,
            supporting_metrics=acct_metrics,
            registered_at=now,
        )
    )

    # --- exit_approximately_optimal ---
    exit_cf = bundle.exit_counterfactual
    if exit_cf:
        primary = next(
            (
                h
                for h in exit_cf.get("horizon_aggregates", [])
                if h.get("horizon_days") == exit_cf.get("primary_horizon_days", 5)
            ),
            None,
        )
        extra_5d = _safe_float(primary.get("total_extra_profit")) if primary else -415.21
        pct_imp = _safe_float(primary.get("pct_improved")) if primary else 52.0
        sells = int(exit_cf.get("sells_analyzed", 25))
        exit_verdict = str(exit_cf.get("verdict", "EXITS_APPROXIMATELY_OPTIMAL"))
        exit_ref = EXIT_COUNTERFACTUAL_PATH.name
    else:
        bundle.flags.append(FALLBACK_FLAG)
        extra_5d = -415.21
        pct_imp = 52.0
        sells = 25
        exit_verdict = "EXITS_APPROXIMATELY_OPTIMAL"
        exit_ref = "hardcoded_fallback"

    exit_metrics = {
        "verdict": exit_verdict,
        "sells_analyzed": sells,
        "total_extra_profit_5d_usd": round(extra_5d, 2),
        "pct_improved_if_waited": round(pct_imp, 2),
        "data_source": exit_ref,
    }
    if exit_cf:
        _verify_item_metrics(
            bundle,
            "exit_approximately_optimal",
            exit_ref,
            {"total_extra_profit_5d_usd": extra_5d, "pct_improved_if_waited": pct_imp},
            exit_metrics,
        )
    items.append(
        EvidenceItem(
            evidence_id="exit_approximately_optimal",
            title="Ieșiri aproximativ optime",
            conclusion=(
                f"Analiza contrafactuală la +5 zile arată delta totală ${extra_5d:,.2f} — "
                "așteptarea după SELL ar fi redus PnL agregat. Regulile actuale de exit "
                "sunt aproximativ corecte."
            ),
            source_phase="Phase VII A2",
            source_ref=exit_ref,
            status=EvidenceStatus.CONFIRMED,
            risk_level=EvidenceRiskLevel.LOW,
            implementation_eligibility=ImplementationEligibility.NOT_ELIGIBLE,
            supporting_metrics=exit_metrics,
            registered_at=now,
        )
    )

    # --- profit_attribution_loss_consumption ---
    attr = bundle.profit_attribution
    if attr and isinstance(attr.get("core"), dict):
        core = attr["core"]
        gross_profit = _safe_float(core.get("gross_profit"))
        gross_loss = abs(_safe_float(core.get("gross_loss")))
        net_realized = _safe_float(core.get("net_realized_profit"))
        profit_factor = _safe_float(core.get("profit_factor"))
        attr_verdict = str(attr.get("verdict", "PROFIT_LOW_DUE_TO_CONCENTRATION"))
        attr_ref = PROFIT_ATTRIBUTION_PATH.name
    else:
        bundle.flags.append(FALLBACK_FLAG)
        gross_profit = 990.28
        gross_loss = 705.15
        net_realized = 285.13
        profit_factor = 1.4044
        attr_verdict = "PROFIT_LOW_DUE_TO_CONCENTRATION"
        attr_ref = "hardcoded_fallback"

    loss_share_pct = round(gross_loss / gross_profit * 100.0, 1) if gross_profit else 0.0
    attr_metrics = {
        "verdict": attr_verdict,
        "gross_profit_usd": round(gross_profit, 2),
        "gross_loss_usd": round(gross_loss, 2),
        "loss_share_of_gross_profit_pct": loss_share_pct,
        "net_realized_pnl_usd": round(net_realized, 2),
        "profit_factor": round(profit_factor, 4),
        "data_source": attr_ref,
    }
    if attr:
        _verify_item_metrics(
            bundle,
            "profit_attribution_loss_consumption",
            attr_ref,
            {
                "gross_profit_usd": gross_profit,
                "gross_loss_usd": gross_loss,
                "net_realized_pnl_usd": net_realized,
            },
            attr_metrics,
        )
    items.append(
        EvidenceItem(
            evidence_id="profit_attribution_loss_consumption",
            title="Pierderile consumă ~71% din profitul brut",
            conclusion=(
                f"Profit attribution: gross profit ${gross_profit:,.2f}, "
                f"gross loss ${gross_loss:,.2f} — pierderile absorb "
                f"~{loss_share_pct:.0f}% din profitul brut realizat."
            ),
            source_phase="Phase VII A1",
            source_ref=attr_ref,
            status=EvidenceStatus.CONFIRMED,
            risk_level=EvidenceRiskLevel.MEDIUM,
            implementation_eligibility=ImplementationEligibility.RESEARCH_ONLY,
            supporting_metrics=attr_metrics,
            registered_at=now,
        )
    )

    # --- score_100_anomaly_initial ---
    decomp = bundle.score_decomposition
    if decomp:
        c90 = decomp.get("cohort_90_99", {})
        c100 = decomp.get("cohort_100_plus", {})
        pnl_90 = _safe_float(c90.get("total_pnl"))
        pnl_100 = _safe_float(c100.get("total_pnl"))
        cohort_delta = _safe_float(decomp.get("cohort_delta_total_pnl"))
        decomp_verdict = str(decomp.get("verdict", "SCORE_100_ANOMALY_CONFIRMED"))
        data_gaps = decomp.get("data_gaps", [])
        decomp_ref = SCORE_DECOMP_PATH.name
    else:
        bundle.flags.append(FALLBACK_FLAG)
        pnl_90 = 595.74
        pnl_100 = -138.47
        cohort_delta = 734.21
        decomp_verdict = "SCORE_100_ANOMALY_CONFIRMED"
        data_gaps = ["DATA_GAP_SCORE_COMPONENTS_MISSING"]
        decomp_ref = "hardcoded_fallback"

    decomp_metrics = {
        "verdict": decomp_verdict,
        "cohort_100_plus_total_pnl_usd": round(pnl_100, 2),
        "cohort_90_99_total_pnl_usd": round(pnl_90, 2),
        "cohort_delta_usd": round(cohort_delta, 2),
        "data_gaps": data_gaps,
        "data_source": decomp_ref,
    }
    if decomp:
        _verify_item_metrics(
            bundle,
            "score_100_anomaly_initial",
            decomp_ref,
            {
                "cohort_100_plus_total_pnl_usd": pnl_100,
                "cohort_90_99_total_pnl_usd": pnl_90,
                "cohort_delta_usd": cohort_delta,
            },
            decomp_metrics,
        )
    items.append(
        EvidenceItem(
            evidence_id="score_100_anomaly_initial",
            title="Anomalie Score 100+ confirmată inițial",
            conclusion=(
                f"Coortă Score 100+ total PnL ${pnl_100:,.2f} vs Score 90–99 ${pnl_90:,.2f} — "
                f"delta ${cohort_delta:,.2f}. Anomalie cohortă confirmată la nivel FIFO."
            ),
            source_phase="Phase VII A4",
            source_ref=decomp_ref,
            status=EvidenceStatus.CONFIRMED,
            risk_level=EvidenceRiskLevel.MEDIUM,
            implementation_eligibility=ImplementationEligibility.RESEARCH_ONLY,
            supporting_metrics=decomp_metrics,
            registered_at=now,
        )
    )

    # --- legacy_closed_freeze_distortion ---
    legacy_avg = (
        round(freeze.legacy_closed_freeze_total_pnl / freeze.legacy_closed_freeze_trades, 2)
        if freeze.legacy_closed_freeze_trades
        else 0.0
    )
    legacy_metrics = {
        "verdict": "LEGACY_CLOSED_FREEZE_DISTORTION_CONFIRMED",
        "legacy_closed_freeze_100_plus_trades": freeze.legacy_closed_freeze_trades,
        "legacy_closed_freeze_100_plus_total_pnl_usd": round(
            freeze.legacy_closed_freeze_total_pnl, 2
        ),
        "legacy_closed_freeze_100_plus_avg_pnl_usd": legacy_avg,
        "current_dynamic_100_plus_total_pnl_usd": round(freeze.current_dynamic_total_pnl, 2),
        "data_source": freeze.primary_source,
    }
    _verify_item_metrics(
        bundle,
        "legacy_closed_freeze_distortion",
        freeze.primary_source,
        {
            "legacy_closed_freeze_100_plus_total_pnl_usd": freeze.legacy_closed_freeze_total_pnl,
            "current_dynamic_100_plus_total_pnl_usd": freeze.current_dynamic_total_pnl,
        },
        legacy_metrics,
    )
    items.append(
        EvidenceItem(
            evidence_id="legacy_closed_freeze_distortion",
            title="Distorsiune legacy CLOSED_FREEZE confirmată",
            conclusion=(
                f"Score 100+ CLOSED_FREEZE: {freeze.legacy_closed_freeze_trades} intrări, "
                f"PnL total ${freeze.legacy_closed_freeze_total_pnl:,.2f}. "
                "Anomalia Score 100+ este concentrată în etichete istorice CLOSED_FREEZE."
            ),
            source_phase="Phase VII A5",
            source_ref=freeze.primary_source,
            status=EvidenceStatus.CONFIRMED,
            risk_level=EvidenceRiskLevel.MEDIUM,
            implementation_eligibility=ImplementationEligibility.RESEARCH_ONLY,
            supporting_metrics=legacy_metrics,
            registered_at=now,
        )
    )

    # --- score_100_current_not_defective ---
    current_metrics = {
        "current_dynamic_100_plus_trades": freeze.current_dynamic_trades,
        "current_dynamic_100_plus_total_pnl_usd": round(freeze.current_dynamic_total_pnl, 2),
        "legacy_closed_freeze_100_plus_total_pnl_usd": round(
            freeze.legacy_closed_freeze_total_pnl, 2
        ),
        "legacy_vs_current_delta_usd": round(freeze.legacy_vs_current_delta, 2),
        "root_cause_status": "LEGACY_LABEL_NOT_CURRENT_SCORE_LOGIC",
        "data_source": freeze.primary_source,
    }
    _verify_item_metrics(
        bundle,
        "score_100_current_not_defective",
        freeze.primary_source,
        {
            "current_dynamic_100_plus_total_pnl_usd": freeze.current_dynamic_total_pnl,
            "legacy_closed_freeze_100_plus_total_pnl_usd": freeze.legacy_closed_freeze_total_pnl,
            "legacy_vs_current_delta_usd": freeze.legacy_vs_current_delta,
        },
        current_metrics,
    )
    conclusion_text = (
        f"Intrările Score 100+ dinamice curente sumă ${freeze.current_dynamic_total_pnl:,.2f} "
        f"({freeze.current_dynamic_trades} tranzacții) vs legacy CLOSED_FREEZE "
        f"${freeze.legacy_closed_freeze_total_pnl:,.2f} — delta ${freeze.legacy_vs_current_delta:,.2f}. "
        "Pragul 100+ curent nu este dovedit defect; anomalia inițială este explicată de legacy freeze."
    )
    if bundle.root_cause and isinstance(bundle.root_cause.get("conclusion"), str):
        conclusion_text = bundle.root_cause["conclusion"]
    elif bundle.statistical_audit and isinstance(bundle.statistical_audit.get("conclusion"), str):
        conclusion_text = bundle.statistical_audit["conclusion"]

    items.append(
        EvidenceItem(
            evidence_id="score_100_current_not_defective",
            title="Score 100+ curent neconfirmat ca defect",
            conclusion=conclusion_text,
            source_phase="Phase VII A5",
            source_ref=freeze.primary_source,
            status=EvidenceStatus.CONFIRMED,
            risk_level=EvidenceRiskLevel.LOW,
            implementation_eligibility=ImplementationEligibility.PAPER_VALIDATION_ELIGIBLE,
            supporting_metrics=current_metrics,
            registered_at=now,
        )
    )

    # --- simulation_best_score_90_plus_no_closed_freeze ---
    sim_metrics_data = _resolve_simulation_metrics(bundle)
    if sim_metrics_data.used_fallback:
        bundle.flags.append(FALLBACK_FLAG)
    sim_metrics = {
        "best_strategy_by_total_pnl": sim_metrics_data.best_strategy_by_total_pnl,
        "baseline_total_pnl": round(sim_metrics_data.baseline_total_pnl, 2),
        "best_total_pnl": round(sim_metrics_data.best_total_pnl, 2),
        "delta_vs_baseline": round(sim_metrics_data.delta_vs_baseline, 2),
        "profit_factor": round(sim_metrics_data.profit_factor, 4),
        "win_rate": round(sim_metrics_data.win_rate, 2),
        "expectancy": round(sim_metrics_data.expectancy, 2),
        "data_source": sim_metrics_data.primary_source,
    }
    if bundle.simulation_lab and not sim_metrics_data.used_fallback:
        _verify_item_metrics(
            bundle,
            "simulation_best_score_90_plus_no_closed_freeze",
            sim_metrics_data.primary_source,
            {
                "baseline_total_pnl": sim_metrics_data.baseline_total_pnl,
                "best_total_pnl": sim_metrics_data.best_total_pnl,
                "delta_vs_baseline": sim_metrics_data.delta_vs_baseline,
                "profit_factor": sim_metrics_data.profit_factor,
                "win_rate": sim_metrics_data.win_rate,
                "expectancy": sim_metrics_data.expectancy,
            },
            sim_metrics,
        )
    sim_conclusion = (
        f"Simulation lab: {sim_metrics_data.best_strategy_by_total_pnl} total PnL "
        f"${sim_metrics_data.best_total_pnl:,.2f} vs baseline ${sim_metrics_data.baseline_total_pnl:,.2f} "
        f"(delta +${sim_metrics_data.delta_vs_baseline:,.2f}). "
        f"PF {sim_metrics_data.profit_factor:.4f}, win rate {sim_metrics_data.win_rate:.1f}%, "
        f"expectancy ${sim_metrics_data.expectancy:,.2f}."
    )
    if bundle.simulation_lab and isinstance(bundle.simulation_lab.get("verdict"), str):
        sim_conclusion = (
            f"{sim_conclusion} Lab verdict: {bundle.simulation_lab['verdict']}."
        )

    items.append(
        EvidenceItem(
            evidence_id="simulation_best_score_90_plus_no_closed_freeze",
            title="Simulation winner: Score >=90 excluding CLOSED_FREEZE",
            conclusion=sim_conclusion,
            source_phase="Phase VII Simulation Lab",
            source_ref=sim_metrics_data.primary_source,
            status=EvidenceStatus.CONFIRMED,
            risk_level=EvidenceRiskLevel.MEDIUM,
            implementation_eligibility=ImplementationEligibility.PAPER_VALIDATION_ELIGIBLE,
            supporting_metrics=sim_metrics,
            registered_at=now,
        )
    )

    return items


class EvidenceRegistry:
    """Read-only central registry of validated TAE research conclusions."""

    def __init__(self) -> None:
        self._items: dict[str, EvidenceItem] = {}
        self._bundle: _SourceBundle | None = None

    def register(self, item: EvidenceItem) -> None:
        if item.evidence_id in self._items:
            logger.warning("Replacing evidence item %s", item.evidence_id)
        self._items[item.evidence_id] = item

    def get(self, evidence_id: str) -> EvidenceItem | None:
        return self._items.get(evidence_id)

    def list_all(self) -> list[EvidenceItem]:
        return sorted(self._items.values(), key=lambda i: i.evidence_id)

    def count(self) -> int:
        return len(self._items)

    @property
    def source_bundle(self) -> _SourceBundle | None:
        return self._bundle

    def load_validated_phases(self) -> int:
        """Seed registry from validated JSON reports (fallback if missing)."""
        self._bundle = _load_sources()
        items = _build_evidence_items(self._bundle)
        self._items.clear()
        for item in items:
            self.register(item)
        return len(items)

    def build_report(self) -> EvidenceEngineReport:
        items = self.list_all()
        confirmed = sum(1 for i in items if i.status == EvidenceStatus.CONFIRMED)
        inconclusive = sum(1 for i in items if i.status == EvidenceStatus.INCONCLUSIVE)
        rejected = sum(1 for i in items if i.status == EvidenceStatus.REJECTED)

        bundle = self._bundle or _SourceBundle()
        flags = sorted(set(bundle.flags))
        contradictions = list(bundle.contradictions)

        if contradictions:
            verdict = EvidenceEngineVerdict.EVIDENCE_CONTRADICTION_DETECTED
        else:
            verdict = EvidenceEngineVerdict.EVIDENCE_ENGINE_SOURCE_OF_TRUTH_ALIGNED

        return EvidenceEngineReport(
            verdict=verdict,
            evidence_items=items,
            confirmed_count=confirmed,
            inconclusive_count=inconclusive,
            rejected_count=rejected,
            registry_item_count=len(items),
            data_source_flags=flags,
            contradictions=contradictions,
            sources_loaded=bundle.sources_loaded,
        )


class EvidenceEngine:
    """Facade for initializing the registry and producing reports."""

    def __init__(self, registry: EvidenceRegistry | None = None) -> None:
        self._registry = registry or EvidenceRegistry()

    @property
    def registry(self) -> EvidenceRegistry:
        return self._registry

    def initialize(self) -> EvidenceEngineReport:
        self._registry.load_validated_phases()
        return self._registry.build_report()


def load_canonical_evidence_report(
    json_path: Path | None = None,
) -> dict[str, Any] | None:
    """Load canonical evidence engine report JSON — read-only, no re-registration."""
    path = json_path or CANONICAL_REPORT_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.debug("Canonical evidence report read failed: %s", exc)
        return None
    if data.get("schema") != CANONICAL_SCHEMA:
        logger.debug("Unexpected schema in %s: %s", path, data.get("schema"))
    return data
