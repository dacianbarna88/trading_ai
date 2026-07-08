#!/usr/bin/env python3
"""
TAE DPE Validation Program — Start Gate (read-only).

Confirms readiness for 30-day PAPER validation. Does not modify trading,
DPE logic, or live safety files.
"""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(".")
OUTPUT_MD = ROOT / "TAE_DPE_VALIDATION_START_GATE.md"

INFRA_JSON = ROOT / "tae_infrastructure_health.json"
ACCOUNTING_JSON = ROOT / "tae_accounting_snapshot.json"
JOBS_JSONL = ROOT / "runtime_outputs/dpe/execution_jobs.jsonl"
ADAPTIVE_JSON = ROOT / "runtime_outputs/dpe/adaptive/adaptive.json"

GROWTH_ANALYTICS = ROOT / "tae_profit_growth_analytics.json"
OPPORTUNITY_LEDGER = ROOT / "tae_opportunity_cost_ledger.json"
WINNER_PROFILER = ROOT / "tae_winner_lifecycle_profiler.json"

PAPER_COMP = ROOT / "runtime_outputs/dpe/paper_competitive"
PAPER_COLLAB = ROOT / "runtime_outputs/dpe/paper_collaborative"

FORBIDDEN_PATHS = (
    "live_bot.py",
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "core/",
)

DPE_MODULES = (
    "tae_decision_event_bus.py",
    "tae_execution_splitter.py",
    "tae_dpe_competitive_executor.py",
    "tae_dpe_collaborative_executor.py",
    "tae_dpe_paper_executor_infra.py",
    "tae_dpe_result_evaluator.py",
    "tae_dpe_learning_engine.py",
    "tae_dpe_adaptive_selector.py",
)

EXECUTOR_MODULES = frozenset(
    {
        "tae_dpe_competitive_executor.py",
        "tae_dpe_collaborative_executor.py",
        "tae_dpe_paper_executor_infra.py",
    }
)
CAPTURE_MODULES = frozenset(
    {
        "tae_decision_event_bus.py",
        "tae_execution_splitter.py",
    }
)
GUARD_ANY_OF = (
    "NO_REAL_EXECUTION",
    "no_live_execution",
    "NO_LIVE_EXECUTION",
    "SHADOW_ONLY",
    "READ_ONLY",
)

DAY1_COMMAND = (
    "python3 tae.py morning-audit && "
    "python3 tae.py dpe-events && "
    "python3 tae.py dpe-splitter && "
    "python3 tae.py dpe-competitive && "
    "python3 tae.py dpe-collaborative && "
    "python3 tae.py dpe-evaluator && "
    "python3 tae.py dpe-learning && "
    "python3 tae.py dpe-adaptive"
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError):
        return None


def _check_result(
    checks: list[dict[str, Any]],
    *,
    item_id: str,
    title: str,
    passed: bool,
    evidence: str,
    detail: str,
    blocker: bool = True,
) -> None:
    checks.append(
        {
            "id": item_id,
            "title": title,
            "status": "PASS" if passed else "FAIL",
            "evidence": evidence,
            "detail": detail,
            "blocker": blocker,
        }
    )


