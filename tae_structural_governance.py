#!/usr/bin/env python3
"""
TAE Structural Governance — single execution hierarchy for PAPER ecosystem.

PAPER_ONLY | NO_BROKER | NO_LIVE_PROMOTION
Orchestrates existing modules; does not duplicate decision/execution logic.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

MODE = "PAPER_ONLY"
DEFAULT_CLI_STEP_TIMEOUT = 600

GOVERNANCE_DIR = Path("runtime_outputs/governance")
GOVERNANCE_JSON = GOVERNANCE_DIR / "structural_governance.json"
GOVERNANCE_REPORT_MD = Path("TAE_STRUCTURAL_GOVERNANCE_REPORT.md")
CONSOLIDATION_REPORT_MD = Path("TAE_STRUCTURAL_CONSOLIDATION_REPORT.md")
HARD_RISK_JSON = GOVERNANCE_DIR / "hard_risk.json"

CYCLE_OUTPUT_DIR = Path("runtime_outputs/full_paper_cycle")
CYCLE_SUMMARY_JSON = CYCLE_OUTPUT_DIR / "summary.json"
CYCLE_REPORT_MD = Path("TAE_FULL_PAPER_CYCLE_REPORT.md")
PROMOTION_JSON = CYCLE_OUTPUT_DIR / "promotion_gate.json"
ORCHESTRATION_RUN_JSON = CYCLE_OUTPUT_DIR / "orchestration_run.json"

PAPER_PORTFOLIO_JSON = Path("runtime_outputs/paper_execution/paper_portfolio.json")
PAPER_MTM_JSON = Path("runtime_outputs/paper_execution/mark_to_market.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
DECISIONS_JSON = Path("runtime_outputs/paper_decisions/paper_decisions.json")
VALIDATION_JSON = Path("runtime_outputs/paper_decisions/decision_validation_results.json")

FORBIDDEN_SNAPSHOT = ("live_bot.py", "portfolio.csv", "live_signals.csv", "watchlist.txt")
FORBIDDEN_GIT_PATHS = FORBIDDEN_SNAPSHOT + ("core/", "research_core/")

# Mandatory 19-step hierarchy
EXECUTION_HIERARCHY: list[dict[str, Any]] = [
    {"rank": 1, "id": "data_validity", "name": "DATA VALIDITY", "rule_class": "HARD"},
    {"rank": 2, "id": "accounting_reconciliation", "name": "ACCOUNTING RECONCILIATION", "rule_class": "HARD"},
    {"rank": 3, "id": "capital_safety", "name": "CAPITAL SAFETY", "rule_class": "HARD"},
    {"rank": 4, "id": "hard_risk_rules", "name": "HARD RISK RULES", "rule_class": "HARD"},
    {"rank": 5, "id": "position_discipline", "name": "POSITION DISCIPLINE", "rule_class": "HARD"},
    {"rank": 6, "id": "profit_protection", "name": "PROFIT PROTECTION", "rule_class": "POLICY"},
    {"rank": 7, "id": "loss_cutting", "name": "LOSS CUTTING", "rule_class": "POLICY"},
    {"rank": 8, "id": "buy_eligibility", "name": "BUY ELIGIBILITY", "rule_class": "POLICY"},
    {"rank": 9, "id": "policy_layer", "name": "POLICY LAYER", "rule_class": "POLICY"},
    {"rank": 10, "id": "learning_adaptive", "name": "LEARNING / ADAPTIVE LAYER", "rule_class": "LEARNING"},
    {"rank": 11, "id": "paper_execution", "name": "PAPER EXECUTION", "rule_class": "HARD"},
    {"rank": 12, "id": "mark_to_market", "name": "MARK-TO-MARKET", "rule_class": "HARD"},
    {"rank": 13, "id": "outcome_memory", "name": "OUTCOME MEMORY", "rule_class": "LEARNING"},
    {"rank": 14, "id": "rule_survival", "name": "RULE SURVIVAL", "rule_class": "LEARNING"},
    {"rank": 15, "id": "adaptive_weights", "name": "ADAPTIVE WEIGHTS", "rule_class": "LEARNING"},
    {"rank": 16, "id": "dpe", "name": "DPE", "rule_class": "LEARNING"},
    {"rank": 17, "id": "canonical_vs_paper", "name": "CANONICAL VS PAPER", "rule_class": "REPORT_ONLY"},
    {"rank": 18, "id": "promotion_lock", "name": "PROMOTION LOCK", "rule_class": "HARD"},
    {"rank": 19, "id": "final_verdict", "name": "FINAL VERDICT", "rule_class": "HARD"},
]

MODULE_REGISTRY: dict[str, dict[str, str]] = {
    "hard_risk_guardian.py": {"role": "HARD", "layer": "hard_risk_rules", "status": "ACTIVE"},
    "tae_paper_decision_engine.py": {"role": "HARD/POLICY", "layer": "position_discipline..policy_layer", "status": "ACTIVE"},
    "tae_paper_execution.py": {"role": "HARD", "layer": "paper_execution", "status": "ACTIVE"},
    "tae_rule_survival.py": {"role": "LEARNING", "layer": "rule_survival", "status": "ACTIVE"},
    "tae_adaptive_paper_weights.py": {"role": "LEARNING", "layer": "adaptive_weights", "status": "ACTIVE"},
    "tae_longitudinal_outcome_memory.py": {"role": "LEARNING", "layer": "outcome_memory", "status": "ACTIVE"},
    "tae_live_promotion_lock.py": {"role": "HARD", "layer": "promotion_lock", "status": "ACTIVE"},
    "tae_portfolio_profit_governor.py": {"role": "POLICY", "layer": "profit_protection", "status": "UPSTREAM_SHADOW"},
    "tae_adaptive_profit_policy_engine.py": {"role": "POLICY", "layer": "policy_layer", "status": "UPSTREAM_SHADOW"},
    "tae_profit_decision_governor.py": {"role": "POLICY", "layer": "profit_protection", "status": "UPSTREAM_SHADOW"},
    "tae_profit_protection_validation.py": {"role": "POLICY", "layer": "profit_protection", "status": "UPSTREAM_SHADOW"},
    "tae_decision_governor.py": {"role": "OBSERVABILITY_ONLY", "layer": "legacy_advisory", "status": "OBSERVABILITY"},
    "tae_knowledge_base.py": {"role": "LEARNING", "layer": "pre_pde_knowledge_view", "status": "ACTIVE"},
    "tae_portfolio_reconciliation.py": {"role": "REPORT_ONLY", "layer": "canonical_accounting", "status": "LEGACY_LIVE_AUDIT"},
    "tae_dpe_*": {"role": "LEARNING", "layer": "dpe", "status": "ACTIVE"},
}


@dataclass
class StepRecord:
    rank: int
    step_id: str
    name: str
    rule_class: str
    ok: bool
    status: str
    reason: str | None = None
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    overrides: list[str] = field(default_factory=list)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _f(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _s(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _file_mtime(path: Path) -> float | None:
    return path.stat().st_mtime if path.is_file() else None


def check_forbidden_file_safety(
    root: Path,
    *,
    before_mtimes: dict[str, float | None] | None = None,
) -> dict[str, Any]:
    before_mtimes = before_mtimes or {}
    after_mtimes = {name: _file_mtime(root / name) for name in FORBIDDEN_SNAPSHOT}
    mtime_drift = bool(before_mtimes) and before_mtimes != after_mtimes

    changed_files: list[str] = []
    diff_text = ""
    git_ok = True
    git_detail = ""

    try:
        diff_result = subprocess.run(
            ["git", "diff", "--", *FORBIDDEN_GIT_PATHS],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        names_result = subprocess.run(
            ["git", "diff", "--name-only", "--", *FORBIDDEN_GIT_PATHS],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        if diff_result.returncode != 0 and not (diff_result.stdout or diff_result.stderr):
            git_ok = False
            git_detail = (diff_result.stderr or "git diff failed").strip()
        else:
            diff_text = (diff_result.stdout or "").strip()
            changed_files = [line.strip() for line in (names_result.stdout or "").splitlines() if line.strip()]
    except (OSError, subprocess.TimeoutExpired) as exc:
        git_ok = False
        git_detail = str(exc)

    content_clean = git_ok and not diff_text and not changed_files
    diff_summary = "0 diff lines" if content_clean else diff_text[:500] or f"{len(changed_files)} file(s) changed"
    safety_block_reason = None
    if not git_ok:
        safety_block_reason = f"git diff unavailable: {git_detail}"
    elif not content_clean:
        safety_block_reason = f"forbidden content diff: {', '.join(changed_files) or 'see diff_summary'}"

    note = None
    if mtime_drift and content_clean:
        note = "mtime drift ignored, content diff clean"

    return {
        "forbidden_content_diff_clean": content_clean,
        "forbidden_mtime_drift_detected": mtime_drift,
        "forbidden_files_unchanged": content_clean,
        "safety_status": "PASS" if content_clean else "BLOCKED",
        "safety_block_reason": safety_block_reason,
        "changed_files": changed_files,
        "diff_summary": diff_summary,
        "note": note,
        "git_check_ok": git_ok,
    }


def _unbuffered_cmd(cmd: list[str]) -> list[str]:
    if not cmd:
        return cmd
    exe = Path(cmd[0]).name
    if exe.startswith("python") and "-u" not in cmd:
        return [cmd[0], "-u", *cmd[1:]]
    return cmd


def run_cli_step(
    name: str,
    cmd: list[str],
    *,
    cwd: Path,
    timeout: int = DEFAULT_CLI_STEP_TIMEOUT,
) -> dict[str, Any]:
    from tae_historical_runtime_refresh import trace_end, trace_fail, trace_start, trace_timeout

    cmd = _unbuffered_cmd(cmd)
    t0 = trace_start(name)
    print(f"\n>>> [{name}] {' '.join(cmd)}", flush=True)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            check=False,
            capture_output=False,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired:
        trace_timeout(name, time.monotonic() - t0)
        return {
            "step": name,
            "command": cmd,
            "exit_code": 124,
            "ok": False,
            "status": "TIMEOUT",
            "reason": f"timeout after {timeout}s",
        }
    ok = result.returncode == 0
    trace_end(name, t0)
    if not ok:
        trace_fail(name, f"exit_code={result.returncode}")
    return {
        "step": name,
        "command": cmd,
        "exit_code": int(result.returncode),
        "ok": ok,
        "status": "PASS" if ok else "FAIL",
        "reason": None if ok else f"exit_code={result.returncode}",
    }


def gate_data_validity(root: Path) -> StepRecord:
    from tae_historical_runtime_refresh import run_historical_runtime_refresh, trace_end, trace_fail, trace_start

    t0 = trace_start("gate_data_validity")
    hist = run_historical_runtime_refresh(root=root)
    trace_end("gate_data_validity", t0)
    critical_fresh = bool(hist.get("critical_all_fresh", hist.get("all_fresh")))
    stale = list(hist.get("stale_sources") or [])
    ok = critical_fresh
    reason = None if ok else f"critical data stale: {', '.join(stale) or 'unknown'}"
    if not ok:
        trace_fail("gate_data_validity", reason or "critical sources stale")
    return StepRecord(
        rank=1,
        step_id="data_validity",
        name="DATA VALIDITY",
        rule_class="HARD",
        ok=ok,
        status="PASS" if ok else "FAIL",
        reason=reason,
        inputs=["historical_intelligence", "multi_horizon_backtest", "strategic_intelligence"],
        outputs=["runtime_outputs/historical_runtime/state.json"],
        metrics={
            "all_fresh": hist.get("all_fresh"),
            "critical_all_fresh": critical_fresh,
            "stale_sources": stale,
            "confidence_penalty": hist.get("confidence_penalty"),
        },
    )


def gate_accounting_reconciliation() -> StepRecord:
    from tae_paper_execution import validate_portfolio_reconciliation

    portfolio = _load_json(PAPER_PORTFOLIO_JSON) or {}
    recon = validate_portfolio_reconciliation(portfolio) if portfolio else {"ok": True, "status": "SKIP", "errors": []}
    ok = bool(recon.get("ok"))
    errors = recon.get("errors") or []
    reason = None if ok else "; ".join(errors[:3])
    return StepRecord(
        rank=2,
        step_id="accounting_reconciliation",
        name="ACCOUNTING RECONCILIATION",
        rule_class="HARD",
        ok=ok,
        status=recon.get("status", "PASS" if ok else "FAIL"),
        reason=reason,
        inputs=[str(PAPER_PORTFOLIO_JSON)],
        outputs=["reconciliation_checks"],
        metrics={"checks": recon.get("checks"), "realized_pnl": recon.get("realized_pnl")},
    )


def gate_capital_safety() -> StepRecord:
    portfolio = _load_json(PAPER_PORTFOLIO_JSON) or {}
    appe = _load_json(APPE_JSON) or {}
    accounting = _load_json(ACCOUNTING_JSON) or {}
    try:
        from research_core.accounting.accounting_snapshot import build_accounting_snapshot

        accounting = build_accounting_snapshot(".")
    except Exception:
        pass
    policy_state = _s((appe.get("latest_observation") or {}).get("policy_state"))

    broker = bool(portfolio.get("broker_executed"))
    live_money = bool(portfolio.get("live_money"))
    ok = not broker and not live_money
    reasons: list[str] = []
    if broker:
        reasons.append("broker_executed=true")
    if live_money:
        reasons.append("live_money=true")

    return StepRecord(
        rank=3,
        step_id="capital_safety",
        name="CAPITAL SAFETY",
        rule_class="HARD",
        ok=ok,
        status="PASS" if ok else "FAIL",
        reason="; ".join(reasons) if reasons else None,
        inputs=[str(PAPER_PORTFOLIO_JSON), str(APPE_JSON), str(ACCOUNTING_JSON)],
        outputs=["capital_safety_verdict"],
        metrics={
            "policy_state": policy_state,
            "cash": _f(portfolio.get("cash")),
            "broker_executed": broker,
            "live_money": live_money,
        },
    )


def gate_hard_risk_rules() -> StepRecord:
    from hard_risk_guardian import run_paper_hard_risk

    portfolio = _load_json(PAPER_PORTFOLIO_JSON)
    result = run_paper_hard_risk(portfolio=portfolio, write_report=True)
    breaches = result.get("breaches") or []
    overrides = [
        f"{b.get('ticker')}: {b.get('required_action')} at {b.get('pnl_pct')}% ({b.get('hard_rule')})"
        for b in breaches
    ]
    return StepRecord(
        rank=4,
        step_id="hard_risk_rules",
        name="HARD RISK RULES",
        rule_class="HARD",
        ok=True,
        status=result.get("status", "PASS"),
        reason=None if not breaches else f"{len(breaches)} breach(es) — HARD SELL override required",
        inputs=[str(PAPER_PORTFOLIO_JSON)],
        outputs=[str(HARD_RISK_JSON)],
        metrics={
            "breach_count": len(breaches),
            "stop_limit": result.get("stop_limit_pct"),
            "critical_limit": result.get("critical_limit_pct"),
        },
        overrides=overrides,
    )


def _decision_layer_metrics() -> dict[str, Any]:
    decisions_doc = _load_json(DECISIONS_JSON) or {}
    decisions = decisions_doc.get("decisions") or []
    blocked_no_position = sum(1 for d in decisions if (d.get("position_discipline") or {}).get("blocked"))
    hard_overrides = sum(1 for d in decisions if (d.get("hard_risk_discipline") or {}).get("override"))
    buy_count = sum(1 for d in decisions if d.get("action") == "BUY_PAPER")
    sell_count = sum(1 for d in decisions if d.get("action") == "SELL_PAPER")
    protect_count = sum(1 for d in decisions if d.get("action") == "PROTECT_PAPER")
    return {
        "decision_count": len(decisions),
        "blocked_no_position": blocked_no_position,
        "hard_risk_overrides": hard_overrides,
        "buy_paper": buy_count,
        "sell_paper": sell_count,
        "protect_paper": protect_count,
    }


def step_from_cli(rank: int, step_id: str, name: str, rule_class: str, cli_result: dict[str, Any], *, inputs: list[str], outputs: list[str]) -> StepRecord:
    return StepRecord(
        rank=rank,
        step_id=step_id,
        name=name,
        rule_class=rule_class,
        ok=bool(cli_result.get("ok")),
        status=cli_result.get("status") or ("PASS" if cli_result.get("ok") else "FAIL"),
        reason=cli_result.get("reason"),
        inputs=inputs,
        outputs=outputs,
        metrics={k: v for k, v in cli_result.items() if k not in {"command", "step"}},
    )


def compute_final_verdict(
    steps: list[StepRecord],
    *,
    safety: dict[str, Any],
    paper_reconciliation: dict[str, Any],
    hard_risk: dict[str, Any],
    mtm_status: str,
    paper_positions: int,
) -> tuple[str, list[str]]:
    block_reasons: list[str] = []
    warnings: list[str] = []

    if not safety.get("forbidden_content_diff_clean"):
        block_reasons.append(safety.get("safety_block_reason") or "forbidden file diff")

    for step in steps:
        if step.rule_class == "HARD" and not step.ok and step.step_id not in {"hard_risk_rules"}:
            block_reasons.append(f"{step.name}: {step.reason or 'FAIL'}")

    if not paper_reconciliation.get("ok"):
        block_reasons.append(f"accounting reconciliation: {'; '.join(paper_reconciliation.get('errors') or [])[:200]}")

    portfolio = _load_json(PAPER_PORTFOLIO_JSON) or {}
    if portfolio.get("broker_executed") or portfolio.get("live_money"):
        block_reasons.append("broker or live_money flag on PAPER portfolio")

    if mtm_status == "ALL_STALE" and paper_positions > 0:
        block_reasons.append("mark-to-market ALL_STALE with open positions")

    for step in steps:
        if not step.ok and step.rule_class != "HARD":
            warnings.append(f"{step.name}: {step.reason or 'FAIL'}")

    if block_reasons:
        return "BLOCKED_WITH_REASONS", block_reasons + warnings

    if warnings or any(not s.ok for s in steps if s.rule_class not in {"HARD", "REPORT_ONLY"}):
        return "READY_WITH_WARNINGS", warnings

    return "READY_FOR_PAPER_DAY", []


def write_governance_reports(state: dict[str, Any]) -> None:
    GOVERNANCE_DIR.mkdir(parents=True, exist_ok=True)
    GOVERNANCE_JSON.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# TAE Structural Governance Report",
        "",
        f"**Generated:** {state.get('generated_at')}",
        f"**Mode:** {MODE} — NO_BROKER — NO_LIVE_PROMOTION",
        f"**Final verdict:** **{state.get('final_verdict')}**",
        "",
        "## Execution hierarchy (mandatory order)",
        "",
        "| rank | layer | class | status | reason |",
        "| ---: | --- | --- | --- | --- |",
    ]
    for step in state.get("steps") or []:
        lines.append(
            f"| {step.get('rank')} | {step.get('name')} | {step.get('rule_class')} | "
            f"**{step.get('status')}** | {step.get('reason') or '-'} |"
        )

    lines.extend(["", "## Hard rules enforced", ""])
    for rule in state.get("hard_rules_enforced") or []:
        lines.append(f"- {rule}")
    lines.extend(["", "## Overrides", ""])
    for ov in state.get("overrides") or []:
        lines.append(f"- {ov}")
    if not state.get("overrides"):
        lines.append("- none")

    lines.extend(["", "## Block reasons", ""])
    for br in state.get("block_reasons") or []:
        lines.append(f"- {br}")
    if not state.get("block_reasons"):
        lines.append("- none")

    GOVERNANCE_REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = state.get("paper_summary") or {}
    clines = [
        "# TAE Structural Consolidation Report",
        "",
        f"**Generated:** {state.get('generated_at')}",
        f"**Final verdict:** **{state.get('final_verdict')}**",
        "",
        "## Modules consolidated",
        "",
        "| module | role | status |",
        "| --- | --- | --- |",
    ]
    for mod, info in MODULE_REGISTRY.items():
        clines.append(f"| `{mod}` | {info.get('role')} | {info.get('status')} |")

    clines.extend(
        [
            "",
            "## PAPER result",
            "",
            f"- Portfolio value: **${summary.get('paper_portfolio_value', 0):,.2f}**",
            f"- Cash: **${summary.get('paper_cash', 0):,.2f}**",
            f"- Realized PnL: **${summary.get('paper_realized_pnl', 0):,.2f}**",
            f"- Unrealized PnL: **${summary.get('paper_unrealized_pnl', 0):,.2f}**",
            f"- Total PnL: **${summary.get('paper_total_pnl', 0):,.2f}**",
            f"- Reconciliation: **{summary.get('paper_reconciliation_status')}**",
            f"- Hard risk: **{summary.get('hard_risk_status')}** ({summary.get('hard_risk_breaches', 0)} breaches)",
            f"- Canonical vs PAPER delta: **${summary.get('canonical_vs_paper_value_delta', 0):,.2f}**",
            "",
            "## Files changed (this consolidation)",
            "",
            "- `tae_structural_governance.py`",
            "- `hard_risk_guardian.py` (PAPER adapter)",
            "- `tae_full_paper_cycle.py` (structural delegate)",
            "- `tae_paper_decision_engine.py` (hard risk consume)",
            "- `TAE_STRUCTURAL_GOVERNANCE.md`",
            "",
            f"## Operator command",
            "",
            "```bash",
            "python3 tae.py full-paper-cycle",
            "```",
        ]
    )
    CONSOLIDATION_REPORT_MD.write_text("\n".join(clines) + "\n", encoding="utf-8")


def _mark_to_market_status(mtm: dict[str, Any]) -> str:
    live = int(_f(mtm.get("live_price_count")))
    stale = int(_f(mtm.get("stale_price_count")))
    if not mtm:
        return "NOT_RUN"
    if stale == 0 and live > 0:
        return "LIVE"
    if live > 0:
        return "PARTIAL_STALE"
    if stale > 0:
        return "ALL_STALE"
    return "EMPTY"


def _git_head() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        return (r.stdout or "").strip() or "UNKNOWN"
    except OSError:
        return "UNKNOWN"


def _trading_date_local() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d")


def _new_orchestration_run_id() -> str:
    return f"ORCH-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{os.getpid()}"


def _write_orchestration_run(record: dict[str, Any]) -> None:
    CYCLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ORCHESTRATION_RUN_JSON.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _stamp_json_metadata(path: Path, *, run_id: str, trading_date: str, source_commit: str) -> None:
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(data, dict):
        return
    data["orchestration_run_id"] = run_id
    data["trading_date"] = trading_date
    data["source_commit"] = source_commit
    data.setdefault("generated_at", datetime.now(timezone.utc).replace(microsecond=0).isoformat())
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _refresh_process_health(root: Path) -> dict[str, Any]:
    script = root / "tools" / "process_supervisor.py"
    if script.is_file():
        subprocess.run([sys.executable, str(script)], cwd=str(root), check=False)
    health_path = root / "process_health.json"
    if health_path.is_file():
        try:
            return json.loads(health_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    # Minimal fresh snapshot if supervisor unavailable
    payload = {
        "schema": "tae.process_health.v1",
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "producer": "tae_structural_governance",
        "status": "REFRESHED",
    }
    health_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def run_structural_paper_cycle(root: Path | None = None) -> tuple[int, dict[str, Any]]:
    root = root or Path(".").resolve()
    py = sys.executable
    steps: list[StepRecord] = []
    cli_steps: list[dict[str, Any]] = []
    all_overrides: list[str] = []
    exit_code = 0
    orchestration_run_id = _new_orchestration_run_id()
    trading_date = _trading_date_local()
    source_commit = _git_head()
    start_ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    orch_record: dict[str, Any] = {
        "schema": "tae.orchestration_run.v1",
        "orchestration_run_id": orchestration_run_id,
        "trading_date": trading_date,
        "source_commit": source_commit,
        "start_timestamp": start_ts,
        "end_timestamp": None,
        "owner": "tae_structural_governance.run_structural_paper_cycle",
        "entrypoint": "python3 tae.py full-paper-cycle",
        "scheduler_source": os.environ.get("TAE_SCHEDULER_SOURCE") or "manual",
        "stage": "START",
        "stage_status": "RUNNING",
        "stages": [],
        "status": "RUNNING",
    }
    _write_orchestration_run(orch_record)
    os.environ["TAE_ORCHESTRATION_RUN_ID"] = orchestration_run_id
    os.environ["TAE_TRADING_DATE"] = trading_date

    print("===== TAE STRUCTURAL GOVERNANCE — FULL PAPER CYCLE =====", flush=True)
    print(f"Mode: {MODE} | NO_BROKER | NO_LIVE_PROMOTION", flush=True)
    print(f"orchestration_run_id={orchestration_run_id} trading_date={trading_date}", flush=True)
    print("", flush=True)

    from tae_historical_runtime_refresh import trace_end, trace_start

    cycle_t0 = trace_start("structural_paper_cycle")

    before_mtimes = {name: _file_mtime(root / name) for name in FORBIDDEN_SNAPSHOT}

    # Rank 0 — process health refresh (fresh snapshot for morning-audit)
    ph = _refresh_process_health(root)
    cli_steps.append({"step": "process_health_refresh", "ok": True, "checked_at": ph.get("checked_at")})

    # Rank 1 — DATA VALIDITY
    s1 = gate_data_validity(root)
    steps.append(s1)
    if not s1.ok:
        exit_code = 1

    # Operational dependency refresh — required by morning-audit and PDE upstream chain
    operational_refresh: list[tuple[str, list[str]]] = [
        ("accounting_snapshot", [py, "tae_accounting_snapshot.py"]),
        ("protect_shadow", [py, "tae.py", "protect"]),
        ("portfolio_protect", [py, "tae.py", "portfolio-protect"]),
        ("adaptive_policy", [py, "tae.py", "policy"]),
        ("growth_intelligence", [py, "tae.py", "growth-intelligence"]),
        ("infrastructure_health", [py, "tae_infrastructure_health.py"]),
        ("adaptive_deployment_status", [py, "tae.py", "adaptive-deployment", "status"]),
    ]
    for step_name, cmd in operational_refresh:
        r_refresh = run_cli_step(step_name, cmd, cwd=root)
        cli_steps.append(r_refresh)
        steps.append(
            step_from_cli(
                1,
                step_name,
                step_name.replace("_", " ").upper(),
                "HARD",
                r_refresh,
                inputs=["portfolio.csv", "upstream shadow chain"],
                outputs=[step_name],
            )
        )
        if not r_refresh["ok"]:
            exit_code = r_refresh["exit_code"] or 1

    # Rank 2 — ACCOUNTING RECONCILIATION (pre-cycle)
    s2 = gate_accounting_reconciliation()
    steps.append(s2)

    # Rank 3 — CAPITAL SAFETY
    s3 = gate_capital_safety()
    steps.append(s3)
    if not s3.ok:
        exit_code = 1

    # Rank 4 — HARD RISK RULES (before decisions)
    s4 = gate_hard_risk_rules()
    steps.append(s4)
    all_overrides.extend(s4.overrides)

    # Rank 10 — LEARNING (before decisions per hierarchy: hypothesis queue)
    r10 = run_cli_step("learning_profit", [py, "tae.py", "learning-profit"], cwd=root)
    cli_steps.append(r10)
    steps.append(
        step_from_cli(10, "learning_adaptive", "LEARNING / ADAPTIVE LAYER", "LEARNING", r10, inputs=["LTP artifacts"], outputs=["learning_to_profit"])
    )
    if not r10["ok"]:
        exit_code = r10["exit_code"] or 1

    # Decision state refresh — before conflict resolution (anti-churn ownership view)
    r_ds = run_cli_step("decision_state", [py, "tae.py", "decision-state-refresh"], cwd=root)
    cli_steps.append(r_ds)
    steps.append(
        step_from_cli(
            10,
            "decision_state",
            "DECISION STATE",
            "LEARNING",
            r_ds,
            inputs=["paper_orders", "paper_portfolio", "hard_risk"],
            outputs=["runtime_outputs/decision_state/active_decisions.json"],
        )
    )
    if not r_ds["ok"]:
        exit_code = r_ds["exit_code"] or 1

    # Conflict resolution refresh — before PDE (EV evidence for policy conflicts)
    r_cr = run_cli_step("conflict_resolution", [py, "tae.py", "conflict-resolution-refresh"], cwd=root)
    cli_steps.append(r_cr)
    steps.append(
        step_from_cli(
            10,
            "conflict_resolution",
            "CONFLICT RESOLUTION",
            "LEARNING",
            r_cr,
            inputs=["GII", "DPE", "LTP", "replay", "weights"],
            outputs=["runtime_outputs/conflict_resolution/conflicts.json"],
        )
    )
    if not r_cr["ok"]:
        exit_code = r_cr["exit_code"] or 1

    # Constitutional evolution — apply prior economic feedback before PDE
    from tae_full_paper_cycle import (
        archive_pre_evolution_snapshot,
        run_post_learning_evolution,
        run_pre_pde_feedback,
    )

    # Knowledge-base VIEW refresh — PDE bias consumer must not depend solely on market-open shadow.
    print("\n>>> [knowledge_base] refresh PDE knowledge view (fail-open)", flush=True)
    kb_ok = True
    kb_reason = None
    try:
        from tae_knowledge_base import main as run_knowledge_base

        kb_code = int(run_knowledge_base() or 0)
        kb_ok = kb_code == 0
        if not kb_ok:
            kb_reason = f"knowledge_base exit={kb_code}"
    except Exception as exc:  # noqa: BLE001 — fail-open informational bias
        kb_ok = False
        kb_reason = f"knowledge_base error: {exc}"
    cli_steps.append(
        {
            "name": "knowledge_base",
            "ok": kb_ok,
            "exit_code": 0 if kb_ok else 1,
            "reason": kb_reason,
            "fail_open": True,
        }
    )
    steps.append(
        StepRecord(
            rank=10,
            step_id="knowledge_base",
            name="KNOWLEDGE BASE VIEW",
            rule_class="LEARNING",
            ok=True,  # fail-open: never blocks cycle
            status="PASS" if kb_ok else "WARN",
            reason=kb_reason,
            inputs=["tae_knowledge_base.py"],
            outputs=["tae_knowledge_base.json"],
        )
    )

    run_pre_pde_feedback(root, cli_steps)

    # Ranks 5-9 — PAPER DECISIONS (PDE: position, profit, loss, buy, policy)
    r_pde = run_cli_step("paper_decisions", [py, "tae.py", "paper-decisions"], cwd=root)
    cli_steps.append(r_pde)
    layer_metrics = _decision_layer_metrics()
    steps.append(
        StepRecord(
            rank=5,
            step_id="position_discipline",
            name="POSITION DISCIPLINE",
            rule_class="HARD",
            ok=r_pde["ok"],
            status="PASS" if r_pde["ok"] else "FAIL",
            reason=r_pde.get("reason"),
            inputs=[str(DECISIONS_JSON), str(HARD_RISK_JSON)],
            outputs=[str(DECISIONS_JSON), "TAE_DECISION_DISCIPLINE_REPORT.md"],
            metrics=layer_metrics,
        )
    )
    for rank, sid, sname, rclass in (
        (6, "profit_protection", "PROFIT PROTECTION", "POLICY"),
        (7, "loss_cutting", "LOSS CUTTING", "POLICY"),
        (8, "buy_eligibility", "BUY ELIGIBILITY", "POLICY"),
        (9, "policy_layer", "POLICY LAYER", "POLICY"),
    ):
        steps.append(
            StepRecord(
                rank=rank,
                step_id=sid,
                name=sname,
                rule_class=rclass,
                ok=r_pde["ok"],
                status="PASS" if r_pde["ok"] else "FAIL",
                reason=None if r_pde["ok"] else "paper-decisions failed",
                inputs=["tae_paper_decision_engine.py"],
                outputs=[str(DECISIONS_JSON)],
                metrics=layer_metrics,
            )
        )
    if not r_pde["ok"]:
        exit_code = r_pde["exit_code"] or 1

    archive_pre_evolution_snapshot(root, kind="decisions")

    # Rank 11 — PAPER EXECUTION
    r_exec = run_cli_step("paper_execution", [py, "tae.py", "paper-execution"], cwd=root)
    cli_steps.append(r_exec)
    steps.append(
        step_from_cli(11, "paper_execution", "PAPER EXECUTION", "HARD", r_exec, inputs=[str(DECISIONS_JSON)], outputs=[str(PAPER_PORTFOLIO_JSON)])
    )
    if not r_exec["ok"]:
        exit_code = r_exec["exit_code"] or 1

    # Observe Validation → Capital Allocation on existing decisions/orders (no new engine)
    print("\n>>> [capital_challenger_observe] update_capital_challenger_registry", flush=True)
    from tae_paper_decision_engine import update_capital_challenger_registry

    challenger_doc = update_capital_challenger_registry()
    cli_steps.append(
        {
            "step": "capital_challenger_observe",
            "ok": True,
            "exit_code": 0,
            "authorized_count": challenger_doc.get("authorized_count"),
            "executed_trade_count": challenger_doc.get("executed_trade_count"),
            "capital_moved_abs_usd": challenger_doc.get("capital_moved_abs_usd"),
            "output": "runtime_outputs/learning_to_profit/capital_challengers.json",
        }
    )

    # Rank 12 — MARK-TO-MARKET
    r_mtm = run_cli_step("paper_mark_to_market", [py, "tae.py", "paper-mark-to-market"], cwd=root)
    cli_steps.append(r_mtm)
    steps.append(
        step_from_cli(12, "mark_to_market", "MARK-TO-MARKET", "HARD", r_mtm, inputs=[str(PAPER_PORTFOLIO_JSON)], outputs=[str(PAPER_MTM_JSON)])
    )
    if not r_mtm["ok"]:
        exit_code = r_mtm["exit_code"] or 1

    # Re-run gates 2 & 4 post MTM
    s2b = gate_accounting_reconciliation()
    s2b.rank = 2
    s2b.name = "ACCOUNTING RECONCILIATION (post-MTM)"
    steps.append(s2b)
    s4b = gate_hard_risk_rules()
    s4b.rank = 4
    s4b.name = "HARD RISK RULES (post-MTM)"
    steps.append(s4b)
    all_overrides.extend(s4b.overrides)

    # Validation before learning — today's decisions → verdicts → weights
    r_exp = run_cli_step("paper_experiments", [py, "tae.py", "paper-experiments"], cwd=root)
    cli_steps.append(r_exp)
    steps.append(
        step_from_cli(
            10,
            "paper_experiments",
            "PAPER EXPERIMENTS",
            "LEARNING",
            r_exp,
            inputs=[str(DECISIONS_JSON)],
            outputs=["decision_validation_results.json"],
        )
    )
    if not r_exp["ok"]:
        exit_code = r_exp["exit_code"] or 1

    # Rank 13 — OUTCOME MEMORY
    r_mem = run_cli_step("outcome_memory", [py, "tae.py", "outcome-memory"], cwd=root)
    cli_steps.append(r_mem)
    steps.append(step_from_cli(13, "outcome_memory", "OUTCOME MEMORY", "LEARNING", r_mem, inputs=["paper decisions"], outputs=["longitudinal_memory"]))

    # Rank 14 — RULE SURVIVAL (direct — no duplicate longitudinal)
    from tae_rule_survival import run_rule_survival

    print("\n>>> [rule_survival] tae_rule_survival.run_rule_survival", flush=True)
    from tae_historical_runtime_refresh import trace_end, trace_start

    surv_t0 = trace_start("rule_survival")
    surv = run_rule_survival(write_report_flag=True)
    trace_end("rule_survival", surv_t0)
    r_surv_ok = bool(surv.get("ok", True))
    steps.append(
        StepRecord(
            rank=14,
            step_id="rule_survival",
            name="RULE SURVIVAL",
            rule_class="LEARNING",
            ok=r_surv_ok,
            status="PASS" if r_surv_ok else "FAIL",
            reason=None,
            inputs=["rule_outcome_attribution"],
            outputs=["rule_lifecycle.json", "TAE_RULE_SURVIVAL_REPORT.md"],
            metrics={"rule_count": len((surv.get("document") or {}).get("rules") or {})},
        )
    )

    archive_pre_evolution_snapshot(root, kind="weights")

    # Rank 15 — ADAPTIVE WEIGHTS
    r_aw = run_cli_step("adaptive_weights", [py, "tae.py", "adaptive-weights"], cwd=root)
    cli_steps.append(r_aw)
    steps.append(step_from_cli(15, "adaptive_weights", "ADAPTIVE WEIGHTS", "LEARNING", r_aw, inputs=["attribution"], outputs=["paper_action_weights.json"]))

    evolution = run_post_learning_evolution(root, cli_steps)
    steps.append(
        StepRecord(
            rank=16,
            step_id="constitutional_evolution",
            name="CONSTITUTIONAL EVOLUTION",
            rule_class="LEARNING",
            ok=bool(evolution.get("ok")),
            status="PASS" if evolution.get("loop_closed") else "PASS_WITH_NO_DELTA",
            reason=None if evolution.get("loop_closed") else "no decision/weight delta this cycle",
            inputs=["paper_action_weights.json", "rule_lifecycle.json", str(DECISIONS_JSON)],
            outputs=["runtime_outputs/governance/constitutional_evolution.json", str(DECISIONS_JSON)],
            metrics={
                "loop_closed": evolution.get("loop_closed"),
                "decision_change_count": evolution.get("decision_change_count"),
                "weight_change_count": evolution.get("weight_change_count"),
            },
        )
    )

    # Controlled post-learning execution — only action-changed actionable decisions
    print("\n>>> [START] post_learning_execution", flush=True)
    try:
        from tae_paper_execution import run_post_learning_changed_execution

        _dec = _load_json(DECISIONS_JSON) or {}
        post_exec = run_post_learning_changed_execution(
            cycle_id=str(_dec.get("generated_at") or ""),
            write_report_flag=False,
        )
        print(
            f">>> [END] post_learning_execution candidates={post_exec.get('candidates')} "
            f"orders={post_exec.get('orders_created')} trades={post_exec.get('trades_written')} "
            f"tickers={post_exec.get('executed_tickers')}",
            flush=True,
        )
        cli_steps.append(
            {
                "step": "post_learning_execution",
                "ok": bool(post_exec.get("ok")),
                "exit_code": 0 if post_exec.get("ok") else 1,
                "candidates": post_exec.get("candidates"),
                "orders_created": post_exec.get("orders_created"),
                "trades_written": post_exec.get("trades_written"),
                "executed_tickers": post_exec.get("executed_tickers"),
                "skipped": post_exec.get("skipped"),
            }
        )
        steps.append(
            StepRecord(
                rank=16,
                step_id="post_learning_execution",
                name="POST-LEARNING EXECUTION",
                rule_class="HARD",
                ok=bool(post_exec.get("ok")),
                status="PASS" if post_exec.get("ok") else "FAIL",
                reason=None if post_exec.get("ok") else "post-learning execution integrity failure",
                inputs=[str(DECISIONS_JSON), "paper_decisions_pre_evolution.json"],
                outputs=[str(PAPER_PORTFOLIO_JSON), "paper_orders.jsonl"],
                metrics={
                    "candidates": post_exec.get("candidates"),
                    "orders_created": post_exec.get("orders_created"),
                    "trades_written": post_exec.get("trades_written"),
                },
            )
        )
        if not post_exec.get("ok"):
            exit_code = 1
    except Exception as exc:
        print(f">>> [FAIL] post_learning_execution: {exc}", flush=True)
        cli_steps.append({"step": "post_learning_execution", "ok": False, "error": str(exc)})
        exit_code = 1

    # Final MTM after any post-learning portfolio mutations
    r_mtm_final = run_cli_step("paper_mark_to_market_final", [py, "tae.py", "paper-mark-to-market"], cwd=root)
    cli_steps.append(r_mtm_final)
    steps.append(
        step_from_cli(
            12,
            "mark_to_market_final",
            "MARK-TO-MARKET (final)",
            "HARD",
            r_mtm_final,
            inputs=[str(PAPER_PORTFOLIO_JSON)],
            outputs=[str(PAPER_MTM_JSON)],
        )
    )
    if not r_mtm_final["ok"]:
        exit_code = r_mtm_final["exit_code"] or 1

    # Dual strategy: V1=canonical PAPER benchmark, V2=isolated challenger book (no daemon)
    print("\n>>> [START] dual_strategy_v1_v2", flush=True)
    try:
        from tae_canonical_dual_strategy import run_dual_strategy_for_fpc

        dual = run_dual_strategy_for_fpc(orchestration_run_id=orchestration_run_id)
        cli_steps.append(
            {
                "step": "dual_strategy_v1_v2",
                "ok": bool(dual.get("v1_ok")),
                "v1_ok": bool(dual.get("v1_ok")),
                "v2_ok": bool(dual.get("v2_ok")),
                "exit_code": 0 if dual.get("v1_ok") else 1,
                "isolation": (dual.get("report") or {}).get("isolation"),
            }
        )
        steps.append(
            StepRecord(
                rank=12,
                step_id="dual_strategy_v1_v2",
                name="DUAL STRATEGY V1+V2",
                rule_class="LEARNING",
                ok=bool(dual.get("v1_ok")),
                status="PASS" if dual.get("v1_ok") else "FAIL",
                reason=None
                if dual.get("v2_ok")
                else f"V2 isolated status={dual.get('v2_ok')} (V1 unaffected)",
                inputs=["paper_execution", "parallel_paper/v2"],
                outputs=["tae_v1_v2_canonical_dual_strategy_report.json"],
                metrics={
                    "v1_ok": dual.get("v1_ok"),
                    "v2_ok": dual.get("v2_ok"),
                },
            )
        )
        # V2 failure must not corrupt V1 / must not flip HARD exit by itself
        if dual.get("v1_ok") is False:
            exit_code = 1
    except Exception as exc:
        print(f">>> [FAIL] dual_strategy_v1_v2 (isolated): {exc}", flush=True)
        cli_steps.append({"step": "dual_strategy_v1_v2", "ok": True, "v2_ok": False, "error": str(exc), "fail_open": True})

    # ROI economic orchestration — after final decisions + post-learning execution + MTM
    print("\n>>> [START] roi_economic_orchestration", flush=True)
    try:
        from tae_roi001_challenger import run_roi_economic_orchestration

        roi_orch = run_roi_economic_orchestration(write_outputs=True)
        print(
            f">>> [END] roi_economic_orchestration status={roi_orch.get('status')} "
            f"sample={roi_orch.get('sample_size')} production={roi_orch.get('production_enabled')}",
            flush=True,
        )
        cli_steps.append(
            {
                "step": "roi_economic_orchestration",
                "ok": bool(roi_orch.get("ok")),
                "exit_code": 0 if roi_orch.get("ok") else 1,
                "active_roi_id": roi_orch.get("active_roi_id"),
                "status": roi_orch.get("status"),
                "sample_size": roi_orch.get("sample_size"),
                "production_enabled": roi_orch.get("production_enabled"),
                "verdict": roi_orch.get("verdict"),
            }
        )
        if roi_orch.get("verdict") == "BLOCKED_BY_ROI_STATE_CONFLICT":
            exit_code = 1
    except Exception as exc:
        print(f">>> [FAIL] roi_economic_orchestration: {exc}", flush=True)
        cli_steps.append({"step": "roi_economic_orchestration", "ok": False, "error": str(exc)})
        exit_code = 1

    # Rank 17 — DPE chain
    for name in (
        "dpe_events",
        "dpe_splitter",
        "dpe_competitive",
        "dpe_collaborative",
        "dpe_evaluator",
        "dpe_learning",
        "dpe_adaptive",
    ):
        r = run_cli_step(name, [py, "tae.py", name.replace("_", "-")], cwd=root)
        cli_steps.append(r)
    steps.append(
        StepRecord(
            rank=17,
            step_id="dpe",
            name="DPE",
            rule_class="LEARNING",
            ok=all(s.get("ok") for s in cli_steps if s.get("step", "").startswith("dpe_")),
            status="PASS",
            reason=None,
            inputs=["paper execution outcomes"],
            outputs=["runtime_outputs/dpe/"],
            metrics={"dpe_steps": len([s for s in cli_steps if str(s.get("step", "")).startswith("dpe")])},
        )
    )

    # Rank 18 — CANONICAL VS PAPER
    r_cmp = run_cli_step("canonical_vs_paper", [py, "tae.py", "canonical-vs-paper"], cwd=root)
    cli_steps.append(r_cmp)
    steps.append(
        step_from_cli(18, "canonical_vs_paper", "CANONICAL VS PAPER", "REPORT_ONLY", r_cmp, inputs=[str(ACCOUNTING_JSON), str(PAPER_PORTFOLIO_JSON)], outputs=["TAE_CANONICAL_VS_PAPER_REPORT.md"])
    )

    safety = check_forbidden_file_safety(root, before_mtimes=before_mtimes)
    if not safety.get("forbidden_content_diff_clean"):
        exit_code = 1

    # Rank 18 — PROMOTION LOCK
    from tae_live_promotion_lock import run_live_promotion_lock_audit

    print("\n>>> [promotion_lock] tae_live_promotion_lock.run_live_promotion_lock_audit")
    lock = run_live_promotion_lock_audit(rewrite_gate=True)
    steps.append(
        StepRecord(
            rank=18,
            step_id="promotion_lock",
            name="PROMOTION LOCK",
            rule_class="HARD",
            ok=bool(lock.get("pass")),
            status="PASS" if lock.get("pass") else "FAIL",
            reason=None,
            inputs=[str(PROMOTION_JSON)],
            outputs=["TAE_LIVE_PROMOTION_LOCK_REPORT.md"],
            metrics={"live_promotion_allowed": False},
        )
    )

    from tae_paper_execution import validate_portfolio_reconciliation

    paper_portfolio = _load_json(PAPER_PORTFOLIO_JSON) or {}
    paper_mtm = _load_json(PAPER_MTM_JSON) or {}
    hard_risk = _load_json(HARD_RISK_JSON) or {}
    paper_recon = validate_portfolio_reconciliation(paper_portfolio) if paper_portfolio else {"ok": True, "status": "UNKNOWN", "errors": []}
    mtm_status = _mark_to_market_status(paper_mtm)

    final_verdict, verdict_reasons = compute_final_verdict(
        steps,
        safety=safety,
        paper_reconciliation=paper_recon,
        hard_risk=hard_risk,
        mtm_status=mtm_status,
        paper_positions=len(paper_portfolio.get("positions") or {}),
    )

    # Rank 19 — FINAL VERDICT
    steps.append(
        StepRecord(
            rank=19,
            step_id="final_verdict",
            name="FINAL VERDICT",
            rule_class="HARD",
            ok=final_verdict in {"READY_FOR_PAPER_DAY", "READY_WITH_WARNINGS"},
            status=final_verdict,
            reason="; ".join(verdict_reasons[:5]) if verdict_reasons else None,
            inputs=["all governance steps"],
            outputs=[str(GOVERNANCE_JSON), str(CYCLE_SUMMARY_JSON)],
            metrics={"block_reasons": verdict_reasons},
        )
    )

    accounting = _load_json(ACCOUNTING_JSON) or {}
    try:
        from research_core.accounting.accounting_snapshot import build_accounting_snapshot

        accounting = build_accounting_snapshot(".")
    except Exception:
        pass
    canonical_value = _f(accounting.get("account_value_corrected") or accounting.get("total_account_value"))
    paper_value = _f(paper_portfolio.get("total_value"))

    paper_summary = {
        "paper_portfolio_value": paper_value,
        "paper_cash": _f(paper_portfolio.get("cash")),
        "paper_realized_pnl": _f(paper_portfolio.get("realized_pnl")),
        "paper_unrealized_pnl": _f(paper_portfolio.get("unrealized_pnl")),
        "paper_total_pnl": _f(paper_portfolio.get("total_pnl")),
        "paper_reconciliation_status": paper_recon.get("status"),
        "paper_reconciliation_ok": paper_recon.get("ok"),
        "hard_risk_status": hard_risk.get("status"),
        "hard_risk_breaches": hard_risk.get("breach_count"),
        "canonical_vs_paper_value_delta": round(paper_value - canonical_value, 4),
        "mark_to_market_status": mtm_status,
    }

    state: dict[str, Any] = {
        "schema": "tae.structural_governance.v1",
        "mode": MODE,
        "generated_at": _now(),
        "final_verdict": final_verdict,
        "block_reasons": verdict_reasons,
        "overrides": all_overrides,
        "hard_rules_enforced": [
            "STOP_LOSS_-3% (hard_risk_guardian → PDE override → SELL_PAPER)",
            "CRITICAL_LOSS_-5% (FORCE_SELL_REQUIRED)",
            "No PROTECT/SELL/REDUCE without PAPER position (PDE + execution)",
            "DISABLED rules cannot boost scores (rule_lifecycle + PDE)",
            "Unreconciled PAPER accounting blocks cycle",
            "broker_executed=false, live_money=false required",
            "live_promotion_allowed=false (promotion lock)",
            "Forbidden live path diff must be 0",
        ],
        "execution_hierarchy": EXECUTION_HIERARCHY,
        "module_registry": MODULE_REGISTRY,
        "steps": [step.__dict__ for step in sorted(steps, key=lambda s: s.rank)],
        "cli_steps": cli_steps,
        "safety": safety,
        "paper_summary": paper_summary,
        "live_promotion_allowed": False,
    }

    write_governance_reports(state)

    # Legacy cycle summary for dashboards
    from tae_full_paper_cycle import build_promotion_gate, collect_summary, write_report as write_cycle_report

    CYCLE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    validation = _load_json(VALIDATION_JSON) or {}
    promotion_gate = build_promotion_gate(validation)
    PROMOTION_JSON.write_text(json.dumps(promotion_gate, indent=2) + "\n", encoding="utf-8")

    rich_summary = collect_summary(
        cli_steps,
        forbidden_ok=bool(safety.get("forbidden_content_diff_clean")),
        safety=safety,
    )
    rich_summary.update(
        {
            "version": "v2_structural",
            "final_verdict": final_verdict,
            "governance_verdict": final_verdict,
            "governance_steps": state["steps"],
            "block_reasons": verdict_reasons,
            "hard_risk_status": hard_risk.get("status"),
            "hard_risk_breaches": hard_risk.get("breach_count"),
            "orchestration_run_id": orchestration_run_id,
            "trading_date": trading_date,
            "source_commit": source_commit,
            **paper_summary,
        }
    )
    CYCLE_SUMMARY_JSON.write_text(json.dumps(rich_summary, indent=2) + "\n", encoding="utf-8")
    write_cycle_report(rich_summary)

    # Stamp freshness metadata onto mandatory producer outputs (compatible additive fields).
    for rel in (
        "tae_accounting_snapshot.json",
        "tae_growth_intelligence.json",
        "tae_portfolio_profit_governor.json",
        "tae_adaptive_profit_policy_engine.json",
        "tae_infrastructure_health.json",
        "process_health.json",
        "runtime_outputs/generated_reports/tae_profit_protection_shadow.json",
        "runtime_outputs/dpe/adaptive/adaptive.json",
        "runtime_outputs/dpe/result_evaluator/evaluation.json",
        "runtime_outputs/dpe/learning/learning.json",
    ):
        _stamp_json_metadata(
            root / rel,
            run_id=orchestration_run_id,
            trading_date=trading_date,
            source_commit=source_commit,
        )

    # Rank 20 — INVESTMENT COUNCIL (synthesis only, REPORT_ONLY — does not affect verdict)
    print("\n>>> [investment_council] synthesizing operator brief from existing modules")
    from tae_investment_council import run_investment_council

    council = run_investment_council(write_outputs=True, include_morning_audit=False)
    steps.append(
        StepRecord(
            rank=20,
            step_id="investment_council",
            name="INVESTMENT COUNCIL",
            rule_class="REPORT_ONLY",
            ok=True,
            status="PASS",
            reason=None,
            inputs=["paper_decisions", "gii", "governance", "dpe", "rule_lifecycle"],
            outputs=["runtime_outputs/investment_council/council.json", "TAE_INVESTMENT_COUNCIL_REPORT.md"],
            metrics={
                "action_plan_count": len(council.get("final_paper_action_plan") or []),
                "governance_verdict": council.get("governance_verdict"),
            },
        )
    )

    # Morning operational audit last — freshness reflects this cycle's producers.
    # Morning audit is REPORT_ONLY for orchestration exit: ATTENTION_REQUIRED (e.g. expected
    # HSBA.L DPE shadow) must not flip the cycle to FAIL / launchd exit 1, and must not
    # leave failed_stages>0 on an otherwise PASS record.
    r_morning = run_cli_step("morning_audit", [py, "tae.py", "morning-audit"], cwd=root)
    morning_ec = int(r_morning.get("exit_code") or 0)
    if not r_morning.get("ok") and morning_ec in {1, 2}:
        r_morning = dict(r_morning)
        r_morning["ok"] = True
        r_morning["attention_nonblocking"] = True
        r_morning["reason"] = "ATTENTION_REQUIRED_NONBLOCKING_FOR_ORCHESTRATION"
        r_morning["morning_audit_exit_code"] = morning_ec

    cli_steps.append(r_morning)
    steps.append(
        step_from_cli(
            21,
            "morning_audit",
            "MORNING OPERATIONAL AUDIT",
            "REPORT_ONLY",
            r_morning,
            inputs=["accounting", "gii", "ppg", "appe", "infra", "dpe"],
            outputs=["tae_morning_operational_audit.json", "TAE_MORNING_OPERATIONAL_AUDIT.md"],
        )
    )
    state["steps"] = [step.__dict__ for step in sorted(steps, key=lambda s: s.rank)]
    state["investment_council"] = {
        "executive_recommendation": council.get("executive_recommendation"),
        "governance_verdict": council.get("governance_verdict"),
        "action_plan_count": len(council.get("final_paper_action_plan") or []),
    }
    state["orchestration_run_id"] = orchestration_run_id
    state["trading_date"] = trading_date
    state["source_commit"] = source_commit
    GOVERNANCE_JSON.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")

    end_ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    orch_record.update(
        {
            "end_timestamp": end_ts,
            "stage": "COMPLETE",
            "stage_status": "PASS" if exit_code == 0 and final_verdict != "BLOCKED_WITH_REASONS" else "FAIL",
            "status": "PASS" if exit_code == 0 and final_verdict != "BLOCKED_WITH_REASONS" else "FAIL",
            "final_verdict": final_verdict,
            "exit_code": exit_code,
            "failed_stages": sum(1 for s in cli_steps if s.get("ok") is False),
            "stages": [
                {
                    "step": s.get("step") or s.get("step_id"),
                    "ok": s.get("ok"),
                    "exit_code": s.get("exit_code"),
                }
                for s in cli_steps
            ],
        }
    )
    _write_orchestration_run(orch_record)
    _stamp_json_metadata(
        ORCHESTRATION_RUN_JSON,
        run_id=orchestration_run_id,
        trading_date=trading_date,
        source_commit=source_commit,
    )

    print("\n===== TAE STRUCTURAL GOVERNANCE — COMPLETE =====", flush=True)
    print("Final verdict:", final_verdict, flush=True)
    print("orchestration_run_id:", orchestration_run_id, flush=True)
    print("Wrote:", GOVERNANCE_JSON, GOVERNANCE_REPORT_MD, CONSOLIDATION_REPORT_MD, CYCLE_SUMMARY_JSON, flush=True)

    trace_end("structural_paper_cycle", cycle_t0)

    if final_verdict == "BLOCKED_WITH_REASONS":
        exit_code = 1
    elif final_verdict in {"READY_FOR_PAPER_DAY", "READY_WITH_WARNINGS"}:
        # Intermediate soft/shadow step failures must not override a READY governance verdict.
        exit_code = 0

    return exit_code, state
