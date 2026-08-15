#!/usr/bin/env python3
"""
TAE Strategy Lab Facade — Sprint 1 + Sprint 2

READ-ONLY SSOT orchestration over parallel-paper books + research/econ adapters.
PAPER_ONLY observation | NO_BROKER | NO_LIVE | NO_AUTO_PROMOTE

Does not authorize BUY/SELL, mutate arm books, start/stop runtimes,
or change V1/V2 trading policy. Sprint 2 adapters never own accounting/replay/research.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_learning_economic_ablation import equity_metrics
from tae_parallel_paper_config import (
    PROJECT_ROOT,
    REPORTS_DIR,
    arm_config,
    arm_paths,
    configured_arms,
    enabled_arms,
    load_parallel_paper_config,
)
from tae_strategy_lab_adapters import (
    CycleAnalyticsAdapter,
    EconomicsAdapter,
    ReplayAdapter,
    ResearchAdapter,
)

SCHEMA = "tae.strategy_lab.facade.v4"
SCOREBOARD_SCHEMA = "tae.strategy_lab.scoreboard.v2"
REGISTRY_PATH = PROJECT_ROOT / "config" / "tae_strategy_lab_registry.json"
LAB_OUT_DIR = PROJECT_ROOT / "runtime_outputs" / "strategy_lab"
SCOREBOARD_PATH = LAB_OUT_DIR / "economic_scoreboard.json"
HEALTH_PATH = LAB_OUT_DIR / "strategy_health.json"
EXPLANATIONS_PATH = LAB_OUT_DIR / "strategy_explanations.json"
RESEARCH_SUMMARY_PATH = LAB_OUT_DIR / "research_summary.json"
ECONOMIC_METRICS_PATH = LAB_OUT_DIR / "economic_metrics.json"
EXPERIMENTAL_REGISTRY_PATH = LAB_OUT_DIR / "experimental_challengers.json"
METRICS_CSV = REPORTS_DIR / "tae_parallel_daily_metrics.csv"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _f(v: Any, default: float = 0.0) -> float:
    try:
        x = float(v)
        if math.isnan(x) or math.isinf(x):
            return default
        return x
    except (TypeError, ValueError):
        return default


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


def git_head() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=str(PROJECT_ROOT),
                stderr=subprocess.DEVNULL,
                text=True,
            )
            .strip()
            or None
        )
    except Exception:
        return None


def load_registry(path: Path | None = None) -> dict[str, Any]:
    """Load declarative Strategy Lab registry SSOT."""
    p = Path(path) if path is not None else REGISTRY_PATH
    doc = _read_json(p)
    if not doc:
        raise FileNotFoundError(f"strategy_lab_registry_missing:{p}")
    if not isinstance(doc.get("strategies"), list):
        raise ValueError("strategy_lab_registry_invalid:strategies")
    return doc


def list_strategies(
    *,
    status: str | None = None,
    enabled_only: bool = True,
    registry: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    reg = registry or load_registry()
    rows: list[dict[str, Any]] = []
    for s in reg.get("strategies") or []:
        if not isinstance(s, dict):
            continue
        if enabled_only and s.get("enabled_in_lab") is not True:
            continue
        if status and _s(s.get("status")).upper() != _s(status).upper():
            continue
        rows.append(dict(s))
    return rows


def _arm_account(arm: str) -> dict[str, Any] | None:
    return _read_json(arm_paths(_s(arm).lower())["account"])


def _arm_portfolio(arm: str) -> dict[str, Any] | None:
    return _read_json(arm_paths(_s(arm).lower())["portfolio"])


def _arm_snapshot(arm: str) -> dict[str, Any] | None:
    return _read_json(arm_paths(_s(arm).lower())["accounting"])


def _read_daily_metrics() -> list[dict[str, Any]]:
    if not METRICS_CSV.is_file():
        return []
    with METRICS_CSV.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _equity_curve_for_arm(arm: str, starting: float, metrics: list[dict[str, Any]]) -> list[float]:
    # Daily metrics CSV currently emits V1_av / V2_av; future arms use {ARM}_av.
    key = f"{_s(arm).upper()}_av"
    curve = [float(starting)]
    for row in metrics:
        av = _f(row.get(key), float("nan"))
        if math.isnan(av):
            continue
        curve.append(av)
    return curve


def _cycle_metrics_from_attribution(arm: str) -> dict[str, Any]:
    """Prefer paper economic_summary; fall back to arm accounting_snapshot. No new formulas."""
    arm_l = _s(arm).lower()
    eco_adapter = EconomicsAdapter()
    block = eco_adapter.arm_block(arm_l)
    source = "runtime_outputs/parallel_paper/attribution/economic_summary.json"
    if not block:
        snap = _arm_snapshot(arm_l) or {}
        block = snap.get("economic_attribution") if isinstance(snap, dict) else None
        source = f"runtime_outputs/parallel_paper/{arm_l}/accounting_snapshot.json#economic_attribution"
    if not isinstance(block, dict):
        return {
            "expectancy": None,
            "profit_per_cycle": None,
            "win_rate": None,
            "average_cycle": None,
            "open_cycles": None,
            "closed_cycles": None,
            "capital_utilization_pct": None,
            "net_realized_pnl": None,
            "source": "missing_attribution",
        }
    return {
        "expectancy": block.get("expectancy_per_closed_cycle"),
        "profit_per_cycle": block.get("expectancy_per_closed_cycle"),
        "win_rate": block.get("win_rate"),
        "average_cycle": block.get("average_holding_seconds"),
        "open_cycles": block.get("open_cycles"),
        "closed_cycles": block.get("closed_cycles"),
        "capital_utilization_pct": block.get("capital_utilization_pct"),
        "net_realized_pnl": block.get("net_realized_pnl"),
        "transaction_costs": block.get("transaction_costs"),
        "source": source,
    }


def _fees_from_tx(snap: dict[str, Any] | None, account: dict[str, Any] | None) -> float | None:
    if snap and isinstance(snap.get("transaction_cost_metrics"), dict):
        tcm = snap["transaction_cost_metrics"]
        if tcm.get("sell_costs") is not None or tcm.get("buy_costs") is not None:
            return round(_f(tcm.get("sell_costs")) + _f(tcm.get("buy_costs")), 6)
    if account and isinstance(account.get("transaction_cost_metrics"), dict):
        tcm = account["transaction_cost_metrics"]
        return round(_f(tcm.get("sell_costs")) + _f(tcm.get("buy_costs")), 6)
    return None


def build_strategy_row(
    strategy: dict[str, Any],
    *,
    cfg: dict[str, Any],
    metrics_rows: list[dict[str, Any]],
    head: str | None,
) -> dict[str, Any]:
    arm = _s(strategy.get("runtime_arm")).lower()
    acfg = arm_config(arm, cfg) or {}
    starting = _f(acfg.get("starting_capital"), _f(cfg.get(f"{arm.upper()}_STARTING_CAPITAL"), 30000.0))
    account = _arm_account(arm) or {}
    portfolio = _arm_portfolio(arm) or {}
    snap = _arm_snapshot(arm)
    ap = arm_paths(arm)
    av = _f(account.get("account_value"), float("nan"))
    cash = _f(account.get("cash"), float("nan"))
    invested = _f(account.get("invested"), float("nan"))
    realized = _f(account.get("realized_pnl"), float("nan"))
    unrealized = _f(account.get("unrealized_pnl"), float("nan"))
    pnl = av - starting if not math.isnan(av) else float("nan")
    ret = (100.0 * pnl / starting) if starting and not math.isnan(pnl) else float("nan")

    curve = _equity_curve_for_arm(arm, starting, metrics_rows)
    em = equity_metrics(curve, starting) if len(curve) >= 2 else {
        "sharpe": None,
        "sortino": None,
        "max_drawdown": None,
        "source_note": "insufficient_daily_metrics_for_equity_metrics",
    }

    positions = portfolio.get("positions") or {}
    n_pos = len([p for p in positions.values() if isinstance(p, dict) and _f(p.get("shares")) > 0])
    exposure = invested if not math.isnan(invested) else None
    cash_util = None
    if not math.isnan(av) and av > 0 and not math.isnan(invested):
        cash_util = round(100.0 * invested / av, 6)

    cycle_m = _cycle_metrics_from_attribution(arm)

    # Latest daily pnl from metrics if present
    last = metrics_rows[-1] if metrics_rows else {}
    daily_pnl_key = f"{arm.upper()}_pnl"
    profit_per_day = _f(last.get(daily_pnl_key), float("nan"))

    recon = account.get("reconciliation_pass")
    identity_ok = None
    if not any(math.isnan(x) for x in (av, cash, invested, unrealized)):
        identity_ok = abs((cash + invested + unrealized) - av) <= 0.02

    # capital_efficiency: prefer attribution capital_utilization_pct when present
    cap_eff = cycle_m.get("capital_utilization_pct")
    if cap_eff is None:
        cap_eff = cash_util

    return {
        "strategy_id": strategy.get("strategy_id"),
        "display_name": strategy.get("display_name"),
        "status": strategy.get("status"),
        "runtime_arm": arm,
        "commit_binding": strategy.get("commit") or head,
        "promotion_state": strategy.get("promotion_state"),
        "read_only": True,
        "account_value": None if math.isnan(av) else round(av, 6),
        "pnl": None if math.isnan(pnl) else round(pnl, 6),
        "return_pct": None if math.isnan(ret) else round(ret, 6),
        "sharpe": em.get("sharpe"),
        "sortino": em.get("sortino"),
        "roi": None,  # ROI-001 is challenger-global, not per parallel arm
        "expectancy": cycle_m.get("expectancy"),
        "profit_per_cycle": cycle_m.get("profit_per_cycle"),
        "profit_per_day": None if math.isnan(profit_per_day) else round(profit_per_day, 6),
        "capital_efficiency": cap_eff,
        "drawdown": em.get("max_drawdown"),
        "win_rate": cycle_m.get("win_rate"),
        "average_cycle": cycle_m.get("average_cycle"),
        "exposure": None if exposure is None or math.isnan(exposure) else round(exposure, 6),
        "cash": None if math.isnan(cash) else round(cash, 6),
        "cash_utilization": cash_util,
        "fees": _fees_from_tx(snap, account),
        "open_positions": n_pos,
        "realized_pnl": None if math.isnan(realized) else round(realized, 6),
        "unrealized_pnl": None if math.isnan(unrealized) else round(unrealized, 6),
        "accounting_integrity": (
            "PASS"
            if recon is True and identity_ok is not False
            else ("WARN" if recon is True else "FAIL" if recon is False else None)
        ),
        "data_integrity": "PASS" if account else None,
        "decision_integrity": None,  # no canonical per-arm decision integrity SSOT
        "execution_integrity": None,  # no canonical per-arm execution integrity SSOT
        "sources": {
            "account": str(ap["account"].relative_to(PROJECT_ROOT)),
            "portfolio": str(ap["portfolio"].relative_to(PROJECT_ROOT)),
            "daily_metrics": str(METRICS_CSV.relative_to(PROJECT_ROOT)) if METRICS_CSV.is_file() else None,
            "equity_metrics_owner": "tae_learning_economic_ablation.equity_metrics",
            "cycle_metrics": cycle_m.get("source"),
            "arm_config": acfg or None,
        },
        "account_ts": account.get("ts"),
        "identity_cash_invested_unrealized_eq_av": identity_ok,
        "reconciliation_pass": recon,
        "clock_group": strategy.get("clock_group") or acfg.get("clock_group"),
        "market_mark_group": strategy.get("market_mark_group") or acfg.get("market_mark_group"),
        "execution_mode": strategy.get("execution_mode") or acfg.get("execution_mode") or "PAPER",
        "live_allowed": False,
        "economic_experiment_uid": strategy.get("economic_experiment_uid"),
        "learning_cycle_id": strategy.get("learning_cycle_id"),
        "hypothesis_id": strategy.get("hypothesis_id"),
    }


def reconcile_with_parallel_books(
    scoreboard_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Exact AV/cash reconcile lab scoreboard vs parallel account.json SSOT."""
    checks = []
    all_pass = True
    for row in scoreboard_rows:
        arm = _s(row.get("runtime_arm")).lower()
        acct = _arm_account(arm) or {}
        av_lab = row.get("account_value")
        cash_lab = row.get("cash")
        av_book = acct.get("account_value")
        cash_book = acct.get("cash")
        av_ok = av_lab is not None and abs(_f(av_lab) - _f(av_book)) <= 0.01
        cash_ok = cash_lab is not None and abs(_f(cash_lab) - _f(cash_book)) <= 0.01
        ok = bool(av_ok and cash_ok and acct)
        all_pass = all_pass and ok
        checks.append(
            {
                "strategy_id": row.get("strategy_id"),
                "runtime_arm": arm,
                "account_value_lab": av_lab,
                "account_value_book": av_book,
                "cash_lab": cash_lab,
                "cash_book": cash_book,
                "match": ok,
                "book_path": str(arm_paths(arm)["account"]) if arm else None,
            }
        )
    return {
        "pass": all_pass,
        "checks": checks,
        "rule": "lab.account_value/cash must equal parallel account.json within $0.01",
    }


