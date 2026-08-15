#!/usr/bin/env python3
"""Deterministic glue shared by existing TAE self-improvement components."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
LOSS_CAUSAL_PATH = PROJECT_ROOT / "TAE_LOSS_CAUSAL_CLASSIFICATION.json"

BEHAVIOR_FAMILIES = (
    "ENTRY",
    "EXIT",
    "ACCUMULATION",
    "CAPITAL",
    "MARKET_CONTEXT",
    "DATA_EXECUTION",
)
BEHAVIOR_CLASSES = {
    "ENTRY": ("LATE_ENTRY", "LOW_QUALITY_ENTRY", "REENTRY_MISSED"),
    "EXIT": ("EARLY_STOP", "LOSS_CRYSTALLIZATION", "EARLY_PROFIT_EXIT"),
    "ACCUMULATION": ("ACCUMULATION_TIMING",),
    "CAPITAL": ("CAPITAL_UNDERUTILIZATION", "CAPITAL_MISALLOCATION"),
    "MARKET_CONTEXT": ("CONTEXT_UNKNOWN", "VOLATILITY_REVERSAL"),
    "DATA_EXECUTION": ("DATA_GAP", "EXECUTION_DEGRADATION"),
}
CLASSIFICATION_VERSION = "tae.behavior.v1"
CLOSED_CYCLES_REQUIRED = 30
OBSERVATION_DAYS_REQUIRED = 20
try:
    from tae_learning_economic_attribution_engine import MIN_MATURED_IMPACT as SAMPLE_REQUIRED
except Exception:
    SAMPLE_REQUIRED = 8


def _text(evidence: dict[str, Any]) -> str:
    fields = (
        "primary_cause",
        "reason",
        "rule",
        "notes",
        "text",
        "description",
        "causal_reasoning",
    )
    return " | ".join(str(evidence.get(key) or "") for key in fields).upper()


def _values(evidence: dict[str, Any], *keys: str) -> list[str]:
    values: list[str] = []
    members = evidence.get("evidence_members")
    rows = members if isinstance(members, list) else [evidence]
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in keys:
            value = row.get(key)
            if value not in (None, "", "UNKNOWN"):
                values.append(str(value))
    return sorted(set(values))


def classify_behavior(evidence: dict) -> dict:
    """Classify explicit evidence; ticker identity is never a classifier input."""
    evidence = evidence if isinstance(evidence, dict) else {}
    text = _text(evidence)
    family = "UNKNOWN"
    class_ = "UNKNOWN"
    root_cause = str(
        evidence.get("primary_cause")
        or evidence.get("root_cause")
        or evidence.get("reason")
        or evidence.get("rule")
        or "UNKNOWN"
    ).upper()
    why: list[str] = []

    canonical = next(
        (
            (candidate_family, candidate_class)
            for candidate_family, candidates in BEHAVIOR_CLASSES.items()
            for candidate_class in candidates
            if root_cause == candidate_class
        ),
        None,
    )
    if canonical:
        family, class_ = canonical
        why.append("explicit canonical behavior class")
    elif "REENTRY_MISSED" in text:
        family, class_ = "ENTRY", "REENTRY_MISSED"
        why.append("explicit REENTRY_MISSED evidence")
    elif "LATE_ENTRY" in text or "BAD_TIMING" in text:
        family, class_ = "ENTRY", "LATE_ENTRY"
        why.append("explicit LATE_ENTRY/BAD_TIMING evidence")
    elif "BAD_SELECTION" in text or "BAD_ENTRY" in text:
        family, class_ = "ENTRY", "LOW_QUALITY_ENTRY"
        why.append("explicit BAD_SELECTION/BAD_ENTRY evidence")
    elif "STOP_TOO_TIGHT" in text:
        family, class_ = "EXIT", "EARLY_STOP"
        why.append("explicit STOP_TOO_TIGHT evidence")
    elif "STRATEGY_STOP_V1" in text and float(evidence.get("realized_pnl") or 0) < 0:
        family, class_ = "EXIT", "LOSS_CRYSTALLIZATION"
        why.append("negative realized loss crystallized by STRATEGY_STOP_V1")
    elif "TAKE_PROFIT" in text and (
        float(evidence.get("realized_pnl") or 0) < 0
        or "EARLY" in text
        or "NEGATIVE" in text
    ):
        family, class_ = "EXIT", "EARLY_PROFIT_EXIT"
        why.append("early/negative TAKE_PROFIT evidence")
    elif "UNAVOIDABLE_MARKET_MOVE" in text:
        family = "MARKET_CONTEXT"
        class_ = (
            "VOLATILITY_REVERSAL"
            if any(token in text for token in ("VOLATILITY REVERSAL", "VOLATILITY_REVERSAL", "WHIPSAW"))
            else "CONTEXT_UNKNOWN"
        )
        why.append("explicit unavoidable market move evidence")

    event_ids = _values(evidence, "event_id", "case_id", "decision_id")
    cycle_ids = _values(evidence, "cycle_id", "learning_cycle_id", "position_cycle_id")
    execution_ids = _values(evidence, "execution_id")
    rules = _values(evidence, "rule", "reason", "affected_rule")
    tickers = _values(evidence, "ticker")
    count = max(
        int(evidence.get("evidence_count") or 0),
        len(evidence.get("evidence_members") or []) if isinstance(evidence.get("evidence_members"), list) else 0,
        1 if evidence else 0,
    )
    explicit = class_ != "UNKNOWN"
    independent_tickers = len(tickers)
    confidence = 0.0
    if explicit:
        confidence = min(0.9, 0.51 + 0.08 * min(count, 3) + 0.04 * min(independent_tickers, 2))
    why_not = []
    if not explicit:
        why_not.append("no canonical explicit behavior signal")
    if count < 2:
        why_not.append("fewer than two evidence members")
    if independent_tickers < 2:
        why_not.append("not independently observed across two tickers")
    return {
        "behavior_class": class_,
        "behavior_family": family,
        "root_cause": root_cause,
        "confidence": round(confidence, 3),
        "evidence_count": count,
        "source_event_ids": event_ids,
        "source_cycle_ids": cycle_ids,
        "source_execution_ids": execution_ids,
        "source_rules": rules,
        "source_tickers": tickers,
        "observation_window": evidence.get("observation_window") or {
            "first_seen": evidence.get("first_seen"),
            "last_seen": evidence.get("last_seen"),
        },
        "classification_version": CLASSIFICATION_VERSION,
        "why_classified": why,
        "why_unknown": [] if explicit else ["INSUFFICIENT_EXPLICIT_BEHAVIOR_EVIDENCE"],
        "why_not_higher_confidence": why_not,
    }


def behavior_cohort_key(
    family: Any,
    class_: Any,
    parent_strategy: Any,
    policy_or_context: Any,
) -> str:
    values = (family, class_, parent_strategy, policy_or_context)
    return "|".join(str(value or "UNKNOWN").strip().upper() for value in values)


def load_loss_causal_cases(path: Path | None = None) -> list[dict[str, Any]]:
    """Read the existing causal artifact without treating it as fill evidence."""
    try:
        payload = json.loads((path or LOSS_CAUSAL_PATH).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return []
    rows = payload.get("cases") if isinstance(payload, dict) else None
    return [dict(row) for row in (rows or []) if isinstance(row, dict)]


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def economic_experiment_uid(
    hypothesis_id: Any,
    parent_strategy: Any,
    single_change: Any,
    cohort_key: Any,
    config_hash: Any,
) -> str:
    basis = {
        "hypothesis_id": str(hypothesis_id or "UNKNOWN"),
        "parent_strategy": str(parent_strategy or "UNKNOWN"),
        "single_change": single_change,
        "cohort_key": str(cohort_key or "UNKNOWN"),
        "config_hash": str(config_hash or "UNKNOWN"),
    }
    return "EEU-" + stable_hash(basis)[:16]


def _artifact_rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, dict)]
    if not isinstance(value, dict):
        return []
    for key in (
        "rows",
        "items",
        "queue",
        "experiments",
        "hypotheses",
        "cycles",
        "strategies",
        "results",
        "challengers",
    ):
        if isinstance(value.get(key), list):
            return [row for row in value[key] if isinstance(row, dict)]
    return [value] if value else []


def _join_status(anchor: dict[str, Any], artifact: Any) -> str:
    rows = _artifact_rows(artifact)
    if not rows:
        return "MISSING"
    uid = str(anchor.get("economic_experiment_uid") or "")
    hypothesis_id = str(anchor.get("hypothesis_id") or "")
    uid_matches = [
        row for row in rows if uid and str(row.get("economic_experiment_uid") or "") == uid
    ]
    id_matches = [
        row for row in rows if hypothesis_id and str(row.get("hypothesis_id") or "") == hypothesis_id
    ]
    matches = uid_matches or id_matches
    if not matches:
        return "MISSING"
    identities = {
        (
            str(row.get("economic_experiment_uid") or uid),
            str(row.get("hypothesis_id") or hypothesis_id),
        )
        for row in matches
    }
    if len(identities) > 1:
        return "AMBIGUOUS"
    for row in matches:
        row_uid = str(row.get("economic_experiment_uid") or "")
        row_hypothesis = str(row.get("hypothesis_id") or "")
        if uid and row_uid and row_uid != uid:
            return "CONFLICT"
        if hypothesis_id and row_hypothesis and row_hypothesis != hypothesis_id:
            return "CONFLICT"
    return "PASS"


def validate_experiment_joins(artifacts: dict) -> dict:
    """Validate identity joins; historical IDs remain explicit legacy mappings."""
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    anchor = artifacts.get("hypothesis") or artifacts.get("cycle") or artifacts.get("anchor") or {}
    if not isinstance(anchor, dict):
        anchor = {}
    mapping = {
        "ROI_QUEUE_JOINED": ("roi_queue",),
        "LTP_QUEUE_JOINED": ("ltp_queue", "paper_queue"),
        "REPLAY_JOINED": ("replay", "replay_results"),
        "SELF_IMPROVE_JOINED": ("self_improve", "cycles"),
        "CHALLENGER_JOINED": ("challenger", "challengers"),
        "STRATEGY_LAB_JOINED": ("strategy_lab", "experimental_registry"),
    }
    result: dict[str, Any] = {}
    for output, aliases in mapping.items():
        artifact = next((artifacts[key] for key in aliases if key in artifacts), None)
        result[output] = _join_status(anchor, artifact)
    result["LEGACY_ID_MAPPING"] = (
        bool(anchor.get("hypothesis_id"))
        and not bool(anchor.get("economic_experiment_uid"))
    )
    result["activation_blocked"] = any(
        result[key] == "CONFLICT" for key in mapping
    )
    return result


def parse_validation_requirements(validation_rule: str) -> dict:
    raw = str(validation_rule or "")
    parsed: dict[str, Any] = {}
    patterns = {
        "days": r"(?i)\b(?:over|for|within|minimum|at least)?\s*(\d+)\s*(?:calendar\s+)?days?\b",
        "closed_cycles": r"(?i)\b(?:at least|minimum|>=?)?\s*(\d+)\s*closed[\s_-]*cycles?\b",
        "confidence": r"(?i)\bconfidence\s*(?:>=?|of|at least)?\s*(0(?:\.\d+)?|1(?:\.0+)?|\d+(?:\.\d+)?%)",
    }
    spans: list[tuple[int, int]] = []
    for key, pattern in patterns.items():
        match = re.search(pattern, raw)
        if not match:
            continue
        value = match.group(1)
        parsed[key] = (
            float(value.rstrip("%")) / 100.0
            if key == "confidence" and value.endswith("%")
            else float(value)
            if key == "confidence"
            else int(value)
        )
        spans.append(match.span())
    residue = raw
    for start, end in sorted(spans, reverse=True):
        residue = residue[:start] + " " + residue[end:]
    unparsed = residue.strip(" .,;:-")
    if not parsed:
        status = "NONE"
    elif not unparsed:
        status = "COMPLETE"
    else:
        status = "PARTIAL"
    return {
        "validation_rule_raw": raw,
        "validation_requirements_parsed": parsed,
        "unparsed_requirements": [unparsed] if unparsed else [],
        "PARSE_STATUS": status,
    }


def _remaining(observed: Any, required: Any) -> int | str:
    if required in (None, "UNKNOWN"):
        return "UNKNOWN"
    try:
        return max(0, int(required) - int(observed or 0))
    except (TypeError, ValueError):
        return int(required)


def build_remaining_evidence(
    observed: dict,
    requirements: dict | None = None,
) -> dict:
    """Expose exact canonical deficits and explicit unknown, ungated dimensions."""
    observed = observed if isinstance(observed, dict) else {}
    supplied = requirements if isinstance(requirements, dict) else {}
    parsed = supplied.get("validation_requirements_parsed")
    parsed = parsed if isinstance(parsed, dict) else supplied
    required = {
        "events": parsed.get("events", SAMPLE_REQUIRED),
        "cycles": parsed.get("closed_cycles", CLOSED_CYCLES_REQUIRED),
        "days": parsed.get("days", OBSERVATION_DAYS_REQUIRED),
        "outcomes": parsed.get("outcomes", SAMPLE_REQUIRED),
        "earnings": parsed.get("earnings", "UNKNOWN"),
        "recoveries": parsed.get("recoveries", "UNKNOWN"),
        "drawdowns": parsed.get("drawdowns", "UNKNOWN"),
    }
    aliases = {
        "events": ("events", "event_count", "fills"),
        "cycles": ("closed_cycles", "cycles"),
        "days": ("observation_days", "days"),
        "outcomes": ("matured_outcomes", "outcomes", "sample_count"),
        "earnings": ("earnings", "earnings_events"),
        "recoveries": ("recoveries", "recovery_count"),
        "drawdowns": ("drawdowns", "drawdown_count"),
    }
    observed_values: dict[str, Any] = {}
    remaining: dict[str, Any] = {}
    for dimension, keys in aliases.items():
        observed_values[dimension] = next(
            (observed.get(key) for key in keys if observed.get(key) is not None),
            0,
        )
        remaining[dimension] = _remaining(observed_values[dimension], required[dimension])

    codes: list[str] = []
    labels = {
        "events": "EVENTS",
        "cycles": "CLOSED_CYCLES",
        "days": "OBSERVATION_DAYS",
        "outcomes": "MATURED_OUTCOMES",
    }
    for dimension, code in labels.items():
        value = remaining[dimension]
        if isinstance(value, int) and value > 0:
            codes.append(f"NEED_{value}_MORE_{code}")
    for dimension in ("earnings", "recoveries", "drawdowns"):
        if remaining[dimension] == "UNKNOWN":
            codes.append(f"NO_CANONICAL_{dimension.upper()}_GATE")

    if isinstance(remaining["cycles"], int) and remaining["cycles"] > 0:
        wait_status = "WAITING_FOR_CYCLES"
    elif isinstance(remaining["days"], int) and remaining["days"] > 0:
        wait_status = "WAITING_FOR_TIME_WINDOW"
    elif isinstance(remaining["outcomes"], int) and remaining["outcomes"] > 0:
        wait_status = "WAITING_FOR_OUTCOMES"
    elif isinstance(remaining["events"], int) and remaining["events"] > 0:
        wait_status = "WAITING_FOR_EVENTS"
    else:
        wait_status = "READY_FOR_REEVALUATION"

    parts_ro: list[str] = []
    if isinstance(remaining["cycles"], int) and remaining["cycles"] > 0:
        parts_ro.append(f"{remaining['cycles']} cicluri închise")
    if isinstance(remaining["days"], int) and remaining["days"] > 0:
        parts_ro.append(f"{remaining['days']} zile de observație")
    if isinstance(remaining["outcomes"], int) and remaining["outcomes"] > 0:
        parts_ro.append(f"{remaining['outcomes']} rezultate mature")
    if isinstance(remaining["events"], int) and remaining["events"] > 0:
        parts_ro.append(f"{remaining['events']} evenimente")
    explanation = (
        "Mai sunt necesare " + " și ".join(parts_ro) + "."
        if parts_ro
        else "Dovezile canonice sunt suficiente pentru reevaluare."
    )
    evaluation_at_raw = observed.get("evaluation_at") or observed.get("as_of")
    try:
        evaluation_at = datetime.fromisoformat(
            str(evaluation_at_raw).replace("Z", "+00:00")
        ) if evaluation_at_raw else datetime.now(timezone.utc)
    except ValueError:
        evaluation_at = datetime.now(timezone.utc)
    remaining_days = remaining["days"]
    next_at = (
        (evaluation_at + timedelta(days=remaining_days)).isoformat()
        if isinstance(remaining_days, int) and remaining_days > 0
        else None
    )
    return {
        **{f"observed_{key}": value for key, value in observed_values.items()},
        **{f"required_{key}": value for key, value in required.items()},
        **{f"remaining_{key}": value for key, value in remaining.items()},
        "missing_evidence_codes": codes,
        "unknown_gate_reasons": {
            key: "NO_CANONICAL_GATE"
            for key in ("earnings", "recoveries", "drawdowns")
            if required[key] == "UNKNOWN"
        },
        "explanation": explanation,
        "wait_status": wait_status,
        "next_eligible_evaluation_at": next_at,
    }
