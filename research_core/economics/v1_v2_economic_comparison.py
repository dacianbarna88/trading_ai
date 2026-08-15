#!/usr/bin/env python3
"""
Canonical V1 vs V2 economic observability (read-only).

V1 / V2 here are Parallel PAPER profit/loss management arms — NOT DPE
Competitive / Collaborative philosophies.

Definitions (code SSOT):
  V1 exit: tae_strategy_v2_routing.v1_mechanical_exit_action (−3% stop / +5% TP)
  V2 exit: tae_strategy_v2_exit_policy.evaluate_exit_policy (+10% close / −5% critical;
           V1 −3% skipped as STRATEGY_STOP_V1_ONLY)

Entrypoints:
  V1: tae_parallel_paper_runtime._run_v1_arm
  V2: tae_parallel_paper_runtime._run_v2_arm

Economic SSOT paths: runtime_outputs/parallel_paper/{v1,v2}/

PAPER_ONLY | NO_BROKER | NO mutation of portfolios / journals / BUY/SELL.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_parallel_paper_config import load_parallel_paper_config, paths as parallel_paths
from tae_strategy_v2_routing import (
    V1_STOP_LOSS_PCT,
    V1_TAKE_PROFIT_PCT,
    RISK_RULE_INVENTORY,
    v1_mechanical_exit_action,
)

ATTRIBUTION_TOLERANCE_USD = 0.02
MIN_MATCHED_CLOSED_FOR_VERDICT = 1
DPE_CONTAMINATION_TOKENS = frozenset(
    {"COMPETITIVE", "COLLABORATIVE", "DPE_COMPETITIVE", "DPE_COLLABORATIVE"}
)

# Exit reason buckets from real code reason strings (no invented categories).
EXIT_BUCKETS = (
    "stop_loss",
    "take_profit",
    "trailing",
    "profit_lock",
    "hard_risk",
    "independent_risk",
    "manual_or_other",
)

_SNAP_RE = re.compile(
    r"^(?P<prefix>PP-SNAP-[A-F0-9]+)-(?P<ticker>[A-Z0-9.\-]+)-(?P<arm>V1|V2)(?:-(?P<rest>.+))?$",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return float(default)
        out = float(v)
        if math.isnan(out) or math.isinf(out):
            return float(default)
        return out
    except (TypeError, ValueError):
        return float(default)


def _s(v: Any) -> str:
    return str(v or "").strip()


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError:
        return []
    return rows


def canonical_definitions() -> dict[str, Any]:
    """Proven V1/V2 definitions from code (no Competitive/Collaborative)."""
    from tae_strategy_v2_exit_policy import (
        POLICY_VERSION,
        REASON_CLOSE_HR,
        REASON_CLOSE_PROFIT,
        evaluate_exit_policy,
    )

    return {
        "v1": {
            "name": "Parallel PAPER V1",
            "canonical_definition": (
                "V1 mechanical post-entry exit: sell at strategy stop −3% "
                f"({V1_STOP_LOSS_PCT}) or take-profit +5% ({V1_TAKE_PROFIT_PCT}) via "
                "tae_strategy_v2_routing.v1_mechanical_exit_action; live trailing "
                "protection (−3% / activate +5% / trail 3% / lock 2%) lives in "
                "core/trailing.py for LIVE ledger only. Parallel V1 default mode "
                "CANONICAL_PAPER_MIRROR observes canonical PAPER without mutating it."
            ),
            "entrypoint": "tae_parallel_paper_runtime._run_v1_arm",
            "exit_function": "tae_strategy_v2_routing.v1_mechanical_exit_action",
            "economic_ssot": [
                "runtime_outputs/parallel_paper/v1/account.json",
                "runtime_outputs/parallel_paper/v1/accounting_snapshot.json",
                "runtime_outputs/parallel_paper/v1/portfolio.json",
                "runtime_outputs/parallel_paper/v1/canonical_mirror_snapshot.json",
                "runtime_outputs/parallel_paper/v1/journals/decisions.jsonl",
                "runtime_outputs/parallel_paper/v1/journals/executions.jsonl",
                "runtime_outputs/parallel_paper/v1/journals/trades.jsonl",
            ],
            "ownership_markers": ["arm=V1", "strategy_version=V1", "runtime_id=parallel_v1"],
            "is_competitive": False,
            "is_collaborative": False,
            "stop_loss_pct": V1_STOP_LOSS_PCT,
            "take_profit_pct": V1_TAKE_PROFIT_PCT,
            "risk_inventory": RISK_RULE_INVENTORY.get("STRATEGY_STOP_V1"),
        },
        "v2": {
            "name": "Parallel PAPER V2",
            "canonical_definition": (
                "V2 cycle exit policy (exit_policy.v1): does NOT apply V1 −3%/+5% "
                "mechanical stops; CLOSE_CYCLE at +10% vs aggregate average cost "
                f"({REASON_CLOSE_PROFIT}) or CRITICAL hard-risk −5% ({REASON_CLOSE_HR}); "
                "−3% guardian class is STRATEGY_STOP_V1_ONLY and is skipped for V2. "
                "Accumulation via OPEN/ADD tranches (20%, max 5, drop 3%)."
            ),
            "entrypoint": "tae_parallel_paper_runtime._run_v2_arm",
            "exit_function": "tae_strategy_v2_exit_policy.evaluate_exit_policy",
            "policy_version": POLICY_VERSION,
            "exit_callable": evaluate_exit_policy.__name__,
            "economic_ssot": [
                "runtime_outputs/parallel_paper/v2/account.json",
                "runtime_outputs/parallel_paper/v2/accounting_snapshot.json",
                "runtime_outputs/parallel_paper/v2/portfolio.json",
                "runtime_outputs/parallel_paper/v2/cycle_state.json",
                "runtime_outputs/parallel_paper/v2/journals/decisions.jsonl",
                "runtime_outputs/parallel_paper/v2/journals/executions.jsonl",
                "runtime_outputs/parallel_paper/v2/journals/trades.jsonl",
            ],
            "ownership_markers": [
                "arm=V2",
                "strategy_version=V2",
                "strategy_v2_cycle_id / cycle_id=V2CYC-*",
                "runtime_id=parallel_v2",
            ],
            "is_competitive": False,
            "is_collaborative": False,
            "minimum_cycle_profit_pct": 0.10,
            "critical_hard_risk_pct": -5.0,
            "v1_mechanical_stop_applied": False,
        },
        "difference": (
            "After entry, V1 uses mechanical −3% stop / +5% take-profit (or LIVE trailing). "
            "V2 holds through V1-only −3%, accumulates on dips, closes at +10% cycle profit "
            "or −5% critical hard-risk — not DPE Competitive/Collaborative."
        ),
        "v1_is_competitive": False,
        "v2_is_collaborative": False,
    }


def parse_opportunity_key(decision_id: str) -> dict[str, str] | None:
    """Align V1/V2 rows that share PP-SNAP-<hash>-<TICKER>-<arm>."""
    m = _SNAP_RE.match(_s(decision_id))
    if not m:
        return None
    return {
        "opportunity_id": f"{m.group('prefix').upper()}-{m.group('ticker').upper()}",
        "snap_id": m.group("prefix").upper(),
        "ticker": m.group("ticker").upper(),
        "arm": m.group("arm").upper(),
    }


def classify_exit_reason(reason: str) -> str:
    r = _s(reason).upper()
    if not r:
        return "manual_or_other"
    if "TRAIL" in r:
        return "trailing"
    if "PROFIT_LOCK" in r or "LOCKED_PROFIT" in r:
        return "profit_lock"
    if "STOP_LOSS" in r or "STRATEGY_STOP_V1" in r or r.endswith("_STOP"):
        return "stop_loss"
    if "TAKE_PROFIT" in r or "CLOSE_PROFIT" in r or "PROFIT_TARGET" in r:
        return "take_profit"
    if "HARD_RISK" in r or "CRITICAL" in r or "CLOSE_HARD_RISK" in r:
        return "hard_risk"
    if "INDEPENDENT" in r:
        return "independent_risk"
    if "GOVERNANCE" in r or "MANUAL" in r:
        return "manual_or_other"
    if r.startswith("SELL") or "CLOSE" in r:
        return "manual_or_other"
    return "manual_or_other"


def _empty_metrics() -> dict[str, Any]:
    return {
        "capital_base": None,
        "account_value": None,
        "cash": None,
        "invested_capital": None,
        "realized_pnl": None,
        "unrealized_pnl": None,
        "total_pnl": None,
        "net_pnl": None,
        "fees": 0.0,
        "roi_pct": None,
        "daily_return_pct": None,
        "cumulative_return_pct": None,
        "closed_trades": 0,
        "open_trades": 0,
        "winning_trades": 0,
        "losing_trades": 0,
        "win_rate": None,
        "average_winner": None,
        "average_loser": None,
        "largest_winner": None,
        "largest_loser": None,
        "payoff_ratio": None,
        "expectancy": None,
        "profit_factor": None,
        "max_drawdown": None,
        "current_drawdown": None,
        "capital_at_risk": None,
        "maximum_adverse_excursion": None,
        "average_adverse_excursion": None,
        "consecutive_losses": 0,
        "maximum_favorable_excursion": None,
        "profit_capture_ratio": None,
        "profit_given_back_before_exit": None,
        "missed_profit_after_exit": None,
        "average_profit_at_exit": None,
        "trailing_efficiency": None,
        "average_loss_at_exit": None,
        "maximum_loss_before_exit": None,
        "avoided_loss_after_exit": None,
        "stop_efficiency": None,
        "late_stop_count": 0,
        "premature_stop_count": 0,
        "exit_reason_counts": {k: 0 for k in EXIT_BUCKETS},
        "exit_reason_pnl": {k: 0.0 for k in EXIT_BUCKETS},
    }


def _arm_ownership_ok(rows: list[dict[str, Any]], expected_arm: str) -> tuple[bool, list[str]]:
    issues: list[str] = []
    for row in rows:
        arm = _s(row.get("arm")).upper()
        if arm and arm != expected_arm:
            issues.append(f"foreign_arm:{arm}:decision={row.get('decision_id')}")
        for key in ("philosophy", "dpe_arm", "execution_arm", "mode"):
            val = _s(row.get(key)).upper()
            if val in DPE_CONTAMINATION_TOKENS:
                issues.append(f"dpe_contamination:{val}:decision={row.get('decision_id')}")
                break
    return len(issues) == 0, issues


def _duplicate_execution_ids(rows: list[dict[str, Any]]) -> list[str]:
    counts: Counter[str] = Counter()
    for row in rows:
        eid = _s(row.get("execution_id"))
        if eid:
            counts[eid] += 1
    return [eid for eid, n in counts.items() if n > 1]


def _duplicate_execution_id_details(rows: list[dict[str, Any]], arm: str) -> list[dict[str, Any]]:
    """Diagnostic detail for duplicate execution_ids — no journal rewrite."""
    by_eid: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        eid = _s(row.get("execution_id"))
        if not eid:
            continue
        by_eid.setdefault(eid, []).append(row)
    out: list[dict[str, Any]] = []
    for eid, group in sorted(by_eid.items()):
        if len(group) < 2:
            continue
        payloads = []
        timestamps = []
        for row in group:
            payloads.append(
                {
                    "action": _s(row.get("action")).upper(),
                    "ticker": _s(row.get("ticker")).upper(),
                    "pnl": row.get("realized_pnl") if row.get("realized_pnl") is not None else row.get("pnl"),
                    "price": row.get("price") or row.get("exit_price") or row.get("mark_price"),
                    "quantity": row.get("quantity") or row.get("shares"),
                }
            )
            timestamps.append(_s(row.get("ts") or row.get("timestamp") or row.get("exit_timestamp")))
        same_payload = len({json.dumps(p, sort_keys=True, default=str) for p in payloads}) == 1
        ts_nonzero = [t for t in timestamps if t]
        out.append(
            {
                "arm": arm,
                "execution_id": eid,
                "occurrence_count": len(group),
                "first_timestamp": min(ts_nonzero) if ts_nonzero else None,
                "last_timestamp": max(ts_nonzero) if ts_nonzero else None,
                "same_payload_or_conflicting_payload": "same_payload" if same_payload else "conflicting_payload",
            }
        )
    return out


_CLOSE_ACTIONS = {"SELL", "CLOSE", "CLOSE_CYCLE", "SELL_STOP_LOSS", "SELL_TAKE_PROFIT", "SELL_TRAILING"}
_OPEN_ACTIONS = {"BUY", "OPEN", "ADD", "ADD_TRANCHE", "REBUY", "REENTRY"}
_QTY_REL_TOL = 1e-6
_PX_REL_TOL = 1e-4
_PNL_ABS_TOL = ATTRIBUTION_TOLERANCE_USD


def _row_source_journal(row: dict[str, Any], default: str = "unknown") -> str:
    src = _s(row.get("_source_journal") or row.get("source_journal") or default)
    return src or default


def _normalize_action_family(action: str) -> str | None:
    a = _s(action).upper()
    if a in _CLOSE_ACTIONS:
        return "CLOSE"
    if a in _OPEN_ACTIONS:
        return "OPEN"
    if a:
        return a
    return None


def _economic_quantity(row: dict[str, Any]) -> float | None:
    raw = row.get("quantity")
    if raw is None:
        raw = row.get("shares")
    if raw is None:
        return None
    return _f(raw)


def _economic_price(row: dict[str, Any]) -> float | None:
    for key in ("price", "fill_price", "exit_price", "mark_price", "entry_price"):
        if row.get(key) is not None:
            return _f(row.get(key))
    return None


def _economic_pnl(row: dict[str, Any]) -> float | None:
    if row.get("realized_pnl") is not None:
        return _f(row.get("realized_pnl"))
    if row.get("pnl") is not None:
        return _f(row.get("pnl"))
    return None


def _economic_cycle_id(row: dict[str, Any]) -> str:
    return _s(
        row.get("position_cycle_id")
        or row.get("cycle_id")
        or row.get("family_id")
        or row.get("parent_cycle_id")
    )


def _approx_equal(a: float | None, b: float | None, *, abs_tol: float, rel_tol: float = 0.0) -> bool:
    if a is None or b is None:
        return True  # missing on one side is schema variance, not conflict
    if abs(a - b) <= abs_tol:
        return True
    scale = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / scale <= rel_tol


def _rows_economically_equivalent(a: dict[str, Any], b: dict[str, Any]) -> tuple[bool, str | None]:
    """Return (equivalent, conflict_reason). Schema field-name variance is allowed."""
    eid_a = _s(a.get("execution_id"))
    eid_b = _s(b.get("execution_id"))
    if not eid_a or not eid_b:
        return False, "MISSING_EXECUTION_ID"
    if eid_a != eid_b:
        return False, "CONFLICTING_ECONOMIC_PAYLOAD"

    ticker_a = _s(a.get("ticker")).upper()
    ticker_b = _s(b.get("ticker")).upper()
    if ticker_a and ticker_b and ticker_a != ticker_b:
        return False, "CONFLICTING_ECONOMIC_PAYLOAD"

    fam_a = _normalize_action_family(_s(a.get("action")))
    fam_b = _normalize_action_family(_s(b.get("action")))
    if fam_a and fam_b and fam_a != fam_b:
        return False, "CONFLICTING_ECONOMIC_PAYLOAD"

    dec_a = _s(a.get("decision_id"))
    dec_b = _s(b.get("decision_id"))
    if dec_a and dec_b and dec_a != dec_b:
        return False, "CONFLICTING_ECONOMIC_PAYLOAD"

    arm_a = _s(a.get("arm") or a.get("strategy_arm") or a.get("owner")).upper()
    arm_b = _s(b.get("arm") or b.get("strategy_arm") or b.get("owner")).upper()
    if arm_a in {"V1", "V2"} and arm_b in {"V1", "V2"} and arm_a != arm_b:
        return False, "CROSS_ARM_EXECUTION_ID_REUSE"

    cyc_a = _economic_cycle_id(a)
    cyc_b = _economic_cycle_id(b)
    if cyc_a and cyc_b and cyc_a != cyc_b:
        return False, "CONFLICTING_ECONOMIC_PAYLOAD"

    if not _approx_equal(
        _economic_quantity(a),
        _economic_quantity(b),
        abs_tol=1e-6,
        rel_tol=_QTY_REL_TOL,
    ):
        return False, "CONFLICTING_ECONOMIC_PAYLOAD"
    if not _approx_equal(_economic_price(a), _economic_price(b), abs_tol=1e-6, rel_tol=_PX_REL_TOL):
        return False, "CONFLICTING_ECONOMIC_PAYLOAD"
    if not _approx_equal(_economic_pnl(a), _economic_pnl(b), abs_tol=_PNL_ABS_TOL, rel_tol=0.0):
        return False, "CONFLICTING_ECONOMIC_PAYLOAD"
    return True, None


def _prefer_value(*values: Any) -> Any:
    for v in values:
        if v is None:
            continue
        if isinstance(v, str) and not v.strip():
            continue
        return v
    return None


def _merge_equivalent_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic merge: richest non-conflicting economic fields + source_journals."""
    ordered = sorted(
        rows,
        key=lambda r: (
            0 if _row_source_journal(r) == "trades" else 1 if _row_source_journal(r) == "executions" else 2,
            _s(r.get("ts") or r.get("timestamp") or ""),
            json.dumps(r, sort_keys=True, default=str),
        ),
    )
    base = dict(ordered[0])
    sources = sorted({_row_source_journal(r) for r in ordered})
    qty = _prefer_value(*(_economic_quantity(r) for r in ordered))
    px = _prefer_value(*(_economic_price(r) for r in ordered))
    pnl = _prefer_value(*(_economic_pnl(r) for r in ordered))
    action = _prefer_value(*(_s(r.get("action")).upper() for r in ordered))
    # Prefer CLOSE family canonical label from first non-empty CLOSE action, else first action.
    close_actions = [_s(r.get("action")).upper() for r in ordered if _normalize_action_family(_s(r.get("action"))) == "CLOSE"]
    if close_actions:
        # Deterministic preference: CLOSE < SELL < others
        pref = {"CLOSE": 0, "CLOSE_CYCLE": 1, "SELL": 2, "SELL_TRAILING": 3, "SELL_TAKE_PROFIT": 4, "SELL_STOP_LOSS": 5}
        action = sorted(close_actions, key=lambda a: (pref.get(a, 99), a))[0]
    base.update(
        {
            "execution_id": _s(ordered[0].get("execution_id")),
            "decision_id": _prefer_value(*(_s(r.get("decision_id")) for r in ordered)),
            "ticker": _prefer_value(*(_s(r.get("ticker")).upper() for r in ordered)),
            "action": action,
            "quantity": qty,
            "shares": qty,
            "price": px,
            "fill_price": px,
            "exit_price": px if _normalize_action_family(action or "") == "CLOSE" else ordered[0].get("exit_price"),
            "realized_pnl": pnl,
            "pnl": pnl,
            "arm": _prefer_value(*(_s(r.get("arm")).upper() for r in ordered)),
            "strategy_arm": _prefer_value(*(_s(r.get("strategy_arm") or r.get("arm")).upper() for r in ordered)),
            "owner": _prefer_value(*(r.get("owner") for r in ordered)),
            "position_cycle_id": _prefer_value(*(_economic_cycle_id(r) for r in ordered)) or None,
            "ts": _prefer_value(*(_s(r.get("ts") or r.get("timestamp") or r.get("exit_timestamp")) for r in ordered)),
            "fees": _prefer_value(*(_f(r.get("fees")) if r.get("fees") is not None else None for r in ordered)),
            "reason": _prefer_value(
                *(_s(r.get("reason") or r.get("reason_code") or r.get("close_reason")) for r in ordered)
            ),
            "source_journals": sources,
            "dedupe_class": "DUAL_JOURNAL_EQUIVALENT" if len(sources) > 1 else "SINGLE_SOURCE",
        }
    )
    return base