def live_lock_status() -> dict[str, Any]:
    """Observe live promotion lock — never mutate."""
    try:
        import tae_live_promotion_lock as lock

        if hasattr(lock, "load_lock") or hasattr(lock, "status"):
            fn = getattr(lock, "status", None) or getattr(lock, "load_lock", None)
            if callable(fn):
                st = fn()
                return {"ok": True, "status": st, "auto_promote": False}
        return {
            "ok": True,
            "module": "tae_live_promotion_lock",
            "auto_promote": False,
            "note": "module_present_observe_only",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "auto_promote": False}


def research_pointers() -> dict[str, Any]:
    """Pointers to research owners — adapters read, never execute pipelines."""
    return {
        "strategy_evolution_daily_runner": "research_core/strategy_evolution/daily_runner.py",
        "candidate_registry": "research_core/strategy_evolution/candidate_registry.py",
        "promotion_gate": "research_core/strategy_evolution/promotion_gate.py",
        "roi001": "tae_roi001_challenger.py",
        "capital_challengers": "runtime_outputs/learning_to_profit/capital_challengers.json",
        "chronological_replay": "tae_chronological_portfolio_replay.py",
        "paper_economic_attribution": "tae_paper_economic_attribution.py",
        "sprint_executes_research": False,
        "sprint_executes_replay": False,
    }


