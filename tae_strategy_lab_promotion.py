#!/usr/bin/env python3
"""
TAE Strategy Lab Promotion — Sprint 4

HUMAN-GATED only | PAPER domain | NO_AUTO_PROMOTE | NO_LIVE_MUTATION

Owns lab lifecycle state transitions (champion/challenger/archive/rollback).
Does not authorize BUY/SELL, mutate parallel books, or unlock LIVE.
Wraps research promotion_gate evidence; does not duplicate gate formulas.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_parallel_paper_config import PROJECT_ROOT

LAB_OUT_DIR = PROJECT_ROOT / "runtime_outputs" / "strategy_lab"
PROMOTION_STATE_PATH = LAB_OUT_DIR / "promotion_state.json"
PROMOTION_TICKETS_PATH = LAB_OUT_DIR / "promotion_tickets.jsonl"
PROMOTION_AUDIT_PATH = LAB_OUT_DIR / "promotion_audit.jsonl"
CHAMPION_ARCHIVE_PATH = LAB_OUT_DIR / "champion_archive.json"
REGISTRY_PATH = PROJECT_ROOT / "config" / "tae_strategy_lab_registry.json"
EXPERIMENTAL_REGISTRY_PATH = LAB_OUT_DIR / "experimental_challengers.json"

PROMOTION_DOMAIN = "PARALLEL_PAPER_PRIMARY"
AUTONOMOUS_PAPER_EVOLUTION_DOMAIN = "AUTONOMOUS_PAPER_EVOLUTION"
EXECUTION_MODE = "PAPER"

LIFECYCLE_STATES = frozenset(
    {
        "BASELINE",
        "CHAMPION",
        "CHALLENGER",
        "CANDIDATE",
        "REJECTED",
        "ARCHIVED",
        "ROLLBACK_CANDIDATE",
        "SUSPENDED",
    }
)

# Explicit allowed transitions (fail-closed otherwise).
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "CANDIDATE": frozenset({"CHALLENGER", "REJECTED", "SUSPENDED"}),
    "CHALLENGER": frozenset({"CHAMPION", "REJECTED", "SUSPENDED"}),
    "CHAMPION": frozenset({"ARCHIVED", "CHALLENGER", "SUSPENDED"}),
    "ARCHIVED": frozenset({"ROLLBACK_CANDIDATE"}),
    "ROLLBACK_CANDIDATE": frozenset({"CHAMPION", "ARCHIVED", "SUSPENDED"}),
    "REJECTED": frozenset({"ARCHIVED", "CANDIDATE"}),
    "BASELINE": frozenset({"CHAMPION", "CHALLENGER", "SUSPENDED", "ARCHIVED"}),
    "SUSPENDED": frozenset({"CHALLENGER", "CANDIDATE", "ARCHIVED"}),
}

# Graduated autonomy: transitions in this table apply immediately, with no
# human ticket approval. Scope is deliberately narrow — CANDIDATE -> CHALLENGER
# only starts isolated PAPER testing (no capital movement, no champion change,
# no LIVE impact). Every other transition, including CHALLENGER -> CHAMPION,
# stays strictly human-gated via approve_ticket()/apply_ticket() below.
AUTO_APPROVED_TRANSITIONS: dict[str, frozenset[str]] = {
    "CANDIDATE": frozenset({"CHALLENGER"}),
}

TICKET_TYPES = frozenset(
    {
        "ADVANCE_TO_CHALLENGER",
        "PROMOTE_TO_CHAMPION",
        "REJECT_CHALLENGER",
        "ROLLBACK_CHAMPION",
        "SUSPEND",
    }
)

TICKET_OPEN = "PENDING_HUMAN"
TICKET_APPROVED = "APPROVED"
TICKET_REJECTED = "REJECTED"
TICKET_APPLIED = "APPLIED"
TICKET_CANCELLED = "CANCELLED"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _s(v: Any, default: str = "") -> str:
    return str(v if v is not None else default).strip()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _atomic_write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True, default=str) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def audit(
    event: str,
    payload: dict[str, Any] | None = None,
    *,
    domain: str = PROMOTION_DOMAIN,
    auto_promote: bool = False,
) -> None:
    _append_jsonl(
        PROMOTION_AUDIT_PATH,
        {
            "ts": _now(),
            "event": event,
            "auto_promote": bool(
                auto_promote and domain == AUTONOMOUS_PAPER_EVOLUTION_DOMAIN
            ),
            "live_mutation": False,
            "promotion_domain": domain,
            "payload": payload or {},
        },
    )


def load_registry_identity() -> dict[str, Any]:
    doc = _read_json(REGISTRY_PATH)
    if not doc:
        raise FileNotFoundError(f"registry_missing:{REGISTRY_PATH}")
    experimental = _read_json(EXPERIMENTAL_REGISTRY_PATH) or {}
    base = [row for row in doc.get("strategies") or [] if isinstance(row, dict)]
    seen = {_s(row.get("strategy_id")) for row in base}
    for row in experimental.get("strategies") or []:
        if not isinstance(row, dict):
            continue
        sid = _s(row.get("strategy_id"))
        if not sid or sid in seen:
            continue
        base.append(
            {
                **row,
                "status": "CANDIDATE",
                "strategy_class": "EXPERIMENTAL_CHALLENGER",
                "lifecycle_state": "CANDIDATE",
                "experimental_only": True,
                "live_allowed": False,
                "enabled_in_parallel_paper": bool(row.get("enabled_in_parallel_paper", False)),
            }
        )
        seen.add(sid)
    doc = dict(doc)
    doc["strategies"] = base
    return doc


def _seed_strategies_from_registry(reg: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for s in reg.get("strategies") or []:
        if not isinstance(s, dict):
            continue
        sid = _s(s.get("strategy_id"))
        if not sid:
            continue
        status = _s(s.get("status")).upper()
        if "CHAMPION" in status or status == "BASELINE" or "BASELINE" in status:
            life = "CHAMPION" if "CHAMPION" in status or status.endswith("BASELINE") else "BASELINE"
            if status == "CHAMPION_OR_BASELINE":
                life = "CHAMPION"
        elif "CHALLENGER" in status:
            life = "CHALLENGER"
        elif "CANDIDATE" in status:
            life = "CANDIDATE"
        elif "REJECT" in status:
            life = "REJECTED"
        elif "ARCHIVE" in status:
            life = "ARCHIVED"
        else:
            life = "CHALLENGER" if sid.upper() != "V1" else "CHAMPION"
        out[sid] = {
            "strategy_id": sid,
            "lifecycle_state": life,
            "runtime_arm": s.get("runtime_arm"),
            "strategy_class": s.get("strategy_class"),
            "experimental_only": bool(s.get("experimental_only", False)),
            "enabled_in_parallel_paper": bool(s.get("enabled_in_parallel_paper", False)),
            "baseline_role": sid.upper() == "V1",
            "promotion_state": "HUMAN_GATED",
            "live_allowed": False,
            "execution_mode": EXECUTION_MODE,
        }
    return out


def default_promotion_state(reg: dict[str, Any] | None = None) -> dict[str, Any]:
    reg = reg or load_registry_identity()
    strategies = _seed_strategies_from_registry(reg)
    champion = next(
        (sid for sid, row in strategies.items() if row.get("lifecycle_state") == "CHAMPION"),
        None,
    )
    return {
        "schema": "tae.strategy_lab.promotion_state.v1",
        "promotion_domain": PROMOTION_DOMAIN,
        "execution_mode": EXECUTION_MODE,
        "live_allowed": False,
        "auto_promote": False,
        "autonomous_paper_evolution": {
            "enabled": False,
            "domain": AUTONOMOUS_PAPER_EVOLUTION_DOMAIN,
            "live_allowed": False,
            "paused_at": None,
            "pause_reason": None,
        },
        "updated_at": _now(),
        "champion_strategy_id": champion,
        "strategies": strategies,
        "open_ticket_ids": [],
        "last_applied_ticket_id": None,
        "notes": "Lab PAPER promotion domain only. LIVE forbidden. Human approval required.",
    }


def load_promotion_state(*, create_if_missing: bool = True) -> dict[str, Any]:
    doc = _read_json(PROMOTION_STATE_PATH)
    if doc is None:
        if not create_if_missing:
            return default_promotion_state()
        doc = default_promotion_state()
        _atomic_write_json(PROMOTION_STATE_PATH, doc)
        audit("PROMOTION_STATE_SEEDED", {"champion": doc.get("champion_strategy_id")})
        return doc
    doc["live_allowed"] = False
    doc["auto_promote"] = False
    doc["execution_mode"] = EXECUTION_MODE
    doc["promotion_domain"] = PROMOTION_DOMAIN
    doc.setdefault(
        "autonomous_paper_evolution",
        {
            "enabled": False,
            "domain": AUTONOMOUS_PAPER_EVOLUTION_DOMAIN,
            "live_allowed": False,
            "paused_at": None,
            "pause_reason": None,
        },
    )
    seeded = _seed_strategies_from_registry(load_registry_identity())
    strategies = dict(doc.get("strategies") or {})
    for sid, row in seeded.items():
        if sid not in strategies:
            strategies[sid] = row
    doc["strategies"] = strategies
    return doc


def save_promotion_state(doc: dict[str, Any]) -> Path:
    doc = dict(doc)
    doc["live_allowed"] = False
    doc["auto_promote"] = False
    doc["execution_mode"] = EXECUTION_MODE
    doc["promotion_domain"] = PROMOTION_DOMAIN
    doc["updated_at"] = _now()
    # Enforce single champion
    champs = [
        sid
        for sid, row in (doc.get("strategies") or {}).items()
        if isinstance(row, dict) and row.get("lifecycle_state") == "CHAMPION"
    ]
    if len(champs) > 1:
        raise ValueError(f"MULTIPLE_CHAMPIONS_FORBIDDEN:{champs}")
    doc["champion_strategy_id"] = champs[0] if champs else None
    _atomic_write_json(PROMOTION_STATE_PATH, doc)
    return PROMOTION_STATE_PATH


def load_champion_archive() -> dict[str, Any]:
    doc = _read_json(CHAMPION_ARCHIVE_PATH)
    if doc is None:
        return {
            "schema": "tae.strategy_lab.champion_archive.v1",
            "promotion_domain": PROMOTION_DOMAIN,
            "entries": [],
        }
    return doc


def save_champion_archive(doc: dict[str, Any]) -> Path:
    doc = dict(doc)
    doc["promotion_domain"] = PROMOTION_DOMAIN
    doc["updated_at"] = _now()
    _atomic_write_json(CHAMPION_ARCHIVE_PATH, doc)
    return CHAMPION_ARCHIVE_PATH


def validate_transition(from_state: str, to_state: str) -> dict[str, Any]:
    fr = _s(from_state).upper()
    to = _s(to_state).upper()
    if fr not in LIFECYCLE_STATES or to not in LIFECYCLE_STATES:
        return {"ok": False, "reason": "UNKNOWN_STATE", "from": fr, "to": to}
    allowed = ALLOWED_TRANSITIONS.get(fr, frozenset())
    if to not in allowed:
        return {
            "ok": False,
            "reason": "TRANSITION_FORBIDDEN",
            "from": fr,
            "to": to,
            "allowed": sorted(allowed),
        }
    return {"ok": True, "from": fr, "to": to}


def live_lock_observe() -> dict[str, Any]:
    """Observe live promotion lock — never unlock or mutate LIVE."""
    try:
        import tae_live_promotion_lock as lock

        return {
            "ok": True,
            "module": "tae_live_promotion_lock",
            "live_allowed": False,
            "auto_promote": False,
            "note": "observe_only; Sprint4 never calls enforce to enable LIVE",
            "has_enforce": hasattr(lock, "enforce_promotion_gate"),
            "has_audit": hasattr(lock, "run_live_promotion_lock_audit"),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "live_allowed": False, "auto_promote": False}


def build_promotion_recommendation(
    *,
    research: dict[str, Any],
    replay: dict[str, Any],
    health: dict[str, Any],
    economics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Read-only recommendation. Never applies. Wraps existing gate/research evidence.
    """
    state = load_promotion_state(create_if_missing=True)
    gate = research.get("promotion_gate") or {}
    evo = research.get("strategy_evolution") or {}
    replay_state = replay.get("replay_state")
    recon_pass = health.get("reconciliation_pass")
    live = live_lock_observe()

    blockers: list[str] = []
    if not recon_pass:
        blockers.append("RECONCILIATION_NOT_PASS")
    if replay_state == "MISSING":
        blockers.append("REPLAY_MISSING")
    if live.get("live_allowed") is True:
        blockers.append("LIVE_ALLOWED_UNEXPECTED")

    gate_entries = gate.get("entries") or []
    review_id = gate.get("review_candidate_id")
    eligible_gate = any(
        isinstance(e, dict)
        and _s(e.get("decision")).upper() in {"PROMOTION_REVIEW_ELIGIBLE", "ELIGIBLE"}
        for e in gate_entries
    )
    if gate_entries and not eligible_gate and not review_id:
        # Gate present but no eligible review candidate — advisory blocker for promote.
        blocked = [
            e
            for e in gate_entries
            if isinstance(e, dict) and e.get("blockers")
        ]
        if blocked:
            blockers.append("RESEARCH_PROMOTION_GATE_BLOCKED")

    champion = state.get("champion_strategy_id")
    challengers = [
        sid
        for sid, row in (state.get("strategies") or {}).items()
        if isinstance(row, dict) and row.get("lifecycle_state") == "CHALLENGER"
    ]

    recommended_action = "HOLD_HUMAN_REVIEW"
    recommended_strategy = None
    if challengers and recon_pass and replay_state != "MISSING":
        recommended_action = "CONSIDER_PROMOTE_TO_CHAMPION"
        recommended_strategy = challengers[0]
    if blockers:
        recommended_action = "NOT_READY"

    return {
        "schema": "tae.strategy_lab.promotion_recommendation.v1",
        "generated_at": _now(),
        "promotion_domain": PROMOTION_DOMAIN,
        "execution_mode": EXECUTION_MODE,
        "live_allowed": False,
        "auto_promote": False,
        "applies_changes": False,
        "champion_strategy_id": champion,
        "challenger_strategy_ids": challengers,
        "recommended_action": recommended_action,
        "recommended_strategy_id": recommended_strategy,
        "blockers": blockers,
        "evidence": {
            "research_completeness": evo.get("completeness"),
            "research_verdict": evo.get("daily_runner_verdict") or evo.get("verdict"),
            "promotion_gate_verdict": gate.get("verdict"),
            "promotion_gate_review_candidate_id": review_id,
            "replay_state": replay_state,
            "replay_recommendation": (replay.get("chronological") or {}).get("recommendation")
            if isinstance(replay.get("chronological"), dict)
            else None,
            "reconciliation_pass": recon_pass,
            "roi_global_verdict": ((economics or {}).get("roi001") or {}).get("verdict")
            if economics
            else None,
            "live_lock": live,
            "gate_owner": "research_core/strategy_evolution/promotion_gate.py",
        },
        "human_required": True,
        "produces_promotion": False,
    }


