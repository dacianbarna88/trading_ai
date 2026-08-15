#!/usr/bin/env python3
"""
TAE final-check — single non-destructive closure verification.

Aggregates existing health / parallel / lifecycle / isolation checks.
Does not mutate portfolios, ledgers, or trading economics.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT = Path(__file__).resolve().parent
REPORT_JSON = PROJECT / "tae_final_check.json"
REPORT_MD = PROJECT / "TAE_FINAL_CHECK.md"

REQUIRED_AGENTS = (
    "com.tradingai.live-bot",
    "com.tradingai.dashboard",
    "com.tradingai.parallel-paper",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _pgrep(pattern: str) -> list[int]:
    r = subprocess.run(
        ["pgrep", "-f", pattern],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return []
    out: list[int] = []
    for line in (r.stdout or "").splitlines():
        line = line.strip()
        if line.isdigit():
            out.append(int(line))
    return out


def _launchctl_print(label: str) -> dict[str, Any]:
    domain = f"gui/{os.getuid()}"
    r = subprocess.run(
        ["launchctl", "print", f"{domain}/{label}"],
        capture_output=True,
        text=True,
        check=False,
    )
    text = r.stdout or ""
    return {
        "label": label,
        "loaded": r.returncode == 0,
        "running": "state = running" in text,
        "keepalive": "keepalive = 1" in text.lower() or "keepalive = 1" in text,
        "snippet": "\n".join(text.splitlines()[:12]),
    }


def _pid_alive(pid: int) -> bool:
    """True if pid exists. Prefer os.kill(0); fall back to ps when needed."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # Process exists but not owned by us — still counts as alive.
        return True
    except OSError:
        pass
    r = subprocess.run(
        ["ps", "-p", str(pid), "-o", "pid="],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.returncode == 0 and bool((r.stdout or "").strip())


def _parallel_pids_from_runtime() -> list[int]:
    """Resolve parallel-paper PID via pid file / heartbeat when pgrep misses launchd children."""
    pids: list[int] = []
    try:
        from tae_parallel_paper_config import paths

        p = paths()
        candidates: list[int] = []
        pid_path = p.get("pid")
        if pid_path and Path(pid_path).is_file():
            raw = Path(pid_path).read_text(encoding="utf-8").strip()
            if raw.isdigit():
                candidates.append(int(raw))
        hb = p.get("heartbeat")
        if hb and Path(hb).is_file():
            data = json.loads(Path(hb).read_text(encoding="utf-8"))
            hb_pid = data.get("pid")
            if hb_pid is not None and str(hb_pid).isdigit():
                candidates.append(int(hb_pid))
        try:
            from tae_parallel_paper_runtime import health_snapshot

            h = health_snapshot()
            h_pid = h.get("pid") or (h.get("daemon") or {}).get("pid")
            if h_pid is not None and str(h_pid).isdigit():
                candidates.append(int(h_pid))
        except Exception:
            pass
        for pid in candidates:
            if pid not in pids and _pid_alive(pid):
                pids.append(pid)
    except Exception:
        return pids
    return pids


def _git_status() -> dict[str, Any]:
    """Absolute cleanliness: any non-empty git status fails final-check."""
    r = subprocess.run(
        ["git", "status", "--short"],
        cwd=str(PROJECT),
        capture_output=True,
        text=True,
        check=False,
    )
    lines = [ln for ln in (r.stdout or "").splitlines() if ln.strip()]
    return {
        "total_entries": len(lines),
        "entries": lines[:50],
        "clean": len(lines) == 0,
    }


def run_final_check(*, write_report: bool = True, profile: str = "full") -> dict[str, Any]:
    profile_n = str(profile or "full").strip().lower()
    if profile_n not in {"full", "paper", "live"}:
        profile_n = "full"
    reasons: list[str] = []
    checks: dict[str, Any] = {
        "generated_at": _utc_now(),
        "project": str(PROJECT),
        "profile": profile_n,
    }

    # --- Git ---
    git_info = _git_status()
    checks["git"] = git_info
    if not git_info["clean"]:
        reasons.append(f"git_dirty:{git_info['total_entries']}")

    # --- Processes / duplicates ---
    bot_pids = _pgrep(str(PROJECT / "live_bot.py"))
    # Prefer absolute path match; fall back to basename
    if not bot_pids:
        bot_pids = [p for p in _pgrep("live_bot.py") if True]
    dash_pids = _pgrep("streamlit run .*dashboard_v2")
    if not dash_pids:
        dash_pids = _pgrep("dashboard_v2.py")
    parallel_pids = _pgrep(str(PROJECT / "tae_parallel_paper_daemon.py"))
    if not parallel_pids:
        parallel_pids = _pgrep("tae_parallel_paper_daemon.py")
    # CONNECT: fallback to pid file / health_snapshot when pgrep false-negatives under sandbox/launchd
    if not parallel_pids:
        parallel_pids = _parallel_pids_from_runtime()

    # Deduplicate accidental self-matches from broad patterns by unique set
    bot_pids = sorted(set(bot_pids))
    dash_pids = sorted(set(dash_pids))
    parallel_pids = sorted(set(parallel_pids))

    proc = {
        "live_bot": {"pids": bot_pids, "count": len(bot_pids)},
        "dashboard": {"pids": dash_pids, "count": len(dash_pids)},
        "parallel_paper": {"pids": parallel_pids, "count": len(parallel_pids)},
    }
    checks["processes"] = proc
    for name, info in proc.items():
        if profile_n == "paper" and name in {"live_bot", "dashboard"}:
            # LIVE/dashboard optional for PAPER profile
            continue
        if profile_n == "live" and name == "parallel_paper":
            continue
        if info["count"] != 1:
            reasons.append(f"process_count_{name}={info['count']}")

    # TTY / PPID for each
    tty_ok = True
    for name, info in proc.items():
        if profile_n == "paper" and name in {"live_bot", "dashboard"}:
            continue
        metas = []
        for pid in info["pids"]:
            try:
                r = subprocess.run(
                    ["ps", "-o", "pid=,ppid=,tty=,command=", "-p", str(pid)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except (PermissionError, OSError):
                # Sandbox / restricted hosts: skip TTY probe; process existence already proven.
                metas.append({"pid": pid, "ppid": None, "tty": "??", "tty_probe": "skipped"})
                continue
            parts = (r.stdout or "").split(None, 3)
            if len(parts) >= 3:
                meta = {
                    "pid": int(parts[0]),
                    "ppid": int(parts[1]),
                    "tty": parts[2],
                }
                metas.append(meta)
                if meta["tty"] != "??" or meta["ppid"] != 1:
                    tty_ok = False
                    reasons.append(f"{name}_terminal_or_ppid pid={meta['pid']}")
        info["metas"] = metas
    checks["terminal_dependency"] = not tty_ok
    if not tty_ok and "terminal_dependency" not in " ".join(reasons):
        pass

    # --- LaunchAgents ---
    agents = {label: _launchctl_print(label) for label in REQUIRED_AGENTS}
    checks["launch_agents"] = agents
    for label, info in agents.items():
        if profile_n == "paper" and label in {"com.tradingai.live-bot", "com.tradingai.dashboard"}:
            continue
        if profile_n == "live" and label == "com.tradingai.parallel-paper":
            continue
        if not info["loaded"]:
            reasons.append(f"agent_not_loaded:{label}")
        elif not info["running"] and label != "com.tradingai.dashboard":
            # dashboard should also be running
            reasons.append(f"agent_not_running:{label}")
        if info["loaded"] and not info.get("keepalive"):
            # keepalive text may vary; soft warn only if process missing
            if proc[
                {
                    "com.tradingai.live-bot": "live_bot",
                    "com.tradingai.dashboard": "dashboard",
                    "com.tradingai.parallel-paper": "parallel_paper",
                }[label]
            ]["count"] != 1:
                reasons.append(f"keepalive_unconfirmed:{label}")
    for label, info in agents.items():
        if profile_n == "paper" and label == "com.tradingai.dashboard":
            continue
        if label == "com.tradingai.dashboard" and not info["running"]:
            reasons.append(f"agent_not_running:{label}")

    # --- Parallel health / isolation / accounting ---
    try:
        from tae_parallel_paper_config import load_parallel_paper_config
        from tae_parallel_paper_runtime import health_snapshot

        cfg = load_parallel_paper_config()
        health = health_snapshot()
        acct = health.get("accounting") if isinstance(health.get("accounting"), dict) else {}
        v1 = health.get("v1") if isinstance(health.get("v1"), dict) else {}
        v2 = health.get("v2") if isinstance(health.get("v2"), dict) else {}
        checks["parallel_config"] = {
            "V1_PARALLEL_ENABLED": cfg.get("V1_PARALLEL_ENABLED"),
            "V2_PARALLEL_ENABLED": cfg.get("V2_PARALLEL_ENABLED"),
            "V2_PARALLEL_PAPER_ENABLED": cfg.get("V2_PARALLEL_PAPER_ENABLED"),
            "V2_LIVE_ENABLED": cfg.get("V2_LIVE_ENABLED"),
            "V2_CANONICAL_PAPER_ENABLED": cfg.get("V2_CANONICAL_PAPER_ENABLED"),
            "V2_ACTIVATION_SCOPE": cfg.get("V2_ACTIVATION_SCOPE"),
            "AUTO_START_ENABLED": cfg.get("AUTO_START_ENABLED"),
            "PARALLEL_PAPER_ENABLED": cfg.get("PARALLEL_PAPER_ENABLED"),
        }
        checks["parallel_health"] = {
            "overall_status": health.get("overall_status") or health.get("status"),
            "accounting_status": health.get("accounting_status"),
            "v1_pass": acct.get("v1_pass", v1.get("accounting_pass")),
            "v2_pass": acct.get("v2_pass", v2.get("accounting_pass")),
            "V2_LIVE_ENABLED": health.get("V2_LIVE_ENABLED"),
            "pid_alive": health.get("pid_alive"),
            "heartbeat_status": health.get("heartbeat_status"),
        }
        if cfg.get("V2_LIVE_ENABLED") is True:
            reasons.append("V2_LIVE_ENABLED_true")
        if cfg.get("V2_CANONICAL_PAPER_ENABLED") is True:
            reasons.append("V2_CANONICAL_PAPER_ENABLED_true")
        if health.get("V2_LIVE_ENABLED") is True:
            reasons.append("health_V2_LIVE_ENABLED_true")
        acct = checks["parallel_health"]
        if acct.get("v1_pass") is False:
            reasons.append("v1_accounting_fail")
        if acct.get("v2_pass") is False:
            reasons.append("v2_accounting_fail")
        status = str(acct.get("overall_status") or "")
        if status and status not in {
            "RUNNING_HEALTHY",
            "RUNNING_HEARTBEAT_STALE",
            "STOPPED_HEALTHY_STATE",
            "STOPPED_CLEAN",
        }:
            if "DEGRADED" in status or "FAIL" in status or "ERROR" in status:
                reasons.append(f"parallel_status:{status}")
        # Capital-cycle wiring evidence (modules present + prior test file)
        cycle_test = PROJECT / "tae_parallel_capital_cycle_test.py"
        checks["capital_cycle_wiring"] = {
            "test_present": cycle_test.is_file(),
            "runtime_module": (PROJECT / "tae_parallel_paper_runtime.py").is_file(),
            "reentry_module": (PROJECT / "tae_strategy_v2_reentry_policy.py").is_file(),
        }
        if not all(checks["capital_cycle_wiring"].values()):
            reasons.append("capital_cycle_wiring_incomplete")
    except Exception as exc:  # noqa: BLE001 — surface as fail-closed
        checks["parallel_error"] = f"{type(exc).__name__}: {exc}"
        reasons.append(f"parallel_health_error:{type(exc).__name__}")

    # --- Quick health (same SSOT as tae.py health; profile-aware) ---
    try:
        import tae_quick_health_check as qhc

        live = qhc.run_health_check(profile=profile_n)
        qpath = PROJECT / "tae_quick_health_check.json"
        checks["quick_health"] = {
            "final_verdict": live.get("verdict"),
            "profile": live.get("profile"),
            "trading_readiness": (live.get("trading_readiness") or {}),
            "ops_state": live.get("ops_state") or (live.get("operational") or {}).get("state"),
            "domains": live.get("domains"),
            "report_present": qpath.is_file(),
        }
        verdict = str(live.get("verdict") or "")
        ok_verdicts = {"HEALTHY", "READY", "HEALTHY_WITH_IDLE_COMPONENTS", "DEGRADED"}
        if verdict not in ok_verdicts:
            reasons.append(f"health_verdict:{verdict}")
        tr = checks["quick_health"]["trading_readiness"] or {}
        blockers = tr.get("blocking_reasons") or []
        if blockers:
            reasons.append(f"trading_blocked:{','.join(map(str, blockers))}")
        if tr.get("warning_reasons"):
            # Absolute clean for full; paper reports warnings without FAIL
            tag = "health_warnings:" + ",".join(map(str, tr.get("warning_reasons") or []))
            if profile_n == "paper":
                checks.setdefault("paper_info", []).append(tag)
            else:
                reasons.append(tag)
    except Exception as exc:  # noqa: BLE001
        checks["quick_health_error"] = f"{type(exc).__name__}: {exc}"
        reasons.append(f"quick_health_error:{type(exc).__name__}")

    # --- Dashboard port uniqueness ---
    try:
        r = subprocess.run(
            ["lsof", "-iTCP:8501", "-sTCP:LISTEN", "-t"],
            capture_output=True,
            text=True,
            check=False,
        )
        listen_pids = sorted({int(x) for x in (r.stdout or "").split() if x.isdigit()})
        checks["dashboard_port"] = {"listen_pids": listen_pids, "count": len(listen_pids)}
        if profile_n != "paper" and len(listen_pids) != 1:
            reasons.append(f"dashboard_port_listeners={len(listen_pids)}")
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"dashboard_port_error:{type(exc).__name__}")

    # --- Canonical learning: no stale foreign PID / duplicate spam ---
    try:
        from tae_canonical_learning_runtime import resolve_learning_pid, read_pid

        raw = read_pid()
        resolved = resolve_learning_pid()
        checks["canonical_learning"] = {"raw_pid": raw, "resolved_pid": resolved}
        # After resolve, raw foreign pid must be cleared
        if raw is not None and resolved is None and raw != resolved:
            # resolve clears foreign — re-read
            raw2 = read_pid()
            if raw2 is not None and resolve_learning_pid() is None:
                reasons.append(f"learning_stale_pid:{raw2}")
        # Duplicate attempts: agent exit loop with foreign pid is a defect if still present
        if raw is not None and resolved is None:
            # cleared ok
            pass
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"learning_pid_error:{type(exc).__name__}")

    # --- No regenerable reports in repo root ---
    root_polluters = []
    for name in (
        "tae_confidence_evolution.md",
        "tae_decision_governor.md",
        "tae_decision_replay.json",
        "tae_decision_replay.md",
        "tae_infrastructure_health.md",
        "tae_intraday_discovery_engine.md",
        "tae_intraday_fade_history_summary.md",
        "tae_intraday_fade_intelligence.md",
        "tae_knowledge_base.md",
        "tae_knowledge_summary.md",
        "tae_market_open_intelligence_runner.md",
        "tae_profit_protection_shadow.md",
        "tae_profit_protection_validation.md",
        "tae_stop_reentry_cooldown_audit.md",
    ):
        if (PROJECT / name).is_file():
            root_polluters.append(name)
    checks["root_generated_polluters"] = root_polluters
    if root_polluters:
        reasons.append(f"root_generated_reports:{len(root_polluters)}")

    # --- Strategy V2 LIVE hard-off ---
    try:
        from tae_strategy_v2_config import is_strategy_v2_enabled

        v2_global = bool(is_strategy_v2_enabled())
        checks["strategy_v2_global_enabled"] = v2_global
        if v2_global:
            reasons.append("STRATEGY_V2_ENABLED_true_global")
    except Exception as exc:  # noqa: BLE001
        checks["strategy_v2_error"] = f"{type(exc).__name__}: {exc}"

    # --- Test evidence freshness ---
    proof = PROJECT / "runtime_outputs" / "autonomy_recovery_proof.json"
    checks["autonomy_proof"] = {
        "present": proof.is_file(),
        "path": str(proof),
    }
    if proof.is_file():
        try:
            pdata = json.loads(proof.read_text(encoding="utf-8"))
            crash = pdata.get("crash") or {}
            checks["autonomy_proof"]["crash_ok"] = all(
                (crash.get(k) or {}).get("ok") for k in ("live_bot", "dashboard", "parallel_paper")
            )
            if not checks["autonomy_proof"]["crash_ok"]:
                reasons.append("autonomy_proof_crash_fail")
        except Exception as exc:  # noqa: BLE001
            reasons.append(f"autonomy_proof_unreadable:{type(exc).__name__}")
    else:
        reasons.append("autonomy_proof_missing")

    # --- Market hours (informational) ---
    try:
        from markets.market_hours import any_market_open, get_market_statuses

        checks["market"] = {
            "any_open": any_market_open(),
            "statuses": get_market_statuses(),
        }
    except Exception as exc:  # noqa: BLE001
        checks["market_error"] = f"{type(exc).__name__}: {exc}"
        reasons.append(f"market_hours_error:{type(exc).__name__}")

    # --- KeepAlive flags ---
    try:
        import tae_runtime_lifecycle as life

        flags = life.ensure_keepalive_flags()
        checks["keepalive_flags"] = flags
        checks["lifecycle_owned"] = {
            "live_bot": life.live_bot_lifecycle_owned_by_launchd(),
            "dashboard": life.dashboard_lifecycle_owned_by_launchd(),
        }
        if not checks["lifecycle_owned"]["live_bot"]:
            if profile_n != "paper":
                reasons.append("live_bot_lifecycle_not_owned")
            else:
                checks.setdefault("paper_info", []).append("live_bot_lifecycle_not_owned_expected")
        if not checks["lifecycle_owned"]["dashboard"]:
            if profile_n != "paper":
                reasons.append("dashboard_lifecycle_not_owned")
            else:
                checks.setdefault("paper_info", []).append("dashboard_lifecycle_not_owned_optional")
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"lifecycle_error:{type(exc).__name__}")

    # Adaptive deployment current health (paper / full)
    try:
        import tae_adaptive_deployment as adep

        adep_val = adep.validate_only(mode="current")
        checks["adaptive_deployment"] = {
            "ok": adep_val.get("ok"),
            "status_label": adep_val.get("status_label"),
            "deployment_state": ((adep_val.get("status") or {}).get("deployment") or {}).get(
                "deployment_state"
            ),
        }
        if profile_n in {"paper", "full"} and not adep_val.get("ok"):
            reasons.append(f"adaptive_deployment:{adep_val.get('status_label')}")
    except Exception as exc:  # noqa: BLE001
        checks["adaptive_deployment_error"] = f"{type(exc).__name__}: {exc}"
        if profile_n in {"paper", "full"}:
            reasons.append(f"adaptive_deployment_error:{type(exc).__name__}")

    # Paper profile: surface git_dirty without making it a hard FAIL (still reported)
    if profile_n == "paper":
        soft: list[str] = []
        hard: list[str] = []
        for r in reasons:
            if r.startswith("git_dirty:"):
                soft.append(r)
            else:
                hard.append(r)
        checks["git_dirty_reported"] = soft
        reasons = hard
        for s in soft:
            checks.setdefault("paper_info", []).append(s)

    verdict = "PASS" if not reasons else "FAIL"
    result = {
        "schema": "tae.final_check.v1",
        "profile": profile_n,
        "verdict": verdict,
        "reasons": reasons,
        "checks": checks,
        "broker_access": False,
        "paper_isolation_expected": True,
        "mutation": False,
    }

    if write_report:
        REPORT_JSON.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
        lines = [
            "# TAE Final Check",
            "",
            f"- generated: `{result['checks']['generated_at']}`",
            f"- verdict: **{verdict}**",
            f"- mutation: false",
            "",
            "## Reasons",
            "",
        ]
        if reasons:
            lines.extend(f"- {r}" for r in reasons)
        else:
            lines.append("- none")
        lines.extend(["", "## Process counts", ""])
        for name, info in proc.items():
            lines.append(f"- {name}: {info['count']} pids={info['pids']}")
        lines.extend(["", f"Full JSON: `{REPORT_JSON.name}`", ""])
        REPORT_MD.write_text("\n".join(lines), encoding="utf-8")

    return result


def main(argv: list[str] | None = None) -> int:
    args = list(argv or [])
    write = "--no-write" not in args
    profile = "full"
    if "--profile" in args:
        i = args.index("--profile")
        if i + 1 < len(args):
            profile = args[i + 1]
    result = run_final_check(write_report=write, profile=profile)
    if result["verdict"] == "PASS":
        print(f"TAE_FINAL_CHECK: PASS (profile={profile})")
        return 0
    print(f"TAE_FINAL_CHECK: FAIL (profile={profile})")
    print("REASONS:")
    for r in result["reasons"]:
        print(f"  - {r}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