def _persist_lab(path: Path, doc: dict[str, Any]) -> str:
    LAB_OUT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _parallel_paper_state(arm: str) -> str:
    acct = _arm_account(arm)
    if not acct:
        return "MISSING_BOOK"
    if acct.get("reconciliation_pass") is True:
        return "PARALLEL_ACTIVE_RECON_PASS"
    if acct.get("reconciliation_pass") is False:
        return "PARALLEL_ACTIVE_RECON_FAIL"
    return "PARALLEL_ACTIVE"


def _economic_validation_state(row: dict[str, Any]) -> str:
    if row.get("account_value") is None:
        return "MISSING_ECONOMICS"
    exp = row.get("expectancy")
    if exp is None:
        return "PARTIAL_METRICS"
    if _f(exp) >= 0 and _f(row.get("pnl")) >= 0:
        return "ECONOMIC_OBSERVED_NONNEG"
    return "ECONOMIC_OBSERVED_NEG"


def _promotion_readiness(
    *,
    strategy: dict[str, Any],
    research: dict[str, Any],
    replay: dict[str, Any],
    row: dict[str, Any],
) -> str:
    # Never READY_TO_PROMOTE automatically — human gate only.
    gate = (research.get("promotion_gate") or {}).get("verdict")
    replay_state = replay.get("replay_state")
    if strategy.get("promotion_state") == "HUMAN_GATED":
        if row.get("accounting_integrity") != "PASS":
            return "NOT_READY_ACCOUNTING"
        if replay_state == "MISSING":
            return "NOT_READY_REPLAY_MISSING"
        if gate:
            return "HUMAN_GATED_REVIEW_ONLY"
        return "HUMAN_GATED"
    return "HUMAN_GATED"


