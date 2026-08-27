#!/usr/bin/env python3
"""
Parallel PAPER N-arm configuration SSOT.

PAPER_ONLY | NO_BROKER | NO_LIVE_CAPITAL
Sprint 3: declarative arms[] topology with legacy V1_*/V2_* aliases.
V2 activation scope: PARALLEL_PAPER only. LIVE cannot be enabled via env.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "tae_parallel_paper_config.json"
CONFIG_SCHEMA = "tae.parallel_paper.config.v2"
CONFIG_SCHEMA_LEGACY = "tae.parallel_paper.config.v1"
EXPERIMENTAL_ARMS_PATH = (
    PROJECT_ROOT
    / "runtime_outputs"
    / "learning_to_profit"
    / "self_improve"
    / "experimental_arms.json"
)

_raw_root = os.environ.get("TAE_PARALLEL_PAPER_ROOT") or str(
    PROJECT_ROOT / "runtime_outputs" / "parallel_paper"
)
ROOT = Path(_raw_root)
if not ROOT.is_absolute():
    ROOT = (PROJECT_ROOT / ROOT).resolve()
else:
    ROOT = ROOT.resolve()
V1_DIR = ROOT / "v1"
V2_DIR = ROOT / "v2"
V3_DIR = ROOT / "v3"
REPORTS_DIR = ROOT / "reports"

# Activation scopes — LIVE is never selectable via env
ALLOWED_SCOPES = frozenset(
    {"DISABLED", "TEST", "REPLAY", "PARALLEL_PAPER", "CANONICAL_PAPER", "LIVE"}
)

# Policy handlers currently implemented in tae_parallel_paper_runtime.
# "v3" added Phase 3 (_run_v3_arm — tae_strategy_v3_learning_policy.decide_v3).
KNOWN_POLICY_BINDINGS = frozenset({"v1", "v2", "v3", "experimental"})

CLOCK_GROUP_DEFAULT = "parallel-paper-main"
MARKET_MARK_GROUP_DEFAULT = "parallel-paper-main"

_DEFAULTS: dict[str, Any] = {
    "schema": CONFIG_SCHEMA,
    "PARALLEL_PAPER_ENABLED": True,
    "V1_PARALLEL_ENABLED": True,
    "V2_PARALLEL_ENABLED": True,
    "V1_STARTING_CAPITAL": 30000.0,
    "V2_STARTING_CAPITAL": 30000.0,
    "V1_MIN_CASH_RESERVE": 500.0,
    "V2_MIN_CASH_RESERVE": 500.0,
    "DAILY_REPORT_ENABLED": True,
    "DAILY_REPORT_TIME": "22:30",
    "TIMEZONE": "Europe/Bucharest",
    "MARKET_SESSION_POLICY": "session_aware_mark_and_report",
    "REPORT_OUTPUT_DIRECTORY": str(REPORTS_DIR),
    "AUTO_START_ENABLED": False,
    "FAIL_ISOLATION_ENABLED": True,
    "RUNTIME_INTERVAL_SEC": 300,
    "HEARTBEAT_MAX_AGE_SEC": 660,
    "V1_MODE": "ISOLATED_PARALLEL_PAPER",
    "V2_MODE": "ISOLATED_PARALLEL_PAPER",
    "CANONICAL_PAPER_PORTFOLIO": "runtime_outputs/paper_execution/paper_portfolio.json",
    "CANONICAL_PAPER_TRADES": "runtime_outputs/paper_execution/paper_trades.jsonl",
    "V2_ACTIVATION_SCOPE": "PARALLEL_PAPER",
    "V2_LIVE_ENABLED": False,
    "V2_CANONICAL_PAPER_ENABLED": False,
    "V2_PARALLEL_PAPER_ENABLED": True,
    "STRATEGY_V2_GLOBAL_ENABLED": False,
    "PAPER_TX_COST_ENABLED": True,
    "PAPER_SLIPPAGE_BPS": 5.0,
    "PAPER_SPREAD_BPS": 0.0,
    "PAPER_COMMISSION_BPS": 0.0,
    "PAPER_COMMISSION_USD": 0.0,
    "WATCHLIST": [],
    "note": (
        "Isolated executable PARALLEL_PAPER arms via declarative arms[]. "
        "Equal 30k starting capital for enabled policy arms. "
        "Does not touch canonical PAPER, portfolio.csv, or LIVE. "
        "V1_MODE=CANONICAL_PAPER_MIRROR is optional/offline-only (not the experiment default). "
        "PAPER_TX_* unified paper transaction costs (tae_paper_transaction_costs SSOT). "
        "Disabled stub arms (e.g. v3) declare topology only — no strategy, no book."
    ),
}


def _bool(v: Any, default: bool = False) -> bool:
    if v is True or v == 1:
        return True
    if v is False or v == 0:
        return False
    if isinstance(v, str) and v.strip().lower() in {"true", "1", "yes", "on"}:
        return True
    if isinstance(v, str) and v.strip().lower() in {"false", "0", "no", "off"}:
        return False
    return default


def _s(v: Any, default: str = "") -> str:
    return str(v if v is not None else default).strip()


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _normalize_arm_row(raw: dict[str, Any], *, fallback_id: str) -> dict[str, Any]:
    arm_id = _s(raw.get("arm_id") or fallback_id).lower()
    binding_raw = raw.get("policy_binding")
    if binding_raw is None or _s(binding_raw) == "":
        policy_binding = None
    else:
        policy_binding = _s(binding_raw).lower()
    enabled = _bool(raw.get("enabled"), False)
    mode = _s(raw.get("mode") or "ISOLATED_PARALLEL_PAPER").upper()
    if arm_id == "v1" and mode not in {"CANONICAL_PAPER_MIRROR", "ISOLATED_PARALLEL_PAPER"}:
        mode = "ISOLATED_PARALLEL_PAPER"
    if arm_id != "v1":
        # Non-V1 arms are isolated parallel paper only in Sprint 3.
        mode = "ISOLATED_PARALLEL_PAPER"
    return {
        "arm_id": arm_id,
        "enabled": enabled,
        "policy_binding": policy_binding,
        "mode": mode,
        "starting_capital": _f(raw.get("starting_capital"), 30000.0),
        "min_cash_reserve": _f(raw.get("min_cash_reserve"), 500.0),
        "clock_group": _s(raw.get("clock_group") or CLOCK_GROUP_DEFAULT),
        "market_mark_group": _s(raw.get("market_mark_group") or MARKET_MARK_GROUP_DEFAULT),
        "execution_mode": _s(raw.get("execution_mode") or "PAPER").upper() or "PAPER",
        "live_allowed": False,  # hard safety — never LIVE via arm config
        "book_relpath": _s(raw.get("book_relpath") or f"runtime_outputs/parallel_paper/{arm_id}"),
        "notes": _s(raw.get("notes")),
    }


def synthesize_arms_from_legacy(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Build arms[] from legacy V1_*/V2_* flags when arms key is absent."""
    return [
        _normalize_arm_row(
            {
                "arm_id": "v1",
                "enabled": _bool(cfg.get("V1_PARALLEL_ENABLED"), True),
                "policy_binding": "v1",
                "mode": cfg.get("V1_MODE") or "ISOLATED_PARALLEL_PAPER",
                "starting_capital": cfg.get("V1_STARTING_CAPITAL"),
                "min_cash_reserve": cfg.get("V1_MIN_CASH_RESERVE"),
            },
            fallback_id="v1",
        ),
        _normalize_arm_row(
            {
                "arm_id": "v2",
                "enabled": _bool(cfg.get("V2_PARALLEL_ENABLED"), True)
                and _bool(cfg.get("V2_PARALLEL_PAPER_ENABLED"), True),
                "policy_binding": "v2",
                "mode": "ISOLATED_PARALLEL_PAPER",
                "starting_capital": cfg.get("V2_STARTING_CAPITAL"),
                "min_cash_reserve": cfg.get("V2_MIN_CASH_RESERVE"),
            },
            fallback_id="v2",
        ),
    ]