def _tag_journal_rows(rows: list[dict[str, Any]], journal: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        tagged = dict(row)
        tagged["_source_journal"] = journal
        out.append(tagged)
    return out


def _classify_arm_execution_ids(
    *,
    arm: str,
    executions: list[dict[str, Any]],
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    """Classify same-arm execution_id duplicates (no journal rewrite)."""
    exec_rows = _tag_journal_rows(executions, "executions")
    trade_rows = _tag_journal_rows(trades, "trades")
    within_exec = _duplicate_execution_ids(exec_rows)
    within_trade = _duplicate_execution_ids(trade_rows)

    by_eid: dict[str, list[dict[str, Any]]] = {}
    for row in exec_rows + trade_rows:
        eid = _s(row.get("execution_id"))
        if not eid:
            continue
        by_eid.setdefault(eid, []).append(row)

    dual_equivalent: list[str] = []
    conflicting: list[dict[str, Any]] = []
    unresolved: list[str] = []
    for eid, group in sorted(by_eid.items()):
        if len(group) < 2:
            continue
        journals = {_row_source_journal(r) for r in group}
        if "executions" in journals and len([r for r in group if _row_source_journal(r) == "executions"]) > 1:
            conflicting.append(
                {"arm": arm, "execution_id": eid, "class": "SAME_JOURNAL_DUPLICATE", "journal": "executions"}
            )
            continue
        if "trades" in journals and len([r for r in group if _row_source_journal(r) == "trades"]) > 1:
            conflicting.append(
                {"arm": arm, "execution_id": eid, "class": "SAME_JOURNAL_DUPLICATE", "journal": "trades"}
            )
            continue
        if journals == {"executions", "trades"} and len(group) == 2:
            ok, reason = _rows_economically_equivalent(group[0], group[1])
            if ok:
                dual_equivalent.append(eid)
            else:
                conflicting.append(
                    {
                        "arm": arm,
                        "execution_id": eid,
                        "class": reason or "CONFLICTING_ECONOMIC_PAYLOAD",
                        "journals": sorted(journals),
                    }
                )
            continue
        # >2 rows or unexpected journal mix
        all_ok = True
        reason_code = None
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ok, reason = _rows_economically_equivalent(group[i], group[j])
                if not ok:
                    all_ok = False
                    reason_code = reason
                    break
            if not all_ok:
                break
        if all_ok and journals == {"executions", "trades"}:
            dual_equivalent.append(eid)
        elif not all_ok:
            conflicting.append(
                {
                    "arm": arm,
                    "execution_id": eid,
                    "class": reason_code or "UNRESOLVED_DUPLICATE",
                    "journals": sorted(journals),
                    "occurrence_count": len(group),
                }
            )
        else:
            unresolved.append(eid)

    integrity_fail = bool(within_exec or within_trade or conflicting or unresolved)
    return {
        "arm": arm,
        "WITHIN_EXECUTIONS_JOURNAL_DUPLICATES": len(within_exec),
        "WITHIN_TRADES_JOURNAL_DUPLICATES": len(within_trade),
        "within_executions_ids": within_exec,
        "within_trades_ids": within_trade,
        "DUAL_JOURNAL_EQUIVALENT_IDS": dual_equivalent,
        "CONFLICTING_EXECUTION_IDS": conflicting,
        "UNRESOLVED_DUPLICATE_IDS": unresolved,
        "EXECUTION_ID_INTEGRITY": "FAIL" if integrity_fail else "PASS",
        "DUAL_JOURNAL_RECORDING": "EXPECTED" if dual_equivalent and not integrity_fail else (
            "PRESENT" if dual_equivalent else "NONE"
        ),
    }


def _closed_trade_pnls(trades: list[dict[str, Any]], executions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build closed-trade economics with dual-journal economic dedupe by execution_id."""
    tagged = _tag_journal_rows(trades, "trades") + _tag_journal_rows(executions, "executions")
    candidates: list[dict[str, Any]] = []
    for row in tagged:
        action = _s(row.get("action")).upper()
        if action not in _CLOSE_ACTIONS:
            continue
        pnl = _economic_pnl(row)
        if pnl is None:
            shares = _f(row.get("shares") or row.get("quantity"))
            price = _f(row.get("price") or row.get("exit_price") or row.get("mark_price"))
            avg = _f(row.get("avg_price") or row.get("entry_price") or row.get("average_cost"))
            if shares and price and avg:
                pnl = shares * (price - avg)
        reason = _s(row.get("reason") or row.get("reason_code") or row.get("close_reason"))
        candidates.append(
            {
                **row,
                "ticker": _s(row.get("ticker")).upper(),
                "ts": row.get("ts") or row.get("timestamp") or row.get("exit_timestamp"),
                "action": action,
                "pnl": None if pnl is None else _f(pnl),
                "realized_pnl": None if pnl is None else _f(pnl),
                "fees": _f(row.get("fees")),
                "exit_reason": reason,
                "exit_bucket": classify_exit_reason(reason),
                "decision_id": row.get("decision_id"),
                "execution_id": row.get("execution_id"),
                "entry_price": row.get("entry_price") or row.get("avg_price") or row.get("average_cost"),
                "exit_price": row.get("exit_price") or row.get("price") or row.get("mark_price") or row.get("fill_price"),
                "quantity": _economic_quantity(row),
                "shares": _economic_quantity(row),
                "arm": _s(row.get("arm")).upper(),
                "_source_journal": _row_source_journal(row),
            }
        )

    by_eid: dict[str, list[dict[str, Any]]] = {}
    no_eid: list[dict[str, Any]] = []
    for row in candidates:
        eid = _s(row.get("execution_id"))
        if not eid:
            tagged_row = dict(row)
            tagged_row["dedupe_class"] = "MISSING_EXECUTION_ID"
            tagged_row["source_journals"] = [_row_source_journal(row)]
            no_eid.append(tagged_row)
            continue
        by_eid.setdefault(eid, []).append(row)

    out: list[dict[str, Any]] = []
    for eid in sorted(by_eid):
        group = by_eid[eid]
        if len(group) == 1:
            row = dict(group[0])
            row["source_journals"] = [_row_source_journal(group[0])]
            row["dedupe_class"] = "SINGLE_SOURCE"
            out.append(row)
            continue
        # Attempt pairwise economic equivalence; if any conflict, keep all rows marked.
        conflict = False
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ok, _reason = _rows_economically_equivalent(group[i], group[j])
                if not ok:
                    conflict = True
                    break
            if conflict:
                break
        if conflict:
            for row in group:
                r = dict(row)
                r["source_journals"] = [_row_source_journal(row)]
                r["dedupe_class"] = "CONFLICTING_ECONOMIC_PAYLOAD"
                out.append(r)
            continue
        merged = _merge_equivalent_rows(group)
        reason = _s(merged.get("reason") or merged.get("exit_reason"))
        out.append(
            {
                "ticker": _s(merged.get("ticker")).upper(),
                "ts": merged.get("ts"),
                "action": _s(merged.get("action")).upper(),
                "pnl": None if merged.get("realized_pnl") is None else _f(merged.get("realized_pnl")),
                "fees": _f(merged.get("fees")),
                "exit_reason": reason,
                "exit_bucket": classify_exit_reason(reason),
                "decision_id": merged.get("decision_id"),
                "execution_id": merged.get("execution_id"),
                "entry_price": merged.get("entry_price"),
                "exit_price": merged.get("exit_price") or merged.get("price"),
                "quantity": merged.get("quantity"),
                "shares": merged.get("shares"),
                "arm": _s(merged.get("arm")).upper(),
                "source_journals": list(merged.get("source_journals") or []),
                "dedupe_class": "DUAL_JOURNAL_EQUIVALENT",
                "position_cycle_id": merged.get("position_cycle_id"),
            }
        )

    out.extend(no_eid)
    out.sort(key=lambda r: (_s(r.get("ts")), _s(r.get("execution_id")), _s(r.get("ticker"))))
    return out


def _noncomparability_reason(a: dict[str, Any], b: dict[str, Any]) -> str:
    """Explicit reason codes for identity-matched but economically non-comparable pairs."""
    v1_val = a.get("value")
    v2_val = b.get("value")
    q1 = _f(a.get("quantity"))
    q2 = _f(b.get("quantity"))
    if v1_val is None or v2_val is None or _f(v1_val) <= 0 or _f(v2_val) <= 0:
        return "MISSING_ENTRY_NOTIONAL"
    if q1 > 0 and q2 > 0:
        ratio = max(q1, q2) / max(min(q1, q2), 1e-9)
        if ratio >= 2.0:
            return "ENTRY_QUANTITY_NOT_COMPARABLE"
    # Structural full-vs-tranche / unequal notional with shared identity.
    if abs(_f(v1_val) - _f(v2_val)) > max(1.0, 0.05 * max(_f(v1_val), _f(v2_val), 1.0)):
        return "STRUCTURAL_SIZING_DIFFERENCE"
    return "CAPITAL_BASIS_DIFFERENCE"


def _trade_quality(closed: list[dict[str, Any]], metrics: dict[str, Any]) -> None:
    pnls = [c["pnl"] for c in closed if c.get("pnl") is not None]
    metrics["closed_trades"] = len(closed)
    if not pnls:
        return
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    metrics["winning_trades"] = len(wins)
    metrics["losing_trades"] = len(losses)
    metrics["win_rate"] = (len(wins) / len(pnls)) if pnls else None
    metrics["average_winner"] = (sum(wins) / len(wins)) if wins else None
    metrics["average_loser"] = (sum(losses) / len(losses)) if losses else None
    metrics["largest_winner"] = max(wins) if wins else None
    metrics["largest_loser"] = min(losses) if losses else None
    avg_w = metrics["average_winner"] or 0.0
    avg_l = abs(metrics["average_loser"] or 0.0)
    metrics["payoff_ratio"] = (avg_w / avg_l) if avg_l > 0 else None
    metrics["expectancy"] = sum(pnls) / len(pnls)
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    metrics["profit_factor"] = (gross_win / gross_loss) if gross_loss > 0 else (None if not wins else float("inf"))
    # consecutive losses
    streak = 0
    max_streak = 0
    for p in pnls:
        if p < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    metrics["consecutive_losses"] = max_streak
    for c in closed:
        bucket = c.get("exit_bucket") or "manual_or_other"
        metrics["exit_reason_counts"][bucket] = int(metrics["exit_reason_counts"].get(bucket, 0)) + 1
        if c.get("pnl") is not None:
            metrics["exit_reason_pnl"][bucket] = _f(metrics["exit_reason_pnl"].get(bucket)) + _f(c["pnl"])
    # MFE/MAE / capture — only when explicit fields present (do not invent)
    mfe_vals = [_f(c.get("mfe")) for c in closed if c.get("mfe") is not None]
    mae_vals = [_f(c.get("mae")) for c in closed if c.get("mae") is not None]
    if mfe_vals:
        metrics["maximum_favorable_excursion"] = max(mfe_vals)
    if mae_vals:
        metrics["maximum_adverse_excursion"] = min(mae_vals)
        metrics["average_adverse_excursion"] = sum(mae_vals) / len(mae_vals)
    capture = []
    for c in closed:
        if c.get("mfe") is not None and _f(c.get("mfe")) > 0 and c.get("pnl") is not None:
            capture.append(_f(c["pnl"]) / _f(c["mfe"]))
    if capture:
        metrics["profit_capture_ratio"] = sum(capture) / len(capture)
    givebacks = [_f(c.get("profit_given_back")) for c in closed if c.get("profit_given_back") is not None]
    missed = [_f(c.get("missed_profit_after_exit")) for c in closed if c.get("missed_profit_after_exit") is not None]
    avoided = [_f(c.get("avoided_loss_after_exit")) for c in closed if c.get("avoided_loss_after_exit") is not None]
    if givebacks:
        metrics["profit_given_back_before_exit"] = sum(givebacks)
    if missed:
        metrics["missed_profit_after_exit"] = sum(missed)
    if avoided:
        metrics["avoided_loss_after_exit"] = sum(avoided)
    pos_exits = [c["pnl"] for c in closed if c.get("pnl") is not None and c["pnl"] > 0]
    neg_exits = [c["pnl"] for c in closed if c.get("pnl") is not None and c["pnl"] < 0]
    if pos_exits:
        metrics["average_profit_at_exit"] = sum(pos_exits) / len(pos_exits)
    if neg_exits:
        metrics["average_loss_at_exit"] = sum(neg_exits) / len(neg_exits)
        metrics["maximum_loss_before_exit"] = min(neg_exits)


def _load_arm_state(arm: str, p: dict[str, Path], cfg: dict[str, Any]) -> dict[str, Any]:
    arm_u = arm.upper()
    key = arm.lower()
    account = _read_json(p[f"{key}_account"])
    accounting = _read_json(p[f"{key}_accounting"])
    portfolio = _read_json(p[f"{key}_portfolio"])
    if arm_u == "V1" and not portfolio:
        portfolio = _read_json(p.get("v1_mirror_snapshot", Path()))
    decisions = _read_jsonl(p[f"{key}_decisions"])
    executions = _read_jsonl(p[f"{key}_executions"])
    trades = _read_jsonl(p[f"{key}_trades"])
    cycles = _read_json(p["v2_cycles"]) if arm_u == "V2" else {}

    own_ok, own_issues = _arm_ownership_ok(decisions + executions + trades, arm_u)
    eid_diag = _classify_arm_execution_ids(arm=arm_u, executions=executions, trades=trades)
    # Legacy list retained for tests: only integrity-failing ids (not dual-journal equivalent).
    conflicting_ids = [
        str(c.get("execution_id"))
        for c in (eid_diag.get("CONFLICTING_EXECUTION_IDS") or [])
        if c.get("execution_id")
    ]
    conflicting_ids.extend(eid_diag.get("within_executions_ids") or [])
    conflicting_ids.extend(eid_diag.get("within_trades_ids") or [])
    conflicting_ids.extend(eid_diag.get("UNRESOLVED_DUPLICATE_IDS") or [])
    dup_eids = sorted(set(conflicting_ids))
    dup_details = _duplicate_execution_id_details(executions + trades, arm_u)

    # Reject rows without arm when journal claims arm (trades may omit arm — require path ownership)
    path_ok = f"/parallel_paper/{key}/" in str(p[f"{key}_account"]).replace("\\", "/")

    # ownership_ok = state/path isolation only — duplicate IDs are reported separately.
    state_ownership_ok = bool(own_ok and path_ok)
    integrity_fail = eid_diag.get("EXECUTION_ID_INTEGRITY") == "FAIL"

    metrics = _empty_metrics()
    src = account or accounting or {}
    start = _f(
        src.get("starting_value")
        or src.get("starting_capital")
        or portfolio.get("starting_capital")
        or portfolio.get("starting_value")
        or (cfg.get("V1_STARTING_CAPITAL") if arm_u == "V1" else cfg.get("V2_STARTING_CAPITAL")),
    )
    av = _f(src.get("account_value") or portfolio.get("account_value") or portfolio.get("total_value"))
    cash = _f(src.get("cash") or portfolio.get("cash"))
    invested = _f(src.get("invested") or portfolio.get("invested"))
    if invested <= 0 and portfolio.get("positions"):
        invested = sum(
            _f(pos.get("shares")) * _f(pos.get("avg_price"))
            for pos in (portfolio.get("positions") or {}).values()
        )
    realized = _f(src.get("realized_pnl") or portfolio.get("realized_pnl"))
    unrealized = _f(src.get("unrealized_pnl") or portfolio.get("unrealized_pnl"))
    if "total_pnl" in src and src.get("total_pnl") is not None:
        total = _f(src.get("total_pnl"))
    else:
        total = realized + unrealized
    fees = _f(src.get("fees") or portfolio.get("fees"))
    net = total - fees

    metrics.update(
        {
            "capital_base": start,
            "account_value": av if (account or accounting or portfolio) else None,
            "cash": cash if (account or accounting or portfolio) else None,
            "invested_capital": invested,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": total,
            "net_pnl": net,
            "fees": fees,
            "roi_pct": ((total / start) * 100.0) if start else None,
            "cumulative_return_pct": ((total / start) * 100.0) if start else None,
            "open_trades": len(portfolio.get("positions") or {})
            if isinstance(portfolio.get("positions"), dict)
            else 0,
            "capital_at_risk": invested,
            "current_drawdown": min(0.0, total) if start else None,
            "max_drawdown": min(0.0, total) if start else None,  # path DD not persisted → use cumulative floor
        }
    )

    closed = _closed_trade_pnls(trades, executions)
    # Tag arm from path if missing
    for c in closed:
        if not c.get("arm"):
            c["arm"] = arm_u
    _trade_quality(closed, metrics)
    metrics["TRADE_QUALITY_METRICS_DEDUPED"] = True
    metrics["deduplicated_closed_trades"] = len(closed)
    metrics["dual_journal_equivalent_closed"] = sum(
        1 for c in closed if c.get("dedupe_class") == "DUAL_JOURNAL_EQUIVALENT"
    )

    open_cycles = 0
    if arm_u == "V2" and isinstance(cycles.get("cycles"), dict):
        open_cycles = sum(
            1
            for c in cycles["cycles"].values()
            if _s(c.get("status")).upper() not in {"CLOSED", "BLOCKED"}
        )
        metrics["open_trades"] = max(metrics["open_trades"], open_cycles)

    return {
        "arm": arm_u,
        "account": account,
        "accounting": accounting,
        "portfolio": portfolio,
        "decisions": decisions,
        "executions": executions,
        "trades": trades,
        "cycles": cycles,
        "metrics": metrics,
        "closed_trades": closed,
        # Dual-journal equivalent does not flip ownership_ok; real integrity failures still do.
        "ownership_ok": bool(state_ownership_ok and not integrity_fail),
        "state_ownership_ok": state_ownership_ok,
        "ownership_issues": own_issues,
        "duplicate_execution_ids": dup_eids,
        "duplicate_execution_id_details": dup_details,
        "execution_id_diagnostics": eid_diag,
        "path_ok": path_ok,
        "v1_mode": _s(src.get("V1_MODE") or portfolio.get("v1_mode") or cfg.get("V1_MODE")),
        "source": _s(src.get("source") or portfolio.get("source")),
    }


def _match_opportunities(
    v1: dict[str, Any],
    v2: dict[str, Any],
) -> dict[str, Any]:
    """Like-for-like alignment by shared PP-SNAP opportunity id."""

    def _entry_events(arm_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for row in arm_state["decisions"] + arm_state["executions"] + arm_state["trades"]:
            action = _s(row.get("action")).upper()
            if action not in {"BUY", "OPEN", "ADD"}:
                continue
            parsed = parse_opportunity_key(_s(row.get("decision_id")))
            if not parsed:
                # fallback: ticker + entry ts
                ticker = _s(row.get("ticker")).upper()
                ts = _s(row.get("ts") or row.get("timestamp"))[:19]
                if not ticker or not ts:
                    continue
                oid = f"TS-{ticker}-{ts}"
            else:
                oid = parsed["opportunity_id"]
            prev = out.get(oid)
            if prev is None or action in {"BUY", "OPEN"}:
                out[oid] = {
                    "opportunity_id": oid,
                    "ticker": _s(row.get("ticker")).upper(),
                    "entry_timestamp": row.get("ts") or row.get("timestamp"),
                    "entry_price": _f(row.get("mark_price") or row.get("price") or row.get("entry_price")),
                    "quantity": _f(row.get("quantity") or row.get("shares")),
                    "value": _f(row.get("value")),
                    "decision_id": row.get("decision_id"),
                    "execution_id": row.get("execution_id"),
                    "action": action,
                    "arm": arm_state["arm"],
                }
        return out

    def _exit_by_ticker(arm_state: dict[str, Any]) -> dict[str, dict[str, Any]]:
        by_t: dict[str, dict[str, Any]] = {}
        for c in arm_state["closed_trades"]:
            t = _s(c.get("ticker")).upper()
            if t:
                by_t[t] = c
        return by_t

    e1 = _entry_events(v1)
    e2 = _entry_events(v2)
    x1 = _exit_by_ticker(v1)
    x2 = _exit_by_ticker(v2)

    matched: list[dict[str, Any]] = []
    identity_matched_not_comparable: list[dict[str, Any]] = []
    v1_only: list[dict[str, Any]] = []
    v2_only: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []

    all_ids = sorted(set(e1) | set(e2))
    for oid in all_ids:
        a = e1.get(oid)
        b = e2.get(oid)
        if a and not b:
            v1_only.append(a)
            continue
        if b and not a:
            v2_only.append(b)
            continue
        assert a and b
        same_ticker = a["ticker"] == b["ticker"]
        same_entry_px = abs(a["entry_price"] - b["entry_price"]) <= 1e-6 or (
            a["entry_price"] > 0 and b["entry_price"] > 0 and abs(a["entry_price"] - b["entry_price"]) / a["entry_price"] < 1e-4
        )
        # Comparable capital: same methodology requires similar notional OR documented tranche vs full —
        # user requires same capital for primary winner; flag unequal notionals as ambiguous.
        capital_comparable = abs(a["value"] - b["value"]) <= max(1.0, 0.05 * max(a["value"], b["value"], 1.0))
        if not (same_ticker and same_entry_px):
            unmatched.append({"opportunity_id": oid, "v1": a, "v2": b, "reason": "ticker_or_entry_price_mismatch"})
            continue
        if not capital_comparable:
            reason_code = _noncomparability_reason(a, b)
            identity_matched_not_comparable.append(
                {
                    "opportunity_id": oid,
                    "identity_matched": True,
                    "economically_comparable": False,
                    "reason": "entry_notional_not_comparable",
                    "reason_code": reason_code,
                    "v1_value": a["value"],
                    "v2_value": b["value"],
                    "v1_quantity": a.get("quantity"),
                    "v2_quantity": b.get("quantity"),
                    "v1": a,
                    "v2": b,
                }
            )
            # Keep legacy unmatched list for older consumers, with explicit identity flag.
            unmatched.append(
                {
                    "opportunity_id": oid,
                    "v1": a,
                    "v2": b,
                    "reason": "entry_notional_not_comparable",
                    "reason_code": reason_code,
                    "identity_matched": True,
                    "economically_comparable": False,
                    "v1_value": a["value"],
                    "v2_value": b["value"],
                }
            )
            continue

        t = a["ticker"]
        ex1 = x1.get(t)
        ex2 = x2.get(t)
        v1_pnl = ex1.get("pnl") if ex1 else None
        v2_pnl = ex2.get("pnl") if ex2 else None
        # Open MTM if still open and mark present on portfolios
        if v1_pnl is None:
            pos = (v1.get("portfolio") or {}).get("positions") or {}
            p = pos.get(t) or {}
            if _f(p.get("shares")) > 0:
                v1_pnl = _f(p.get("shares")) * (_f(p.get("current_price")) - _f(p.get("avg_price")))
        if v2_pnl is None:
            pos = (v2.get("portfolio") or {}).get("positions") or {}
            p = pos.get(t) or {}
            if _f(p.get("shares")) > 0:
                v2_pnl = _f(p.get("shares")) * (_f(p.get("current_price")) - _f(p.get("avg_price")))

        diff = None
        winner = "TIE"
        if v1_pnl is not None and v2_pnl is not None:
            diff = _f(v2_pnl) - _f(v1_pnl)
            if abs(diff) < ATTRIBUTION_TOLERANCE_USD:
                winner = "TIE"
            elif diff > 0:
                winner = "V2"
            else:
                winner = "V1"

        closed_both = bool(ex1) and bool(ex2)
        matched.append(
            {
                "opportunity_id": oid,
                "ticker": t,
                "entry_timestamp": a.get("entry_timestamp"),
                "entry_price": a.get("entry_price"),
                "v1_entry_value": a.get("value"),
                "v2_entry_value": b.get("value"),
                "v1_exit_timestamp": (ex1 or {}).get("ts"),
                "v1_exit_price": (ex1 or {}).get("exit_price"),
                "v1_pnl": v1_pnl,
                "v1_exit_reason": (ex1 or {}).get("exit_reason"),
                "v2_exit_timestamp": (ex2 or {}).get("ts"),
                "v2_exit_price": (ex2 or {}).get("exit_price"),
                "v2_pnl": v2_pnl,
                "v2_exit_reason": (ex2 or {}).get("exit_reason"),
                "winner": winner,
                "economic_difference": diff,
                "closed_both": closed_both,
                "status": "CLOSED_MATCHED" if closed_both else "OPEN_OR_PARTIAL",
                "identity_matched": True,
                "economically_comparable": True,
            }
        )

    return {
        "matched_opportunities": matched,
        "identity_matched_not_comparable": identity_matched_not_comparable,
        "v1_only_opportunities": v1_only,
        "v2_only_opportunities": v2_only,
        "unmatched_or_ambiguous": unmatched,
    }


def _build_attribution(matched: list[dict[str, Any]]) -> dict[str, Any]:
    """Reconcile matched closed PnL difference into exit-reason components."""
    closed = [m for m in matched if m.get("closed_both") and m.get("economic_difference") is not None]
    total = sum(_f(m.get("economic_difference")) for m in closed)
    comps = {
        "stop_loss_difference": 0.0,
        "take_profit_difference": 0.0,
        "trailing_difference": 0.0,
        "profit_lock_difference": 0.0,
        "exit_timing_difference": 0.0,
        "profit_capture_difference": 0.0,
        "avoided_loss_difference": 0.0,
        "fees_difference": 0.0,
        "open_pnl_difference": 0.0,
        "unattributed_difference": 0.0,
    }
    for m in closed:
        d = _f(m.get("economic_difference"))
        b1 = classify_exit_reason(_s(m.get("v1_exit_reason")))
        b2 = classify_exit_reason(_s(m.get("v2_exit_reason")))
        # Attribute full pair delta to the non-tie exit class preferring V2 reason then V1
        bucket = b2 if b2 != "manual_or_other" else b1
        key_map = {
            "stop_loss": "stop_loss_difference",
            "take_profit": "take_profit_difference",
            "trailing": "trailing_difference",
            "profit_lock": "profit_lock_difference",
            "hard_risk": "avoided_loss_difference",
            "independent_risk": "avoided_loss_difference",
            "manual_or_other": "exit_timing_difference",
        }
        comps[key_map.get(bucket, "unattributed_difference")] += d

    open_pairs = [m for m in matched if not m.get("closed_both") and m.get("economic_difference") is not None]
    open_diff = sum(_f(m.get("economic_difference")) for m in open_pairs)
    comps["open_pnl_difference"] = open_diff

    attributed = sum(comps.values())
    # Total difference for reconciliation = closed + open matched observational
    total_all = total + open_diff
    residual = total_all - attributed
    # residual should be ~0 because we assigned all components; keep explicit unattributed adjust
    if abs(residual) > ATTRIBUTION_TOLERANCE_USD:
        comps["unattributed_difference"] += residual
        attributed = sum(comps.values())

    ok = abs(attributed - total_all) <= ATTRIBUTION_TOLERANCE_USD
    return {
        "TOTAL_V1_V2_DIFFERENCE": total_all,
        "matched_closed_difference": total,
        "components": comps,
        "sum_components": attributed,
        "tolerance_usd": ATTRIBUTION_TOLERANCE_USD,
        "ATTRIBUTION_RECONCILIATION": "PASS" if ok else "FAIL",
        "narrative": _attribution_narrative(total_all, comps),
    }


def _attribution_narrative(total: float, comps: dict[str, float]) -> str:
    if abs(total) < ATTRIBUTION_TOLERANCE_USD:
        return "No material matched V1/V2 economic difference to attribute."
    leader = "V2" if total > 0 else "V1"
    lines = [f"{leader} leads by {total:+.2f} USD on matched sample.", "Attribution:"]
    labels = {
        "profit_capture_difference": "profit capture",
        "avoided_loss_difference": "avoided / hard-risk losses",
        "take_profit_difference": "take-profit exits",
        "stop_loss_difference": "stop-loss exits",
        "trailing_difference": "trailing",
        "profit_lock_difference": "profit lock",
        "exit_timing_difference": "exit timing",
        "fees_difference": "fees",
        "open_pnl_difference": "open MTM",
        "unattributed_difference": "unattributed",
    }
    for k, label in labels.items():
        v = _f(comps.get(k))
        if abs(v) >= ATTRIBUTION_TOLERANCE_USD:
            lines.append(f"  {v:+.2f} USD {label}")
    return "\n".join(lines)


def _leaders(v1m: dict[str, Any], v2m: dict[str, Any], matched: list[dict[str, Any]], *, sample_ok: bool) -> dict[str, str]:
    if not sample_ok:
        insuff = "INSUFFICIENT_COMPARABLE_SAMPLE"
        return {
            "profit_leader": insuff,
            "risk_adjusted_leader": insuff,
            "profit_capture_leader": insuff,
            "loss_protection_leader": insuff,
            "overall_economic_leader": insuff,
        }

    def _cmp(a: Any, b: Any, *, higher_better: bool = True) -> str:
        if a is None or b is None:
            return "INSUFFICIENT_COMPARABLE_SAMPLE"
        if abs(_f(a) - _f(b)) < ATTRIBUTION_TOLERANCE_USD:
            return "TIE"
        if higher_better:
            return "V1" if _f(a) > _f(b) else "V2"
        return "V1" if _f(a) < _f(b) else "V2"

    profit = _cmp(v1m.get("total_pnl"), v2m.get("total_pnl"), higher_better=True)
    # risk-adjusted: prefer lower |max_drawdown| then higher expectancy
    dd = _cmp(abs(_f(v1m.get("max_drawdown"))), abs(_f(v2m.get("max_drawdown"))), higher_better=False)
    risk_adj = dd
    if dd == "TIE":
        risk_adj = _cmp(v1m.get("expectancy"), v2m.get("expectancy"), higher_better=True)

    closed_matched = [m for m in matched if m.get("closed_both")]
    if closed_matched:
        v1_sum = sum(_f(m.get("v1_pnl")) for m in closed_matched)
        v2_sum = sum(_f(m.get("v2_pnl")) for m in closed_matched)
        overall = "TIE" if abs(v2_sum - v1_sum) < ATTRIBUTION_TOLERANCE_USD else ("V2" if v2_sum > v1_sum else "V1")
        capture = overall  # without MFE fields, profit on matched closed is proxy
        loss_prot = _cmp(
            sum(_f(m.get("v1_pnl")) for m in closed_matched if _f(m.get("v1_pnl")) < 0),
            sum(_f(m.get("v2_pnl")) for m in closed_matched if _f(m.get("v2_pnl")) < 0),
            higher_better=True,  # less negative better → higher algebraically
        )
    else:
        overall = "INSUFFICIENT_COMPARABLE_SAMPLE"
        capture = "INSUFFICIENT_COMPARABLE_SAMPLE"
        loss_prot = "INSUFFICIENT_COMPARABLE_SAMPLE"

    return {
        "profit_leader": profit,
        "risk_adjusted_leader": risk_adj,
        "profit_capture_leader": capture,
        "loss_protection_leader": loss_prot,
        "overall_economic_leader": overall,
    }


def _verdict_from_leaders(
    *,
    ownership_ok: bool,
    contamination: str,
    capital_comparable: bool,
    matched_closed: int,
    leaders: dict[str, str],
    duplicate_block: bool,
    missing_data: bool,
    identity_matched_not_comparable: int = 0,
    economically_comparable: int = 0,
) -> tuple[str, float, str]:
    # Cross-arm / semantic contamination still hard-blocks integrity.
    if contamination != "NONE" or not ownership_ok:
        return "DATA_INTEGRITY_BLOCKED", 0.0, "Ownership/isolation integrity failed."
    # Duplicate IDs block comparison integrity but are not cross-arm contamination.
    if duplicate_block:
        return (
            "DATA_INTEGRITY_BLOCKED",
            0.0,
            "Execution ID integrity failed (same-journal duplicate, cross-arm reuse, or conflicting payload).",
        )
    if identity_matched_not_comparable > 0 and economically_comparable == 0:
        return (
            "DATASETS_NOT_COMPARABLE_BY_DESIGN",
            0.4,
            "Shared opportunity identity exists but economic exposure is structurally non-comparable.",
        )
    if missing_data or not capital_comparable or matched_closed < MIN_MATCHED_CLOSED_FOR_VERDICT:
        return (
            "INSUFFICIENT_COMPARABLE_SAMPLE",
            0.25,
            "Matched closed like-for-like sample insufficient or capital not comparable.",
        )
    overall = leaders.get("overall_economic_leader")
    if overall == "V1":
        return "V1_ECONOMIC_LEADER", 0.7, "Matched closed economics favor V1."
    if overall == "V2":
        return "V2_ECONOMIC_LEADER", 0.7, "Matched closed economics favor V2."
    if overall == "TIE":
        return "ECONOMIC_TIE", 0.6, "Matched closed economics are within tolerance."
    return "INSUFFICIENT_COMPARABLE_SAMPLE", 0.25, "No overall leader from matched sample."


def get_v1_v2_economic_comparison(
    *,
    project_root: Path | None = None,
    write_report: bool = False,
) -> dict[str, Any]:
    """
    Read-only V1 vs V2 economic comparison.

    Does not mutate portfolios, journals, orders, trades, BUY/SELL, or configs.
    """
    root = Path(project_root) if project_root is not None else Path(__file__).resolve().parents[2]
    cfg = load_parallel_paper_config()
    p = parallel_paths()

    definitions = canonical_definitions()
    v1 = _load_arm_state("V1", p, cfg)
    v2 = _load_arm_state("V2", p, cfg)

    # Semantic contamination block: refuse if journals claim DPE philosophies as arm identity
    contamination = "NONE"
    for state in (v1, v2):
        for row in state["decisions"][:50]:
            arm = _s(row.get("arm")).upper()
            if arm in DPE_CONTAMINATION_TOKENS:
                contamination = "DETECTED"
                break
        if contamination == "DETECTED":
            break

    cross = "NONE"
    # Path cross-check: V1 account must not equal V2 path
    if str(p["v1_account"].resolve()) == str(p["v2_account"].resolve()):
        cross = "DETECTED"
    # Foreign arm in opposite journal
    if any(_s(r.get("arm")).upper() == "V2" for r in v1["decisions"]):
        cross = "DETECTED"
    if any(_s(r.get("arm")).upper() == "V1" for r in v2["decisions"]):
        cross = "DETECTED"

    isolation = {
        "V1_STATE_ISOLATION": "PROVEN" if v1.get("state_ownership_ok", v1["ownership_ok"]) and cross == "NONE" else (
            "PARTIAL" if v1["path_ok"] else "NOT_PROVEN"
        ),
        "V2_STATE_ISOLATION": "PROVEN" if v2.get("state_ownership_ok", v2["ownership_ok"]) and cross == "NONE" else (
            "PARTIAL" if v2["path_ok"] else "NOT_PROVEN"
        ),
        "CROSS_CONTAMINATION": cross,
        "CROSS_ARM_CONTAMINATION": cross if cross != "NONE" else "NONE",
        "V1_V2_SEMANTIC_CONTAMINATION": (
            "V1_V2_SEMANTIC_CONTAMINATION_BLOCKED" if contamination != "NONE" else "CLEAR"
        ),
    }

    match = _match_opportunities(v1, v2)
    matched = match["matched_opportunities"]
    identity_not_comp = match.get("identity_matched_not_comparable") or []
    matched_closed = [m for m in matched if m.get("closed_both")]
    identity_matched_count = len(matched) + len(identity_not_comp)
    economically_comparable_count = len(matched)

    start_v1 = _f(v1["metrics"].get("capital_base"))
    start_v2 = _f(v2["metrics"].get("capital_base"))
    capital_comparable = abs(start_v1 - start_v2) <= 1.0 and v1.get("v1_mode") != "CANONICAL_PAPER_MIRROR"
    # Mirror mode + unequal notionals ⇒ not like-for-like for overall money winner
    if v1.get("v1_mode") == "CANONICAL_PAPER_MIRROR":
        capital_comparable = False

    missing = not (v1["account"] or v1["accounting"]) or not (v2["account"] or v2["accounting"])
    v1_diag = dict(v1.get("execution_id_diagnostics") or {})
    v2_diag = dict(v2.get("execution_id_diagnostics") or {})
    dual_ids = sorted(
        set(v1_diag.get("DUAL_JOURNAL_EQUIVALENT_IDS") or [])
        | set(v2_diag.get("DUAL_JOURNAL_EQUIVALENT_IDS") or [])
    )
    within_exec = int(v1_diag.get("WITHIN_EXECUTIONS_JOURNAL_DUPLICATES") or 0) + int(
        v2_diag.get("WITHIN_EXECUTIONS_JOURNAL_DUPLICATES") or 0
    )
    within_trade = int(v1_diag.get("WITHIN_TRADES_JOURNAL_DUPLICATES") or 0) + int(
        v2_diag.get("WITHIN_TRADES_JOURNAL_DUPLICATES") or 0
    )
    conflicting = list(v1_diag.get("CONFLICTING_EXECUTION_IDS") or []) + list(
        v2_diag.get("CONFLICTING_EXECUTION_IDS") or []
    )
    # Cross-arm shared execution ids
    v1_eids = {
        _s(r.get("execution_id"))
        for r in (v1.get("executions") or []) + (v1.get("trades") or [])
        if _s(r.get("execution_id"))
    }
    v2_eids = {
        _s(r.get("execution_id"))
        for r in (v2.get("executions") or []) + (v2.get("trades") or [])
        if _s(r.get("execution_id"))
    }
    cross_shared = sorted(v1_eids & v2_eids)
    for eid in cross_shared:
        conflicting.append({"execution_id": eid, "class": "CROSS_ARM_EXECUTION_ID_REUSE", "arms": ["V1", "V2"]})

    integrity_fail = bool(
        within_exec
        or within_trade
        or cross_shared
        or conflicting
        or v1_diag.get("UNRESOLVED_DUPLICATE_IDS")
        or v2_diag.get("UNRESOLVED_DUPLICATE_IDS")
        or v1_diag.get("EXECUTION_ID_INTEGRITY") == "FAIL"
        or v2_diag.get("EXECUTION_ID_INTEGRITY") == "FAIL"
    )
    # Real integrity failures only (dual-journal equivalent is expected and not a block).
    dup_block = integrity_fail
    # State ownership excludes duplicate-ID uniqueness (reported separately).
    state_ownership_isolation = bool(
        v1.get("state_ownership_ok", v1["ownership_ok"])
        and v2.get("state_ownership_ok", v2["ownership_ok"])
        and contamination == "NONE"
        and cross == "NONE"
    )
    ownership_ok = bool(state_ownership_isolation and not dup_block)

    execution_id_integrity = "FAIL" if integrity_fail else "PASS"
    dual_journal_recording = (
        "EXPECTED" if dual_ids and not integrity_fail else ("PRESENT" if dual_ids else "NONE")
    )
    cross_arm = "NONE" if cross == "NONE" and not cross_shared else "DETECTED"
    comparison_integrity = {
        "STATE_OWNERSHIP_ISOLATION": "PASS" if state_ownership_isolation else "FAIL",
        "EXECUTION_ID_INTEGRITY": execution_id_integrity,
        "DUAL_JOURNAL_RECORDING": dual_journal_recording,
        "WITHIN_EXECUTIONS_JOURNAL_DUPLICATES": within_exec,
        "WITHIN_TRADES_JOURNAL_DUPLICATES": within_trade,
        "CROSS_ARM_SHARED_EXECUTION_IDS": len(cross_shared),
        "CROSS_ARM_SHARED_EXECUTION_ID_LIST": cross_shared,
        "DUAL_JOURNAL_EQUIVALENT_IDS": len(dual_ids),
        "DUAL_JOURNAL_EQUIVALENT_ID_LIST": dual_ids,
        "CONFLICTING_EXECUTION_IDS": len(conflicting),
        "CONFLICTING_EXECUTION_ID_DETAILS": conflicting,
        "DEDUPLICATED_ECONOMIC_TRADES": int(v1["metrics"].get("deduplicated_closed_trades") or 0)
        + int(v2["metrics"].get("deduplicated_closed_trades") or 0),
        # Legacy alias: PASS when integrity PASS (dual-journal no longer fails uniqueness).
        "EXECUTION_ID_UNIQUENESS": execution_id_integrity,
        "CROSS_ARM_CONTAMINATION": cross_arm,
        "OVERALL_COMPARISON_INTEGRITY": (
            "BLOCKED"
            if (not state_ownership_isolation or dup_block or contamination != "NONE")
            else (
                "PASS_STRUCTURAL_NONCOMPARABILITY"
                if identity_matched_count > 0 and economically_comparable_count == 0
                else "PASS"
            )
        ),
        "duplicate_execution_id_details": list(v1.get("duplicate_execution_id_details") or [])
        + list(v2.get("duplicate_execution_id_details") or []),
    }

    sample_ok = bool(
        ownership_ok
        and capital_comparable
        and len(matched_closed) >= MIN_MATCHED_CLOSED_FOR_VERDICT
        and not missing
        and not dup_block
        and economically_comparable_count > 0
    )

    leaders = _leaders(v1["metrics"], v2["metrics"], matched, sample_ok=sample_ok)
    verdict, confidence, main_reason = _verdict_from_leaders(
        ownership_ok=state_ownership_isolation,
        contamination=contamination if contamination != "NONE" else ("DETECTED" if cross != "NONE" else "NONE"),
        capital_comparable=capital_comparable,
        matched_closed=len(matched_closed),
        leaders=leaders,
        duplicate_block=dup_block,
        missing_data=missing,
        identity_matched_not_comparable=len(identity_not_comp),
        economically_comparable=economically_comparable_count,
    )
    # Prefer structural non-comparability as comparison status when identity matched but exposure differs.
    comparison_status = verdict
    if identity_matched_count > 0 and economically_comparable_count == 0 and state_ownership_isolation and not dup_block:
        comparison_status = "DATASETS_NOT_COMPARABLE_BY_DESIGN"
        if verdict != "DATA_INTEGRITY_BLOCKED":
            verdict = "DATASETS_NOT_COMPARABLE_BY_DESIGN"
            main_reason = (
                "STRUCTURAL_NONCOMPARABILITY: shared opportunity identity exists but economic "
                "exposure is structurally non-comparable (V1 full vs V2 tranche / entry notional)."
            )
            confidence = 0.4
    elif verdict == "DATASETS_NOT_COMPARABLE_BY_DESIGN":
        comparison_status = "DATASETS_NOT_COMPARABLE_BY_DESIGN"

    attribution = _build_attribution(matched)

    # Account-level difference always reported as observational money
    v1_total = v1["metrics"].get("total_pnl")
    v2_total = v2["metrics"].get("total_pnl")
    observational_diff: Any = None
    if v1_total is not None and v2_total is not None and state_ownership_isolation:
        observational_diff = _f(v2_total) - _f(v1_total)

    # Leadership CURRENT_DIFFERENCE requires matched like-for-like sample
    if not sample_ok:
        current_diff: Any = "NOT_PROVEN"
    elif observational_diff is None:
        current_diff = "NOT_PROVEN"
    else:
        current_diff = observational_diff

    # Top advantages from matched list
    scored = [m for m in matched if m.get("economic_difference") is not None]
    v1_adv = sorted(scored, key=lambda m: _f(m.get("economic_difference")))[:5]  # V2-V1 negative ⇒ V1 better
    v2_adv = sorted(scored, key=lambda m: -_f(m.get("economic_difference")))[:5]

    economic_errors = []
    for m in matched:
        # Only demonstrable from fields — without MFE we cannot claim premature/late
        if m.get("closed_both") and m.get("v1_exit_reason") and m.get("v2_exit_reason"):
            if classify_exit_reason(_s(m.get("v1_exit_reason"))) == "take_profit" and _f(m.get("v2_pnl")) > _f(m.get("v1_pnl")):
                economic_errors.append(
                    {
                        "type": "profit_taken_too_early",
                        "opportunity_id": m.get("opportunity_id"),
                        "detail": "V1 take-profit while V2 realized more on same opportunity",
                    }
                )
            if classify_exit_reason(_s(m.get("v1_exit_reason"))) == "stop_loss" and _f(m.get("v2_pnl")) > _f(m.get("v1_pnl")):
                economic_errors.append(
                    {
                        "type": "premature_stop",
                        "opportunity_id": m.get("opportunity_id"),
                        "detail": "V1 stop while V2 outcome better on same opportunity",
                    }
                )

    period = {
        "v1_updated": (v1.get("account") or {}).get("ts") or (v1.get("portfolio") or {}).get("updated_at"),
        "v2_updated": (v2.get("account") or {}).get("ts") or (v2.get("portfolio") or {}).get("updated_at"),
        "v1_mode": v1.get("v1_mode"),
        "v2_mode": "ISOLATED_PARALLEL_PAPER",
        "scope": "PARALLEL_PAPER",
        "live_enabled": False,
    }

    data_quality = {
        "ownership_ok": ownership_ok,
        "state_ownership_ok": state_ownership_isolation,
        "capital_comparable": capital_comparable,
        "matched_opportunities": len(matched),
        "IDENTITY_MATCHED_OPPORTUNITIES": identity_matched_count,
        "ECONOMICALLY_COMPARABLE_OPPORTUNITIES": economically_comparable_count,
        "identity_matched_opportunities": identity_matched_count,
        "economically_comparable_opportunities": economically_comparable_count,
        "identity_matched_not_comparable": len(identity_not_comp),
        "matched_closed": len(matched_closed),
        "v1_only": len(match["v1_only_opportunities"]),
        "v2_only": len(match["v2_only_opportunities"]),
        "unmatched_or_ambiguous": len(match["unmatched_or_ambiguous"]),
        "no_shared_opportunities": identity_matched_count == 0
        and len(match["v1_only_opportunities"]) + len(match["v2_only_opportunities"]) > 0,
        "shared_but_structurally_noncomparable": identity_matched_count > 0 and economically_comparable_count == 0,
        "duplicate_execution_ids_v1": v1["duplicate_execution_ids"],
        "duplicate_execution_ids_v2": v2["duplicate_execution_ids"],
        "WITHIN_EXECUTIONS_JOURNAL_DUPLICATES": within_exec,
        "WITHIN_TRADES_JOURNAL_DUPLICATES": within_trade,
        "CROSS_ARM_SHARED_EXECUTION_IDS": len(cross_shared),
        "DUAL_JOURNAL_EQUIVALENT_IDS": len(dual_ids),
        "CONFLICTING_EXECUTION_IDS": len(conflicting),
        "EXECUTION_ID_INTEGRITY": execution_id_integrity,
        "DUAL_JOURNAL_RECORDING": dual_journal_recording,
        "DEDUPLICATED_ECONOMIC_TRADES": comparison_integrity["DEDUPLICATED_ECONOMIC_TRADES"],
        "missing_account_data": missing,
        "v1_decision_count": len(v1["decisions"]),
        "v2_decision_count": len(v2["decisions"]),
        "note": (
            "IDENTITY_MATCHED counts shared opportunity identity; ECONOMICALLY_COMPARABLE requires "
            "comparable exposure. Dual-journal equivalent execution_ids are expected and counted once "
            "for trade-quality metrics. Account-level PnL remains observational SSOT."
        ),
    }

    payload: dict[str, Any] = {
        "generated_at": _now_iso(),
        "schema": "tae.v1_v2_economic_comparison.v1",
        "read_only": True,
        "comparison_period": period,
        "data_quality": data_quality,
        "definitions": definitions,
        "state_isolation": isolation,
        "comparison_integrity": comparison_integrity,
        "STATE_OWNERSHIP_ISOLATION": comparison_integrity["STATE_OWNERSHIP_ISOLATION"],
        "EXECUTION_ID_INTEGRITY": comparison_integrity["EXECUTION_ID_INTEGRITY"],
        "DUAL_JOURNAL_RECORDING": comparison_integrity["DUAL_JOURNAL_RECORDING"],
        "EXECUTION_ID_UNIQUENESS": comparison_integrity["EXECUTION_ID_INTEGRITY"],  # legacy alias
        "CROSS_ARM_CONTAMINATION": comparison_integrity["CROSS_ARM_CONTAMINATION"],
        "OVERALL_COMPARISON_INTEGRITY": comparison_integrity["OVERALL_COMPARISON_INTEGRITY"],
        "WITHIN_EXECUTIONS_JOURNAL_DUPLICATES": within_exec,
        "WITHIN_TRADES_JOURNAL_DUPLICATES": within_trade,
        "CROSS_ARM_SHARED_EXECUTION_IDS": len(cross_shared),
        "DUAL_JOURNAL_EQUIVALENT_IDS": len(dual_ids),
        "CONFLICTING_EXECUTION_IDS": len(conflicting),
        "DEDUPLICATED_ECONOMIC_TRADES": comparison_integrity["DEDUPLICATED_ECONOMIC_TRADES"],
        "COMPARISON_STATUS": comparison_status,
        "IDENTITY_MATCHED_OPPORTUNITIES": identity_matched_count,
        "ECONOMICALLY_COMPARABLE_OPPORTUNITIES": economically_comparable_count,
        "ACCOUNT_LEVEL_METRICS": {
            "v1_account_value": v1["metrics"].get("account_value"),
            "v2_account_value": v2["metrics"].get("account_value"),
            "v1_realized_pnl": v1["metrics"].get("realized_pnl"),
            "v2_realized_pnl": v2["metrics"].get("realized_pnl"),
            "v1_unrealized_pnl": v1["metrics"].get("unrealized_pnl"),
            "v2_unrealized_pnl": v2["metrics"].get("unrealized_pnl"),
            "v1_total_pnl": v1_total,
            "v2_total_pnl": v2_total,
            "source": "account_or_portfolio_ssot",
        },
        "TRADE_QUALITY_METRICS_DEDUPED": {
            "v1_closed_trades": v1["metrics"].get("closed_trades"),
            "v2_closed_trades": v2["metrics"].get("closed_trades"),
            "v1_win_rate": v1["metrics"].get("win_rate"),
            "v2_win_rate": v2["metrics"].get("win_rate"),
            "v1_profit_factor": v1["metrics"].get("profit_factor"),
            "v2_profit_factor": v2["metrics"].get("profit_factor"),
            "v1_expectancy": v1["metrics"].get("expectancy"),
            "v2_expectancy": v2["metrics"].get("expectancy"),
            "deduplicated": True,
        },
        "matched_sample": {
            "matched_count": len(matched),
            "matched_closed_count": len(matched_closed),
            "identity_matched_count": identity_matched_count,
            "economically_comparable_count": economically_comparable_count,
            "usable_for_verdict": sample_ok,
        },
        "v1": {
            **v1["metrics"],
            "mode": v1.get("v1_mode"),
            "source": v1.get("source"),
            "ownership_ok": v1["ownership_ok"],
            "state_ownership_ok": v1.get("state_ownership_ok", v1["ownership_ok"]),
        },
        "v2": {
            **v2["metrics"],
            "mode": "ISOLATED_PARALLEL_PAPER",
            "source": "PARALLEL_PAPER",
            "ownership_ok": v2["ownership_ok"],
            "state_ownership_ok": v2.get("state_ownership_ok", v2["ownership_ok"]),
        },
        "difference": {
            "V1_ACCOUNT_VALUE": v1["metrics"].get("account_value"),
            "V2_ACCOUNT_VALUE": v2["metrics"].get("account_value"),
            "V1_REALIZED_PNL": v1["metrics"].get("realized_pnl"),
            "V2_REALIZED_PNL": v2["metrics"].get("realized_pnl"),
            "V1_UNREALIZED_PNL": v1["metrics"].get("unrealized_pnl"),
            "V2_UNREALIZED_PNL": v2["metrics"].get("unrealized_pnl"),
            "V1_TOTAL_PNL": v1_total,
            "V2_TOTAL_PNL": v2_total,
            "CURRENT_DIFFERENCE": current_diff,
            "account_value_observational_difference": (
                None
                if observational_diff is None
                else _f(v2["metrics"].get("account_value")) - _f(v1["metrics"].get("account_value"))
            ),
            "account_value": _f(v2["metrics"].get("account_value")) - _f(v1["metrics"].get("account_value")),
            "realized_pnl": _f(v2["metrics"].get("realized_pnl")) - _f(v1["metrics"].get("realized_pnl")),
            "unrealized_pnl": _f(v2["metrics"].get("unrealized_pnl")) - _f(v1["metrics"].get("unrealized_pnl")),
            "total_pnl": observational_diff,
            "total_pnl_leadership_difference": current_diff,
            "net_pnl": _f(v2["metrics"].get("net_pnl")) - _f(v1["metrics"].get("net_pnl")),
            "roi_pct": None
            if v1["metrics"].get("roi_pct") is None or v2["metrics"].get("roi_pct") is None
            else _f(v2["metrics"].get("roi_pct")) - _f(v1["metrics"].get("roi_pct")),
            "max_drawdown": _f(v2["metrics"].get("max_drawdown")) - _f(v1["metrics"].get("max_drawdown")),
            "profit_factor": None,
            "expectancy": None
            if v1["metrics"].get("expectancy") is None or v2["metrics"].get("expectancy") is None
            else _f(v2["metrics"].get("expectancy")) - _f(v1["metrics"].get("expectancy")),
            "profit_capture": None
            if v1["metrics"].get("profit_capture_ratio") is None or v2["metrics"].get("profit_capture_ratio") is None
            else _f(v2["metrics"].get("profit_capture_ratio")) - _f(v1["metrics"].get("profit_capture_ratio")),
            "avoided_loss": None
            if v1["metrics"].get("avoided_loss_after_exit") is None or v2["metrics"].get("avoided_loss_after_exit") is None
            else _f(v2["metrics"].get("avoided_loss_after_exit")) - _f(v1["metrics"].get("avoided_loss_after_exit")),
        },
        "attribution": attribution,
        "matched_opportunities": matched,
        "identity_matched_not_comparable": identity_not_comp,
        "v1_only_opportunities": match["v1_only_opportunities"],
        "v2_only_opportunities": match["v2_only_opportunities"],
        "unmatched_or_ambiguous": match["unmatched_or_ambiguous"],
        "v1_top_advantages": v1_adv,
        "v2_top_advantages": v2_adv,
        "economic_errors": economic_errors,
        "profit_leader": leaders["profit_leader"],
        "risk_adjusted_leader": leaders["risk_adjusted_leader"],
        "profit_capture_leader": leaders["profit_capture_leader"],
        "loss_protection_leader": leaders["loss_protection_leader"],
        "overall_economic_leader": leaders["overall_economic_leader"],
        "confidence": confidence,
        "verdict": verdict,
        "main_reason": main_reason,
        "MAIN_ECONOMIC_REASON": main_reason,
        "project_root": str(root),
    }

    if write_report:
        _persist_reports(root, payload)

    return payload


def _persist_reports(root: Path, payload: dict[str, Any]) -> None:
    json_path = root / "tae_v1_v2_economic_comparison.json"
    md_path = root / "TAE_V1_V2_ECONOMIC_COMPARISON.md"
    json_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    md_path.write_text(format_comparison_markdown(payload), encoding="utf-8")


def _fmt_money(v: Any) -> str:
    if v is None or v == "NOT_PROVEN":
        return str(v) if v is not None else "N/A"
    try:
        return f"${float(v):,.2f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_pct(v: Any) -> str:
    if v is None:
        return "N/A"
    try:
        return f"{float(v):.2f}%"
    except (TypeError, ValueError):
        return str(v)


def format_comparison_section(payload: dict[str, Any], *, verbose: bool = False) -> str:
    """Operator section for morning-audit (money first)."""
    diff = payload.get("difference") or {}
    v1 = payload.get("v1") or {}
    v2 = payload.get("v2") or {}
    dq = payload.get("data_quality") or {}
    period = payload.get("comparison_period") or {}
    lines = [
        "============================================================",
        "V1 vs V2 — ECONOMIC RESULTS",
        "============================================================",
        "",
        f"Comparison period: V1_MODE={period.get('v1_mode')} | V2_MODE={period.get('v2_mode')} | scope={period.get('scope')}",
        f"Identity-matched opportunities: {dq.get('IDENTITY_MATCHED_OPPORTUNITIES', dq.get('identity_matched_opportunities'))}",
        f"Economically comparable opportunities: {dq.get('ECONOMICALLY_COMPARABLE_OPPORTUNITIES', dq.get('economically_comparable_opportunities'))} "
        f"(closed={dq.get('matched_closed')})",
        (
            "Note: shared opportunities exist but economic exposure is structurally non-comparable"
            if dq.get("shared_but_structurally_noncomparable")
            else (
                "Note: no shared opportunities"
                if dq.get("no_shared_opportunities")
                else "Note: identity match and economic comparability evaluated separately"
            )
        ),
        f"Data quality: state_ownership={payload.get('STATE_OWNERSHIP_ISOLATION') or dq.get('state_ownership_ok')} "
        f"execution_id_integrity={payload.get('EXECUTION_ID_INTEGRITY')} "
        f"dual_journal={payload.get('DUAL_JOURNAL_RECORDING')} "
        f"cross_arm={payload.get('CROSS_ARM_CONTAMINATION')} "
        f"capital_comparable={dq.get('capital_comparable')} "
        f"unmatched={dq.get('unmatched_or_ambiguous')}",
        f"Execution-id diagnostics: within_exec={payload.get('WITHIN_EXECUTIONS_JOURNAL_DUPLICATES')} "
        f"within_trades={payload.get('WITHIN_TRADES_JOURNAL_DUPLICATES')} "
        f"cross_arm_shared={payload.get('CROSS_ARM_SHARED_EXECUTION_IDS')} "
        f"dual_journal_equivalent={payload.get('DUAL_JOURNAL_EQUIVALENT_IDS')} "
        f"conflicting={payload.get('CONFLICTING_EXECUTION_IDS')} "
        f"deduplicated_economic_trades={payload.get('DEDUPLICATED_ECONOMIC_TRADES')}",
        f"Comparison integrity: {payload.get('OVERALL_COMPARISON_INTEGRITY')} | "
        f"COMPARISON_STATUS={payload.get('COMPARISON_STATUS') or payload.get('verdict')}",
        f"State isolation: {(payload.get('state_isolation') or {})}",
        "",
        "ACCOUNT_LEVEL_METRICS (SSOT; not journal-summed)",
        f"  V1 realized={_fmt_money((payload.get('ACCOUNT_LEVEL_METRICS') or {}).get('v1_realized_pnl'))} "
        f"V2 realized={_fmt_money((payload.get('ACCOUNT_LEVEL_METRICS') or {}).get('v2_realized_pnl'))}",
        "TRADE_QUALITY_METRICS_DEDUPED (one economic trade per equivalent execution_id)",
        f"  V1 closed={((payload.get('TRADE_QUALITY_METRICS_DEDUPED') or {}).get('v1_closed_trades'))} "
        f"V2 closed={((payload.get('TRADE_QUALITY_METRICS_DEDUPED') or {}).get('v2_closed_trades'))}",
        "",
        f"{'':24} {'V1':>14} {'V2':>14} {'Difference':>14}",
        f"{'Account value:':24} {_fmt_money(v1.get('account_value')):>14} {_fmt_money(v2.get('account_value')):>14} {_fmt_money(diff.get('account_value')):>14}",
        f"{'Realized PnL:':24} {_fmt_money(v1.get('realized_pnl')):>14} {_fmt_money(v2.get('realized_pnl')):>14} {_fmt_money(diff.get('realized_pnl')):>14}",
        f"{'Unrealized PnL:':24} {_fmt_money(v1.get('unrealized_pnl')):>14} {_fmt_money(v2.get('unrealized_pnl')):>14} {_fmt_money(diff.get('unrealized_pnl')):>14}",
        f"{'Total PnL:':24} {_fmt_money(v1.get('total_pnl')):>14} {_fmt_money(v2.get('total_pnl')):>14} {_fmt_money(diff.get('total_pnl')):>14}",
        f"{'Net PnL:':24} {_fmt_money(v1.get('net_pnl')):>14} {_fmt_money(v2.get('net_pnl')):>14} {_fmt_money(diff.get('net_pnl')):>14}",
        f"{'ROI:':24} {_fmt_pct(v1.get('roi_pct')):>14} {_fmt_pct(v2.get('roi_pct')):>14} {_fmt_pct(diff.get('roi_pct')):>14}",
        f"{'Max drawdown:':24} {_fmt_money(v1.get('max_drawdown')):>14} {_fmt_money(v2.get('max_drawdown')):>14} {_fmt_money(diff.get('max_drawdown')):>14}",
        f"{'Profit factor:':24} {str(v1.get('profit_factor')):>14} {str(v2.get('profit_factor')):>14} {'N/A':>14}",
        f"{'Expectancy:':24} {_fmt_money(v1.get('expectancy')):>14} {_fmt_money(v2.get('expectancy')):>14} {_fmt_money(diff.get('expectancy')):>14}",
        f"{'Profit capture:':24} {str(v1.get('profit_capture_ratio')):>14} {str(v2.get('profit_capture_ratio')):>14} {'N/A':>14}",
        f"{'Avoided loss:':24} {_fmt_money(v1.get('avoided_loss_after_exit')):>14} {_fmt_money(v2.get('avoided_loss_after_exit')):>14} {_fmt_money(diff.get('avoided_loss')):>14}",
        "",
        f"V1_TOTAL_PNL={v1.get('total_pnl')}",
        f"V2_TOTAL_PNL={v2.get('total_pnl')}",
        f"CURRENT_DIFFERENCE={diff.get('CURRENT_DIFFERENCE')}",
        "",
        f"PROFIT LEADER: {payload.get('profit_leader')}",
        f"RISK-ADJUSTED LEADER: {payload.get('risk_adjusted_leader')}",
        f"PROFIT-CAPTURE LEADER: {payload.get('profit_capture_leader')}",
        f"LOSS-PROTECTION LEADER: {payload.get('loss_protection_leader')}",
        f"OVERALL ECONOMIC LEADER: {payload.get('overall_economic_leader')}",
        "",
        f"ECONOMIC ADVANTAGE: {diff.get('CURRENT_DIFFERENCE')}",
        f"MAIN REASON: {payload.get('main_reason')}",
        f"CONFIDENCE: {payload.get('confidence')}",
        f"VERDICT: {payload.get('verdict')}",
        "",
    ]

    attr = payload.get("attribution") or {}
    if attr.get("narrative"):
        lines.append(str(attr["narrative"]))
        lines.append(f"ATTRIBUTION_RECONCILIATION={attr.get('ATTRIBUTION_RECONCILIATION')}")
        lines.append("")

    if verbose:
        lines.extend(_verbose_tables(payload))
    return "\n".join(lines)


def _verbose_tables(payload: dict[str, Any]) -> list[str]:
    v1 = payload.get("v1") or {}
    v2 = payload.get("v2") or {}
    diff = payload.get("difference") or {}
    lines = [
        "--- Verbose: metric table ---",
        "Metric | V1 | V2 | Difference | Leader",
    ]
    rows = [
        ("account_value", v1.get("account_value"), v2.get("account_value"), diff.get("account_value")),
        ("realized_pnl", v1.get("realized_pnl"), v2.get("realized_pnl"), diff.get("realized_pnl")),
        ("unrealized_pnl", v1.get("unrealized_pnl"), v2.get("unrealized_pnl"), diff.get("unrealized_pnl")),
        ("total_pnl", v1.get("total_pnl"), v2.get("total_pnl"), diff.get("total_pnl")),
        ("net_pnl", v1.get("net_pnl"), v2.get("net_pnl"), diff.get("net_pnl")),
        ("roi_pct", v1.get("roi_pct"), v2.get("roi_pct"), diff.get("roi_pct")),
        ("win_rate", v1.get("win_rate"), v2.get("win_rate"), None),
        ("profit_factor", v1.get("profit_factor"), v2.get("profit_factor"), None),
        ("expectancy", v1.get("expectancy"), v2.get("expectancy"), diff.get("expectancy")),
        ("max_drawdown", v1.get("max_drawdown"), v2.get("max_drawdown"), diff.get("max_drawdown")),
    ]
    for name, a, b, d in rows:
        leader = "TIE"
        if a is not None and b is not None:
            if abs(_f(a) - _f(b)) >= ATTRIBUTION_TOLERANCE_USD:
                higher_better = name not in {"max_drawdown"}
                if higher_better:
                    leader = "V1" if _f(a) > _f(b) else "V2"
                else:
                    leader = "V1" if abs(_f(a)) < abs(_f(b)) else "V2"
        lines.append(f"{name} | {a} | {b} | {d} | {leader}")

    lines.append("")
    lines.append("--- Verbose: exit reason ---")
    lines.append("Exit reason | V1 trades | V1 PnL | V2 trades | V2 PnL | Advantage")
    for bucket in EXIT_BUCKETS:
        c1 = (v1.get("exit_reason_counts") or {}).get(bucket, 0)
        c2 = (v2.get("exit_reason_counts") or {}).get(bucket, 0)
        p1 = (v1.get("exit_reason_pnl") or {}).get(bucket, 0.0)
        p2 = (v2.get("exit_reason_pnl") or {}).get(bucket, 0.0)
        adv = "TIE"
        if abs(_f(p2) - _f(p1)) >= ATTRIBUTION_TOLERANCE_USD:
            adv = "V2" if _f(p2) > _f(p1) else "V1"
        lines.append(f"{bucket} | {c1} | {p1} | {c2} | {p2} | {adv}")

    lines.append("")
    lines.append("--- Verbose: matched opportunities ---")
    for m in payload.get("matched_opportunities") or []:
        lines.append(
            f"{m.get('ticker')} entry={m.get('entry_timestamp')}@{m.get('entry_price')} "
            f"V1_exit={m.get('v1_exit_timestamp')}/{m.get('v1_exit_price')}/{m.get('v1_pnl')}/{m.get('v1_exit_reason')} "
            f"V2_exit={m.get('v2_exit_timestamp')}/{m.get('v2_exit_price')}/{m.get('v2_pnl')}/{m.get('v2_exit_reason')} "
            f"winner={m.get('winner')} diff={m.get('economic_difference')}"
        )
    if not (payload.get("matched_opportunities") or []):
        lines.append("(none — see unmatched_or_ambiguous for notional mismatches)")

    lines.append("")
    lines.append("--- Verbose: top V1 advantages ---")
    for m in payload.get("v1_top_advantages") or []:
        lines.append(f"  {m.get('opportunity_id')} diff={m.get('economic_difference')}")
    lines.append("--- Verbose: top V2 advantages ---")
    for m in payload.get("v2_top_advantages") or []:
        lines.append(f"  {m.get('opportunity_id')} diff={m.get('economic_difference')}")

    lines.append("")
    lines.append("--- Verbose: economic errors (demonstrable only) ---")
    errs = payload.get("economic_errors") or []
    if not errs:
        lines.append("  (none demonstrable from current fields)")
    for e in errs:
        lines.append(f"  {e.get('type')}: {e.get('detail')}")
    return lines


def format_comparison_markdown(payload: dict[str, Any]) -> str:
    return (
        "# TAE V1 vs V2 Economic Comparison\n\n"
        f"Generated: {payload.get('generated_at')}\n\n"
        f"```text\n{format_comparison_section(payload, verbose=True)}\n```\n"
    )