def _explain_strategy(
    row: dict[str, Any],
    *,
    peers: list[dict[str, Any]],
    arm_attr: dict[str, Any] | None,
) -> dict[str, Any]:
    """Deterministic explanation layer from existing attribution/metrics only."""
    pnl = row.get("pnl")
    realized = row.get("realized_pnl")
    unrealized = row.get("unrealized_pnl")
    dd = row.get("drawdown")
    cash_util = row.get("cash_utilization")
    cap_eff = row.get("capital_efficiency")
    exp = row.get("expectancy")
    win_rate = row.get("win_rate")
    closed = None if not arm_attr else arm_attr.get("closed_cycles")
    costs = None if not arm_attr else arm_attr.get("transaction_costs")

    why_pnl_parts = []
    if pnl is not None:
        why_pnl_parts.append(f"pnl={pnl}")
    if realized is not None:
        why_pnl_parts.append(f"realized_pnl={realized}")
    if unrealized is not None:
        why_pnl_parts.append(f"unrealized_pnl={unrealized}")
    if costs is not None:
        why_pnl_parts.append(f"transaction_costs={costs}")
    if not why_pnl_parts:
        why_pnl = "NO_CANONICAL_PNL_FIELDS"
    elif _f(pnl) < 0:
        why_pnl = "NEGATIVE_PNL|" + "|".join(why_pnl_parts)
    elif _f(pnl) > 0:
        why_pnl = "POSITIVE_PNL|" + "|".join(why_pnl_parts)
    else:
        why_pnl = "FLAT_PNL|" + "|".join(why_pnl_parts)

    if dd is None:
        why_dd = "NO_CANONICAL_DRAWDOWN"
    else:
        why_dd = f"MAX_DRAWDOWN_PCT={dd}|source=tae_learning_economic_ablation.equity_metrics"

    if cap_eff is None and cash_util is None:
        why_cap = "NO_CANONICAL_CAPITAL_EFFICIENCY"
    else:
        why_cap = (
            f"capital_efficiency={cap_eff}|cash_utilization={cash_util}"
            f"|open_positions={row.get('open_positions')}|exposure={row.get('exposure')}"
        )

    if exp is None:
        why_exp = "NO_CANONICAL_EXPECTANCY"
    else:
        why_exp = (
            f"expectancy_per_closed_cycle={exp}|win_rate={win_rate}"
            f"|closed_cycles={closed}|source=paper_economic_attribution"
        )

    ranked = sorted(
        [p for p in peers if p.get("pnl") is not None],
        key=lambda r: (_f(r.get("pnl")), _s(r.get("strategy_id"))),
        reverse=True,
    )
    rank = None
    for i, p in enumerate(ranked, start=1):
        if p.get("strategy_id") == row.get("strategy_id"):
            rank = i
            break
    if rank is None:
        why_rank = "NO_RANK_PNL_MISSING"
    else:
        peer_bits = [
            f"{p.get('strategy_id')}:pnl={p.get('pnl')}"
            for p in ranked
        ]
        why_rank = f"RANK_BY_PNL={rank}|n={len(ranked)}|" + "|".join(peer_bits)

    return {
        "strategy_id": row.get("strategy_id"),
        "runtime_arm": row.get("runtime_arm"),
        "WHY_PNL": why_pnl,
        "WHY_DRAWDOWN": why_dd,
        "WHY_CAPITAL": why_cap,
        "WHY_EXPECTANCY": why_exp,
        "WHY_RANK": why_rank,
        "inputs": {
            "pnl": pnl,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "drawdown": dd,
            "capital_efficiency": cap_eff,
            "expectancy": exp,
            "win_rate": win_rate,
            "closed_cycles": closed,
            "transaction_costs": costs,
        },
        "deterministic": True,
        "invents_formulas": False,
    }