def sync_legacy_flags_from_arms(cfg: dict[str, Any], arms: list[dict[str, Any]]) -> None:
    """Keep V1_*/V2_* aliases in sync with arms[] for existing callers."""
    by_id = {a["arm_id"]: a for a in arms}
    v1 = by_id.get("v1")
    v2 = by_id.get("v2")
    if v1:
        cfg["V1_PARALLEL_ENABLED"] = bool(v1.get("enabled"))
        cfg["V1_STARTING_CAPITAL"] = float(v1.get("starting_capital") or 30000.0)
        cfg["V1_MIN_CASH_RESERVE"] = float(v1.get("min_cash_reserve") or 500.0)
        cfg["V1_MODE"] = str(v1.get("mode") or "ISOLATED_PARALLEL_PAPER")
    if v2:
        cfg["V2_PARALLEL_ENABLED"] = bool(v2.get("enabled"))
        cfg["V2_PARALLEL_PAPER_ENABLED"] = bool(v2.get("enabled"))
        cfg["V2_STARTING_CAPITAL"] = float(v2.get("starting_capital") or 30000.0)
        cfg["V2_MIN_CASH_RESERVE"] = float(v2.get("min_cash_reserve") or 500.0)
        cfg["V2_MODE"] = "ISOLATED_PARALLEL_PAPER"
    v3 = by_id.get("v3")
    if v3:
        # Phase 4: give v3 the same V{n}_STARTING_CAPITAL/V{n}_MIN_CASH_RESERVE
        # legacy-style aliases v1/v2 already get, so generic per-arm report
        # code (tae_today_activity_report.py, tae_parallel_paper_reports.py)
        # can read `cfg[f"{arm}_STARTING_CAPITAL"]` for any of the three arms
        # without a v1/v2-only special case.
        cfg["V3_PARALLEL_ENABLED"] = bool(v3.get("enabled"))
        cfg["V3_STARTING_CAPITAL"] = float(v3.get("starting_capital") or 30000.0)
        cfg["V3_MIN_CASH_RESERVE"] = float(v3.get("min_cash_reserve") or 500.0)
        cfg["V3_MODE"] = "ISOLATED_PARALLEL_PAPER"