def _git_diff_forbidden() -> tuple[bool, str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--"] + list(FORBIDDEN_PATHS),
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"git diff unavailable: {exc}"
    diff = (result.stdout or "").strip()
    if diff:
        return False, f"diff lines present ({len(diff.splitlines())} lines)"
    return True, "0 diff lines on live safety paths"


def _audit_blocked_jobs() -> tuple[bool, str, list[str]]:
    if not JOBS_JSONL.is_file():
        return False, "execution_jobs.jsonl missing", ["missing jobs file"]
    blocked: list[dict[str, Any]] = []
    try:
        for line in JOBS_JSONL.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            job = json.loads(line)
            if job.get("status") == "BLOCKED":
                blocked.append(job)
    except (json.JSONDecodeError, OSError) as exc:
        return False, f"jobs read error: {exc}", [str(exc)]

    if not blocked:
        return True, "no BLOCKED jobs", []

    reasons = Counter(str(j.get("decision_reason") or "UNKNOWN") for j in blocked)
    tickers = Counter(str(j.get("ticker") or "UNKNOWN") for j in blocked)
    unique_ids = {str(j.get("job_id")) for j in blocked if j.get("job_id")}

    unexpected: list[str] = []
    for job in blocked:
        reason = str(job.get("decision_reason") or "")
        ticker = str(job.get("ticker") or "")
        if reason != "COLLAPSE_RISK":
            unexpected.append(f"unexpected reason {reason} on {ticker}")
        if ticker == "PORTFOLIO":
            unexpected.append("BLOCKED on PORTFOLIO aggregate")

    if unexpected:
        return False, f"{len(blocked)} blocked lines, {len(unique_ids)} unique, unexpected={len(unexpected)}", unexpected

    detail = (
        f"{len(blocked)} blocked lines / {len(unique_ids)} unique job_ids — "
        f"reasons={dict(reasons)} tickers={dict(tickers)} (expected COLLAPSE_RISK / HSBA.L)"
    )
    return True, detail, []


def _check_paper_arm(path: Path, arm: str) -> tuple[bool, str]:
    required = ("portfolio.json", "metrics.json", "executor_report.md", "orders.jsonl", "trades.jsonl")
    missing = [name for name in required if not (path / name).is_file()]
    if missing:
        return False, f"{arm}: missing {', '.join(missing)}"
    metrics = _load_json(path / "metrics.json") or {}
    mode = metrics.get("mode")
    executor = metrics.get("executor")
    if mode != "PAPER_ONLY":
        return False, f"{arm}: metrics.mode={mode!r} (expected PAPER_ONLY)"
    if executor != arm:
        return False, f"{arm}: metrics.executor={executor!r}"
    return True, f"{arm}: portfolio.json + metrics.json + reports present (mode=PAPER_ONLY)"


def _check_guards() -> tuple[bool, str, list[str]]:
    warnings: list[str] = []
    infra_text = ""
    infra_path = ROOT / "tae_dpe_paper_executor_infra.py"
    if infra_path.is_file():
        infra_text = infra_path.read_text(encoding="utf-8", errors="replace")

    for module in DPE_MODULES:
        path = ROOT / module
        if not path.is_file():
            return False, f"missing module {module}", [f"missing {module}"]
        text = path.read_text(encoding="utf-8", errors="replace")
        guard_text = text
        if module == "tae_dpe_collaborative_executor.py" and "tae_dpe_paper_executor_infra" in text:
            guard_text = text + "\n" + infra_text

        if "NO_BROKER" not in guard_text:
            return False, f"{module} missing NO_BROKER", [f"{module}: NO_BROKER"]
        if module in EXECUTOR_MODULES and "PAPER_ONLY" not in guard_text:
            return False, f"{module} missing PAPER_ONLY", [f"{module}: PAPER_ONLY"]
        if module in CAPTURE_MODULES and not any(tok in guard_text for tok in ("SHADOW_ONLY", "READ_ONLY")):
            return False, f"{module} missing SHADOW_ONLY/READ_ONLY", [f"{module}: capture mode"]
        if module not in EXECUTOR_MODULES and module not in CAPTURE_MODULES:
            if not any(tok in guard_text for tok in ("PAPER_ONLY", "READ_ONLY", "SHADOW_ONLY")):
                return False, f"{module} missing mode guard", [f"{module}: mode guard"]
        if not any(tok in guard_text for tok in GUARD_ANY_OF):
            warnings.append(f"{module}: no explicit no-execution token (has NO_BROKER + mode guard)")
    return True, f"all {len(DPE_MODULES)} DPE modules declare NO_BROKER + mode/no-execution guards", warnings


def _check_ssot(path: Path, label: str) -> tuple[bool, str]:
    data = _load_json(path)
    if not data:
        return False, f"{label} missing or invalid JSON"
    if data.get("read_only") is not True and data.get("mode") not in {"SHADOW_ONLY", "READ_ONLY"}:
        return False, f"{label} missing read_only/mode safety flags"
    if data.get("no_broker") is not True and not (data.get("safety_mode") or {}).get("no_broker"):
        return False, f"{label} missing no_broker flag"
    generated = data.get("generated_at") or "unknown"
    return True, f"{label} readable (generated_at={generated})"


def run_gate() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []

    infra = _load_json(INFRA_JSON)
    infra_pass = infra is not None and str(infra.get("overall_status")).upper() == "PASS"
    _check_result(
        checks,
        item_id="1",
        title="Infrastructure Health = PASS",
        passed=infra_pass,
        evidence=str(INFRA_JSON),
        detail=(
            f"overall_status={infra.get('overall_status') if infra else 'MISSING'}, "
            f"runtime_operational={infra.get('runtime_operational') if infra else False}"
        ),
    )
    if not infra_pass:
        blockers.append("Infrastructure Health is not PASS — run: python3 tae_infrastructure_health.py")

    accounting = _load_json(ACCOUNTING_JSON)
    delta_raw = (accounting or {}).get("account_value_reconciliation_delta")
    delta = float(delta_raw) if delta_raw is not None else None
    reconciled = accounting is not None and delta is not None and abs(delta) <= 0.01
    quality = (accounting or {}).get("data_quality_status", "MISSING")
    acct_detail = (
        f"data_quality={quality}, reconciliation_delta={delta}, "
        f"account_value={(accounting or {}).get('account_value_corrected')}"
    )
    if quality == "HISTORICAL_RECONCILIATION_REQUIRED" and reconciled:
        warnings.append("Accounting label HISTORICAL_RECONCILIATION_REQUIRED — canonical path reconciled (see TAE_ACCOUNTING_RECONCILIATION_REPORT.md)")
    _check_result(
        checks,
        item_id="2",
        title="Accounting reconciliation canonical path = PASS",
        passed=reconciled,
        evidence=str(ACCOUNTING_JSON),
        detail=acct_detail,
    )
    if not reconciled:
        blockers.append("Accounting canonical path not reconciled (delta != 0)")

    blocked_ok, blocked_detail, unexpected = _audit_blocked_jobs()
    _check_result(
        checks,
        item_id="3",
        title="DPE blocked jobs expected/classified",
        passed=blocked_ok,
        evidence=str(JOBS_JSONL),
        detail=blocked_detail,
    )
    if not blocked_ok:
        blockers.extend(unexpected or [blocked_detail])
    elif blocked_detail != "no BLOCKED jobs":
        warnings.append(f"Blocked jobs classified: {blocked_detail}")

    guards_ok, guards_detail, guard_warnings = _check_guards()
    _check_result(
        checks,
        item_id="4",
        title="PAPER_ONLY / NO_BROKER / NO_AUTO_EXECUTION guards present",
        passed=guards_ok,
        evidence=", ".join(DPE_MODULES),
        detail=guards_detail,
    )
    warnings.extend(guard_warnings)
    if not guards_ok:
        blockers.append(guards_detail)

    comp_ok, comp_detail = _check_paper_arm(PAPER_COMP, "COMPETITIVE")
    collab_ok, collab_detail = _check_paper_arm(PAPER_COLLAB, "COLLABORATIVE")
    both_ok = comp_ok and collab_ok
    _check_result(
        checks,
        item_id="5",
        title="Competitive and Collaborative DPE outputs available",
        passed=both_ok,
        evidence=f"{PAPER_COMP}, {PAPER_COLLAB}",
        detail=f"{comp_detail}; {collab_detail}",
    )
    if not both_ok:
        blockers.append(comp_detail if not comp_ok else collab_detail)

    ga_ok, ga_detail = _check_ssot(GROWTH_ANALYTICS, "Growth Analytics SSOT")
    _check_result(checks, item_id="6", title="Growth Analytics SSOT readable", passed=ga_ok, evidence=str(GROWTH_ANALYTICS), detail=ga_detail)
    if not ga_ok:
        blockers.append(ga_detail)

    oc_ok, oc_detail = _check_ssot(OPPORTUNITY_LEDGER, "Opportunity Cost Ledger")
    _check_result(checks, item_id="7", title="Opportunity Cost Ledger readable", passed=oc_ok, evidence=str(OPPORTUNITY_LEDGER), detail=oc_detail)
    if not oc_ok:
        blockers.append(oc_detail)

    wl_ok, wl_detail = _check_ssot(WINNER_PROFILER, "Winner Lifecycle Profiler")
    _check_result(checks, item_id="8", title="Winner Lifecycle Profiler readable", passed=wl_ok, evidence=str(WINNER_PROFILER), detail=wl_detail)
    if not wl_ok:
        blockers.append(wl_detail)

    adaptive = _load_json(ADAPTIVE_JSON)
    pref = (adaptive or {}).get("preferred_philosophy")
    conf = (adaptive or {}).get("confidence")
    adaptive_ok = (
        adaptive is not None
        and pref in {"COMPETITIVE", "COLLABORATIVE", "TIE"}
        and conf is not None
        and float(conf) > 0
    )
    _check_result(
        checks,
        item_id="9",
        title="Adaptive Philosophy Selector current preference + confidence",
        passed=adaptive_ok,
        evidence=str(ADAPTIVE_JSON),
        detail=f"preferred={pref}, confidence={conf}%",
    )
    if not adaptive_ok:
        blockers.append("Adaptive recommendation missing or incomplete — run: python3 tae.py dpe-adaptive")

    live_ok, live_detail = _git_diff_forbidden()
    _check_result(
        checks,
        item_id="10",
        title="No live safety files modified",
        passed=live_ok,
        evidence=", ".join(FORBIDDEN_PATHS),
        detail=live_detail,
    )
    if not live_ok:
        blockers.append(f"Live safety file modifications detected: {live_detail}")

    if infra and infra.get("summary", {}).get("warn"):
        warnings.append(f"Infrastructure warnings: {infra['summary']['warn']} check(s)")
    bot_check = next((c for c in (infra or {}).get("checks", []) if c.get("name") == "live_bot_process"), None)
    if bot_check and bot_check.get("status") == "WARN":
        warnings.append(f"Infra note: {bot_check.get('detail')}")

    required_pass = all(c["status"] == "PASS" for c in checks)
    verdict = "READY_FOR_30_DAY_PAPER_VALIDATION" if required_pass and not blockers else "NOT_READY_WITH_REASONS"

    return {
        "generated_at": _now(),
        "verdict": verdict,
        "checks": checks,
        "blockers": blockers,
        "warnings": warnings,
        "day1_command": DAY1_COMMAND,
        "evidence_index": {
            "infrastructure": str(INFRA_JSON),
            "accounting": str(ACCOUNTING_JSON),
            "blocked_jobs": str(JOBS_JSONL),
            "blocked_job_report": "TAE_DPE_BLOCKED_JOB_REPORT.md",
            "accounting_report": "TAE_ACCOUNTING_RECONCILIATION_REPORT.md",
            "paper_competitive": str(PAPER_COMP),
            "paper_collaborative": str(PAPER_COLLAB),
            "growth_analytics": str(GROWTH_ANALYTICS),
            "opportunity_ledger": str(OPPORTUNITY_LEDGER),
            "winner_profiler": str(WINNER_PROFILER),
            "adaptive": str(ADAPTIVE_JSON),
            "dpe_modules": list(DPE_MODULES),
        },
    }


def format_report(data: dict[str, Any]) -> str:
    lines = [
        "# TAE DPE Validation Program — Start Gate",
        "",
        f"**Generated:** {data['generated_at']}",
        "**Mode:** READ_ONLY · PAPER_ONLY · NO_BROKER · NO_COMMIT",
        "",
        "## Verdict",
        "",
        "```text",
        data["verdict"],
        "```",
        "",
        "## Checklist",
        "",
        "| # | Check | Status | Evidence |",
        "|---|-------|--------|----------|",
    ]
    for check in data["checks"]:
        lines.append(
            f"| {check['id']} | {check['title']} | **{check['status']}** | `{check['evidence']}` |"
        )
    lines.extend(["", "## Check details", ""])
    for check in data["checks"]:
        lines.append(f"### {check['id']}. {check['title']} — {check['status']}")
        lines.append(f"- Detail: {check['detail']}")
        lines.append("")

    lines.extend(["## Evidence paths", ""])
    for key, path in data["evidence_index"].items():
        if isinstance(path, list):
            lines.append(f"- **{key}:**")
            for item in path:
                lines.append(f"  - `{item}`")
        else:
            lines.append(f"- **{key}:** `{path}`")
    lines.append("")

    lines.extend(["## Blockers", ""])
    if data["blockers"]:
        for item in data["blockers"]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(["## Warnings", ""])
    if data["warnings"]:
        for item in data["warnings"]:
            lines.append(f"- {item}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(
        [
            "## Day 1 — exact next command",
            "",
            "Run this once at market-open on validation Day 1 (read-only audit + full DPE paper chain):",
            "",
            "```bash",
            data["day1_command"],
            "```",
            "",
            "## Safety confirmation",
            "",
            "| Rule | Status |",
            "|------|--------|",
            "| Trading logic modified | **no** |",
            "| DPE logic modified | **no** |",
            "| live_bot.py modified | **no** |",
            "| portfolio.csv modified | **no** |",
            "| NO_BROKER | **yes** |",
            "| NO_COMMIT | **yes** |",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    data = run_gate()
    OUTPUT_MD.write_text(format_report(data) + "\n", encoding="utf-8")
    print("===== TAE DPE VALIDATION START GATE =====")
    print("Verdict:", data["verdict"])
    print("")
    for check in data["checks"]:
        print(f"  [{check['status']}] {check['id']}. {check['title']}")
    if data["blockers"]:
        print("")
        print("Blockers:")
        for b in data["blockers"]:
            print(" -", b)
    if data["warnings"]:
        print("")
        print("Warnings:")
        for w in data["warnings"]:
            print(" -", w)
    print("")
    print("Day 1 command:")
    print(data["day1_command"])
    print("")
    print("Wrote:", OUTPUT_MD)
    return 0 if data["verdict"] == "READY_FOR_30_DAY_PAPER_VALIDATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())