def create_ticket(
    *,
    ticket_type: str,
    strategy_id: str,
    target_state: str,
    requested_by: str,
    rationale: str = "",
    rollback_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ttype = _s(ticket_type).upper()
    if ttype not in TICKET_TYPES:
        return {"ok": False, "reason": "UNKNOWN_TICKET_TYPE", "ticket_type": ttype}
    sid = _s(strategy_id)
    to_state = _s(target_state).upper()
    state = load_promotion_state(create_if_missing=True)
    row = dict((state.get("strategies") or {}).get(sid) or {})
    if not row:
        return {"ok": False, "reason": "STRATEGY_NOT_IN_PROMOTION_STATE", "strategy_id": sid}
    fr = _s(row.get("lifecycle_state")).upper()
    check = validate_transition(fr, to_state)
    if not check.get("ok"):
        audit("TICKET_CREATE_REJECTED", {"strategy_id": sid, "check": check, "ticket_type": ttype})
        return {"ok": False, **check}

    auto_apply = to_state in AUTO_APPROVED_TRANSITIONS.get(fr, frozenset())

    ticket = {
        "ticket_id": f"PLT-{uuid.uuid4().hex[:12].upper()}",
        "schema": "tae.strategy_lab.promotion_ticket.v1",
        "created_at": _now(),
        "ticket_type": ttype,
        "promotion_domain": PROMOTION_DOMAIN,
        "execution_mode": EXECUTION_MODE,
        "live_allowed": False,
        "auto_promote": False,
        "strategy_id": sid,
        "from_state": fr,
        "to_state": to_state,
        "status": TICKET_APPLIED if auto_apply else TICKET_OPEN,
        "requested_by": _s(requested_by) or "UNKNOWN",
        "rationale": _s(rationale),
        "approver": "TAE_STRATEGY_LAB_AUTO_GATE" if auto_apply else None,
        "approved_at": _now() if auto_apply else None,
        "applied_at": _now() if auto_apply else None,
        "human_approval": not auto_apply,
        "auto_applied": auto_apply,
        "rollback_plan": rollback_plan
        or {
            "previous_champion_id": state.get("champion_strategy_id"),
            "restore_on_rollback": True,
        },
    }
    _append_jsonl(PROMOTION_TICKETS_PATH, ticket)

    if auto_apply:
        strategies = dict(state.get("strategies") or {})
        row["lifecycle_state"] = to_state
        row["last_transition_at"] = _now()
        row["last_ticket_id"] = ticket["ticket_id"]
        row["live_allowed"] = False
        strategies[sid] = row
        state["strategies"] = strategies
        save_promotion_state(state)
        audit(
            "TICKET_AUTO_APPLIED",
            {
                "ticket_id": ticket["ticket_id"],
                "ticket_type": ttype,
                "strategy_id": sid,
                "from": fr,
                "to": to_state,
            },
        )
        return {"ok": True, "ticket": ticket, "auto_applied": True, "live_mutation": False}

    open_ids = list(state.get("open_ticket_ids") or [])
    open_ids.append(ticket["ticket_id"])
    state["open_ticket_ids"] = open_ids
    save_promotion_state(state)
    audit("TICKET_CREATED", {"ticket_id": ticket["ticket_id"], "ticket_type": ttype, "strategy_id": sid})
    return {"ok": True, "ticket": ticket}


def _integrity_gate(value: dict[str, Any]) -> bool:
    for key in (
        "accounting_integrity",
        "accounting_status",
        "data_integrity",
        "data_integrity_status",
        "execution_integrity",
        "execution_status",
        "reconciliation_pass",
        "contamination",
    ):
        if key not in value:
            continue
        item = value.get(key)
        if key == "contamination" and item not in (None, False, "", "NONE", "PASS"):
            return False
        if item is False or str(item).upper() in {
            "FAIL",
            "FAILED",
            "INVALID",
            "REJECTED",
            "CONTAMINATED",
        }:
            return False
        if isinstance(item, dict) and (
            item.get("ok") is False
            or item.get("pass") is False
            or str(item.get("status") or "").upper()
            in {"FAIL", "FAILED", "INVALID", "REJECTED"}
        ):
            return False
    return True


def _autonomous_gate(cycle: dict[str, Any]) -> dict[str, Any]:
    remaining = cycle.get("remaining_evidence")
    if isinstance(remaining, dict):
        ready = remaining.get("wait_status") == "READY_FOR_REEVALUATION"
    else:
        ready = str(remaining or "").lower() == "ready"
    metrics = cycle.get("lifecycle_metrics") or cycle.get("metrics") or cycle
    closed = int(metrics.get("closed_cycles") or cycle.get("closed_cycles") or 0)
    days = int(metrics.get("observation_days") or cycle.get("observation_days") or 0)
    expectancy = metrics.get(
        "expectancy_per_closed_cycle",
        cycle.get("expectancy", cycle.get("expectancy_positive")),
    )
    expectancy_positive = (
        expectancy is True
        if isinstance(expectancy, bool)
        else expectancy is not None and float(expectancy) > 0
    )
    pnl_delta = metrics.get(
        "pnl_delta",
        cycle.get("pnl_delta", cycle.get("profit_effect", cycle.get("pnl_delta_positive"))),
    )
    pnl_delta_positive = (
        pnl_delta is True
        if isinstance(pnl_delta, bool)
        else pnl_delta is not None and float(pnl_delta) > 0
    )
    checks = {
        "remaining_evidence_ready": ready,
        "closed_cycles_30": closed >= 30,
        "observation_days_20": days >= 20,
        "expectancy_positive": expectancy_positive,
        "pnl_delta_positive": pnl_delta_positive,
        "integrity_pass": _integrity_gate({**cycle, **metrics}),
    }
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "closed_cycles": closed,
        "observation_days": days,
        "reason": (
            "AUTONOMOUS_ECONOMIC_GATE_PASS"
            if all(checks.values())
            else "AUTO_PROMOTION_BLOCKED_NO_CANONICAL_GATE"
        ),
    }


