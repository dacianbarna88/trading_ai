#!/usr/bin/env python3
"""
TAE Learning-to-Profit Bridge — PAPER_ONLY / READ_ONLY / NO_BROKER.

Consolidates existing learning and profit SSOT outputs into ranked PAPER hypotheses
and a paper experiment queue. Does NOT execute trades, modify live paths, or promote to live.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_self_improve_wiring import (
    behavior_cohort_key,
    classify_behavior,
    economic_experiment_uid,
    load_loss_causal_cases,
    parse_validation_requirements,
    stable_hash,
)

SCHEMA = "tae_learning_to_profit_bridge"
VERSION = "v1"
MODE = "PAPER_ONLY"

GII_JSON = Path("tae_growth_intelligence.json")
LEDGER_JSON = Path("tae_opportunity_cost_ledger.json")
LIFECYCLE_JSON = Path("tae_winner_lifecycle_profiler.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
PROTECTION_SHADOW_JSON = Path("tae_profit_protection_shadow.json")
PROTECTION_VALIDATION_JSON = Path("tae_profit_protection_validation.json")
DPE_EVAL_JSON = Path("runtime_outputs/dpe/result_evaluator/evaluation.json")
DPE_LEARNING_JSON = Path("runtime_outputs/dpe/learning/learning.json")
DPE_ADAPTIVE_JSON = Path("runtime_outputs/dpe/adaptive/adaptive.json")
DECISION_REPLAY_JSON = Path("tae_decision_replay.json")
CONFIDENCE_JSON = Path("tae_confidence_evolution.json")
PATTERN_DISCOVERY_TXT = Path("pattern_discovery_summary.txt")
LEARNING_ATTRIBUTION_JSON = Path("tae_learning_economic_attribution.json")
FORWARD_LEARNING_JSON = Path("tae_forward_learning_evidence_status.json")
ABLATION_SUMMARY_JSON = Path("tae_learning_ablation_summary.json")
RULE_OUTCOME_ATTRIBUTION_JSON = Path("runtime_outputs/paper_execution/rule_outcome_attribution.json")
PARALLEL_ECONOMIC_SUMMARY_JSON = Path("runtime_outputs/parallel_paper/attribution/economic_summary.json")
LONGITUDINAL_MEMORY_INDEX = Path("runtime_outputs/longitudinal_memory/memory_index.json")
V1_TRADES = Path("runtime_outputs/parallel_paper/v1/journals/trades.jsonl")
V1_EXECS = Path("runtime_outputs/parallel_paper/v1/journals/executions.jsonl")
LOSS_CAUSAL_JSON = Path("TAE_LOSS_CAUSAL_CLASSIFICATION.json")

OUTPUT_DIR = Path("runtime_outputs/learning_to_profit")
HYPOTHESES_JSON = OUTPUT_DIR / "hypotheses.json"
QUEUE_JSONL = OUTPUT_DIR / "paper_experiment_queue.jsonl"
REPORT_MD = Path("TAE_LEARNING_TO_PROFIT_BRIDGE_REPORT.md")

FORBIDDEN_WRITE_PREFIXES = (
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "live_bot.py",
    "core/",
    "research_core/",
)

FRESHNESS_HOURS = {
    "growth_intelligence": (GII_JSON, 24),
    "opportunity_ledger": (LEDGER_JSON, 24),
    "winner_lifecycle": (LIFECYCLE_JSON, 24),
    "ppg": (PPG_JSON, 24),
    "appe": (APPE_JSON, 24),
    "profit_protection_shadow": (PROTECTION_SHADOW_JSON, 24),
    "dpe_evaluation": (DPE_EVAL_JSON, 48),
    "dpe_learning": (DPE_LEARNING_JSON, 48),
    "dpe_adaptive": (DPE_ADAPTIVE_JSON, 48),
    "decision_replay": (DECISION_REPLAY_JSON, 72),
    "confidence_evolution": (CONFIDENCE_JSON, 72),
    "learning_attribution": (LEARNING_ATTRIBUTION_JSON, 48),
    "forward_learning": (FORWARD_LEARNING_JSON, 24),
    "ablation_summary": (ABLATION_SUMMARY_JSON, 72),
    "rule_outcome_attribution": (RULE_OUTCOME_ATTRIBUTION_JSON, 24),
    "parallel_economic_summary": (PARALLEL_ECONOMIC_SUMMARY_JSON, 24),
    "longitudinal_memory_index": (LONGITUDINAL_MEMORY_INDEX, 24),
    "v1_trades": (V1_TRADES, 24),
    "v1_executions": (V1_EXECS, 24),
}

CAPITAL_EFFICIENCY_THRESHOLD = 35.0
OPPORTUNITY_COST_MIN_USD = 25.0
PROTECTION_MIN_MISSED_USD = 15.0


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any, default: str = "UNKNOWN") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def load_json(path: Path) -> tuple[dict[str, Any] | None, bool]:
    if not path.is_file():
        return None, False
    try:
        return json.loads(path.read_text(encoding="utf-8")), True
    except (json.JSONDecodeError, OSError):
        return None, False


def _load_jsonl_rows(path: Path, limit: int = 5000) -> list[dict[str, Any]]:
    """Load valid JSON objects from a JSONL artifact, failing soft on bad rows."""
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if len(rows) >= limit:
                    break
                try:
                    row = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        return []
    return rows


def file_age_hours(path: Path) -> float | None:
    if not path.is_file():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return round((datetime.now(timezone.utc) - mtime).total_seconds() / 3600, 1)


def assert_safe_output_path(path: Path) -> None:
    resolved = str(path.resolve())
    output_root = OUTPUT_DIR.resolve()
    if path.resolve() != REPORT_MD.resolve() and output_root not in path.resolve().parents:
        raise RuntimeError(f"Unsafe output path outside learning_to_profit/: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def _hypothesis(
    *,
    hypothesis_id: str,
    hypothesis_type: str,
    source_systems: list[str],
    evidence_summary: str,
    affected_tickers: list[str],
    target_metric: str,
    expected_profit_mechanism: str,
    risk_level: str,
    confidence: float,
    required_paper_duration: int,
    validation_rule: str,
    rejection_rule: str,
    paper_experiment_action: str,
    paper_experiment_description: str,
    priority_score: float,
) -> dict[str, Any]:
    parsed_requirements = parse_validation_requirements(validation_rule)
    return {
        "hypothesis_id": hypothesis_id,
        "hypothesis_type": hypothesis_type,
        "source_systems": source_systems,
        "evidence_summary": evidence_summary,
        "affected_tickers": affected_tickers,
        "target_metric": target_metric,
        "expected_profit_mechanism": expected_profit_mechanism,
        "risk_level": risk_level,
        "confidence": round(confidence, 3),
        "required_paper_duration": required_paper_duration,
        "validation_rule": validation_rule,
        "validation_requirements_parsed": parsed_requirements[
            "validation_requirements_parsed"
        ],
        "validation_requirements_parse_status": parsed_requirements["PARSE_STATUS"],
        "validation_requirements_unparsed": parsed_requirements[
            "unparsed_requirements"
        ],
        "rejection_rule": rejection_rule,
        "live_promotion_allowed": False,
        "mode": MODE,
        "paper_experiment": {
            "action": paper_experiment_action,
            "description": paper_experiment_description,
        },
        "priority_score": round(priority_score, 2),
        "created_at": _now(),
    }


def load_sources() -> tuple[dict[str, dict[str, Any] | None], dict[str, bool]]:
    paths = {
        "growth_intelligence": GII_JSON,
        "opportunity_ledger": LEDGER_JSON,
        "winner_lifecycle": LIFECYCLE_JSON,
        "ppg": PPG_JSON,
        "appe": APPE_JSON,
        "profit_protection_shadow": PROTECTION_SHADOW_JSON,
        "profit_protection_validation": PROTECTION_VALIDATION_JSON,
        "dpe_evaluation": DPE_EVAL_JSON,
        "dpe_learning": DPE_LEARNING_JSON,
        "dpe_adaptive": DPE_ADAPTIVE_JSON,
        "decision_replay": DECISION_REPLAY_JSON,
        "confidence_evolution": CONFIDENCE_JSON,
        "learning_attribution": LEARNING_ATTRIBUTION_JSON,
        "forward_learning": FORWARD_LEARNING_JSON,
        "ablation_summary": ABLATION_SUMMARY_JSON,
        "rule_outcome_attribution": RULE_OUTCOME_ATTRIBUTION_JSON,
        "parallel_economic_summary": PARALLEL_ECONOMIC_SUMMARY_JSON,
        "longitudinal_memory_index": LONGITUDINAL_MEMORY_INDEX,
        "loss_causal_classification": LOSS_CAUSAL_JSON,
    }
    payloads: dict[str, dict[str, Any] | None] = {}
    loaded: dict[str, bool] = {}
    for key, path in paths.items():
        payloads[key], loaded[key] = load_json(path)
    for key, path in (("v1_trades", V1_TRADES), ("v1_executions", V1_EXECS)):
        rows = _load_jsonl_rows(path)
        payloads[key] = {"rows": rows, "count": len(rows)} if path.is_file() else None
        loaded[key] = path.is_file()
    payloads["pattern_discovery_present"] = {"present": PATTERN_DISCOVERY_TXT.is_file()}
    loaded["pattern_discovery"] = PATTERN_DISCOVERY_TXT.is_file()
    return payloads, loaded


def generate_capital_efficiency_hypotheses(
    gii: dict[str, Any] | None,
    *,
    loaded: bool,
) -> list[dict[str, Any]]:
    if not loaded or not gii:
        return []
    hypotheses: list[dict[str, Any]] = []
    tickers = gii.get("tickers") or []
    candidates = [
        t
        for t in tickers
        if _f(t.get("capital_efficiency")) < CAPITAL_EFFICIENCY_THRESHOLD
        and _f(t.get("current_pct")) > 0
        and _s(t.get("recommended_shadow_strategy")) in {"REDUCE_EXPOSURE_SHADOW", "HOLD_AND_MONITOR_SHADOW"}
    ]
    candidates.sort(key=lambda t: (_f(t.get("capital_efficiency")), -_f(t.get("missed_usd"))))
    for idx, row in enumerate(candidates[:5], start=1):
        ticker = _s(row.get("ticker"))
        cap_eff = _f(row.get("capital_efficiency"))
        missed = _f(row.get("missed_usd"))
        hypotheses.append(
            _hypothesis(
                hypothesis_id=f"LTB-CAP-EFF-{ticker}-{idx:02d}",
                hypothesis_type="CAPITAL_EFFICIENCY",
                source_systems=["tae_growth_intelligence.json"],
                evidence_summary=(
                    f"{ticker} capital_efficiency={cap_eff:.1f} with strategy "
                    f"{_s(row.get('recommended_shadow_strategy'))}; missed=${missed:.2f}."
                ),
                affected_tickers=[ticker],
                target_metric="capital_efficiency",
                expected_profit_mechanism=(
                    "PAPER rotation/reduction frees capital from low return/time positions "
                    "for higher-opportunity shadow candidates."
                ),
                risk_level="MEDIUM" if cap_eff < 20 else "LOW",
                confidence=min(0.85, 0.45 + (CAPITAL_EFFICIENCY_THRESHOLD - cap_eff) / 100),
                required_paper_duration=21,
                validation_rule=(
                    "PAPER arm improves portfolio capital_efficiency by >=5% vs control "
                    "without increasing aggregate_missed_usd."
                ),
                rejection_rule=(
                    "Reject if PAPER rotation increases missed_usd or reduces profit_capture_rate "
                    "vs baseline over 21 days."
                ),
                paper_experiment_action="PAPER_ROTATION_REDUCE",
                paper_experiment_description=(
                    f"PAPER-only reduce/rotate exposure on {ticker}; compare capital efficiency "
                    "against hold control."
                ),
                priority_score=(CAPITAL_EFFICIENCY_THRESHOLD - cap_eff) + missed / 50,
            )
        )
    return hypotheses


def generate_profit_protection_hypotheses(
    shadow: dict[str, Any] | None,
    ppg: dict[str, Any] | None,
    *,
    shadow_loaded: bool,
    ppg_loaded: bool,
) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    seen: set[str] = set()

    if shadow_loaded and shadow:
        for row in shadow.get("positions") or []:
            signal = _s(row.get("protection_signal"))
            if signal in {"HOLD", "NONE", "UNKNOWN"}:
                continue
            ticker = _s(row.get("ticker"))
            if ticker in seen:
                continue
            seen.add(ticker)
            missed = _f(row.get("missed_opportunity_usd"))
            if missed < PROTECTION_MIN_MISSED_USD and "PROTECT" not in signal.upper():
                continue
            action = _s(row.get("suggested_shadow_action"))
            hypotheses.append(
                _hypothesis(
                    hypothesis_id=f"LTB-PROT-{ticker}",
                    hypothesis_type="PROFIT_PROTECTION",
                    source_systems=["tae_profit_protection_shadow.json"],
                    evidence_summary=(
                        f"{ticker} protection_signal={signal}, suggested={action}, "
                        f"missed_opportunity=${missed:.2f}."
                    ),
                    affected_tickers=[ticker],
                    target_metric="profit_at_risk_reduction",
                    expected_profit_mechanism=(
                        "PAPER trailing/protect/trim policy reduces giveback from peak profit."
                    ),
                    risk_level="MEDIUM",
                    confidence=min(0.9, 0.5 + missed / 200),
                    required_paper_duration=30,
                    validation_rule=(
                        "PAPER protect/trim arm reduces missed_opportunity_usd by >=15% "
                        "vs hold baseline on matched ticker cohort."
                    ),
                    rejection_rule=(
                        "Reject if protection trims winners before peak capture "
                        "and profit_capture_rate falls vs control."
                    ),
                    paper_experiment_action="PAPER_TRAILING_PROTECT_TRIM",
                    paper_experiment_description=(
                        f"PAPER test {action} on {ticker}; measure giveback reduction."
                    ),
                    priority_score=missed / 10 + (30 if "PROTECT" in signal.upper() else 10),
                )
            )

    if ppg_loaded and ppg:
        for ticker in ppg.get("top_5_risky_tickers") or []:
            sym = _s(ticker if isinstance(ticker, str) else ticker.get("ticker", ticker))
            if sym in seen or sym == "UNKNOWN":
                continue
            seen.add(sym)
            metrics = ppg.get("metrics") or {}
            at_risk = _f(metrics.get("portfolio_profit_at_risk_score"))
            hypotheses.append(
                _hypothesis(
                    hypothesis_id=f"LTB-PROT-PPG-{sym}",
                    hypothesis_type="PROFIT_PROTECTION",
                    source_systems=["tae_portfolio_profit_governor.json"],
                    evidence_summary=(
                        f"{sym} listed in PPG top_5_risky_tickers; portfolio_at_risk={at_risk:.1f}."
                    ),
                    affected_tickers=[sym],
                    target_metric="portfolio_profit_at_risk_score",
                    expected_profit_mechanism=(
                        "PAPER portfolio-level protect posture lowers aggregate profit-at-risk."
                    ),
                    risk_level="HIGH" if at_risk >= 60 else "MEDIUM",
                    confidence=0.6,
                    required_paper_duration=30,
                    validation_rule=(
                        "PAPER protect policy lowers portfolio_profit_at_risk_score by >=10 points "
                        "without net PnL regression."
                    ),
                    rejection_rule=(
                        "Reject if defensive posture increases opportunity_cost_total "
                        "without reducing drawdown."
                    ),
                    paper_experiment_action="PAPER_PORTFOLIO_PROTECT",
                    paper_experiment_description=(
                        f"PAPER apply PPG-driven protect experiment on {sym} cohort."
                    ),
                    priority_score=at_risk,
                )
            )
    return hypotheses[:8]


def generate_opportunity_cost_hypotheses(
    ledger: dict[str, Any] | None,
    gii: dict[str, Any] | None,
    *,
    ledger_loaded: bool,
    gii_loaded: bool,
) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    if ledger_loaded and ledger:
        entries = list(ledger.get("ledger") or [])
    elif gii_loaded and gii:
        entries = [
            {
                "ticker": t.get("ticker"),
                "missed_usd": t.get("missed_usd"),
                "opportunity_cost_category": t.get("opportunity_category"),
                "opportunity_cost_severity": "UNKNOWN",
                "recommended_shadow_fix": t.get("recommended_shadow_strategy"),
            }
            for t in (gii.get("tickers") or [])
        ]

    locked_categories = {"CAPITAL_LOCKED", "CASH_CONSTRAINT", "POSITION_LIMIT_CONSTRAINT"}
    candidates = [
        e
        for e in entries
        if _f(e.get("missed_usd")) >= OPPORTUNITY_COST_MIN_USD
        and (
            _s(e.get("opportunity_cost_category")) in locked_categories
            or _s(e.get("opportunity_cost_severity")) in {"HIGH", "CRITICAL"}
        )
    ]
    candidates.sort(key=lambda e: _f(e.get("missed_usd")), reverse=True)
    for idx, row in enumerate(candidates[:5], start=1):
        ticker = _s(row.get("ticker"))
        missed = _f(row.get("missed_usd"))
        category = _s(row.get("opportunity_cost_category"))
        fix = _s(row.get("recommended_shadow_fix"))
        hypotheses.append(
            _hypothesis(
                hypothesis_id=f"LTB-OPP-{ticker}-{idx:02d}",
                hypothesis_type="OPPORTUNITY_COST",
                source_systems=[
                    "tae_opportunity_cost_ledger.json" if ledger_loaded else "tae_growth_intelligence.json"
                ],
                evidence_summary=(
                    f"{ticker} missed=${missed:.2f} category={category}; shadow_fix={fix}."
                ),
                affected_tickers=[ticker],
                target_metric="opportunity_cost_total",
                expected_profit_mechanism=(
                    "PAPER reallocation unlocks capital locked in low-upside positions "
                    "to capture missed profit opportunities."
                ),
                risk_level="HIGH" if category in locked_categories else "MEDIUM",
                confidence=min(0.88, 0.5 + missed / 300),
                required_paper_duration=30,
                validation_rule=(
                    "PAPER reallocation reduces opportunity_cost_total by >=10% "
                    "vs locked-capital control arm."
                ),
                rejection_rule=(
                    "Reject if reallocation increases churn or realized losses "
                    "without offsetting opportunity gain."
                ),
                paper_experiment_action="PAPER_REALLOCATION",
                paper_experiment_description=(
                    f"PAPER test capital reallocation for {ticker} ({category}) using {fix}."
                ),
                priority_score=missed / 5,
            )
        )
    return hypotheses


def generate_winner_lifecycle_hypotheses(
    lifecycle: dict[str, Any] | None,
    gii: dict[str, Any] | None,
    *,
    lifecycle_loaded: bool,
    gii_loaded: bool,
) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    if lifecycle_loaded and lifecycle:
        profiles = list(lifecycle.get("profiles") or [])
    elif gii_loaded and gii:
        profiles = [
            {
                "ticker": t.get("ticker"),
                "lifecycle_stage": t.get("lifecycle_stage"),
                "optimal_shadow_action": t.get("recommended_shadow_strategy"),
                "lifecycle_score": t.get("lifecycle_score"),
                "missed_usd": t.get("missed_usd"),
                "confidence": t.get("growth_confidence"),
            }
            for t in (gii.get("tickers") or [])
        ]

    actionable = [
        p
        for p in profiles
        if _s(p.get("optimal_shadow_action")) not in {"UNKNOWN", "COLLECT_MORE_DATA", ""}
    ]
    actionable.sort(
        key=lambda p: (_f(p.get("lifecycle_score")), _f(p.get("missed_usd"))),
        reverse=True,
    )
    for idx, row in enumerate(actionable[:5], start=1):
        ticker = _s(row.get("ticker"))
        stage = _s(row.get("lifecycle_stage"))
        action = _s(row.get("optimal_shadow_action"))
        missed = _f(row.get("missed_usd"))
        conf = _f(row.get("confidence"), 0.55)
        hold_longer = any(k in action.upper() for k in ("KEEP", "HOLD", "GROW"))
        hypotheses.append(
            _hypothesis(
                hypothesis_id=f"LTB-LIFE-{ticker}-{idx:02d}",
                hypothesis_type="WINNER_LIFECYCLE",
                source_systems=[
                    "tae_winner_lifecycle_profiler.json"
                    if lifecycle_loaded
                    else "tae_growth_intelligence.json"
                ],
                evidence_summary=(
                    f"{ticker} lifecycle_stage={stage}, optimal_action={action}, missed=${missed:.2f}."
                ),
                affected_tickers=[ticker],
                target_metric="profit_capture_rate",
                expected_profit_mechanism=(
                    "PAPER lifecycle policy holds winners longer or trims later "
                    "to improve capture vs premature exit."
                ),
                risk_level="LOW" if hold_longer else "MEDIUM",
                confidence=min(0.9, conf if conf <= 1 else conf / 100),
                required_paper_duration=30,
                validation_rule=(
                    "PAPER lifecycle arm improves profit_capture_rate on ticker cohort "
                    "without increasing collapse_probability."
                ),
                rejection_rule=(
                    "Reject if lifecycle experiment increases drawdown or missed_usd "
                    "vs hold baseline over 30 days."
                ),
                paper_experiment_action="PAPER_LIFECYCLE_HOLD" if hold_longer else "PAPER_LIFECYCLE_TRIM",
                paper_experiment_description=(
                    f"PAPER test lifecycle action {action} on {ticker} ({stage})."
                ),
                priority_score=_f(row.get("lifecycle_score")) + missed / 20,
            )
        )
    return hypotheses


def generate_dpe_philosophy_hypotheses(
    adaptive: dict[str, Any] | None,
    evaluation: dict[str, Any] | None,
    learning: dict[str, Any] | None,
    *,
    adaptive_loaded: bool,
    evaluation_loaded: bool,
    learning_loaded: bool,
) -> list[dict[str, Any]]:
    if not any((adaptive_loaded, evaluation_loaded, learning_loaded)):
        return []

    preferred = _s((adaptive or {}).get("preferred_philosophy"), "TIE")
    comp_pct = _f((adaptive or {}).get("competitive_pct"), 50.0)
    collab_pct = _f((adaptive or {}).get("collaborative_pct"), 50.0)
    confidence = _f((adaptive or {}).get("confidence"), 50.0) / 100.0

    overall = (evaluation or {}).get("overall") or {}
    winner = _s(overall.get("winner"), preferred)
    reason = _s(overall.get("reason"), (adaptive or {}).get("reason", ""))
    eval_conf = _f(overall.get("confidence_pct"), confidence * 100) / 100.0

    records = (learning or {}).get("records") or []
    summary = (learning or {}).get("summary") or {}
    dominant = _s(summary.get("dominant_philosophy"), preferred)
    record_count = len(records)

    blended_conf = max(confidence, eval_conf, 0.4 if record_count else 0.25)
    next_comp = round(comp_pct + (5 if winner == "COMPETITIVE" else -5 if winner == "COLLABORATIVE" else 0), 1)
    next_collab = round(100.0 - next_comp, 1)

    sources = []
    if adaptive_loaded:
        sources.append("runtime_outputs/dpe/adaptive/adaptive.json")
    if evaluation_loaded:
        sources.append("runtime_outputs/dpe/result_evaluator/evaluation.json")
    if learning_loaded:
        sources.append("runtime_outputs/dpe/learning/learning.json")

    return [
        _hypothesis(
            hypothesis_id="LTB-DPE-PHIL-001",
            hypothesis_type="DPE_PHILOSOPHY",
            source_systems=sources,
            evidence_summary=(
                f"Adaptive prefers {preferred} ({comp_pct}/{collab_pct}); "
                f"evaluation winner={winner}; learning dominant={dominant}; "
                f"records={record_count}. {reason[:180]}"
            ),
            affected_tickers=[],
            target_metric="profit_capture_rate",
            expected_profit_mechanism=(
                f"PAPER dual-arm weighting experiment shifts toward {winner} philosophy "
                f"({next_comp}% competitive / {next_collab}% collaborative)."
            ),
            risk_level="LOW",
            confidence=blended_conf,
            required_paper_duration=30,
            validation_rule=(
                "PAPER weighted arm beats control on profit_capture_rate and capital_efficiency "
                "over 30-day window with confidence >=55%."
            ),
            rejection_rule=(
                "Reject if weighted philosophy underperforms both pure arms "
                "on total_pnl and max_drawdown."
            ),
            paper_experiment_action="PAPER_DPE_PHILOSOPHY_WEIGHT",
            paper_experiment_description=(
                f"PAPER test {next_comp}/{next_collab} competitive/collaborative split; "
                f"baseline adaptive={preferred}."
            ),
            priority_score=50 + blended_conf * 40 + record_count * 2,
        )
    ]


def generate_stale_learning_hypotheses(loaded: dict[str, bool]) -> list[dict[str, Any]]:
    stale: list[tuple[str, Path, float, float]] = []
    for key, (path, max_hours) in FRESHNESS_HOURS.items():
        age = file_age_hours(path)
        is_loaded = path.is_file()
        if not is_loaded:
            stale.append((key, path, max_hours, -1.0))
        elif age is not None and age > max_hours:
            stale.append((key, path, max_hours, age))

    missing = [s for s in stale if s[3] < 0]
    aged = [s for s in stale if s[3] >= 0]
    if not stale:
        return []

    detail_parts = []
    for key, path, max_h, age in stale[:8]:
        if age < 0:
            detail_parts.append(f"{key}: missing ({path.name})")
        else:
            detail_parts.append(f"{key}: {age:.1f}h old (max {max_h}h)")

    regen_cmds = []
    cmd_map = {
        "growth_intelligence": "python3 tae.py growth-intelligence",
        "opportunity_ledger": "python3 tae.py opportunity",
        "winner_lifecycle": "python3 tae.py winner",
        "ppg": "python3 tae.py portfolio-protect",
        "appe": "python3 tae.py policy",
        "profit_protection_shadow": "python3 tae.py protect",
        "dpe_evaluation": "python3 tae.py dpe-evaluator",
        "dpe_learning": "python3 tae.py dpe-learning",
        "dpe_adaptive": "python3 tae.py dpe-adaptive",
    }
    for key, _, _, _ in stale[:5]:
        if key in cmd_map:
            regen_cmds.append(cmd_map[key])

    risk = "HIGH" if len(missing) >= 3 else "MEDIUM" if stale else "LOW"
    return [
        _hypothesis(
            hypothesis_id="LTB-STALE-001",
            hypothesis_type="STALE_LEARNING",
            source_systems=["infrastructure_freshness_audit"],
            evidence_summary="; ".join(detail_parts),
            affected_tickers=[],
            target_metric="decision_freshness",
            expected_profit_mechanism=(
                "Maintenance experiment refreshes stale advisory/learning artifacts "
                "so downstream PAPER experiments use current evidence."
            ),
            risk_level=risk,
            confidence=0.7 if aged else 0.5,
            required_paper_duration=7,
            validation_rule=(
                "All critical SSOT artifacts regenerated within freshness SLA; "
                "learning-profit bridge produces >=3 non-stale hypotheses."
            ),
            rejection_rule=(
                "Reject maintenance cycle if regenerated artifacts fail schema validation "
                "or morning-audit freshness score decreases."
            ),
            paper_experiment_action="PAPER_MAINTENANCE_REFRESH",
            paper_experiment_description=(
                "Run read-only regeneration commands: " + "; ".join(regen_cmds[:5]) or "manual SSOT refresh"
            ),
            priority_score=100 + len(missing) * 15 + len(aged) * 5,
        )
    ]


def generate_confidence_pattern_hypotheses(
    confidence: dict[str, Any] | None,
    replay: dict[str, Any] | None,
    pattern_present: bool,
    *,
    confidence_loaded: bool,
    replay_loaded: bool,
) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    if confidence_loaded and confidence:
        for entry in (confidence.get("confidence_evolution_entries") or [])[:3]:
            hyp_id = _s(entry.get("hypothesis"), "UNKNOWN")
            if hyp_id == "UNKNOWN":
                continue
            rec = _s(entry.get("recommendation"))
            if rec in {"DO_NOT_PROMOTE_TO_LIVE", "INSUFFICIENT_DATA"}:
                continue
            hypotheses.append(
                _hypothesis(
                    hypothesis_id=f"LTB-CONF-{hyp_id[:24]}",
                    hypothesis_type="PROFIT_PROTECTION",
                    source_systems=["tae_confidence_evolution.json"],
                    evidence_summary=_s(entry.get("summary"), f"Confidence evolution for {hyp_id}"),
                    affected_tickers=[],
                    target_metric="confidence_calibration",
                    expected_profit_mechanism=(
                        "PAPER experiment validates confidence-driven shadow recommendation "
                        "before any advisory consideration."
                    ),
                    risk_level="LOW",
                    confidence=min(0.85, _f(entry.get("confidence_after"), 0.5) / 100 if _f(entry.get("confidence_after")) > 1 else _f(entry.get("confidence_after"), 0.5)),
                    required_paper_duration=30,
                    validation_rule=(
                        f"PAPER shadow test confirms {rec} improves outcome metric vs control."
                    ),
                    rejection_rule=(
                        "Reject if confidence hypothesis fails to beat control on replay sample."
                    ),
                    paper_experiment_action="PAPER_CONFIDENCE_SHADOW",
                    paper_experiment_description=f"PAPER test confidence hypothesis {hyp_id}: {rec}",
                    priority_score=40,
                )
            )

    if replay_loaded and replay:
        for rec in (replay.get("recommendations") or [])[:2]:
            text = _s(rec)
            if "PROMOTE" in text.upper() and "NOT" not in text.upper():
                continue
            if "SHADOW" not in text.upper() and "TEST" not in text.upper() and "OBSERVATION" not in text.upper():
                continue
            hypotheses.append(
                _hypothesis(
                    hypothesis_id=f"LTB-REPLAY-{len(hypotheses)+1:02d}",
                    hypothesis_type="PROFIT_PROTECTION",
                    source_systems=["tae_decision_replay.json"],
                    evidence_summary=text[:240],
                    affected_tickers=[],
                    target_metric="decision_replay_cost_reduction",
                    expected_profit_mechanism=(
                        "PAPER experiment replays costly decision mode to quantify improvement."
                    ),
                    risk_level="MEDIUM",
                    confidence=0.55,
                    required_paper_duration=30,
                    validation_rule="PAPER replay arm reduces attributed decision cost vs baseline.",
                    rejection_rule="Reject if replay experiment increases churn without cost reduction.",
                    paper_experiment_action="PAPER_DECISION_REPLAY",
                    paper_experiment_description=f"PAPER replay experiment: {text[:120]}",
                    priority_score=35,
                )
            )

    if pattern_present and not hypotheses:
        hypotheses.append(
            _hypothesis(
                hypothesis_id="LTB-PATTERN-001",
                hypothesis_type="STALE_LEARNING",
                source_systems=["pattern_discovery_summary.txt"],
                evidence_summary="Pattern discovery summary present; convert top patterns to PAPER tests.",
                affected_tickers=[],
                target_metric="pattern_win_rate",
                expected_profit_mechanism=(
                    "PAPER experiment tests highest-confidence pattern discovery finding."
                ),
                risk_level="LOW",
                confidence=0.45,
                required_paper_duration=30,
                validation_rule="PAPER pattern arm beats baseline win rate on holdout sample.",
                rejection_rule="Reject if pattern fails minimum sample or win-rate threshold.",
                paper_experiment_action="PAPER_PATTERN_DISCOVERY",
                paper_experiment_description="PAPER test top pattern from pattern_discovery_summary.txt",
                priority_score=25,
            )
        )
    return hypotheses[:5]


def generate_loss_pattern_hypotheses(
    payloads: dict[str, dict[str, Any] | None],
    loaded: dict[str, bool],
) -> list[dict[str, Any]]:
    """Generalize existing loss evidence by behavior without inventing fills."""
    trade_rows = ((payloads.get("v1_trades") or {}).get("rows") or []) if loaded.get("v1_trades") else []
    execution_rows = (
        ((payloads.get("v1_executions") or {}).get("rows") or [])
        if loaded.get("v1_executions")
        else []
    )
    trade_by_decision = {
        _s(row.get("decision_id"), ""): row
        for row in trade_rows
        if _s(row.get("decision_id"), "")
    }
    events: dict[str, dict[str, Any]] = {}

    for row in [*execution_rows, *trade_rows]:
        reason = _s(row.get("reason"), "").upper()
        if reason not in {"STRATEGY_STOP_V1", "TAKE_PROFIT"}:
            continue
        paired = trade_by_decision.get(_s(row.get("decision_id"), ""), {})
        pnl = _f(row.get("realized_pnl"), _f(paired.get("realized_pnl"), 0.0))
        if pnl >= 0:
            continue
        event_id = _s(
            row.get("decision_id"),
            _s(row.get("execution_id"), f"{reason}:{_s(row.get('ticker'))}:{_s(row.get('ts'))}"),
        )
        events[event_id] = {
            "event_id": event_id,
            "execution_id": row.get("execution_id"),
            "cycle_id": row.get("position_cycle_id") or row.get("cycle_id"),
            "ticker": _s(row.get("ticker"), _s(paired.get("ticker"))),
            "rule": reason,
            "realized_pnl": pnl,
            "timestamp": row.get("ts") or row.get("timestamp"),
        }

    rule_payload = payloads.get("rule_outcome_attribution") or {}
    if loaded.get("rule_outcome_attribution") and isinstance(rule_payload.get("rules"), dict):
        for rule_id, row in rule_payload["rules"].items():
            rule = _s(rule_id, "").upper()
            losses = int(_f((row or {}).get("losses")))
            pnl = _f((row or {}).get("net_pnl_impact"))
            if rule not in {"STRATEGY_STOP_V1", "TAKE_PROFIT"} or losses <= 0 or pnl >= 0:
                continue
            for idx in range(losses):
                events[f"rule-attribution:{rule}:{idx}"] = {
                    "event_id": f"rule-attribution:{rule}:{idx}",
                    "ticker": _s((row or {}).get("last_ticker")),
                    "rule": rule,
                    "realized_pnl": pnl / losses,
                }

    # Causal cases are evidence members, not executions or reconstructed fills.
    causal_cases = (
        ((payloads.get("loss_causal_classification") or {}).get("cases") or [])
        if loaded.get("loss_causal_classification")
        else []
    )
    for case in causal_cases:
        classification = classify_behavior(case)
        if classification["behavior_class"] not in {
            "LATE_ENTRY",
            "LOW_QUALITY_ENTRY",
            "EARLY_STOP",
            "REENTRY_MISSED",
            "CONTEXT_UNKNOWN",
            "VOLATILITY_REVERSAL",
        }:
            continue
        event_id = str(case.get("case_id") or f"causal:{len(events)}")
        events[event_id] = {
            **case,
            "event_id": event_id,
            "rule": case.get("module_associated") or case.get("primary_cause"),
            "realized_pnl": _f(case.get("pnl")),
            "evidence_source": "TAE_LOSS_CAUSAL_CLASSIFICATION.json",
            "is_fill": False,
        }

    by_behavior: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for event in events.values():
        classified = classify_behavior(event)
        if classified["behavior_class"] == "UNKNOWN":
            continue
        rule = _s(event.get("rule"), _s(event.get("primary_cause")))
        by_behavior.setdefault((classified["behavior_class"], rule), []).append(event)

    hypotheses: list[dict[str, Any]] = []
    dedupe: set[tuple[str, str, str, str]] = set()
    for (behavior_class, rule), rule_events in sorted(by_behavior.items()):
        ticker_counts: dict[str, int] = {}
        for event in rule_events:
            ticker = event["ticker"]
            ticker_counts[ticker] = ticker_counts.get(ticker, 0) + 1
        if len(rule_events) < 3 and not any(count >= 2 for count in ticker_counts.values()):
            continue
        tickers = sorted(ticker for ticker in ticker_counts if ticker != "UNKNOWN")
        event_count = len(rule_events)
        total_loss = sum(_f(event.get("realized_pnl")) for event in rule_events)
        aggregate_evidence = {
            "evidence_members": rule_events,
            "evidence_count": event_count,
            "primary_cause": behavior_class,
            "rule": rule,
            "realized_pnl": total_loss,
            "observation_window": {
                "first_seen": min((str(e.get("timestamp")) for e in rule_events if e.get("timestamp")), default=None),
                "last_seen": max((str(e.get("timestamp")) for e in rule_events if e.get("timestamp")), default=None),
            },
        }
        behavior = classify_behavior(aggregate_evidence)
        parent_strategy = "V1"
        cohort_key = behavior_cohort_key(
            behavior["behavior_family"], behavior["behavior_class"], parent_strategy, rule
        )
        if behavior_class == "LOSS_CRYSTALLIZATION":
            changed_parameter, new_value = "stop_policy_review", "DELAYED_STOP_OR_TRAIL_REVIEW"
            hyp_type = "LOSS_PATTERN_STOP_V1"
        elif behavior["behavior_family"] == "EXIT":
            changed_parameter, new_value = "exit_policy_review", "TAKE_PROFIT_THRESHOLD_REVIEW"
            hyp_type = "LOSS_PATTERN_EXIT"
        else:
            changed_parameter, new_value = "entry_policy_review", f"{behavior_class}_ENTRY_REVIEW"
            hyp_type = "LOSS_PATTERN_ENTRY"
        proposed_change = {
            "changed_parameter": changed_parameter,
            "old_value": rule,
            "new_value": new_value,
        }
        observation_hash = stable_hash(behavior["observation_window"])
        dedupe_key = (
            cohort_key,
            parent_strategy,
            stable_hash(proposed_change),
            observation_hash,
        )
        if dedupe_key in dedupe:
            continue
        dedupe.add(dedupe_key)
        if len(tickers) >= 2 and behavior["confidence"] >= 0.55:
            scope = (
                "RULE_LEVEL_HYPOTHESIS"
                if rule == "STRATEGY_STOP_V1"
                else "COHORT_HYPOTHESIS"
            )
        else:
            scope = "TICKER_SPECIFIC_HYPOTHESIS"
        hyp = _hypothesis(
            hypothesis_id=f"LTB-LOSS-{behavior_class.replace('_', '-')}-{stable_hash(cohort_key)[:6].upper()}",
            hypothesis_type=hyp_type,
            source_systems=[
                "learning_attribution",
                "rule_outcome_attribution",
                "parallel_v1_journals",
            ],
            evidence_summary=(
                f"{event_count} {behavior_class} loss observations across {len(tickers)} ticker(s); "
                f"aggregate realized_pnl=${total_loss:.2f}."
            ),
            affected_tickers=tickers,
            target_metric="realized_exit_pnl",
            expected_profit_mechanism=(
                "A one-dimensional PAPER exit-policy challenger tests whether timing changes "
                "reduce repeated realized losses without weakening hard-risk controls."
            ),
            risk_level="HIGH",
            confidence=behavior["confidence"],
            required_paper_duration=30,
            validation_rule=(
                "PAPER challenger improves matched-cohort realized exit PnL with no increase "
                "in maximum accepted loss."
            ),
            rejection_rule=(
                "Reject if delayed/trailing exit increases drawdown, hard-risk breaches, "
                "or matched-cohort realized loss."
            ),
            paper_experiment_action="PAPER_EXIT_POLICY_CHALLENGER",
            paper_experiment_description=(
                f"PAPER-only review of {rule}; vary only {changed_parameter} against control."
            ),
            priority_score=min(90.0, 70.0 + max(0, event_count - 3) * 2.5),
        )
        hyp.update(
            {
                "proposed_change": proposed_change,
                "causal_reasoning": (
                    f"Repeated negative realized PnL is concentrated in the {rule} exit path; "
                    "isolating exit timing tests causality without changing entry or sizing."
                ),
                "expected_effect": "Lower repeated exit losses and improved realized_exit_pnl.",
                "risk": "Delayed exits may deepen losses; retain all hard-risk limits.",
                "event_count": event_count,
                "rule": rule,
                "affected_rule": rule,
                "parent_strategy": parent_strategy,
                "behavior_class": behavior["behavior_class"],
                "behavior_family": behavior["behavior_family"],
                "behavior_cohort_key": cohort_key,
                "generalization_scope": scope,
                "root_cause": behavior["root_cause"],
                "behavior_classification": behavior,
                "affected_events": behavior["source_event_ids"],
                "evidence_members": rule_events,
                "proposed_change_hash": stable_hash(proposed_change),
                "observation_window_hash": observation_hash,
            }
        )
        hypotheses.append(hyp)
    return hypotheses


def generate_attribution_digest_hypotheses(
    payloads: dict[str, dict[str, Any] | None],
    loaded: dict[str, bool],
) -> list[dict[str, Any]]:
    """Extract up to three explicit negative contribution patterns, schema permitting."""
    candidates: list[tuple[str, str, float]] = []
    for source_key in ("learning_attribution", "ablation_summary"):
        if not loaded.get(source_key):
            continue
        payload = payloads.get(source_key) or {}
        if payload.get("sample_sufficient") is False and not payload.get("matured_impact_decisions"):
            continue
        if payload.get("statistically_fragile") is True and not payload.get("matured_attribution_n"):
            continue
        mappings = [
            payload.get("ticker_contributions"),
            (payload.get("robustness") or {}).get("ticker_contributions"),
            payload.get("by_component"),
            payload.get("component_contributions"),
        ]
        for mapping in mappings:
            if not isinstance(mapping, dict):
                continue
            for name, value in mapping.items():
                contribution = _f(
                    value.get("net_attributable_pnl") if isinstance(value, dict) else value
                )
                if contribution < 0:
                    candidates.append((source_key, _s(name), contribution))

    hypotheses: list[dict[str, Any]] = []
    for idx, (source, pattern, contribution) in enumerate(
        sorted(candidates, key=lambda item: item[2])[:3], start=1
    ):
        hypotheses.append(
            _hypothesis(
                hypothesis_id=f"LTB-ATTR-NEG-{idx:02d}",
                hypothesis_type="ATTRIBUTION_NEGATIVE_CONTRIBUTION",
                source_systems=["learning_attribution", source],
                evidence_summary=f"{pattern} has explicit negative contribution {contribution:.4f}.",
                affected_tickers=[pattern] if source == "ablation_summary" else [],
                target_metric="net_attributable_pnl",
                expected_profit_mechanism=(
                    "A PAPER-only single-factor ablation tests whether reducing the negative "
                    "contributor improves net attributable value."
                ),
                risk_level="MEDIUM",
                confidence=0.65,
                required_paper_duration=30,
                validation_rule="PAPER challenger improves net_attributable_pnl vs unchanged control.",
                rejection_rule="Reject if contribution remains negative or drawdown increases.",
                paper_experiment_action="PAPER_ATTRIBUTION_ABLATION",
                paper_experiment_description=f"PAPER isolate negative contributor {pattern}.",
                priority_score=min(85.0, 70.0 + abs(contribution)),
            )
        )
    return hypotheses


def enrich_hypotheses_with_horizon(hypotheses: list[dict[str, Any]]) -> None:
    """Attach existing multi-horizon SSOT context to each hypothesis (read-only)."""
    from tae_paper_decision_engine import build_horizon_context, load_horizon_ssot

    ctx: dict[str, Any] = {
        "horizon_ssot": load_horizon_ssot(),
        "gii_by": {},
        "live_positions": {},
        "top_growth": [],
        "exp_by_ticker": {},
    }
    for hyp in hypotheses:
        tickers = hyp.get("affected_tickers") or []
        ticker = _s(tickers[0]) if tickers else "SPY"
        hz = build_horizon_context(ticker, ctx)
        hyp["horizon_context"] = hz.get("horizon_context")
        hyp["short_term_trend_7d"] = hz.get("short_term_trend_7d")
        hyp["monthly_trend"] = hz.get("monthly_trend")
        hyp["yearly_trend"] = hz.get("yearly_trend")
        hyp["long_term_trend"] = hz.get("long_term_trend")
        hyp["horizon_alignment_score"] = hz.get("horizon_alignment_score")
        hyp["horizon_conflict_flag"] = hz.get("horizon_conflict_flag")
        hyp["horizon_reason"] = hz.get("horizon_reason")
        systems = list(hyp.get("source_systems") or [])
        for src in ("historical_intelligence.csv", "strategic_intelligence_summary.txt", "horizon_vote_summary.txt"):
            if src not in systems:
                systems.append(src)
        hyp["source_systems"] = systems


def enrich_hypotheses_with_experiment_identity(
    hypotheses: list[dict[str, Any]],
) -> None:
    """Attach join/ranking metadata without changing the priority formula."""
    for hyp in hypotheses:
        proposed = hyp.get("proposed_change") or {
            "changed_parameter": (hyp.get("paper_experiment") or {}).get("action"),
            "old_value": "CONTROL",
            "new_value": (hyp.get("paper_experiment") or {}).get("description"),
        }
        single_change = proposed
        parent = hyp.get("parent_strategy") or "V1"
        cohort = hyp.get("behavior_cohort_key") or behavior_cohort_key(
            hyp.get("behavior_family"),
            hyp.get("behavior_class"),
            parent,
            hyp.get("affected_rule") or (hyp.get("paper_experiment") or {}).get("action"),
        )
        config_hash = stable_hash(
            {"paper_experiment": hyp.get("paper_experiment"), "single_change": single_change}
        )
        hyp["parent_strategy"] = parent
        hyp["single_change"] = single_change
        hyp["config_hash"] = config_hash
        hyp["behavior_class"] = hyp.get("behavior_class") or "UNKNOWN"
        hyp["behavior_family"] = hyp.get("behavior_family") or "UNKNOWN"
        hyp["behavior_cohort_key"] = cohort
        hyp["generalization_scope"] = (
            hyp.get("generalization_scope") or "TICKER_SPECIFIC_HYPOTHESIS"
        )
        hyp["affected_rule"] = hyp.get("affected_rule") or proposed.get(
            "changed_parameter"
        )
        hyp["economic_experiment_uid"] = economic_experiment_uid(
            hyp.get("hypothesis_id"), parent, single_change, cohort, config_hash
        )
        hyp["evidence_remaining"] = hyp.get("evidence_remaining") or {
            "status": "NOT_EVALUATED"
        }
        hyp["behavior_recurrence"] = int(
            hyp.get("event_count") or hyp.get("evidence_count") or 0
        )
        hyp["cross_ticker_count"] = len(set(hyp.get("affected_tickers") or []))
        hyp["aggregate_attributed_loss"] = (
            round(
                sum(
                    min(0.0, _f(row.get("realized_pnl") or row.get("pnl")))
                    for row in hyp.get("evidence_members") or []
                    if isinstance(row, dict)
                ),
                6,
            )
            if hyp.get("evidence_members")
            else None
        )
        hyp["remaining_evidence_summary"] = hyp["evidence_remaining"]
        hyp["capital_at_risk"] = None
        hyp["expected_information_gain"] = None
        hyp["RANKING_FORMULA_CHANGED"] = False


def build_bridge_report(
    payloads: dict[str, dict[str, Any] | None],
    loaded: dict[str, bool],
) -> dict[str, Any]:
    hypotheses: list[dict[str, Any]] = []
    hypotheses.extend(
        generate_capital_efficiency_hypotheses(
            payloads.get("growth_intelligence"),
            loaded=loaded.get("growth_intelligence", False),
        )
    )
    hypotheses.extend(
        generate_profit_protection_hypotheses(
            payloads.get("profit_protection_shadow"),
            payloads.get("ppg"),
            shadow_loaded=loaded.get("profit_protection_shadow", False),
            ppg_loaded=loaded.get("ppg", False),
        )
    )
    hypotheses.extend(
        generate_opportunity_cost_hypotheses(
            payloads.get("opportunity_ledger"),
            payloads.get("growth_intelligence"),
            ledger_loaded=loaded.get("opportunity_ledger", False),
            gii_loaded=loaded.get("growth_intelligence", False),
        )
    )
    hypotheses.extend(
        generate_winner_lifecycle_hypotheses(
            payloads.get("winner_lifecycle"),
            payloads.get("growth_intelligence"),
            lifecycle_loaded=loaded.get("winner_lifecycle", False),
            gii_loaded=loaded.get("growth_intelligence", False),
        )
    )
    hypotheses.extend(
        generate_dpe_philosophy_hypotheses(
            payloads.get("dpe_adaptive"),
            payloads.get("dpe_evaluation"),
            payloads.get("dpe_learning"),
            adaptive_loaded=loaded.get("dpe_adaptive", False),
            evaluation_loaded=loaded.get("dpe_evaluation", False),
            learning_loaded=loaded.get("dpe_learning", False),
        )
    )
    hypotheses.extend(generate_stale_learning_hypotheses(loaded))
    hypotheses.extend(
        generate_confidence_pattern_hypotheses(
            payloads.get("confidence_evolution"),
            payloads.get("decision_replay"),
            loaded.get("pattern_discovery", False),
            confidence_loaded=loaded.get("confidence_evolution", False),
            replay_loaded=loaded.get("decision_replay", False),
        )
    )
    hypotheses.extend(generate_loss_pattern_hypotheses(payloads, loaded))
    hypotheses.extend(generate_attribution_digest_hypotheses(payloads, loaded))
    enrich_hypotheses_with_experiment_identity(hypotheses)

    hypotheses.sort(key=lambda h: h.get("priority_score", 0), reverse=True)
    for rank, hyp in enumerate(hypotheses, start=1):
        hyp["rank"] = rank
    enrich_hypotheses_with_horizon(hypotheses)

    by_type: dict[str, int] = {}
    for hyp in hypotheses:
        t = hyp["hypothesis_type"]
        by_type[t] = by_type.get(t, 0) + 1

    sources_loaded = {k: loaded.get(k, False) for k in loaded if k != "pattern_discovery_present"}
    source_count = sum(1 for v in sources_loaded.values() if v)

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": MODE,
        "read_only": True,
        "no_broker": True,
        "no_live_execution": True,
        "live_promotion_allowed": False,
        "RANKING_FORMULA_CHANGED": False,
        "generated_at": _now(),
        "sources_loaded": sources_loaded,
        "sources_loaded_count": source_count,
        "hypothesis_count": len(hypotheses),
        "hypotheses": hypotheses,
        "summary": {
            "by_type": by_type,
            "top_hypothesis_ids": [h["hypothesis_id"] for h in hypotheses[:5]],
            "required_types_present": {
                t: by_type.get(t, 0) > 0
                for t in (
                    "CAPITAL_EFFICIENCY",
                    "PROFIT_PROTECTION",
                    "OPPORTUNITY_COST",
                    "WINNER_LIFECYCLE",
                    "DPE_PHILOSOPHY",
                    "STALE_LEARNING",
                )
            },
        },
        "safety": {
            "mode": MODE,
            "live_promotion_allowed": False,
            "portfolio_csv_modified": False,
            "live_bot_modified": False,
            "execution_enabled": False,
        },
    }


def build_paper_queue(hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
    queue: list[dict[str, Any]] = []
    for hyp in hypotheses:
        queue.append(
            {
                "queue_id": f"PEQ-{hyp['hypothesis_id']}",
                "hypothesis_id": hyp["hypothesis_id"],
                "hypothesis_type": hyp["hypothesis_type"],
                "economic_experiment_uid": hyp.get("economic_experiment_uid"),
                "behavior_class": hyp.get("behavior_class"),
                "behavior_cohort_key": hyp.get("behavior_cohort_key"),
                "generalization_scope": hyp.get("generalization_scope"),
                "affected_rule": hyp.get("affected_rule"),
                "single_change": hyp.get("single_change"),
                "evidence_remaining": hyp.get("evidence_remaining"),
                "behavior_recurrence": hyp.get("behavior_recurrence"),
                "cross_ticker_count": hyp.get("cross_ticker_count"),
                "aggregate_attributed_loss": hyp.get("aggregate_attributed_loss"),
                "remaining_evidence_summary": hyp.get("remaining_evidence_summary"),
                "capital_at_risk": hyp.get("capital_at_risk"),
                "expected_information_gain": hyp.get("expected_information_gain"),
                "RANKING_FORMULA_CHANGED": False,
                "mode": MODE,
                "live_promotion_allowed": False,
                "priority_score": hyp.get("priority_score", 0),
                "rank": hyp.get("rank", 0),
                "paper_experiment_action": hyp["paper_experiment"]["action"],
                "paper_experiment_description": hyp["paper_experiment"]["description"],
                "affected_tickers": hyp.get("affected_tickers") or [],
                "required_paper_duration": hyp.get("required_paper_duration"),
                "validation_rule": hyp.get("validation_rule"),
                "rejection_rule": hyp.get("rejection_rule"),
                "confidence": hyp.get("confidence"),
                "risk_level": hyp.get("risk_level"),
                "status": "QUEUED",
                "created_at": hyp.get("created_at", _now()),
            }
        )
    return queue


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path, Path]:
    assert_safe_output_path(HYPOTHESES_JSON)
    assert_safe_output_path(QUEUE_JSONL)
    assert_safe_output_path(REPORT_MD)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    HYPOTHESES_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    queue = build_paper_queue(report.get("hypotheses") or [])
    with QUEUE_JSONL.open("w", encoding="utf-8") as handle:
        for item in queue:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    summary = report.get("summary") or {}
    by_type = summary.get("by_type") or {}
    lines = [
        "# TAE Learning-to-Profit Bridge Report",
        "",
        f"**Generated:** {report['generated_at']}",
        f"**Mode:** {MODE} — READ_ONLY — NO_BROKER — NO_LIVE_EXECUTION",
        f"**Live promotion allowed:** false",
        "",
        "> **PAPER_ONLY: ranked hypotheses and experiment queue — no trade execution, no live promotion**",
        "",
        "## Executive summary",
        "",
        f"- Hypotheses generated: **{report.get('hypothesis_count', 0)}**",
        f"- Sources loaded: **{report.get('sources_loaded_count', 0)}**",
        f"- Paper queue entries: **{len(queue)}**",
        "",
        "## Hypothesis types",
        "",
    ]
    for hyp_type, count in sorted(by_type.items()):
        lines.append(f"- **{hyp_type}**: {count}")

    lines.extend(["", "## Top ranked PAPER hypotheses", ""])
    for hyp in (report.get("hypotheses") or [])[:10]:
        tickers = ", ".join(hyp.get("affected_tickers") or []) or "(portfolio-level)"
        lines.append(
            f"### {hyp['rank']}. `{hyp['hypothesis_id']}` — {hyp['hypothesis_type']}"
        )
        lines.append("")
        lines.append(f"- **Tickers:** {tickers}")
        lines.append(f"- **Confidence:** {hyp.get('confidence')} | **Risk:** {hyp.get('risk_level')}")
        lines.append(f"- **Target metric:** {hyp.get('target_metric')}")
        lines.append(f"- **Mechanism:** {hyp.get('expected_profit_mechanism')}")
        lines.append(f"- **PAPER action:** `{hyp['paper_experiment']['action']}`")
        lines.append(f"- **Validation:** {hyp.get('validation_rule')}")
        lines.append(f"- **Rejection:** {hyp.get('rejection_rule')}")
        lines.append(f"- **Sources:** {', '.join(hyp.get('source_systems') or [])}")
        lines.append("")

    lines.extend(
        [
            "## Outputs",
            "",
            f"- `{HYPOTHESES_JSON}`",
            f"- `{QUEUE_JSONL}`",
            "",
            "## Safety confirmation",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            f"| PAPER_ONLY | ✅ |",
            f"| NO_BROKER | ✅ |",
            f"| NO_LIVE_EXECUTION | ✅ |",
            f"| live_promotion_allowed | **false** |",
            f"| portfolio.csv modified | **false** |",
            f"| live_bot.py modified | **false** |",
            "",
            "## Required type coverage",
            "",
        ]
    )
    for t, present in (summary.get("required_types_present") or {}).items():
        lines.append(f"- {t}: {'✅' if present else '⚠️ missing'}")

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return HYPOTHESES_JSON, QUEUE_JSONL, REPORT_MD


def print_summary(report: dict[str, Any]) -> None:
    print("===== TAE LEARNING-TO-PROFIT BRIDGE =====")
    print(f"Mode: {MODE} — READ_ONLY — NO_BROKER — no live promotion")
    print("Hypotheses:", report.get("hypothesis_count", 0))
    print("Sources loaded:", report.get("sources_loaded_count", 0))
    top = (report.get("hypotheses") or [])[:3]
    for hyp in top:
        print(f"  #{hyp.get('rank')} {hyp['hypothesis_id']} [{hyp['hypothesis_type']}] score={hyp.get('priority_score')}")


def main() -> int:
    payloads, loaded = load_sources()
    report = build_bridge_report(payloads, loaded)
    paths = write_outputs(report)
    print_summary(report)
    print("Wrote:", *paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
