#!/usr/bin/env python3
"""PAPER-only orchestration over existing TAE learning and experiment SSOTs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_self_improve_lifecycle import (
    LIVE_AUTONOMY,
    activate_paper_challenger,
    link_hypotheses_to_cycles,
    load_cycles,
    monitor_and_gate,
    run_experiment_scoring,
    run_replay_for_cycle,
)

PROJECT_ROOT = Path(__file__).resolve().parent
LTP_ROOT = PROJECT_ROOT / "runtime_outputs" / "learning_to_profit"
HYPOTHESES_PATH = LTP_ROOT / "hypotheses.json"
PAPER_QUEUE_PATH = LTP_ROOT / "paper_experiment_queue.jsonl"
EXPERIMENT_RESULTS_PATH = LTP_ROOT / "experiment_results.json"
ROI_QUEUE_PATH = PROJECT_ROOT / "tae_roi_queue.json"
ATTRIBUTION_PATH = PROJECT_ROOT / "tae_learning_economic_attribution.json"
POST_CLOSE_RUNS_PATH = LTP_ROOT / "self_improve" / "post_close_runs.jsonl"
DEFAULT_POST_CLOSE_LOG = PROJECT_ROOT / "runtime_outputs" / "self_improve_post_close.log"
POST_CLOSE_CRON_MARKER = "tae.py self-improve post-close"
RECOMMENDED_CRON = (
    "35 23 * * 1-5 cd {root} && {python} tae.py self-improve post-close"
    " >> {root}/runtime_outputs/self_improve_post_close.log 2>&1"
)
_CRON_CD_RE = re.compile(
    r"""\bcd\s+(?:"([^"]+)"|'([^']+)'|([^\s&;]+))""",
    re.IGNORECASE,
)
_CRON_PYTHON_RE = re.compile(
    r"""((?:/(?:[^\s]*)|~/[^\s]*|\./[^\s]*)python3?(?:\.\d+)?|python3(?:\.\d+)?)\s+"""
    r"""(?:-u\s+)?(?:["']?)tae\.py(?:["']?)\s+self-improve\s+post-close""",
)
_CRON_LOG_RE = re.compile(
    r""">>\s*(?:"([^"]+)"|'([^']+)'|([^\s]+))""",
)