def create_autonomous_paper_ticket(
    cycle: dict[str, Any] | None = None,
    *,
    strategy_id: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a machine-approved ticket scoped strictly to autonomous PAPER."""
    source = dict(cycle or evidence or {})
    sid = _s(strategy_id or source.get("strategy_id") or source.get("challenger_strategy"))
    gate = _autonomous_gate(source)
    ticket = {
        "ticket_id": f"APT-{uuid.uuid4().hex[:12].upper()}",
        "schema": "tae.strategy_lab.autonomous_paper_ticket.v1",
        "created_at": _now(),
        "ticket_type": "PROMOTE_TO_CHAMPION",
        "promotion_domain": AUTONOMOUS_PAPER_EVOLUTION_DOMAIN,
        "approval_type": "AUTONOMOUS_ECONOMIC_GATE",
        "approved_by": "TAE_SELF_IMPROVEMENT",
        "execution_mode": "PAPER",
        "live_allowed": False,
        "human_approval": False,
        "auto_promote": True,
        "strategy_id": sid,
        "from_state": "CHALLENGER",
        "to_state": "CHAMPION",
        "status": "AUTO_APPROVED" if gate["ok"] else "BLOCKED",
        "economic_gate": gate,
        "cycle": source,
    }
    _append_jsonl(PROMOTION_TICKETS_PATH, ticket)
    audit(
        "AUTONOMOUS_PAPER_TICKET_CREATED",
        {"ticket_id": ticket["ticket_id"], "strategy_id": sid, "gate": gate},
        domain=AUTONOMOUS_PAPER_EVOLUTION_DOMAIN,
        auto_promote=True,
    )
    return {"ok": gate["ok"], "ticket": ticket, "reason": gate["reason"]}


def apply_autonomous_paper_promotion(ticket_or_cycle: dict[str, Any]) -> dict[str, Any]:
    """Apply only an economic-gated PAPER promotion; LIVE remains impossible."""
    from tae_self_improve_evolution import (
        IMMUTABLE_BASELINES,
        append_lineage,
        is_autonomy_enabled,
    )

    wrapped = ticket_or_cycle.get("ticket")
    ticket = dict(wrapped if isinstance(wrapped, dict) else ticket_or_cycle)
    if ticket.get("promotion_domain") != AUTONOMOUS_PAPER_EVOLUTION_DOMAIN:
        created = create_autonomous_paper_ticket(ticket)
        if not created.get("ok"):
            return created
        ticket = created["ticket"]
    if not is_autonomy_enabled():
        return {"ok": False, "reason": "AUTONOMOUS_PAPER_EVOLUTION_DISABLED"}
    if (
        ticket.get("promotion_domain") != AUTONOMOUS_PAPER_EVOLUTION_DOMAIN
        or ticket.get("execution_mode") != "PAPER"
        or ticket.get("live_allowed") is not False
    ):
        return {"ok": False, "reason": "AUTONOMOUS_DOMAIN_OR_MODE_INVALID"}
    source = ticket.get("cycle") if isinstance(ticket.get("cycle"), dict) else ticket
    gate = ticket.get("economic_gate") or _autonomous_gate(source)
    if not gate.get("ok"):
        return {
            "ok": False,
            "reason": "AUTO_PROMOTION_BLOCKED_NO_CANONICAL_GATE",
            "economic_gate": gate,
        }
    sid = _s(ticket.get("strategy_id") or source.get("strategy_id"))
    if not sid or sid.upper() in IMMUTABLE_BASELINES:
        return {"ok": False, "reason": "AUTONOMOUS_STRATEGY_ID_INVALID"}
    state = load_promotion_state(create_if_missing=True)
    block = state.get("autonomous_paper_evolution") or {}
    if block.get("enabled") is not True or block.get("live_allowed") is not False:
        return {"ok": False, "reason": "AUTONOMOUS_PAPER_EVOLUTION_DISABLED"}
    strategies = dict(state.get("strategies") or {})
    row = dict(strategies.get(sid) or {})
    row.update(
        {
            "strategy_id": sid,
            "lifecycle_state": "CHAMPION",
            "paper_champion_status": "PAPER_CHAMPION_ACTIVE",
            "promotion_domain": AUTONOMOUS_PAPER_EVOLUTION_DOMAIN,
            "execution_mode": "PAPER",
            "live_allowed": False,
            "last_transition_at": _now(),
            "last_ticket_id": ticket.get("ticket_id"),
        }
    )
    previous = state.get("champion_strategy_id")
    if previous and previous != sid:
        previous_row = dict(strategies.get(previous) or {})
        previous_row.update(
            {
                "lifecycle_state": "ARCHIVED",
                "paper_champion_status": "PAPER_CHAMPION_ARCHIVED",
                "archived_at": _now(),
                "live_allowed": False,
            }
        )
        strategies[previous] = previous_row
        _archive_champion_entry(
            strategy_id=previous,
            reason="REPLACED_BY_AUTONOMOUS_PAPER_PROMOTION",
            ticket_id=str(ticket.get("ticket_id")),
            state_row=previous_row,
        )
        if previous.upper() not in IMMUTABLE_BASELINES:
            append_lineage(
                {
                    **previous_row,
                    "strategy_id": previous,
                    "lineage_event_id": f"LIN-ARCHIVE-{uuid.uuid4().hex[:12].upper()}",
                    "status": "PAPER_CHAMPION_ARCHIVED",
                    "execution_mode": "PAPER",
                    "live_allowed": False,
                }
            )
    strategies[sid] = row
    state["strategies"] = strategies
    state["champion_strategy_id"] = sid
    state["autonomous_paper_champion_id"] = sid
    state["last_autonomous_ticket_id"] = ticket.get("ticket_id")
    save_promotion_state(state)
    lineage = dict(source.get("lineage") or {})
    append_lineage(
        {
            **lineage,
            "strategy_id": sid,
            "strategy_version": source.get("strategy_version") or sid,
            "parent_strategy_id": source.get("parent_strategy_id")
            or source.get("control_strategy")
            or lineage.get("parent_strategy_id"),
            "generation": source.get("generation") or lineage.get("generation"),
            "single_change": source.get("single_change")
            or (source.get("proposed_solution") or {}).get("single_change")
            or lineage.get("single_change"),
            "lineage_event_id": f"LIN-PROMOTE-{uuid.uuid4().hex[:12].upper()}",
            "status": "PAPER_CHAMPION_ACTIVE",
            "economic_gate": gate,
            "execution_mode": "PAPER",
            "live_allowed": False,
            "promoted_at": _now(),
        }
    )
    audit(
        "AUTONOMOUS_PAPER_PROMOTED",
        {"strategy_id": sid, "previous_champion_id": previous, "ticket_id": ticket.get("ticket_id")},
        domain=AUTONOMOUS_PAPER_EVOLUTION_DOMAIN,
        auto_promote=True,
    )
    return {
        "ok": True,
        "status": "AUTO_PAPER_PROMOTED",
        "strategy_id": sid,
        "previous_champion_id": previous,
        "paper_champion_status": "PAPER_CHAMPION_ACTIVE",
        "human_approval_required": False,
        "live_promotion_performed": False,
        "auto_promote": True,
        "promotion_domain": AUTONOMOUS_PAPER_EVOLUTION_DOMAIN,
    }


def _load_ticket(ticket_id: str) -> dict[str, Any] | None:
    tid = _s(ticket_id)
    for row in reversed(_read_jsonl(PROMOTION_TICKETS_PATH)):
        if _s(row.get("ticket_id")) == tid:
            return row
    return None


def _rewrite_ticket(ticket: dict[str, Any]) -> None:
    """Append superseding ticket snapshot (append-only audit; latest wins by ticket_id)."""
    ticket = dict(ticket)
    ticket["updated_at"] = _now()
    _append_jsonl(PROMOTION_TICKETS_PATH, ticket)


def approve_ticket(*, ticket_id: str, approver: str, note: str = "") -> dict[str, Any]:
    ticket = _load_ticket(ticket_id)
    if not ticket:
        return {"ok": False, "reason": "TICKET_NOT_FOUND", "ticket_id": ticket_id}
    if ticket.get("status") != TICKET_OPEN:
        return {"ok": False, "reason": "TICKET_NOT_PENDING", "status": ticket.get("status")}
    if not _s(approver):
        return {"ok": False, "reason": "APPROVER_REQUIRED"}
    ticket["status"] = TICKET_APPROVED
    ticket["approver"] = _s(approver)
    ticket["approved_at"] = _now()
    ticket["approval_note"] = _s(note)
    ticket["auto_promote"] = False
    ticket["live_allowed"] = False
    _rewrite_ticket(ticket)
    audit(
        "TICKET_APPROVED",
        {"ticket_id": ticket_id, "approver": approver, "strategy_id": ticket.get("strategy_id")},
    )
    return {"ok": True, "ticket": ticket}


def reject_ticket(*, ticket_id: str, approver: str, note: str = "") -> dict[str, Any]:
    ticket = _load_ticket(ticket_id)
    if not ticket:
        return {"ok": False, "reason": "TICKET_NOT_FOUND", "ticket_id": ticket_id}
    if ticket.get("status") not in {TICKET_OPEN, TICKET_APPROVED}:
        return {"ok": False, "reason": "TICKET_NOT_REJECTABLE", "status": ticket.get("status")}
    ticket["status"] = TICKET_REJECTED
    ticket["approver"] = _s(approver) or ticket.get("approver")
    ticket["rejected_at"] = _now()
    ticket["rejection_note"] = _s(note)
    _rewrite_ticket(ticket)
    state = load_promotion_state(create_if_missing=True)
    state["open_ticket_ids"] = [
        x for x in (state.get("open_ticket_ids") or []) if x != ticket_id
    ]
    save_promotion_state(state)
    audit("TICKET_REJECTED", {"ticket_id": ticket_id, "approver": approver})
    return {"ok": True, "ticket": ticket}


def _archive_champion_entry(
    *,
    strategy_id: str,
    reason: str,
    ticket_id: str,
    state_row: dict[str, Any],
) -> dict[str, Any]:
    arch = load_champion_archive()
    entry = {
        "archive_id": f"ARC-{uuid.uuid4().hex[:10].upper()}",
        "archived_at": _now(),
        "strategy_id": strategy_id,
        "reason": reason,
        "ticket_id": ticket_id,
        "snapshot": dict(state_row),
        "deleted": False,
        "note": "Archive is historical state, not deletion",
    }
    entries = list(arch.get("entries") or [])
    entries.append(entry)
    arch["entries"] = entries
    save_champion_archive(arch)
    return entry


def apply_ticket(*, ticket_id: str) -> dict[str, Any]:
    """
    Apply an APPROVED human ticket. Fail-closed. Never mutates LIVE or books.
    """
    ticket = _load_ticket(ticket_id)
    if not ticket:
        return {"ok": False, "reason": "TICKET_NOT_FOUND", "ticket_id": ticket_id}
    if ticket.get("status") != TICKET_APPROVED:
        return {"ok": False, "reason": "HUMAN_APPROVAL_REQUIRED", "status": ticket.get("status")}
    if ticket.get("live_allowed") is True or ticket.get("auto_promote") is True:
        return {"ok": False, "reason": "FORBIDDEN_LIVE_OR_AUTO_FLAGS"}

    sid = _s(ticket.get("strategy_id"))
    to_state = _s(ticket.get("to_state")).upper()
    state = load_promotion_state(create_if_missing=True)
    strategies = dict(state.get("strategies") or {})
    row = dict(strategies.get(sid) or {})
    if not row:
        return {"ok": False, "reason": "STRATEGY_NOT_IN_PROMOTION_STATE", "strategy_id": sid}
    fr = _s(row.get("lifecycle_state")).upper()
    # Allow ticket.from_state mismatch only if current matches ticket.from_state
    if fr != _s(ticket.get("from_state")).upper():
        return {
            "ok": False,
            "reason": "STATE_DRIFT",
            "current": fr,
            "ticket_from": ticket.get("from_state"),
        }
    check = validate_transition(fr, to_state)
    if not check.get("ok"):
        audit("APPLY_REJECTED", {"ticket_id": ticket_id, "check": check})
        return {"ok": False, **check}

    archive_entry = None
    # Promoting to CHAMPION: archive previous champion first.
    if to_state == "CHAMPION":
        prev = state.get("champion_strategy_id")
        if prev and prev != sid:
            prev_row = dict(strategies.get(prev) or {})
            prev_life = _s(prev_row.get("lifecycle_state")).upper()
            if prev_life == "CHAMPION":
                chk = validate_transition("CHAMPION", "ARCHIVED")
                if not chk.get("ok"):
                    return {"ok": False, "reason": "CANNOT_ARCHIVE_PREV_CHAMPION", **chk}
                archive_entry = _archive_champion_entry(
                    strategy_id=prev,
                    reason="REPLACED_BY_PROMOTION",
                    ticket_id=ticket_id,
                    state_row=prev_row,
                )
                prev_row["lifecycle_state"] = "ARCHIVED"
                prev_row["archived_at"] = _now()
                prev_row["archived_by_ticket"] = ticket_id
                strategies[prev] = prev_row

    row["lifecycle_state"] = to_state
    row["last_transition_at"] = _now()
    row["last_ticket_id"] = ticket_id
    row["live_allowed"] = False
    strategies[sid] = row

    # Single champion invariant
    champs = [k for k, v in strategies.items() if v.get("lifecycle_state") == "CHAMPION"]
    if len(champs) > 1:
        return {"ok": False, "reason": "MULTIPLE_CHAMPIONS_FORBIDDEN", "champions": champs}

    state["strategies"] = strategies
    state["champion_strategy_id"] = champs[0] if champs else None
    state["open_ticket_ids"] = [
        x for x in (state.get("open_ticket_ids") or []) if x != ticket_id
    ]
    state["last_applied_ticket_id"] = ticket_id
    save_promotion_state(state)

    ticket["status"] = TICKET_APPLIED
    ticket["applied_at"] = _now()
    _rewrite_ticket(ticket)
    audit(
        "TICKET_APPLIED",
        {
            "ticket_id": ticket_id,
            "strategy_id": sid,
            "from": fr,
            "to": to_state,
            "archive_id": None if not archive_entry else archive_entry.get("archive_id"),
            "champion": state.get("champion_strategy_id"),
        },
    )
    return {
        "ok": True,
        "ticket": ticket,
        "promotion_state": state,
        "archive_entry": archive_entry,
        "live_mutation": False,
        "books_written": False,
        "auto_promote": False,
    }


def request_rollback(
    *,
    to_strategy_id: str,
    requested_by: str,
    rationale: str = "",
) -> dict[str, Any]:
    """Create rollback ticket: ARCHIVED → ROLLBACK_CANDIDATE (then promote via apply after approve)."""
    state = load_promotion_state(create_if_missing=True)
    sid = _s(to_strategy_id)
    row = (state.get("strategies") or {}).get(sid)
    if not row:
        return {"ok": False, "reason": "STRATEGY_NOT_IN_PROMOTION_STATE", "strategy_id": sid}
    life = _s(row.get("lifecycle_state")).upper()
    if life != "ARCHIVED":
        # Allow creating ROLLBACK path only from ARCHIVED per state model.
        return {
            "ok": False,
            "reason": "ROLLBACK_REQUIRES_ARCHIVED",
            "lifecycle_state": life,
        }
    return create_ticket(
        ticket_type="ROLLBACK_CHAMPION",
        strategy_id=sid,
        target_state="ROLLBACK_CANDIDATE",
        requested_by=requested_by,
        rationale=rationale or "Rollback previous champion to ROLLBACK_CANDIDATE",
        rollback_plan={
            "previous_champion_id": state.get("champion_strategy_id"),
            "restore_strategy_id": sid,
            "next_step_after_apply": "PROMOTE_TO_CHAMPION_VIA_SECOND_TICKET",
        },
    )


def promote_rollback_candidate_to_champion(
    *,
    strategy_id: str,
    requested_by: str,
    rationale: str = "",
) -> dict[str, Any]:
    """Second-step ticket: ROLLBACK_CANDIDATE → CHAMPION (still human-gated)."""
    return create_ticket(
        ticket_type="ROLLBACK_CHAMPION",
        strategy_id=strategy_id,
        target_state="CHAMPION",
        requested_by=requested_by,
        rationale=rationale or "Complete rollback: ROLLBACK_CANDIDATE → CHAMPION",
    )


def list_tickets(*, status: str | None = None) -> list[dict[str, Any]]:
    rows = _read_jsonl(PROMOTION_TICKETS_PATH)
    # Latest snapshot per ticket_id
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        tid = _s(row.get("ticket_id"))
        if tid:
            latest[tid] = row
    out = list(latest.values())
    if status:
        st = _s(status).upper()
        out = [r for r in out if _s(r.get("status")).upper() == st]
    out.sort(key=lambda r: _s(r.get("created_at")))
    return out


def _relpath(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def promotion_status() -> dict[str, Any]:
    state = load_promotion_state(create_if_missing=True)
    return {
        "schema": "tae.strategy_lab.promotion_status.v1",
        "generated_at": _now(),
        "promotion_domain": PROMOTION_DOMAIN,
        "execution_mode": EXECUTION_MODE,
        "live_allowed": False,
        "auto_promote": False,
        "champion_strategy_id": state.get("champion_strategy_id"),
        "strategies": state.get("strategies"),
        "open_ticket_ids": state.get("open_ticket_ids"),
        "pending_tickets": list_tickets(status=TICKET_OPEN),
        "approved_tickets": list_tickets(status=TICKET_APPROVED),
        "archive_count": len((load_champion_archive().get("entries") or [])),
        "live_lock": live_lock_observe(),
        "paths": {
            "promotion_state": _relpath(PROMOTION_STATE_PATH),
            "tickets": _relpath(PROMOTION_TICKETS_PATH),
            "audit": _relpath(PROMOTION_AUDIT_PATH),
            "archive": _relpath(CHAMPION_ARCHIVE_PATH),
        },
    }


__all__ = [
    "ALLOWED_TRANSITIONS",
    "AUTO_APPROVED_TRANSITIONS",
    "AUTONOMOUS_PAPER_EVOLUTION_DOMAIN",
    "LIFECYCLE_STATES",
    "PROMOTION_DOMAIN",
    "apply_autonomous_paper_promotion",
    "apply_ticket",
    "approve_ticket",
    "build_promotion_recommendation",
    "create_autonomous_paper_ticket",
    "create_ticket",
    "list_tickets",
    "load_champion_archive",
    "load_promotion_state",
    "promotion_status",
    "promote_rollback_candidate_to_champion",
    "reject_ticket",
    "request_rollback",
    "validate_transition",
]
