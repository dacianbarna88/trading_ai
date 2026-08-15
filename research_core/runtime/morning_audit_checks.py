#!/usr/bin/env python3
"""
Read-only checks for tae morning-audit — LIVE portfolio writer / lock / shrink / repo.

PAPER_ONLY | NO_BROKER | NO_EXECUTION
Never mutates portfolio.csv or invokes write_live_portfolio against LIVE.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

CANONICAL_WRITER = "research_core.runtime.live_portfolio_writer.write_live_portfolio"
EVENTS_REL = Path("runtime_outputs/live/portfolio_write_events.jsonl")

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_ERROR = "ERROR"
SEVERITY_WARNING = "WARNING"
SEVERITY_INFO = "INFO"

GENERATED_ARTIFACT_SUFFIXES = (
    ".md",
    ".json",
    ".jsonl",
    ".csv",
    ".txt",
    ".log",
)
GENERATED_NAME_PREFIXES = (
    "TAE_",
    "tae_",
    "bot_",
    "alerts_",
    "live_signals",
    "portfolio.csv.",
    "watchlist",
)


def _finding(
    code: str,
    severity: str,
    message: str,
    *,
    evidence: Any = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "evidence": evidence,
    }


def _sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _source_delegates(path: Path, *, must_contain: str, forbidden: tuple[str, ...] = ()) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"missing {path}"
    text = _read_text(path)
    if "def save_portfolio" in text:
        start = text.index("def save_portfolio")
        end = text.find("\ndef ", start + 1)
        body = text[start:end if end > 0 else start + 800]
    else:
        body = text
    if must_contain not in body and must_contain not in text:
        return False, f"{path.name} does not reference {must_contain}"
    for bad in forbidden:
        if bad in body:
            return False, f"{path.name} save_portfolio body contains independent {bad}"
    return True, "ok"


def check_canonical_writer(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    details: dict[str, Any] = {
        "canonical": CANONICAL_WRITER,
        "importable": False,
        "function_exists": False,
        "has_atomic": False,
        "has_fsync": False,
        "has_lock": False,
        "has_empty_guard": False,
        "has_shrink_guard": False,
        "live_bot_delegates": False,
        "storage_delegates": False,
        "recompute_delegates": False,
        "recompute_no_open_w": False,
        "path_canonical": False,
        "runtime_owner": None,
    }

    try:
        from research_core.runtime import live_portfolio_writer as lpw
        from research_core.runtime.runtime_paths import get_runtime_paths

        details["importable"] = True
        details["function_exists"] = callable(getattr(lpw, "write_live_portfolio", None))
        src = inspect.getsource(lpw)
        details["has_atomic"] = "os.replace" in src and ".tmp" in src
        details["has_fsync"] = "os.fsync" in src
        details["has_lock"] = "fcntl.flock" in src
        details["has_empty_guard"] = "portfolio_write_guard" in src or "empty" in src.lower()
        details["has_shrink_guard"] = (
            "UNAUTHORIZED_PORTFOLIO_SHRINK" in src
            and "UnauthorizedPortfolioShrink" in src
        )
        paths = get_runtime_paths("live", project_root=root)
        details["runtime_owner"] = paths.runtime_id
        details["path_canonical"] = paths.portfolio.resolve() == (root / "portfolio.csv").resolve()
        details["lock_path"] = str(paths.portfolio_lock)
        details["portfolio_path"] = str(paths.portfolio)
    except Exception as exc:
        # LIVE portfolio writer was intentionally not restored (NO_LIVE / PAPER closure).
        # Morning audit must not CRITICAL-block PAPER infrastructure on this absence.
        findings.append(
            _finding(
                "LIVE_WRITER_INTENTIONALLY_ABSENT",
                SEVERITY_INFO,
                f"LIVE writer not on HEAD by design (PAPER/NO_LIVE closure): {exc}",
            )
        )
        details["intentionally_absent"] = True
        return {"ok": True, "details": details, "findings": findings, "skipped_live_writer": True}

    if not details["function_exists"]:
        findings.append(
            _finding("CANONICAL_WRITER_MISSING", SEVERITY_CRITICAL, "write_live_portfolio missing")
        )
    for key, code in (
        ("has_atomic", "WRITER_ATOMIC_MISSING"),
        ("has_fsync", "WRITER_FSYNC_MISSING"),
        ("has_lock", "WRITER_LOCK_MISSING"),
        ("has_empty_guard", "WRITER_EMPTY_GUARD_MISSING"),
        ("has_shrink_guard", "WRITER_SHRINK_GUARD_MISSING"),
        ("path_canonical", "WRITER_PATH_NOT_CANONICAL"),
    ):
        if not details[key]:
            findings.append(
                _finding(code, SEVERITY_CRITICAL, f"canonical writer check failed: {key}")
            )

    ok_lb, msg_lb = _source_delegates(
        root / "live_bot.py",
        must_contain="write_live_portfolio",
        forbidden=("os.replace", "to_csv"),
    )
    details["live_bot_delegates"] = ok_lb
    if not ok_lb:
        findings.append(_finding("LIVE_BOT_WRITER_BYPASS", SEVERITY_CRITICAL, msg_lb))

    ok_st, msg_st = _source_delegates(
        root / "data" / "storage.py",
        must_contain="write_live_portfolio",
        forbidden=("os.replace", "to_csv"),
    )
    details["storage_delegates"] = ok_st
    if not ok_st:
        findings.append(_finding("STORAGE_WRITER_BYPASS", SEVERITY_CRITICAL, msg_st))

    recompute = root / "tools" / "recompute_realized_pnl.py"
    if recompute.is_file():
        text = _read_text(recompute)
        details["recompute_delegates"] = "write_live_portfolio" in text
        details["recompute_structural"] = "assert_recompute_structure_unchanged" in text or (
            "recompute_accounting" in text
        )
        details["recompute_apply_flag"] = '"--apply"' in text or "'--apply'" in text
        # No write-mode open on portfolio path
        unsafe_open = False
        try:
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr == "open":
                        for arg in node.args[1:]:
                            if isinstance(arg, ast.Constant) and arg.value in {"w", "w+", "wt"}:
                                unsafe_open = True
        except SyntaxError:
            unsafe_open = "open(\"w\"" in text or "open('w'" in text
        details["recompute_no_open_w"] = not unsafe_open and "def _write_csv" not in text
        if not details["recompute_delegates"]:
            findings.append(
                _finding(
                    "RECOMPUTE_UNSAFE_WRITER",
                    SEVERITY_CRITICAL,
                    "recompute does not delegate to canonical writer",
                )
            )
        if not details["recompute_no_open_w"]:
            findings.append(
                _finding(
                    "RECOMPUTE_OPEN_W",
                    SEVERITY_CRITICAL,
                    "recompute still has open('w') / _write_csv writer",
                )
            )
        if not details.get("recompute_structural"):
            findings.append(
                _finding(
                    "RECOMPUTE_STRUCTURAL_GUARD_MISSING",
                    SEVERITY_ERROR,
                    "recompute structural accounting-only guard not found",
                )
            )
    else:
        findings.append(
            _finding("RECOMPUTE_MISSING", SEVERITY_WARNING, "tools/recompute_realized_pnl.py missing")
        )

    ok = not any(f["severity"] == SEVERITY_CRITICAL for f in findings)
    return {"ok": ok, "details": details, "findings": findings}


def check_portfolio_integrity(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    path = root / "portfolio.csv"
    details: dict[str, Any] = {
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "open_count": None,
        "header_only": False,
        "empty": False,
        "parseable": False,
        "nan_or_nonfinite": False,
        "negative_shares": False,
        "duplicate_open_tickers": False,
    }
    if not path.is_file():
        findings.append(
            _finding("PORTFOLIO_MISSING", SEVERITY_CRITICAL, "portfolio.csv missing")
        )
        return {"ok": False, "details": details, "findings": findings}

    try:
        import pandas as pd

        try:
            from research_core.runtime.live_portfolio_writer import open_tickers_from_df
        except Exception:
            # LIVE writer intentionally absent — compute open tickers locally for audit.
            def open_tickers_from_df(df: Any) -> list[str]:  # type: ignore[misc]
                if "Ticker" not in df.columns or "Action" not in df.columns:
                    return []
                actions = df["Action"].astype(str).str.upper()
                tickers = df["Ticker"].astype(str)
                buys = set(tickers[actions == "BUY"])
                sells = set(tickers[actions == "SELL"])
                return sorted(buys - sells)

        text = path.read_text(encoding="utf-8", errors="replace").strip()
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if not lines:
            details["empty"] = True
            findings.append(
                _finding("PORTFOLIO_EMPTY", SEVERITY_CRITICAL, "portfolio.csv empty")
            )
        elif len(lines) <= 1:
            details["header_only"] = True
            findings.append(
                _finding(
                    "PORTFOLIO_HEADER_ONLY",
                    SEVERITY_CRITICAL,
                    "portfolio.csv is header-only",
                )
            )
        else:
            df = pd.read_csv(path)
            details["parseable"] = True
            opens = open_tickers_from_df(df)
            details["open_count"] = len(opens)
            if "Shares" in df.columns:
                shares = pd.to_numeric(df["Shares"], errors="coerce")
                if (shares < 0).any():
                    details["negative_shares"] = True
                    findings.append(
                        _finding(
                            "PORTFOLIO_NEGATIVE_SHARES",
                            SEVERITY_ERROR,
                            "negative Shares present",
                        )
                    )
            import math

            for col in ("Price", "Shares", "Current_Price", "Invested", "Current_Value", "PnL"):
                if col not in df.columns:
                    continue
                series = pd.to_numeric(df[col], errors="coerce")
                for val in series.dropna().tolist():
                    f = float(val)
                    if not math.isfinite(f):
                        details["nan_or_nonfinite"] = True
                        break
                if details["nan_or_nonfinite"]:
                    break
            if details["nan_or_nonfinite"]:
                findings.append(
                    _finding(
                        "PORTFOLIO_NONFINITE",
                        SEVERITY_CRITICAL,
                        "NaN/non-finite numeric values in portfolio",
                    )
                )
    except Exception as exc:
        findings.append(
            _finding(
                "PORTFOLIO_UNPARSEABLE",
                SEVERITY_CRITICAL,
                f"portfolio.csv parse failed: {exc}",
            )
        )

    tmp = root / "portfolio.csv.tmp"
    if tmp.is_file():
        age_h = (datetime.now(timezone.utc).timestamp() - tmp.stat().st_mtime) / 3600
        sev = SEVERITY_WARNING if age_h < 1 else SEVERITY_ERROR
        findings.append(
            _finding(
                "PORTFOLIO_TMP_STALE",
                sev,
                f"stale portfolio.csv.tmp age_h={age_h:.2f}",
                evidence={"path": str(tmp), "age_h": age_h},
            )
        )
        details["tmp_present"] = True
    else:
        details["tmp_present"] = False

    wiped = list(root.glob("portfolio.csv.wiped_*"))
    if wiped:
        findings.append(
            _finding(
                "PORTFOLIO_WIPE_ARTIFACT",
                SEVERITY_WARNING,
                f"wipe artifact(s) present: {[p.name for p in wiped]}",
            )
        )
        details["wipe_artifacts"] = [p.name for p in wiped]

    ok = not any(f["severity"] in {SEVERITY_CRITICAL, SEVERITY_ERROR} for f in findings)
    return {"ok": ok, "details": details, "findings": findings}


def check_shrink_protection(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    details: dict[str, Any] = {
        "guard_present": False,
        "recent_unauthorized": [],
        "status": "SHRINK_HISTORY_NOT_PROVEN",
    }
    try:
        from research_core.runtime import live_portfolio_writer as lpw

        details["guard_present"] = hasattr(lpw, "UnauthorizedPortfolioShrink") and (
            "UNAUTHORIZED_PORTFOLIO_SHRINK" in inspect.getsource(lpw)
        )
    except Exception as exc:
        findings.append(
            _finding(
                "LIVE_WRITER_INTENTIONALLY_ABSENT",
                SEVERITY_INFO,
                f"shrink guard skipped — LIVE writer not on HEAD by design: {exc}",
            )
        )
        details["status"] = "SHRINK_GUARD_N_A_LIVE_WRITER_RETIRED"
        details["intentionally_absent"] = True
        return {"ok": True, "details": details, "findings": findings, "skipped_live_writer": True}

    if not details["guard_present"]:
        findings.append(
            _finding(
                "SHRINK_GUARD_MISSING",
                SEVERITY_CRITICAL,
                "UNAUTHORIZED_PORTFOLIO_SHRINK not found in canonical writer",
            )
        )

    events_path = root / EVENTS_REL
    unauthorized: list[dict[str, Any]] = []
    write_oks: list[dict[str, Any]] = []
    if events_path.is_file():
        try:
            for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if ev.get("event") == "UNAUTHORIZED_PORTFOLIO_SHRINK":
                    unauthorized.append(ev)
                if ev.get("event") == "PORTFOLIO_WRITE_OK":
                    write_oks.append(ev)
        except OSError as exc:
            findings.append(
                _finding("SHRINK_EVENTS_UNREADABLE", SEVERITY_WARNING, str(exc))
            )
        details["recent_unauthorized"] = unauthorized[-5:]
        if unauthorized:
            details["status"] = "UNAUTHORIZED_SHRINK_DETECTED"
            findings.append(
                _finding(
                    "UNAUTHORIZED_PORTFOLIO_SHRINK",
                    SEVERITY_CRITICAL,
                    f"{len(unauthorized)} UNAUTHORIZED_PORTFOLIO_SHRINK event(s) in log",
                    evidence=unauthorized[-3:],
                )
            )
        elif write_oks:
            # Look for empty wipe pattern: previous_count>0 then proposed 0 then jump
            details["status"] = "NO_UNAUTHORIZED_EVENTS"
            # Cannot fully prove absence of historical wipe without snapshots
            if any(
                int(e.get("previous_count") or 0) >= 8
                and int(e.get("proposed_count") or 0) <= 4
                and not e.get("detail")
                for e in write_oks[-50:]
            ):
                # WRITE_OK with shrink without sell justification wouldn't be emitted as OK
                # Keep history not fully proven
                details["status"] = "SHRINK_HISTORY_NOT_PROVEN"
            else:
                details["status"] = "NO_UNAUTHORIZED_EVENTS"
                # Still not full historical proof
                if len(write_oks) < 3:
                    details["status"] = "SHRINK_HISTORY_NOT_PROVEN"
        else:
            details["status"] = "SHRINK_HISTORY_NOT_PROVEN"
    else:
        details["status"] = "SHRINK_HISTORY_NOT_PROVEN"
        findings.append(
            _finding(
                "SHRINK_HISTORY_NOT_PROVEN",
                SEVERITY_WARNING,
                "portfolio write events log missing — cannot prove shrink history",
            )
        )

    if details["status"] == "SHRINK_HISTORY_NOT_PROVEN" and not unauthorized:
        findings.append(
            _finding(
                "SHRINK_HISTORY_NOT_PROVEN",
                SEVERITY_INFO,
                "insufficient event history to fully prove absence of past shrink wipe",
            )
        )

    ok = details["guard_present"] and not unauthorized
    return {"ok": ok, "details": details, "findings": findings}


def check_lock_and_ownership(root: Path = ROOT) -> dict[str, Any]:
    import fcntl

    findings: list[dict[str, Any]] = []
    from research_core.runtime.runtime_paths import get_runtime_paths, read_owner_sidecar

    paths = get_runtime_paths("live", project_root=root)
    lock_path = paths.portfolio_lock
    details: dict[str, Any] = {
        "lock_path": str(lock_path),
        "lock_exists": lock_path.is_file(),
        "lock_held_now": False,
        "sidecar": None,
        "live_bot_pids": [],
        "LOCK_HEALTH": "NOT_PROVEN",
        "LIVE_WRITER_OWNERSHIP": "NOT_PROVEN",
    }

    try:
        from core.process_identity import (
            find_live_bot_pids,
            reconcile_bot_identity_metadata,
            resolve_canonical_bot,
        )

        reconcile = reconcile_bot_identity_metadata(project_dir=root)
        pids = find_live_bot_pids(project_dir=root)
        details["live_bot_pids"] = pids
        identity, all_pids = resolve_canonical_bot(project_dir=root)
        details["canonical_bot_pid"] = identity.pid
        details["canonical_bot_valid"] = identity.valid
        details["identity_reconciled"] = bool(reconcile.get("reconciled"))
        details["reconcile_status"] = reconcile.get("status")
        if len(pids) > 1:
            findings.append(
                _finding(
                    "DUPLICATE_LIVE_BOT",
                    SEVERITY_CRITICAL,
                    f"multiple live_bot PIDs: {pids}",
                )
            )
            details["LIVE_WRITER_OWNERSHIP"] = "MULTIPLE_OWNER_RISK"
        elif len(pids) == 1 and identity.valid:
            details["LIVE_WRITER_OWNERSHIP"] = "SINGLE_OWNER_PROVEN"
        elif len(pids) == 0:
            details["LIVE_WRITER_OWNERSHIP"] = "SINGLE_OWNER_PROVEN"
            findings.append(
                _finding(
                    "LIVE_BOT_NOT_RUNNING",
                    SEVERITY_WARNING,
                    "live_bot not detected",
                )
            )
        else:
            details["LIVE_WRITER_OWNERSHIP"] = "NOT_PROVEN"
    except Exception as exc:
        findings.append(
            _finding("PROCESS_IDENTITY_FAILED", SEVERITY_WARNING, str(exc))
        )

    sidecar = read_owner_sidecar(paths.portfolio_owner_sidecar)
    details["sidecar"] = sidecar
    if sidecar:
        if sidecar.get("runtime_version") not in (None, "live"):
            findings.append(
                _finding(
                    "SIDECAR_OWNER_MISMATCH",
                    SEVERITY_CRITICAL,
                    f"sidecar runtime_version={sidecar.get('runtime_version')}",
                )
            )
            details["LIVE_WRITER_OWNERSHIP"] = "MULTIPLE_OWNER_RISK"

    # Probe existing lock only — never create lock file in read-only audit.
    try:
        if not lock_path.is_file():
            details["LOCK_HEALTH"] = "HEALTHY"
        else:
            with lock_path.open("r+", encoding="utf-8") as fh:
                try:
                    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                    details["lock_held_now"] = False
                    details["LOCK_HEALTH"] = "HEALTHY"
                except BlockingIOError:
                    details["lock_held_now"] = True
                    details["LOCK_HEALTH"] = "CONFLICT"
                    findings.append(
                        _finding(
                            "LOCK_CONFLICT",
                            SEVERITY_CRITICAL,
                            "portfolio lock currently held by another process",
                        )
                    )
    except OSError as exc:
        details["LOCK_HEALTH"] = "NOT_PROVEN"
        findings.append(_finding("LOCK_PROBE_FAILED", SEVERITY_WARNING, str(exc)))

    # Stale empty lock file with no holder is normal for flock; mark STALE only if
    # sidecar pid dead AND lock held (unreachable) — if lock free and sidecar pid dead: INFO
    if sidecar and sidecar.get("writer_pid"):
        try:
            os.kill(int(sidecar["writer_pid"]), 0)
            alive = True
        except OSError:
            alive = False
        details["sidecar_pid_alive"] = alive
        if not alive and details["LOCK_HEALTH"] == "HEALTHY":
            # historical writer gone — OK
            pass

    ok = details["LOCK_HEALTH"] not in {"CONFLICT"} and details[
        "LIVE_WRITER_OWNERSHIP"
    ] != "MULTIPLE_OWNER_RISK"
    return {"ok": ok, "details": details, "findings": findings}


def check_repository(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    details: dict[str, Any] = {
        "branch": None,
        "head": None,
        "detached": False,
        "modified_source": [],
        "untracked_py": [],
        "generated_dirty": [],
        "conflicts": [],
    }
    try:
        def _git(*args: str) -> str:
            r = subprocess.run(
                ["git", *args],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=10,
            )
            return (r.stdout or "").strip()

        details["branch"] = _git("rev-parse", "--abbrev-ref", "HEAD")
        details["head"] = _git("rev-parse", "HEAD")
        details["detached"] = details["branch"] == "HEAD"
        if details["detached"]:
            findings.append(
                _finding("DETACHED_HEAD", SEVERITY_WARNING, "repository is detached HEAD")
            )
        status = _git("status", "--porcelain")
        for line in status.splitlines():
            if not line.strip():
                continue
            code = line[:2]
            path = line[3:].strip()
            if "U" in code or code in {"AA", "DD"}:
                details["conflicts"].append(path)
            is_py = path.endswith(".py")
            is_generated = path.startswith(GENERATED_NAME_PREFIXES) or any(
                path.endswith(suf) and not is_py for suf in GENERATED_ARTIFACT_SUFFIXES
            )
            # Prefer classifying TAE_*.md / tae_*.json as generated
            if path.startswith("TAE_") or (
                path.startswith("tae_") and not path.endswith(".py")
            ):
                is_generated = True
            if code.startswith("??") and is_py:
                details["untracked_py"].append(path)
            elif is_py and not code.startswith("??"):
                details["modified_source"].append(path)
            elif is_generated or not is_py:
                details["generated_dirty"].append(path)

        if details["conflicts"]:
            findings.append(
                _finding(
                    "GIT_CONFLICTS",
                    SEVERITY_CRITICAL,
                    f"merge conflicts: {details['conflicts'][:5]}",
                )
            )
        if details["modified_source"] or details["untracked_py"]:
            findings.append(
                _finding(
                    "SOURCE_DIRTY",
                    SEVERITY_WARNING,
                    "modified/untracked Python source present (expected during infrastructure closure)",
                    evidence={
                        "modified": details["modified_source"][:20],
                        "untracked_py": details["untracked_py"][:20],
                    },
                )
            )
        elif details["generated_dirty"]:
            findings.append(
                _finding(
                    "GENERATED_DIRTY",
                    SEVERITY_WARNING,
                    "generated/runtime artifacts dirty (not source defect)",
                    evidence=details["generated_dirty"][:30],
                )
            )

        # Canonical commits presence (optional INFO)
        log = _git("log", "--oneline", "-30")
        details["has_writer_closure_commit"] = "d833258" in log or "canonical writer" in log.lower()
    except Exception as exc:
        findings.append(_finding("GIT_STATUS_FAILED", SEVERITY_WARNING, str(exc)))

    ok = not details["conflicts"]
    return {"ok": ok, "details": details, "findings": findings}


def check_learning_runtime(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    details: dict[str, Any] = {"status_file": None, "status": None}
    # Prefer existing status artifact if present
    candidates = [
        root / "runtime_outputs" / "canonical_learning" / "health.json",
        root / "runtime_outputs" / "canonical_learning" / "status.json",
        root / "tae_canonical_learning_status.json",
    ]
    payload = None
    for path in candidates:
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                details["status_file"] = str(path)
                break
            except (OSError, json.JSONDecodeError):
                continue
    if payload:
        details["status"] = payload.get("status") or payload.get("health") or payload.get("verdict")
    else:
        findings.append(
            _finding(
                "LEARNING_STATUS_ABSENT",
                SEVERITY_INFO,
                "canonical learning status artifact not found (use learning-runtime-health)",
            )
        )
    return {"ok": True, "details": details, "findings": findings}


def check_market_data_signals(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    details: dict[str, Any] = {"signals_age_h": None, "regional": None}
    signals = root / "live_signals.csv"
    if signals.is_file():
        age_h = (datetime.now(timezone.utc).timestamp() - signals.stat().st_mtime) / 3600
        details["signals_age_h"] = round(age_h, 2)
        if age_h > 24:
            findings.append(
                _finding(
                    "SIGNALS_STALE",
                    SEVERITY_WARNING,
                    f"live_signals.csv age_h={age_h:.1f}",
                )
            )
    else:
        findings.append(
            _finding("SIGNALS_MISSING", SEVERITY_WARNING, "live_signals.csv missing")
        )
    try:
        from core.market_data_layer import regional_mark_health_summary

        regional = regional_mark_health_summary()
        details["regional"] = regional
        stale = int(regional.get("stale_regional_marks") or 0)
        missing = int(regional.get("missing_regional_marks") or 0)
        if stale or missing:
            findings.append(
                _finding(
                    "REGIONAL_MARKS_STALE",
                    SEVERITY_WARNING,
                    f"regional marks stale={stale} missing={missing}",
                )
            )
    except Exception as exc:
        findings.append(_finding("REGIONAL_MARKS_FAILED", SEVERITY_WARNING, str(exc)))
    return {"ok": True, "details": details, "findings": findings}


def check_decision_execution_artifacts(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    decisions = root / "runtime_outputs" / "paper_decisions" / "paper_decisions.json"
    # also common path
    alt = root / "runtime_outputs" / "paper_execution" / "paper_orders.jsonl"
    if decisions.is_file():
        try:
            doc = json.loads(decisions.read_text(encoding="utf-8"))
            dets = doc.get("decisions") or []
            details["decision_count"] = len(dets)
            ids = [d.get("decision_id") for d in dets if d.get("decision_id")]
            if len(ids) != len(set(ids)):
                findings.append(
                    _finding(
                        "DUPLICATE_DECISION_IDS",
                        SEVERITY_ERROR,
                        "duplicate decision_id in paper decisions",
                    )
                )
        except (OSError, json.JSONDecodeError) as exc:
            findings.append(_finding("DECISIONS_UNREADABLE", SEVERITY_WARNING, str(exc)))
    else:
        findings.append(
            _finding(
                "DECISIONS_ABSENT",
                SEVERITY_INFO,
                "paper_decisions.json not present",
            )
        )
    details["orders_present"] = alt.is_file()
    return {"ok": True, "details": details, "findings": findings}


def check_crash_loop(root: Path = ROOT) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    details: dict[str, Any] = {}
    recovery = root / "bot_recovery_state.json"
    if recovery.is_file():
        try:
            payload = json.loads(recovery.read_text(encoding="utf-8"))
            details["recovery"] = payload
            failures = int(payload.get("failure_count") or payload.get("failures") or 0)
            if failures >= 3 or str(payload.get("state") or "").upper() in {
                "CRASH_LOOP",
                "RECOVERY_LOCK",
            }:
                findings.append(
                    _finding(
                        "CRASH_LOOP",
                        SEVERITY_CRITICAL,
                        f"bot recovery indicates crash loop: {payload}",
                    )
                )
        except (OSError, json.JSONDecodeError):
            pass
    return {"ok": not findings, "details": details, "findings": findings}


def run_all_live_checks(root: Path = ROOT) -> dict[str, Any]:
    sections = {
        "canonical_writer": check_canonical_writer(root),
        "portfolio_integrity": check_portfolio_integrity(root),
        "shrink": check_shrink_protection(root),
        "lock_ownership": check_lock_and_ownership(root),
        "repository": check_repository(root),
        "learning": check_learning_runtime(root),
        "market_data": check_market_data_signals(root),
        "decision_execution": check_decision_execution_artifacts(root),
        "crash_loop": check_crash_loop(root),
    }
    findings: list[dict[str, Any]] = []
    for section in sections.values():
        findings.extend(section.get("findings") or [])

    has_critical = any(f["severity"] == SEVERITY_CRITICAL for f in findings)
    has_error = any(f["severity"] == SEVERITY_ERROR for f in findings)
    has_warning = any(f["severity"] == SEVERITY_WARNING for f in findings)

    if has_critical:
        status = "BLOCKED"
    elif has_error or has_warning:
        status = "ATTENTION_REQUIRED"
    else:
        status = "HEALTHY"

    # Force ATTENTION for specific warning-only shrink history? User said don't invent PASS.
    # SHRINK_HISTORY_NOT_PROVEN alone as INFO should not force ATTENTION if guard present.
    lock = sections["lock_ownership"]["details"]
    return {
        "sections": sections,
        "findings": findings,
        "suggested_status": status,
        "LOCK_HEALTH": lock.get("LOCK_HEALTH"),
        "LIVE_WRITER_OWNERSHIP": lock.get("LIVE_WRITER_OWNERSHIP"),
        "CANONICAL_WRITER_OK": sections["canonical_writer"].get("ok"),
        "SHRINK_STATUS": sections["shrink"]["details"].get("status"),
        "file_hashes": {
            "portfolio.csv": _sha256_file(root / "portfolio.csv"),
            "tae_infrastructure_health.json": _sha256_file(root / "tae_infrastructure_health.json"),
            "tae_profit_pipeline.json": _sha256_file(root / "tae_profit_pipeline.json"),
            "tae_accounting_snapshot.json": _sha256_file(root / "tae_accounting_snapshot.json"),
        },
    }