ALL_STEPS = (
    "outcomes",
    "attribution",
    "hypotheses",
    "link",
    "scoring",
    "replay",
    "activate",
    "monitor",
    "evolve",
    "strategy_lab",
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_jsonl_count(path: Path) -> int:
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        rows = []
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
        return rows
    except (OSError, json.JSONDecodeError):
        return []


def collect_outcomes() -> dict[str, Any]:
    """Read existing journals without mutating either parallel book."""
    counts: dict[str, int] = {}
    for arm in ("v1", "v2"):
        for journal in ("trades", "executions", "decisions"):
            key = f"{arm}_{journal}"
            counts[key] = _read_jsonl_count(
                PROJECT_ROOT / f"runtime_outputs/parallel_paper/{arm}/journals/{journal}.jsonl"
            )
    return {"read_only": True, "journal_counts": counts, "records_seen": sum(counts.values())}


def _attribution(*, dry_run: bool) -> dict[str, Any]:
    artifact = _read_json(ATTRIBUTION_PATH)
    if artifact:
        return {"source": "existing_artifact", "available": True, "artifact": artifact}
    if dry_run:
        return {"source": "missing_artifact", "available": False, "write_skipped": True}
    try:
        from tae_learning_economic_attribution_engine import run_attribution

        return {"source": "measurement_run", "available": True, "artifact": run_attribution()}
    except Exception as exc:
        return {"source": "unavailable", "available": False, "error": str(exc)}


def _regenerate_hypotheses(*, dry_run: bool) -> dict[str, Any]:
    if dry_run:
        doc = _read_json(HYPOTHESES_PATH)
        return {"source": "existing_artifact", "hypothesis_count": len(doc.get("hypotheses") or []), "document": doc}
    try:
        import tae_learning_to_profit_bridge as bridge

        payloads, loaded = bridge.load_sources()
        report = bridge.build_bridge_report(payloads, loaded)
        bridge.write_outputs(report)
        return {"source": "bridge", "hypothesis_count": len(report.get("hypotheses") or []), "document": report}
    except Exception as exc:
        doc = _read_json(HYPOTHESES_PATH)
        return {
            "source": "artifact_fallback",
            "hypothesis_count": len(doc.get("hypotheses") or []),
            "document": doc,
            "error": str(exc),
        }


def _arm_account(arm: dict[str, Any]) -> dict[str, Any]:
    rel = str(arm.get("book_relpath") or "")
    if not rel:
        return {}
    return _read_json(PROJECT_ROOT / rel / "account.json")


def _experimental_day_counts(experimental_arms: list[Any]) -> dict[str, Any]:
    decisions = 0
    fills = 0
    pnl = 0.0
    account_values: dict[str, float] = {}
    drawdowns: dict[str, float] = {}
    expectancy: dict[str, float] = {}
    for arm in experimental_arms:
        if not isinstance(arm, dict):
            continue
        arm_id = str(arm.get("arm_id") or arm.get("strategy_id") or "UNKNOWN")
        account = _arm_account(arm)
        fills += int(account.get("fills") or 0)
        pnl += float(account.get("realized_pnl") or 0) + float(account.get("unrealized_pnl") or 0)
        if account:
            account_values[arm_id] = float(account.get("account_value") or 0)
            drawdowns[arm_id] = float(account.get("drawdown") or 0)
            expectancy[arm_id] = float(
                ((account.get("economic_attribution") or {}).get("expectancy_per_closed_cycle"))
                or account.get("total_pnl")
                or 0
            )
        rel = str(arm.get("book_relpath") or "")
        if rel:
            try:
                decisions += sum(
                    1
                    for line in (PROJECT_ROOT / rel / "journals" / "decisions.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                )
            except OSError:
                pass
    return {
        "EXPERIMENTAL_DECISIONS_TODAY": decisions,
        "EXPERIMENTAL_FILLS_TODAY": fills,
        "EXPERIMENTAL_PNL_TODAY": round(pnl, 6),
        "EXPERIMENTAL_ACCOUNT_VALUES": account_values,
        "EXPERIMENTAL_DRAWDOWNS": drawdowns,
        "EXPERIMENTAL_EXPECTANCY": expectancy,
    }


def build_status() -> dict[str, Any]:
    cycles = load_cycles(limit=10000)
    from tae_self_improve_evolution import (
        MUTATION_ALLOWLIST,
        current_paper_champion,
        get_evolution_control_strategy,
        is_autonomy_enabled,
        load_lineage,
    )

    lineage = load_lineage()
    champion = current_paper_champion()
    from tae_self_improve_experimental import (
        EXPERIMENTAL_ARMS_PATH,
        EXPERIMENTAL_REGISTRY_PATH,
    )

    registered = [
        row
        for row in (_read_json(EXPERIMENTAL_REGISTRY_PATH).get("strategies") or [])
        if isinstance(row, dict)
    ]
    experimental_arms = [
        row
        for row in (_read_json(EXPERIMENTAL_ARMS_PATH).get("arms") or [])
        if isinstance(row, dict)
    ]
    enabled_arms = [arm for arm in experimental_arms if arm.get("enabled") is True]
    counts: dict[str, int] = {}
    for cycle in cycles:
        status = str(cycle.get("status") or "UNKNOWN")
        counts[status] = counts.get(status, 0) + 1
    post_close_rows = _post_close_rows()
    last_post_close = post_close_rows[-1] if post_close_rows else None
    last_cycle = cycles[-1] if cycles else {}
    day_counts = _experimental_day_counts(experimental_arms)
    from tae_self_improve_wiring import validate_experiment_joins

    hypotheses_doc = _read_json(HYPOTHESES_PATH)
    ltp_queue = _read_jsonl(PAPER_QUEUE_PATH)
    roi_queue = _read_json(ROI_QUEUE_PATH)
    join_rows = []
    for cycle in cycles:
        hypothesis = next(
            (
                row
                for row in hypotheses_doc.get("hypotheses") or []
                if row.get("hypothesis_id") == cycle.get("hypothesis_id")
            ),
            cycle,
        )
        join_rows.append(
            {
                "learning_cycle_id": cycle.get("learning_cycle_id"),
                "economic_experiment_uid": cycle.get("economic_experiment_uid"),
                **validate_experiment_joins(
                    {
                        "cycle": cycle,
                        "hypothesis": hypothesis,
                        "roi_queue": roi_queue,
                        "ltp_queue": ltp_queue,
                        "replay": cycle.get("replay_summary"),
                        "self_improve": cycles,
                        "challenger": experimental_arms,
                        "strategy_lab": registered,
                    }
                ),
            }
        )
    experiment_results = _read_json(EXPERIMENT_RESULTS_PATH)
    promising_count = sum(
        1
        for row in experiment_results.get("experiments") or experiment_results.get("results") or []
        if str(row.get("verdict") or "").upper() == "PROMISING"
    )
    paper_edge = sum(
        1
        for row in cycles
        if row.get("status") in {"PAPER_SUPPORTED", "READY_FOR_HUMAN_PROMOTION"}
        or str(row.get("economic_status") or "").upper() in {"PAPER_EDGE_SUPPORTED", "POSITIVE_EXPECTANCY"}
    )
    schedule = schedule_status()
    waiting = [
        row.get("remaining_evidence") or {}
        for row in cycles
        if (row.get("remaining_evidence") or {}).get("wait_status")
        not in (None, "READY_FOR_REEVALUATION")
    ]
    next_evaluations = sorted(
        str(row.get("next_eligible_evaluation_at"))
        for row in waiting
        if row.get("next_eligible_evaluation_at")
    )
    def remaining_total(field: str) -> int:
        return sum(
            int(row.get(field) or 0)
            for row in waiting
            if isinstance(row.get(field), (int, float))
        )
    return {
        "SELF_IMPROVEMENT_STATUS": "ACTIVE" if cycles else "NO_CYCLES",
        "SELF_IMPROVEMENT_SCHEDULE": schedule,
        "LAST_POST_CLOSE_RUN": (last_post_close or {}).get("recorded_at")
        or (last_post_close or {}).get("ts"),
        "LAST_MONITOR_RUN": (last_post_close or {}).get("monitoring", {}).get("checked"),
        "ACTIVE_LEARNING_CYCLES": sum(
            counts.get(status, 0)
            for status in ("READY_FOR_EXPERIMENT", "REPLAY_SUPPORTED", "PAPER_RUNNING")
        ),
        "NEW_HYPOTHESES": counts.get("READY_FOR_EXPERIMENT", 0),
        "PENDING_EXPERIMENTS": counts.get("READY_FOR_EXPERIMENT", 0)
        + counts.get("REPLAY_SUPPORTED", 0),
        "ACTIVE_CHALLENGERS": counts.get("PAPER_RUNNING", 0),
        "ACTIVE_EXPERIMENTAL_ARMS": [
            {
                "arm_id": arm.get("arm_id"),
                "strategy_id": arm.get("strategy_id"),
                "learning_cycle_id": arm.get("learning_cycle_id"),
                "enabled": True,
            }
            for arm in enabled_arms
        ],
        "EXPERIMENTS_CREATED": len(cycles),
        "REPLAYS_RUN": sum(1 for row in cycles if row.get("replay_summary")),
        "PAPER_CHALLENGERS_ACTIVE": counts.get("PAPER_RUNNING", 0),
        "EXPERIMENTAL_CHALLENGERS_REGISTERED": len(registered),
        "EXPERIMENTAL_ARMS_ENABLED": len(enabled_arms),
        "ACTIVE_NOT_TRIGGERED": sum(
            1
            for arm in enabled_arms
            if int((_arm_account(arm).get("fills") or 0)) == 0
        ),
        "EXPERIMENTS_REJECTED": sum(
            1
            for row in cycles
            if row.get("status") == "REPLAY_REJECTED"
            or (row.get("replay_summary") or {}).get("status") == "REPLAY_REJECTED"
        ),
        "EXPERIMENTS_ROLLED_BACK": counts.get("ROLLED_BACK", 0),
        "PAPER_EDGE_SUPPORTED": paper_edge,
        "READY_FOR_HUMAN_PROMOTION": counts.get("READY_FOR_HUMAN_PROMOTION", 0),
        "LAST_HYPOTHESIS": last_cycle.get("hypothesis_id"),
        "LAST_SOLUTION": (last_cycle.get("proposed_solution") or {}).get("single_change")
        or last_cycle.get("single_change"),
        "LAST_EXPERIMENT": last_cycle.get("experiment_id") or last_cycle.get("learning_cycle_id"),
        "LAST_ECONOMIC_VERDICT": (last_cycle.get("replay_summary") or {}).get("verdict")
        or last_cycle.get("rollback_reason")
        or last_cycle.get("status"),
        "PROFIT_EFFECT": sum(float(row.get("profit_effect") or 0) for row in cycles),
        "LOSS_REDUCTION_EFFECT": sum(float(row.get("loss_reduction_effect") or 0) for row in cycles),
        "LEARNING_LOOP_CLOSED": any(
            row.get("status") in {"ROLLED_BACK", "READY_FOR_HUMAN_PROMOTION"} for row in cycles
        ),
        "SCHEDULE_ENABLED": bool(schedule.get("SCHEDULE_ENABLED")),
        "LIVE_AUTONOMY": LIVE_AUTONOMY,
        "AUTONOMOUS_PAPER_EVOLUTION_ENABLED": is_autonomy_enabled(),
        "AUTONOMOUS_PAPER_CHAMPION": (
            None if not champion else champion.get("strategy_id")
        ),
        "AUTONOMOUS_PAPER_CHAMPION_GENERATION": (
            None if not champion else champion.get("generation")
        ),
        "EVOLUTION_CONTROL_STRATEGY": get_evolution_control_strategy(),
        "STRATEGY_LINEAGE_RECORDS": len(lineage),
        "AUTONOMOUS_PAPER_PROMOTIONS": sum(
            1 for row in lineage if row.get("status") == "PAPER_CHAMPION_ACTIVE"
        ),
        "AUTONOMOUS_PAPER_ROLLBACKS": sum(
            1 for row in lineage if row.get("status") == "AUTO_ROLLED_BACK"
        ),
        "LAST_AUTONOMOUS_MUTATION": (
            None if not lineage else lineage[-1].get("single_change")
        ),
        "MUTATION_FAMILIES": sorted(MUTATION_ALLOWLIST),
        "V1_POLICY_CHANGED": False,
        "V2_POLICY_CHANGED": False,
        "NEEDS_MORE_DATA_EXPERIMENTS": len(waiting),
        "REMAINING_EVENTS": remaining_total("remaining_events"),
        "REMAINING_CYCLES": remaining_total("remaining_cycles"),
        "REMAINING_DAYS": remaining_total("remaining_days"),
        "REMAINING_OUTCOMES": remaining_total("remaining_outcomes"),
        "NEXT_REEVALUATION": next_evaluations[0] if next_evaluations else None,
        "PROMISING_EXPERIMENTS": promising_count,
        "REPLAY_SUPPORTED_EXPERIMENTS": counts.get("REPLAY_SUPPORTED", 0),
        "BEHAVIOR_COHORTS": len(
            {row.get("behavior_cohort_key") for row in cycles if row.get("behavior_cohort_key")}
        ),
        "GENERALIZED_BEHAVIOR_HYPOTHESES": sum(
            1
            for row in cycles
            if row.get("generalization_scope")
            in {"COHORT_HYPOTHESIS", "RULE_LEVEL_HYPOTHESIS"}
        ),
        "BEHAVIOR_PATTERNS_FOUND": len(
            {
                row.get("behavior_class")
                for row in cycles
                if row.get("behavior_class") and row.get("behavior_class") != "UNKNOWN"
            }
        ),
        "GENERALIZED_COHORTS": sum(
            1 for row in cycles if row.get("generalization_scope") == "COHORT_HYPOTHESIS"
        ),
        "TICKER_SPECIFIC_PATTERNS": sum(
            1
            for row in cycles
            if row.get("generalization_scope") == "TICKER_SPECIFIC_HYPOTHESIS"
        ),
        "UNKNOWN_BEHAVIOR_PATTERNS": sum(
            1 for row in cycles if row.get("behavior_class") in (None, "", "UNKNOWN")
        ),
        "TOP_LOSS_BEHAVIOR": next(
            (
                row.get("behavior_class")
                for row in cycles
                if row.get("behavior_class") not in (None, "", "UNKNOWN")
                and "LOSS" in str(row.get("hypothesis_type") or "").upper()
            ),
            None,
        ),
        "TOP_PROFIT_BEHAVIOR": None,
        "BEHAVIOR_ATTRIBUTED_PNL": sum(
            float(row.get("profit_effect") or row.get("loss_reduction_effect") or 0)
            for row in cycles
        ),
        "LATE_ENTRY_GENERALIZED": any(
            row.get("behavior_class") == "LATE_ENTRY"
            and row.get("generalization_scope") == "COHORT_HYPOTHESIS"
            for row in cycles
        ),
        "EXPERIMENT_JOIN_STATUS": {
            "conflicts": sum(1 for row in join_rows if row.get("activation_blocked")),
            "joined": sum(
                1
                for row in join_rows
                if row.get("SELF_IMPROVE_JOINED") == "PASS"
                and row.get("LTP_QUEUE_JOINED") in {"PASS", "MISSING", "LEGACY_ID_MAPPING", None}
            ),
        },
        "EXPERIMENT_JOIN_CONFLICTS": sum(
            1 for row in join_rows if row.get("activation_blocked")
        ),
        "UNJOINED_ROI_RECORDS": sum(
            1 for row in join_rows if row.get("ROI_QUEUE_JOINED") == "MISSING"
        ),
        "UNJOINED_LTP_RECORDS": sum(
            1 for row in join_rows if row.get("LTP_QUEUE_JOINED") == "MISSING"
        ),
        "AMBIGUOUS_LEGACY_MAPPINGS": sum(
            1
            for row in join_rows
            if "AMBIGUOUS" in {
                row.get("ROI_QUEUE_JOINED"),
                row.get("LTP_QUEUE_JOINED"),
                row.get("CHALLENGER_JOINED"),
                row.get("STRATEGY_LAB_JOINED"),
            }
        ),
        "EXPERIMENT_JOINS": join_rows,
        "LAST_ECONOMIC_EXPERIMENT_UID": last_cycle.get("economic_experiment_uid"),
        **day_counts,
        "cycles": cycles,
    }


def _strategy_lab_recommendation() -> dict[str, Any]:
    try:
        from tae_strategy_lab_facade import StrategyLabFacade

        return StrategyLabFacade().build_promotion_recommendation()
    except Exception as exc:
        return {"available": False, "error": str(exc), "auto_promote": False}


def _cycle_ready_now(cycle: dict[str, Any], *, at: datetime | None = None) -> bool:
    remaining = cycle.get("remaining_evidence") or {}
    wait_status = remaining.get("wait_status")
    if wait_status in (None, "READY_FOR_REEVALUATION"):
        return True
    next_at = remaining.get("next_eligible_evaluation_at")
    if not next_at:
        return False
    try:
        eligible_at = datetime.fromisoformat(str(next_at).replace("Z", "+00:00"))
    except ValueError:
        return False
    now = at or datetime.now(timezone.utc)
    return eligible_at <= now


def run_self_improve(*, dry_run: bool = False, steps: list[str] | None = None) -> dict[str, Any]:
    selected = set(steps or ALL_STEPS)
    result: dict[str, Any] = {
        "mode": "PAPER_ONLY",
        "dry_run": bool(dry_run),
        "schedule_enabled": bool(schedule_status().get("SCHEDULE_ENABLED")),
        "live_autonomy": False,
        "steps": {},
    }
    outcomes = collect_outcomes() if "outcomes" in selected else {}
    result["steps"]["outcomes"] = outcomes
    attribution = _attribution(dry_run=dry_run) if "attribution" in selected else {}
    result["steps"]["attribution"] = attribution
    hypotheses = _regenerate_hypotheses(dry_run=dry_run) if "hypotheses" in selected else {
        "document": _read_json(HYPOTHESES_PATH)
    }
    result["steps"]["hypotheses"] = {
        key: value for key, value in hypotheses.items() if key != "document"
    }
    hypotheses_doc = hypotheses.get("document") or _read_json(HYPOTHESES_PATH)

    if "link" in selected and not dry_run:
        created = link_hypotheses_to_cycles(hypotheses_doc)
    else:
        created = []
    result["steps"]["link"] = {"created": len(created), "cycles": created, "write_skipped": dry_run}

    if "scoring" in selected and not dry_run:
        result["steps"]["scoring"] = run_experiment_scoring()
    else:
        result["steps"]["scoring"] = {"write_skipped": True}

    replayed = []
    if "replay" in selected and not dry_run:
        for cycle in load_cycles(limit=10000):
            if cycle.get("status") == "READY_FOR_EXPERIMENT" and _cycle_ready_now(cycle):
                replayed.append(run_replay_for_cycle(str(cycle["learning_cycle_id"]), write=False))
    result["steps"]["replay"] = {"replays_run": len(replayed), "results": replayed, "write_skipped": dry_run}

    activated = []
    if "activate" in selected and not dry_run:
        for cycle in load_cycles(limit=10000):
            if cycle.get("status") == "REPLAY_SUPPORTED" and _cycle_ready_now(cycle):
                activated.append(activate_paper_challenger(str(cycle["learning_cycle_id"])))
    result["steps"]["activate"] = {"attempted": len(activated), "results": activated, "write_skipped": dry_run}

    monitored = []
    if "monitor" in selected and not dry_run:
        for cycle in load_cycles(limit=10000):
            if cycle.get("status") == "PAPER_RUNNING":
                monitored.append(monitor_and_gate(str(cycle["learning_cycle_id"])))
    result["steps"]["monitor"] = {"checked": len(monitored), "results": monitored, "write_skipped": dry_run}
    if "evolve" in selected and not dry_run:
        from tae_self_improve_evolution import evolve_autonomous_paper

        result["steps"]["evolve"] = evolve_autonomous_paper()
    else:
        result["steps"]["evolve"] = {"write_skipped": True}
    result["steps"]["strategy_lab"] = (
        _strategy_lab_recommendation() if "strategy_lab" in selected else {"skipped": True}
    )
    result["status"] = build_status()
    return result


def audit() -> dict[str, Any]:
    status = build_status()
    unsafe = [
        row.get("learning_cycle_id")
        for row in status["cycles"]
        if row.get("live_autonomy") is not False or row.get("mode") != "PAPER_ONLY"
    ]
    return {
        "ok": not unsafe,
        "unsafe_cycles": unsafe,
        "live_autonomy": False,
        "parallel_v3_enabled": False,
        "writes_v1_v2_books": False,
        "writes_experimental_books": True,
        "schedule_enabled": bool(status.get("SCHEDULE_ENABLED")),
    }


def explain() -> dict[str, Any]:
    cycles = build_status()["cycles"]
    return {
        "mode": "PAPER_ONLY",
        "latest_cycle": cycles[-1] if cycles else None,
        "policy": "Hypothesis -> scoring -> replay -> isolated PAPER -> human promotion gate",
        "live_autonomy": False,
    }


def monitor_active_challengers() -> dict[str, Any]:
    from tae_self_improve_experimental import monitor_active_challengers as monitor

    return monitor()


def _read_user_crontab_lines() -> tuple[list[str] | None, str | None]:
    """Read-only crontab inspection. Returns (lines, error). lines=None => unavailable."""
    try:
        proc = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None, "CRONTAB_UNAVAILABLE"
    except OSError as exc:
        return None, f"CRONTAB_ERROR:{exc}"
    stderr = (proc.stderr or "").strip()
    if proc.returncode != 0:
        if "no crontab" in stderr.lower():
            return [], None
        return None, f"CRONTAB_READ_FAILED:{proc.returncode}"
    return (proc.stdout or "").splitlines(), None


def _resolve_maybe(path_text: str | None) -> Path | None:
    if not path_text:
        return None
    try:
        return Path(path_text).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        return Path(path_text).expanduser()


def _configured_path(path_text: str | None) -> str | None:
    """Normalize a configured path without collapsing symlinks (e.g. venv/python3)."""
    if not path_text:
        return None
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return str(path)
    try:
        return str(path.resolve())
    except (OSError, RuntimeError, ValueError):
        return str(path)


def _extract_cd_dir(line: str) -> str | None:
    match = _CRON_CD_RE.search(line)
    if not match:
        return None
    return match.group(1) or match.group(2) or match.group(3)


def _extract_python(line: str) -> str | None:
    match = _CRON_PYTHON_RE.search(line)
    return match.group(1) if match else None


def _extract_log_path(line: str) -> str | None:
    match = _CRON_LOG_RE.search(line)
    if not match:
        return None
    return match.group(1) or match.group(2) or match.group(3)


def _python_path_valid(python: str | None, project_root: Path) -> bool:
    if not python:
        return False
    if "/" in python or python.startswith("~") or python.startswith("./"):
        path = Path(python).expanduser()
        if not path.is_file():
            # Allow broken absolute display paths that still resolve via symlink target.
            resolved = _resolve_maybe(python)
            path = resolved if resolved is not None else path
        return bool(path.is_file() and os.access(path, os.X_OK))
    found = shutil.which(python)
    if not found:
        return False
    return Path(found).is_file()


def _parse_post_close_cron_entry(
    line: str, *, project_root: Path
) -> dict[str, Any] | None:
    """Parse one active crontab line belonging to this project's post-close job."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if POST_CLOSE_CRON_MARKER not in stripped:
        return None

    cd_dir = _extract_cd_dir(stripped)
    project_resolved = project_root.resolve()
    if cd_dir:
        resolved_cd = _resolve_maybe(cd_dir)
        if resolved_cd is None or resolved_cd != project_resolved:
            return None
        project_dir = str(resolved_cd)
    else:
        # Accept absolute path references without cd only when they uniquely match.
        if str(project_resolved) not in stripped.replace('"', "").replace("'", ""):
            return None
        project_dir = str(project_resolved)

    tokens = stripped.split()
    if len(tokens) < 6:
        return None
    schedule = " ".join(tokens[:5])
    python_raw = _extract_python(stripped)
    python = _configured_path(python_raw) or (python_raw or "")
    log_raw = _extract_log_path(stripped)
    log_configured = _configured_path(log_raw)
    log_path = log_configured or str(
        project_resolved / "runtime_outputs" / "self_improve_post_close.log"
    )
    tae_script = project_resolved / "tae.py"
    project_dir_valid = Path(project_dir).is_dir()
    python_path_valid = _python_path_valid(python_raw or python, project_resolved)
    command_exists = tae_script.is_file()
    entry_valid = bool(
        project_dir_valid
        and python_path_valid
        and command_exists
        and bool(schedule)
        and POST_CLOSE_CRON_MARKER in stripped
    )
    return {
        "raw": stripped,
        "schedule": schedule,
        "project_dir": project_dir,
        "python": python,
        "command": POST_CLOSE_CRON_MARKER,
        "log_path": log_path,
        "project_dir_valid": project_dir_valid,
        "python_path_valid": python_path_valid,
        "command_exists": command_exists,
        "entry_valid": entry_valid,
    }


def _last_run_status(log_path: Path) -> tuple[str | None, str]:
    if not log_path.is_file():
        return None, "NOT_RUN_YET"
    try:
        modified = datetime.fromtimestamp(log_path.stat().st_mtime, tz=timezone.utc)
        last_log_modified = modified.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except OSError:
        return None, "UNKNOWN"
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return last_log_modified, "UNKNOWN"
    if not text.strip():
        return last_log_modified, "UNKNOWN"
    # Judge only the latest post-close payload; older FAIL/REFUSED rows must not
    # mask a subsequent CIO_READY completion in the append-only log.
    marker = 'tae.self_improve.post_close.v1'
    idx = text.rfind(marker)
    window = text[idx:] if idx >= 0 else text[-12000:]
    upper = window.upper()
    has_pass = bool(
        re.search(r'"STATUS"\s*:\s*"CIO_READY"', upper)
        or (re.search(r'"OK"\s*:\s*TRUE', upper) and "POST_CLOSE" in upper)
    )
    has_fail = bool(
        "TRACEBACK" in upper
        or re.search(r'"STATUS"\s*:\s*"REFUSED_MARKET_OPEN"', upper)
        or (
            re.search(r'"OK"\s*:\s*FALSE', upper)
            and not re.search(r'"STATUS"\s*:\s*"CIO_READY"', upper)
        )
    )
    if has_pass:
        return last_log_modified, "PASS"
    if has_fail:
        return last_log_modified, "FAIL"
    return last_log_modified, "UNKNOWN"


def schedule_status(
    *,
    crontab_lines: list[str] | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    """Read-only detection of the installed self-improve post-close cron entry."""
    root = (project_root or PROJECT_ROOT).resolve()
    recommended = RECOMMENDED_CRON.format(
        root=str(root),
        python=str(root / "venv" / "bin" / "python3"),
    )
    error: str | None = None
    if crontab_lines is None:
        crontab_lines, error = _read_user_crontab_lines()

    if crontab_lines is None:
        return {
            "SCHEDULE_ENABLED": False,
            "installed": False,
            "scheduler": "cron",
            "schedule": None,
            "timezone": "system_local",
            "project_dir": str(root),
            "python": None,
            "command": POST_CLOSE_CRON_MARKER,
            "log_path": str(DEFAULT_POST_CLOSE_LOG.resolve()),
            "entry_valid": False,
            "duplicate_entries": 0,
            "last_log_modified": None,
            "last_run_status": "UNKNOWN",
            "python_path_valid": False,
            "project_dir_valid": root.is_dir(),
            "recommended_cron": recommended,
            "note": f"Fail-soft: crontab unavailable ({error or 'UNKNOWN'}).",
            "detection_error": error,
        }

    matches = [
        parsed
        for line in crontab_lines
        if (parsed := _parse_post_close_cron_entry(line, project_root=root)) is not None
    ]
    installed = bool(matches)
    primary = matches[0] if matches else None
    duplicate_entries = max(0, len(matches) - 1)
    log_path = Path(
        (primary or {}).get("log_path")
        or str(root / "runtime_outputs" / "self_improve_post_close.log")
    )
    last_log_modified, last_run_status = _last_run_status(log_path)
    entry_valid = bool(primary and primary.get("entry_valid"))
    # Prefer a valid entry when duplicates mix valid/invalid.
    for candidate in matches:
        if candidate.get("entry_valid"):
            primary = candidate
            entry_valid = True
            log_path = Path(str(candidate.get("log_path") or log_path))
            last_log_modified, last_run_status = _last_run_status(log_path)
            break

    return {
        "SCHEDULE_ENABLED": bool(installed and entry_valid),
        "installed": installed,
        "scheduler": "cron",
        "schedule": (primary or {}).get("schedule"),
        "timezone": "system_local",
        "project_dir": str((primary or {}).get("project_dir") or root),
        "python": (primary or {}).get("python"),
        "command": POST_CLOSE_CRON_MARKER,
        "log_path": str(log_path),
        "entry_valid": entry_valid,
        "duplicate_entries": duplicate_entries,
        "last_log_modified": last_log_modified,
        "last_run_status": last_run_status,
        "python_path_valid": bool((primary or {}).get("python_path_valid")),
        "project_dir_valid": bool((primary or {}).get("project_dir_valid", root.is_dir())),
        "recommended_cron": recommended,
        "matching_entries": len(matches),
        "note": (
            "Detected installed user crontab entry for self-improve post-close."
            if installed
            else "No matching user crontab entry for self-improve post-close."
        ),
    }


def _post_close_fingerprint(day: str) -> str:
    parts = [day]
    for path in (HYPOTHESES_PATH, ATTRIBUTION_PATH):
        try:
            parts.append(hashlib.sha256(path.read_bytes()).hexdigest())
        except OSError:
            parts.append("MISSING")
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def _post_close_rows() -> list[dict[str, Any]]:
    try:
        lines = POST_CLOSE_RUNS_PATH.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def post_close_pipeline(*, at: datetime | None = None) -> dict[str, Any]:
    """Run the existing self-improvement chain only after EU/UK/US close."""
    from markets.market_hours import is_market_open

    now = at or datetime.now(timezone.utc)
    open_markets = [name for name in ("EU", "UK", "US") if is_market_open(name, at=now)]
    if open_markets:
        return {
            "ok": False,
            "status": "REFUSED_MARKET_OPEN",
            "open_markets": open_markets,
            "SCHEDULE_ENABLED": False,
        }
    day = now.date().isoformat()
    fingerprint = _post_close_fingerprint(day)
    existing = next(
        (
            row
            for row in reversed(_post_close_rows())
            if row.get("day") == day and row.get("fingerprint") == fingerprint
        ),
        None,
    )
    if existing:
        return {**existing, "idempotent_reuse": True}

    pipeline = run_self_improve(dry_run=False)
    monitoring = monitor_active_challengers()
    status = build_status()
    row = {
        "schema": "tae.self_improve.post_close.v1",
        "day": day,
        "fingerprint": fingerprint,
        "recorded_at": now.isoformat(),
        "ok": bool(pipeline.get("status")) and monitoring.get("ok", False),
        "status": "CIO_READY",
        "pipeline": pipeline,
        "monitoring": monitoring,
        "cio_ready_status": {
            key: status.get(key)
            for key in (
                "SELF_IMPROVEMENT_STATUS",
                "EXPERIMENTAL_CHALLENGERS_REGISTERED",
                "EXPERIMENTAL_ARMS_ENABLED",
                "ACTIVE_NOT_TRIGGERED",
                "NEEDS_MORE_DATA_EXPERIMENTS",
                "REMAINING_EVENTS",
                "REMAINING_CYCLES",
                "REMAINING_DAYS",
                "REMAINING_OUTCOMES",
                "NEXT_REEVALUATION",
                "PROMISING_EXPERIMENTS",
                "REPLAY_SUPPORTED_EXPERIMENTS",
                "BEHAVIOR_COHORTS",
                "GENERALIZED_BEHAVIOR_HYPOTHESES",
                "LATE_ENTRY_GENERALIZED",
                "EXPERIMENT_JOIN_CONFLICTS",
                "LAST_ECONOMIC_EXPERIMENT_UID",
                "READY_FOR_HUMAN_PROMOTION",
                "LIVE_AUTONOMY",
                "SCHEDULE_ENABLED",
            )
        },
        "SCHEDULE_ENABLED": False,
        "idempotent_reuse": False,
    }
    POST_CLOSE_RUNS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with POST_CLOSE_RUNS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, sort_keys=True, default=str) + "\n")
    return row


def _view(subcommand: str) -> dict[str, Any]:
    if subcommand in {
        "autonomy-status",
        "lineage",
        "champion",
        "mutations",
        "pause-autonomy",
        "resume-autonomy",
    }:
        from tae_self_improve_evolution import (
            MUTATION_ALLOWLIST,
            current_paper_champion,
            is_autonomy_enabled,
            load_lineage,
            pause_autonomy,
            resume_autonomy,
        )

        if subcommand == "autonomy-status":
            return {
                "enabled": is_autonomy_enabled(),
                "domain": "AUTONOMOUS_PAPER_EVOLUTION",
                "execution_mode": "PAPER",
                "live_allowed": False,
                "global_auto_promote": False,
            }
        if subcommand == "lineage":
            return {"lineage": load_lineage(), "append_only": True}
        if subcommand == "champion":
            return {
                "champion": current_paper_champion(),
                "execution_mode": "PAPER",
                "live_allowed": False,
            }
        if subcommand == "mutations":
            return {
                "mutation_allowlist": {
                    family: sorted(dimensions)
                    for family, dimensions in MUTATION_ALLOWLIST.items()
                }
            }
        if subcommand == "pause-autonomy":
            return {"ok": True, "autonomous_paper_evolution": pause_autonomy()}
        return {"ok": True, "autonomous_paper_evolution": resume_autonomy()}
    status = build_status()
    cycles = status.pop("cycles")
    if subcommand == "status":
        return status
    if subcommand == "audit":
        return audit()
    if subcommand == "explain":
        return explain()
    if subcommand == "experiments":
        return {"experiments": cycles}
    if subcommand == "challengers":
        return {"challengers": [row for row in cycles if row.get("status") == "PAPER_RUNNING"]}
    if subcommand == "results":
        terminal = {"REPLAY_REJECTED", "ROLLED_BACK", "READY_FOR_HUMAN_PROMOTION"}
        return {"results": [row for row in cycles if row.get("status") in terminal]}
    if subcommand == "schedule-status":
        return schedule_status()
    raise ValueError(f"Unknown self-improve subcommand: {subcommand}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tae.py self-improve")
    parser.add_argument(
        "subcommand",
        nargs="?",
        default="status",
        choices=(
            "status",
            "audit",
            "run",
            "explain",
            "experiments",
            "challengers",
            "results",
            "monitor",
            "post-close",
            "schedule-status",
            "autonomy-status",
            "lineage",
            "champion",
            "mutations",
            "pause-autonomy",
            "resume-autonomy",
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--steps", nargs="*")
    args = parser.parse_args(argv)
    if args.subcommand == "run":
        payload = run_self_improve(dry_run=args.dry_run, steps=args.steps)
    elif args.subcommand == "monitor":
        payload = monitor_active_challengers()
    elif args.subcommand == "post-close":
        payload = post_close_pipeline()
    else:
        payload = _view(args.subcommand)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