class StrategyLabFacade:
    """Read-only orchestration façade (Sprint 1 + Sprint 2 adapters)."""

    def __init__(self, registry_path: Path | None = None) -> None:
        self.registry_path = Path(registry_path) if registry_path else REGISTRY_PATH
        self._research = ResearchAdapter()
        self._replay = ReplayAdapter()
        self._economics = EconomicsAdapter()
        self._cycles = CycleAnalyticsAdapter()

    def load_registry(self) -> dict[str, Any]:
        return load_registry(self.registry_path)

    def list_strategies(self, status: str | None = None) -> list[dict[str, Any]]:
        return list_strategies(status=status, registry=self.load_registry())

    def load_research(self) -> dict[str, Any]:
        return self._research.load()

    def load_replay(self) -> dict[str, Any]:
        return self._replay.load()

    def load_economics(self) -> dict[str, Any]:
        return self._economics.load()

    def load_cycle_analytics(self) -> dict[str, Any]:
        return self._cycles.load()

    def build_scoreboard(self, *, persist: bool = True) -> dict[str, Any]:
        reg = self.load_registry()
        cfg = load_parallel_paper_config()
        metrics = _read_daily_metrics()
        head = git_head()
        strategy_specs = list_strategies(registry=reg)
        experimental_doc = _read_json(EXPERIMENTAL_REGISTRY_PATH) or {}
        known_ids = {row.get("strategy_id") for row in strategy_specs}
        for experimental in experimental_doc.get("strategies") or []:
            if not isinstance(experimental, dict):
                continue
            if experimental.get("strategy_id") in known_ids:
                continue
            strategy_specs.append(
                {
                    **experimental,
                    "display_name": experimental.get("display_name")
                    or experimental.get("strategy_id"),
                    "promotion_state": "HUMAN_GATED",
                }
            )
        rows = [
            build_strategy_row(s, cfg=cfg, metrics_rows=metrics, head=head)
            for s in strategy_specs
        ]
        recon = reconcile_with_parallel_books(rows)
        econ = self.load_economics()
        doc = {
            "schema": SCOREBOARD_SCHEMA,
            "lab_id": reg.get("lab_id"),
            "generated_at": _now(),
            "git_head": head,
            "mode": "READ_ONLY",
            "auto_promote": False,
            "autonomous_paper_evolution": _autonomous_paper_status(),
            "live_mutation": False,
            "strategies": rows,
            "reconciliation": recon,
            "live_lock": live_lock_status(),
            "research_pointers": research_pointers(),
            "roi_global": econ.get("roi001"),
            "reuse": reg.get("reuse_map") or {},
            "forbidden": [
                "BUY",
                "SELL",
                "mutate_parallel_books",
                "start_stop_runtime",
                "auto_promote",
                "live_orders",
            ],
        }
        if persist:
            doc["scoreboard_path"] = _persist_lab(SCOREBOARD_PATH, doc)
        return doc

    def build_research_summary(self, *, persist: bool = True) -> dict[str, Any]:
        research = self.load_research()
        replay = self.load_replay()
        sb = self.build_scoreboard(persist=False)
        rows = sb.get("strategies") or []
        by_id = {r.get("strategy_id"): r for r in rows}
        strategies_view = []
        for strat in self.list_strategies():
            sid = strat.get("strategy_id")
            arm = _s(strat.get("runtime_arm")).lower()
            row = by_id.get(sid) or {}
            strategies_view.append(
                {
                    "strategy_id": sid,
                    "candidate_status": strat.get("status"),
                    "research_state": (research.get("strategy_evolution") or {}).get(
                        "completeness"
                    ),
                    "research_verdict": (research.get("strategy_evolution") or {}).get(
                        "daily_runner_verdict"
                    ),
                    "replay_state": replay.get("replay_state"),
                    "parallel_paper_state": _parallel_paper_state(arm),
                    "economic_validation_state": _economic_validation_state(row),
                    "promotion_readiness": _promotion_readiness(
                        strategy=strat, research=research, replay=replay, row=row
                    ),
                    "produces_promotion": False,
                }
            )
        doc = {
            "schema": "tae.strategy_lab.research_summary.v1",
            "generated_at": _now(),
            "git_head": git_head(),
            "mode": "READ_ONLY",
            "auto_promote": False,
            "strategy_evolution": research.get("strategy_evolution"),
            "candidate_registry": {
                "verdict": (research.get("candidate_registry") or {}).get("verdict"),
                "baseline_candidate_id": (research.get("candidate_registry") or {}).get(
                    "baseline_candidate_id"
                ),
                "candidate_count": (research.get("candidate_registry") or {}).get(
                    "candidate_count"
                ),
            },
            "promotion_gate": research.get("promotion_gate"),
            "capital_challengers": {
                "challenger_count": (research.get("capital_challengers") or {}).get(
                    "challenger_count"
                ),
                "authorized_count": (research.get("capital_challengers") or {}).get(
                    "authorized_count"
                ),
                "live_promotion_allowed": (research.get("capital_challengers") or {}).get(
                    "live_promotion_allowed"
                ),
            },
            "replay": {
                "replay_state": replay.get("replay_state"),
                "recommendation": (replay.get("chronological") or {}).get("recommendation")
                if replay.get("chronological")
                else None,
                "reliable_for_promotion": (replay.get("chronological") or {}).get(
                    "reliable_for_promotion"
                )
                if replay.get("chronological")
                else None,
            },
            "strategies": strategies_view,
            "sources": research.get("sources"),
        }
        if persist:
            doc["path"] = _persist_lab(RESEARCH_SUMMARY_PATH, doc)
        return doc

    def build_strategy_health(self, *, persist: bool = True) -> dict[str, Any]:
        research = self.load_research()
        replay = self.load_replay()
        sb = self.build_scoreboard(persist=False)
        rows = sb.get("strategies") or []
        health_rows = []
        for row in rows:
            arm = _s(row.get("runtime_arm")).lower()
            issues = []
            if row.get("accounting_integrity") != "PASS":
                issues.append("ACCOUNTING_NOT_PASS")
            if row.get("account_value") is None:
                issues.append("MISSING_ACCOUNT_VALUE")
            if replay.get("replay_state") == "MISSING":
                issues.append("REPLAY_MISSING")
            health_rows.append(
                {
                    "strategy_id": row.get("strategy_id"),
                    "runtime_arm": arm,
                    "accounting_integrity": row.get("accounting_integrity"),
                    "data_integrity": row.get("data_integrity"),
                    "decision_integrity": row.get("decision_integrity"),
                    "execution_integrity": row.get("execution_integrity"),
                    "reconciliation_pass": row.get("reconciliation_pass"),
                    "parallel_paper_state": _parallel_paper_state(arm),
                    "research_state": (research.get("strategy_evolution") or {}).get(
                        "completeness"
                    ),
                    "replay_state": replay.get("replay_state"),
                    "economic_validation_state": _economic_validation_state(row),
                    "promotion_readiness": _promotion_readiness(
                        strategy={
                            "strategy_id": row.get("strategy_id"),
                            "promotion_state": row.get("promotion_state"),
                        },
                        research=research,
                        replay=replay,
                        row=row,
                    ),
                    "issues": issues,
                    "healthy": len(issues) == 0,
                }
            )
        doc = {
            "schema": "tae.strategy_lab.strategy_health.v1",
            "generated_at": _now(),
            "git_head": git_head(),
            "mode": "READ_ONLY",
            "reconciliation_pass": (sb.get("reconciliation") or {}).get("pass"),
            "strategies": health_rows,
        }
        if persist:
            doc["path"] = _persist_lab(HEALTH_PATH, doc)
        return doc

    def build_strategy_explanation(self, *, persist: bool = True) -> dict[str, Any]:
        sb = self.build_scoreboard(persist=False)
        rows = sb.get("strategies") or []
        econ = self.load_economics()
        arms = econ.get("paper_arms") or {}
        explanations = [
            _explain_strategy(
                row,
                peers=rows,
                arm_attr=arms.get(_s(row.get("runtime_arm")).lower()),
            )
            for row in rows
        ]
        # Sort for determinism
        explanations = sorted(explanations, key=lambda e: _s(e.get("strategy_id")))
        doc = {
            "schema": "tae.strategy_lab.strategy_explanations.v1",
            "generated_at": _now(),
            "git_head": git_head(),
            "mode": "READ_ONLY",
            "deterministic": True,
            "strategies": explanations,
        }
        if persist:
            doc["path"] = _persist_lab(EXPLANATIONS_PATH, doc)
        return doc

    def build_economic_metrics(self, *, persist: bool = True) -> dict[str, Any]:
        sb = self.build_scoreboard(persist=False)
        econ = self.load_economics()
        cycles = self.load_cycle_analytics()
        metrics_rows = []
        for row in sb.get("strategies") or []:
            metrics_rows.append(
                {
                    "strategy_id": row.get("strategy_id"),
                    "runtime_arm": row.get("runtime_arm"),
                    "sharpe": row.get("sharpe"),
                    "sortino": row.get("sortino"),
                    "roi": row.get("roi"),
                    "expectancy": row.get("expectancy"),
                    "profit_per_cycle": row.get("profit_per_cycle"),
                    "profit_per_day": row.get("profit_per_day"),
                    "capital_efficiency": row.get("capital_efficiency"),
                    "average_cycle": row.get("average_cycle"),
                    "drawdown": row.get("drawdown"),
                    "exposure": row.get("exposure"),
                    "win_rate": row.get("win_rate"),
                    "decision_integrity": row.get("decision_integrity"),
                    "execution_integrity": row.get("execution_integrity"),
                    "accounting_integrity": row.get("accounting_integrity"),
                    "sources": row.get("sources"),
                }
            )
        metrics_rows = sorted(metrics_rows, key=lambda r: _s(r.get("strategy_id")))
        doc = {
            "schema": "tae.strategy_lab.economic_metrics.v1",
            "generated_at": _now(),
            "git_head": git_head(),
            "mode": "READ_ONLY",
            "invents_formulas": False,
            "strategies": metrics_rows,
            "roi_global": econ.get("roi001"),
            "roi_queue": econ.get("roi_queue"),
            "learning_attribution": econ.get("learning_attribution"),
            "daily_scorecard": econ.get("daily_scorecard"),
            "ablation_metrics_on": econ.get("ablation_metrics_on"),
            "cycle_analytics_sources": cycles.get("sources"),
            "reconciliation_pass": (sb.get("reconciliation") or {}).get("pass"),
        }
        if persist:
            doc["path"] = _persist_lab(ECONOMIC_METRICS_PATH, doc)
        return doc

    def build_promotion_recommendation(self) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.build_promotion_recommendation(
            research=self.load_research(),
            replay=self.load_replay(),
            health=self.build_strategy_health(persist=False),
            economics=self.load_economics(),
        )

    def create_promotion_ticket(
        self,
        *,
        ticket_type: str,
        strategy_id: str,
        target_state: str,
        requested_by: str,
        rationale: str = "",
    ) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.create_ticket(
            ticket_type=ticket_type,
            strategy_id=strategy_id,
            target_state=target_state,
            requested_by=requested_by,
            rationale=rationale,
        )

    def create_autonomous_paper_ticket(
        self, cycle: dict[str, Any]
    ) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.create_autonomous_paper_ticket(cycle)

    def apply_autonomous_paper_promotion(
        self, ticket_or_cycle: dict[str, Any]
    ) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.apply_autonomous_paper_promotion(ticket_or_cycle)

    def approve_promotion(
        self, *, ticket_id: str, approver: str, note: str = ""
    ) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.approve_ticket(ticket_id=ticket_id, approver=approver, note=note)

    def reject_promotion(
        self, *, ticket_id: str, approver: str, note: str = ""
    ) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.reject_ticket(ticket_id=ticket_id, approver=approver, note=note)

    def apply_human_promotion(self, *, ticket_id: str) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.apply_ticket(ticket_id=ticket_id)

    def request_rollback(
        self, *, to_strategy_id: str, requested_by: str, rationale: str = ""
    ) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.request_rollback(
            to_strategy_id=to_strategy_id,
            requested_by=requested_by,
            rationale=rationale,
        )

    def promotion_status(self) -> dict[str, Any]:
        import tae_strategy_lab_promotion as promo

        return promo.promotion_status()

    def list_strategies_with_lifecycle(self) -> list[dict[str, Any]]:
        import tae_strategy_lab_promotion as promo

        state = promo.load_promotion_state(create_if_missing=True)
        life = state.get("strategies") or {}
        rows = []
        for s in self.list_strategies():
            sid = s.get("strategy_id")
            merged = dict(s)
            if sid in life:
                merged["lifecycle_state"] = life[sid].get("lifecycle_state")
                merged["promotion_domain"] = promo.PROMOTION_DOMAIN
            rows.append(merged)
        return rows

    def status(self) -> dict[str, Any]:
        reg = self.load_registry()
        sb = self.build_scoreboard(persist=False)
        research = self.load_research()
        cfg = load_parallel_paper_config()
        configured = configured_arms(cfg)
        enabled = enabled_arms(cfg)
        import tae_strategy_lab_promotion as promo

        pstat = promo.promotion_status()
        return {
            "schema": SCHEMA,
            "lab_id": reg.get("lab_id"),
            "mode": "READ_ONLY_SSOT_ORCHESTRATION",
            "git_head": git_head(),
            "registry_path": str(self.registry_path.relative_to(PROJECT_ROOT)),
            "strategies_enabled": [s.get("strategy_id") for s in self.list_strategies()],
            "reconciliation_pass": sb.get("reconciliation", {}).get("pass"),
            "research_completeness": (research.get("strategy_evolution") or {}).get(
                "completeness"
            ),
            "auto_promote": False,
            "live_mutation": False,
            "n_arm_topology": True,
            "configured_arm_ids": [a["arm_id"] for a in configured],
            "enabled_arm_ids": [a["arm_id"] for a in enabled],
            "v3_strategy_implemented": False,
            "v3_topology_stub_present": any(a.get("arm_id") == "v3" for a in configured),
            "v3_enabled": any(a.get("arm_id") == "v3" and a.get("enabled") for a in configured),
            "promotion_domain": pstat.get("promotion_domain"),
            "champion_strategy_id": pstat.get("champion_strategy_id"),
            "sprint": 4,
        }


def build_scoreboard(*, persist: bool = True) -> dict[str, Any]:
    return StrategyLabFacade().build_scoreboard(persist=persist)


def _autonomous_paper_status() -> dict[str, Any]:
    try:
        import tae_strategy_lab_promotion as promo

        state = promo.load_promotion_state(create_if_missing=False)
        return {
            **(state.get("autonomous_paper_evolution") or {}),
            "champion_strategy_id": state.get("autonomous_paper_champion_id"),
            "global_auto_promote": False,
            "live_allowed": False,
        }
    except Exception as exc:
        return {
            "enabled": False,
            "champion_strategy_id": None,
            "global_auto_promote": False,
            "live_allowed": False,
            "error": str(exc),
        }


def lab_status() -> dict[str, Any]:
    return StrategyLabFacade().status()


__all__ = [
    "StrategyLabFacade",
    "load_registry",
    "list_strategies",
    "build_scoreboard",
    "reconcile_with_parallel_books",
    "lab_status",
    "REGISTRY_PATH",
    "SCOREBOARD_PATH",
    "HEALTH_PATH",
    "EXPLANATIONS_PATH",
    "RESEARCH_SUMMARY_PATH",
    "ECONOMIC_METRICS_PATH",
]