def validate_arm_topology(arms: list[dict[str, Any]]) -> list[str]:
    """Return human-readable topology errors (empty = ok)."""
    errors: list[str] = []
    seen: set[str] = set()
    seen_books: set[str] = set()
    for a in arms:
        aid = _s(a.get("arm_id")).lower()
        if not aid:
            errors.append("ARM_MISSING_ID")
            continue
        if aid in seen:
            errors.append(f"ARM_DUPLICATE:{aid}")
        seen.add(aid)
        if a.get("live_allowed") is True:
            errors.append(f"ARM_LIVE_FORBIDDEN:{aid}")
        if a.get("execution_mode") not in {"PAPER", ""}:
            errors.append(f"ARM_EXECUTION_NOT_PAPER:{aid}")
        if a.get("enabled"):
            binding = a.get("policy_binding")
            if not binding:
                errors.append(f"ARM_ENABLED_WITHOUT_POLICY:{aid}")
            elif binding not in KNOWN_POLICY_BINDINGS:
                errors.append(f"ARM_ENABLED_UNKNOWN_POLICY:{aid}:{binding}")
            book = _s(a.get("book_relpath"))
            if book in seen_books:
                errors.append(f"ARM_DUPLICATE_BOOK:{aid}:{book}")
            seen_books.add(book)
            if binding == "experimental" and not book.startswith(
                "runtime_outputs/parallel_paper/exp_"
            ):
                errors.append(f"ARM_EXPERIMENTAL_BOOK_OUTSIDE_ISOLATION:{aid}:{book}")
    return errors


def normalize_arms(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    raw_arms = cfg.get("arms")
    if isinstance(raw_arms, list) and raw_arms:
        arms = [
            _normalize_arm_row(a, fallback_id=f"arm{i}")
            for i, a in enumerate(raw_arms)
            if isinstance(a, dict)
        ]
    else:
        arms = synthesize_arms_from_legacy(cfg)
    # Hard safety on every arm
    for a in arms:
        a["live_allowed"] = False
        if _s(a.get("execution_mode")).upper() != "PAPER":
            a["execution_mode"] = "PAPER"
    return arms


def configured_arms(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg if cfg is not None else load_parallel_paper_config()
    arms = cfg.get("arms")
    if isinstance(arms, list) and arms and isinstance(arms[0], dict) and "arm_id" in arms[0]:
        merged = list(arms)
    else:
        merged = normalize_arms(cfg)
    try:
        sidecar = json.loads(EXPERIMENTAL_ARMS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        sidecar = {}
    existing = {str(row.get("arm_id") or "").lower() for row in merged}
    for index, raw in enumerate(sidecar.get("arms") or []):
        if not isinstance(raw, dict):
            continue
        row = _normalize_arm_row(
            {**raw, "policy_binding": "experimental", "execution_mode": "PAPER"},
            fallback_id=f"experimental{index}",
        )
        if row["arm_id"] not in existing:
            merged.append(row)
            existing.add(row["arm_id"])
    return merged


def enabled_arms(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    return [a for a in configured_arms(cfg) if a.get("enabled") is True]


def arm_config(arm_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    aid = _s(arm_id).lower()
    for a in configured_arms(cfg):
        if a.get("arm_id") == aid:
            return dict(a)
    return None


def arm_dir(arm_id: str, *, root: Path | None = None) -> Path:
    base = Path(root) if root is not None else ROOT
    return base / _s(arm_id).lower()


def arm_paths(arm_id: str, *, root: Path | None = None) -> dict[str, Path]:
    """Canonical isolated book paths for one arm_id."""
    d = arm_dir(arm_id, root=root)
    j = d / "journals"
    aid = _s(arm_id).lower()
    out: dict[str, Path] = {
        "dir": d,
        "portfolio": d / "portfolio.json",
        "account": d / "account.json",
        "accounting": d / "accounting_snapshot.json",
        "health": d / "health.json",
        "errors": d / "errors.jsonl",
        "metrics": d / "daily_metrics.jsonl",
        "learning_state": d / "learning_state.json",
        "journals": j,
        "decisions": j / "decisions.jsonl",
        "executions": j / "executions.jsonl",
        "trades": j / "trades.jsonl",
        "learning_events": j / "learning_events.jsonl",
    }
    if aid == "v1":
        out["mirror_snapshot"] = d / "canonical_mirror_snapshot.json"
        out["mirror_meta"] = d / "mirror_meta.json"
    if aid == "v2":
        out["cycles"] = d / "cycle_state.json"
        out["reentry"] = d / "reentry_state.json"
        out["tranches"] = d / "tranche_events.jsonl"
    return out


def load_parallel_paper_config(path: Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path is not None else CONFIG_PATH
    payload = dict(_DEFAULTS)
    if cfg_path.is_file():
        try:
            raw = json.loads(cfg_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                payload.update(raw)
        except (OSError, json.JSONDecodeError):
            pass

    # Hard safety: LIVE always false (env cannot enable)
    payload["V2_LIVE_ENABLED"] = False
    payload["V2_CANONICAL_PAPER_ENABLED"] = False
    payload["STRATEGY_V2_GLOBAL_ENABLED"] = False

    payload["PARALLEL_PAPER_ENABLED"] = _bool(payload.get("PARALLEL_PAPER_ENABLED"), True)
    payload["V1_PARALLEL_ENABLED"] = _bool(payload.get("V1_PARALLEL_ENABLED"), True)
    payload["V2_PARALLEL_ENABLED"] = _bool(payload.get("V2_PARALLEL_ENABLED"), True)
    payload["V2_PARALLEL_PAPER_ENABLED"] = _bool(payload.get("V2_PARALLEL_PAPER_ENABLED"), True)
    payload["DAILY_REPORT_ENABLED"] = _bool(payload.get("DAILY_REPORT_ENABLED"), True)
    payload["AUTO_START_ENABLED"] = _bool(payload.get("AUTO_START_ENABLED"), False)
    payload["FAIL_ISOLATION_ENABLED"] = _bool(payload.get("FAIL_ISOLATION_ENABLED"), True)
    payload["RUNTIME_INTERVAL_SEC"] = int(payload.get("RUNTIME_INTERVAL_SEC") or 300)
    payload["HEARTBEAT_MAX_AGE_SEC"] = int(
        payload.get("HEARTBEAT_MAX_AGE_SEC")
        or max(660, int(payload["RUNTIME_INTERVAL_SEC"]) * 2 + 60)
    )
    v1_mode = str(payload.get("V1_MODE") or "ISOLATED_PARALLEL_PAPER").upper()
    if v1_mode not in {"CANONICAL_PAPER_MIRROR", "ISOLATED_PARALLEL_PAPER"}:
        v1_mode = "ISOLATED_PARALLEL_PAPER"
    payload["V1_MODE"] = v1_mode
    payload["V2_MODE"] = "ISOLATED_PARALLEL_PAPER"
    payload["CANONICAL_PAPER_PORTFOLIO"] = str(
        (
            PROJECT_ROOT
            / (
                payload.get("CANONICAL_PAPER_PORTFOLIO")
                or "runtime_outputs/paper_execution/paper_portfolio.json"
            )
        ).resolve()
        if not Path(
            str(
                payload.get("CANONICAL_PAPER_PORTFOLIO")
                or "runtime_outputs/paper_execution/paper_portfolio.json"
            )
        ).is_absolute()
        else Path(str(payload.get("CANONICAL_PAPER_PORTFOLIO"))).resolve()
    )
    payload["CANONICAL_PAPER_TRADES"] = str(
        (
            PROJECT_ROOT
            / (
                payload.get("CANONICAL_PAPER_TRADES")
                or "runtime_outputs/paper_execution/paper_trades.jsonl"
            )
        ).resolve()
        if not Path(
            str(
                payload.get("CANONICAL_PAPER_TRADES")
                or "runtime_outputs/paper_execution/paper_trades.jsonl"
            )
        ).is_absolute()
        else Path(str(payload.get("CANONICAL_PAPER_TRADES"))).resolve()
    )

    scope = str(payload.get("V2_ACTIVATION_SCOPE") or "PARALLEL_PAPER").upper()
    if scope not in ALLOWED_SCOPES or scope in {"LIVE", "CANONICAL_PAPER"}:
        scope = "PARALLEL_PAPER" if payload["V2_PARALLEL_PAPER_ENABLED"] else "DISABLED"
    if scope == "LIVE":
        scope = "DISABLED"
    payload["V2_ACTIVATION_SCOPE"] = scope

    payload["V1_STARTING_CAPITAL"] = float(payload.get("V1_STARTING_CAPITAL") or 30000.0)
    payload["V2_STARTING_CAPITAL"] = float(payload.get("V2_STARTING_CAPITAL") or 30000.0)
    payload["V1_MIN_CASH_RESERVE"] = float(payload.get("V1_MIN_CASH_RESERVE") or 500.0)
    payload["V2_MIN_CASH_RESERVE"] = float(payload.get("V2_MIN_CASH_RESERVE") or 500.0)
    payload["TIMEZONE"] = str(payload.get("TIMEZONE") or "Europe/Bucharest")
    payload["REPORT_OUTPUT_DIRECTORY"] = str(payload.get("REPORT_OUTPUT_DIRECTORY") or REPORTS_DIR)
    wl = payload.get("WATCHLIST") or []
    payload["WATCHLIST"] = [str(x).upper() for x in wl] if isinstance(wl, list) else []
    if not payload["WATCHLIST"]:
        # Found in the Phase 5 soak (2026-08-25): with WATCHLIST empty here,
        # _watchlist() in tae_parallel_paper_runtime.py falls back to
        # cfg.WATCHLIST ∪ already-held positions only — meaning V1/V2/V3
        # could NEVER discover a ticker they didn't already hold, no matter
        # how large watchlist.txt (the file live_bot.py's separate signal
        # generation reads) was. Falls back to watchlist.txt as the single
        # source of truth so parallel-paper actually sees the same universe
        # live_bot.py does, rather than silently evaluating an ever-static
        # set of previously-held tickers.
        wl_path = PROJECT_ROOT / "watchlist.txt"
        if wl_path.is_file():
            payload["WATCHLIST"] = [
                line.strip().upper()
                for line in wl_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

    arms = configured_arms({**payload, "arms": normalize_arms(payload)})
    # Fail-closed: disable any enabled arm with unknown/missing policy rather than inventing a runner.
    for a in arms:
        if a.get("enabled") and (
            not a.get("policy_binding") or a.get("policy_binding") not in KNOWN_POLICY_BINDINGS
        ):
            a["enabled"] = False
            a["notes"] = (a.get("notes") or "") + "|DISABLED_UNKNOWN_OR_MISSING_POLICY"
    sync_legacy_flags_from_arms(payload, arms)
    payload["arms"] = arms
    payload["arm_topology_errors"] = validate_arm_topology(arms)
    payload["schema"] = CONFIG_SCHEMA
    payload["n_arm_topology"] = True
    payload["known_policy_bindings"] = sorted(KNOWN_POLICY_BINDINGS)
    payload["enabled_arm_ids"] = [a["arm_id"] for a in arms if a.get("enabled")]
    payload["configured_arm_ids"] = [a["arm_id"] for a in arms]
    return payload


def v2_parallel_mutation_allowed(cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_parallel_paper_config()
    if cfg.get("V2_LIVE_ENABLED") is True:
        return False
    if cfg.get("V2_CANONICAL_PAPER_ENABLED") is True:
        return False
    if not cfg.get("PARALLEL_PAPER_ENABLED"):
        return False
    if not cfg.get("V2_PARALLEL_ENABLED"):
        return False
    if not cfg.get("V2_PARALLEL_PAPER_ENABLED"):
        return False
    return str(cfg.get("V2_ACTIVATION_SCOPE")) == "PARALLEL_PAPER"


def ensure_dirs(cfg: dict[str, Any] | None = None) -> None:
    """Create root/report dirs and book dirs for enabled arms only (no disabled stubs)."""
    cfg = cfg or load_parallel_paper_config()
    ROOT.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (ROOT / "attribution").mkdir(parents=True, exist_ok=True)
    (ROOT / "market_snapshots").mkdir(parents=True, exist_ok=True)
    for a in enabled_arms(cfg):
        d = arm_dir(a["arm_id"])
        (d / "journals").mkdir(parents=True, exist_ok=True)


def paths(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_parallel_paper_config()
    ensure_dirs(cfg)
    out: dict[str, Any] = {
        "root": ROOT,
        "v1_dir": V1_DIR,
        "v2_dir": V2_DIR,
        "reports": REPORTS_DIR,
        "attribution_dir": ROOT / "attribution",
        "attribution_store": ROOT / "attribution" / "economic_cycles.json",
        "attribution_summary": ROOT / "attribution" / "economic_summary.json",
        "divergences": ROOT / "divergence_journal.jsonl",
        "runtime_status": ROOT / "runtime_status.json",
        "status": ROOT / "parallel_paper_status.json",
        "heartbeat": ROOT / "parallel_paper_heartbeat.json",
        "pid": ROOT / "parallel_paper.pid",
        "lock": ROOT / "parallel_paper.lock",
        "log": ROOT / "parallel_paper.log",
        "daemon_log": ROOT / "daemon.log",
        "latest_conclusion": ROOT / "latest_daily_conclusion.json",
        "cumulative_md": REPORTS_DIR / "TAE_PARALLEL_CUMULATIVE_REPORT.md",
        "cumulative_json": REPORTS_DIR / "tae_parallel_cumulative_report.json",
        "daily_metrics_csv": REPORTS_DIR / "tae_parallel_daily_metrics.csv",
        "snapshots": ROOT / "market_snapshots",
        "arms": {},
    }
    # Nested per-arm paths for all configured arms (enabled or not — path map only).
    for a in configured_arms(cfg):
        aid = a["arm_id"]
        ap = arm_paths(aid)
        out["arms"][aid] = ap
        # Legacy flat aliases for v1/v2
        if aid == "v1":
            out["v1_portfolio"] = ap["portfolio"]
            out["v1_mirror_snapshot"] = ap.get("mirror_snapshot") or (V1_DIR / "canonical_mirror_snapshot.json")
            out["v1_mirror_meta"] = ap.get("mirror_meta") or (V1_DIR / "mirror_meta.json")
            out["v1_account"] = ap["account"]
            out["v1_decisions"] = ap["decisions"]
            out["v1_executions"] = ap["executions"]
            out["v1_trades"] = ap["trades"]
            out["v1_learning_events"] = ap["learning_events"]
            out["v1_learning_state"] = ap["learning_state"]
            out["v1_accounting"] = ap["accounting"]
            out["v1_metrics"] = ap["metrics"]
            out["v1_errors"] = ap["errors"]
            out["v1_health"] = ap["health"]
        if aid == "v2":
            out["v2_portfolio"] = ap["portfolio"]
            out["v2_account"] = ap["account"]
            out["v2_decisions"] = ap["decisions"]
            out["v2_executions"] = ap["executions"]
            out["v2_trades"] = ap["trades"]
            out["v2_learning_events"] = ap["learning_events"]
            out["v2_learning_state"] = ap["learning_state"]
            out["v2_accounting"] = ap["accounting"]
            out["v2_metrics"] = ap["metrics"]
            out["v2_errors"] = ap["errors"]
            out["v2_health"] = ap["health"]
            out["v2_cycles"] = ap.get("cycles") or (V2_DIR / "cycle_state.json")
            out["v2_reentry"] = ap.get("reentry") or (V2_DIR / "reentry_state.json")
            out["v2_tranches"] = ap.get("tranches") or (V2_DIR / "tranche_events.jsonl")
    # Ensure legacy keys exist even if arms list somehow omitted v1/v2
    for key, path in (
        ("v1_portfolio", V1_DIR / "portfolio.json"),
        ("v1_account", V1_DIR / "account.json"),
        ("v1_decisions", V1_DIR / "journals" / "decisions.jsonl"),
        ("v1_executions", V1_DIR / "journals" / "executions.jsonl"),
        ("v1_trades", V1_DIR / "journals" / "trades.jsonl"),
        ("v1_learning_events", V1_DIR / "journals" / "learning_events.jsonl"),
        ("v1_learning_state", V1_DIR / "learning_state.json"),
        ("v1_accounting", V1_DIR / "accounting_snapshot.json"),
        ("v1_metrics", V1_DIR / "daily_metrics.jsonl"),
        ("v1_errors", V1_DIR / "errors.jsonl"),
        ("v1_health", V1_DIR / "health.json"),
        ("v1_mirror_snapshot", V1_DIR / "canonical_mirror_snapshot.json"),
        ("v1_mirror_meta", V1_DIR / "mirror_meta.json"),
        ("v2_portfolio", V2_DIR / "portfolio.json"),
        ("v2_account", V2_DIR / "account.json"),
        ("v2_decisions", V2_DIR / "journals" / "decisions.jsonl"),
        ("v2_executions", V2_DIR / "journals" / "executions.jsonl"),
        ("v2_trades", V2_DIR / "journals" / "trades.jsonl"),
        ("v2_learning_events", V2_DIR / "journals" / "learning_events.jsonl"),
        ("v2_learning_state", V2_DIR / "learning_state.json"),
        ("v2_accounting", V2_DIR / "accounting_snapshot.json"),
        ("v2_metrics", V2_DIR / "daily_metrics.jsonl"),
        ("v2_errors", V2_DIR / "errors.jsonl"),
        ("v2_health", V2_DIR / "health.json"),
        ("v2_cycles", V2_DIR / "cycle_state.json"),
        ("v2_reentry", V2_DIR / "reentry_state.json"),
        ("v2_tranches", V2_DIR / "tranche_events.jsonl"),
    ):
        out.setdefault(key, path)
    return out
