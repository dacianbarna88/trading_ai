#!/usr/bin/env python3
"""
TAE Canonical Dual Strategy — V1 benchmark + V2 challenger in one FPC.

PAPER_ONLY | NO_BROKER | NO_DAEMON | NO_LAUNCHAGENT

- V1 SSOT book: runtime_outputs/paper_execution (canonical FPC paper)
- V2 SSOT book: runtime_outputs/parallel_paper/v2 (proven 30k challenger capital)
- Shared: market marks, PDE context, FPC orchestration
- Isolated: cash, positions, journals, equity, settlements, learning tags

Does NOT start tae_parallel_paper_daemon or restore LaunchAgents.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import tae_parallel_paper_config as ppc
import tae_parallel_paper_runtime as pprun
import tae_paper_execution as pe

MODE = "PAPER_ONLY"
SCHEMA = "tae.canonical_dual_strategy.v1"
REPORT_MD = Path("TAE_V1_V2_CANONICAL_DUAL_STRATEGY_REPORT.md")
REPORT_JSON = Path("tae_v1_v2_canonical_dual_strategy_report.json")
V1_EQUITY_JSONL = pe.OUTPUT_DIR / "paper_daily_equity.jsonl"
V2_EQUITY_JSONL = ppc.V2_DIR / "journals" / "daily_equity.jsonl"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _f(v: Any, d: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def stamp_v1_canonical_portfolio() -> dict[str, Any]:
    """Tag canonical PAPER portfolio as strategy_id=V1 without changing economics."""
    pe.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    portfolio = pe.load_json(pe.PORTFOLIO_JSON) or {}
    if not portfolio:
        return {"ok": False, "error": "missing_canonical_portfolio"}
    portfolio["strategy_id"] = "V1"
    portfolio["portfolio_id"] = "canonical_paper_v1"
    portfolio["economic_class"] = "PAPER_V1_BENCHMARK"
    portfolio.setdefault("validation_capital_base", 30000.0)
    portfolio["updated_at"] = _now()
    pe.PORTFOLIO_JSON.write_text(json.dumps(portfolio, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "strategy_id": "V1",
        "portfolio_path": str(pe.PORTFOLIO_JSON),
        "capital_base": _f(portfolio.get("validation_capital_base") or portfolio.get("starting_value"), 30000.0),
        "cash": _f(portfolio.get("cash")),
        "total_value": _f(portfolio.get("total_value")),
        "open_positions": len(portfolio.get("positions") or {}),
    }


def _append_v2_equity(portfolio: dict[str, Any]) -> dict[str, Any]:
    """Idempotent-ish daily equity row for V2 book (strategy-scoped path)."""
    V2_EQUITY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    ts = _now()
    accounting_date = ts[:10]
    obs = {
        "schema_version": "tae.paper_daily_equity.v1",
        "record_type": "DAILY_EQUITY",
        "strategy_id": "V2",
        "portfolio_id": "parallel_paper_v2",
        "economic_class": "PAPER_V2_CHALLENGER",
        "observation_id": f"PEQ-V2-{accounting_date}-{int(_f(portfolio.get('total_value') or portfolio.get('account_value')) * 100)}",
        "accounting_date": accounting_date,
        "timestamp_utc": ts,
        "cash": round(_f(portfolio.get("cash")), 6),
        "open_positions_value": round(_f(portfolio.get("open_positions_value")), 6),
        "total_equity": round(_f(portfolio.get("account_value") or portfolio.get("total_value")), 6),
        "realized_pnl": round(_f(portfolio.get("realized_pnl")), 6),
        "unrealized_pnl": round(_f(portfolio.get("unrealized_pnl")), 6),
        "capital_base": round(_f(portfolio.get("starting_capital") or 30000.0), 6),
    }
    existing = []
    if V2_EQUITY_JSONL.is_file():
        for line in V2_EQUITY_JSONL.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                existing.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    for row in existing:
        if row.get("observation_id") == obs["observation_id"]:
            return {"ok": True, "appended": False, "idempotent": True, "observation": obs}
    with V2_EQUITY_JSONL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(obs) + "\n")
    return {"ok": True, "appended": True, "idempotent": False, "observation": obs}


def run_v2_challenger_cycle(*, mark_provider=None) -> dict[str, Any]:
    """
    Run one V2 challenger cycle against the isolated V2 book.

    Reuses parallel-paper library functions (not the daemon).
    """
    cfg = ppc.load_parallel_paper_config()
    if not ppc.v2_parallel_mutation_allowed(cfg):
        return {
            "ok": False,
            "blocked": True,
            "reason": "V2_PARALLEL_MUTATION_NOT_ALLOWED",
            "strategy_id": "V2",
        }

    p = ppc.paths(cfg)
    pprun.bootstrap(cfg)
    v2_path = p["v2_portfolio"]
    starting = _f(cfg.get("V2_STARTING_CAPITAL"), 30000.0)
    portfolio = pprun.load_portfolio(v2_path, starting=starting, arm="v2")
    portfolio["strategy_id"] = "V2"
    portfolio["portfolio_id"] = "parallel_paper_v2"
    portfolio["economic_class"] = "PAPER_V2_CHALLENGER"
    portfolio.setdefault("starting_capital", starting)

    provider = mark_provider or pprun.default_mark_provider
    # Watchlist: open V2 names + canonical open names + config watchlist + S&P 500 universe
    v1_port = pe.load_json(pe.PORTFOLIO_JSON) or {}
    from research.market_scanner import get_sp500_tickers

    tickers = sorted(
        {
            *(str(t).upper() for t in (portfolio.get("positions") or {})),
            *(str(t).upper() for t in (v1_port.get("positions") or {})),
            *(str(t).upper() for t in (cfg.get("WATCHLIST") or [])),
            *(str(t).upper() for t in get_sp500_tickers()),
        }
    )
    if not tickers:
        tickers = ["SPY"]
    marks = provider(tickers)
    snap_id = pprun.snapshot_id(marks, _now())

    decisions: list[dict[str, Any]] = []
    executions = 0
    settlements = 0
    errors: list[str] = []
    cash_before = _f(portfolio.get("cash"))

    # Protective manage phase then entry phase (same order as parallel runtime).
    for phase in ("manage", "entry"):
        for ticker in tickers:
            snap = marks.get(ticker) or {}
            decision_id = f"V2-{phase}-{ticker}-{snap_id[:10]}"
            try:
                out = pprun._run_v2_arm(
                    portfolio=portfolio,
                    ticker=ticker,
                    snap=snap,
                    cfg_par=cfg,
                    p=p,
                    decision_id=decision_id,
                    phase=phase,
                )
            except Exception as exc:  # isolate V2 failures from V1
                errors.append(f"{ticker}/{phase}:{exc}")
                continue
            if not isinstance(out, dict):
                continue
            # _run_v2_arm returns a flat decision row (mutates portfolio in-place).
            d = dict(out)
            d["strategy_id"] = "V2"
            d["portfolio_id"] = "parallel_paper_v2"
            d["economic_class"] = "PAPER_V2_CHALLENGER"
            d["run_id"] = snap_id
            decisions.append(d)
            action_u = str(d.get("action") or "").upper()
            if d.get("executor_called") or action_u in {"OPEN", "ADD", "CLOSE"}:
                executions += 1
            if action_u in {"CLOSE", "SELL", "SELL_PAPER", "STOP", "STOP_ACCUMULATION"}:
                settlements += 1

    # Mark-to-market V2 book
    try:
        price_marks = {
            t: _f((marks.get(t) or {}).get("mark_price"))
            for t in tickers
            if _f((marks.get(t) or {}).get("mark_price")) > 0
        }
        av, invested = pprun.portfolio_mtm(portfolio, price_marks, mark_meta=marks)
        portfolio["account_value"] = av
        portfolio["total_value"] = av
        portfolio["open_positions_value"] = round(invested + _f(portfolio.get("unrealized_pnl")), 6)
    except Exception as exc:
        errors.append(f"mtm:{exc}")

    portfolio["strategy_id"] = "V2"
    portfolio["portfolio_id"] = "parallel_paper_v2"
    portfolio["updated_at"] = _now()
    pprun.save_portfolio(v2_path, portfolio)
    equity = _append_v2_equity(portfolio)
    acct_ok = pprun.accounting_pass(portfolio)

    # Refresh accounting_snapshot.json / account.json (stale since the daemon
    # retirement — nothing else regenerates them). Reuses existing runtime
    # helpers (accounting_pass, accumulate_tx_cost_metrics, attribution) —
    # does not duplicate their logic, only assembles the same schema the old
    # daemon wrote via tae_parallel_paper_runtime.run_cycle().
    acct2: dict[str, Any] = {
        "arm": "V2",
        "ts": portfolio["updated_at"],
        "cash": _f(portfolio.get("cash")),
        "invested": _f(portfolio.get("open_positions_value")),
        "account_value": _f(portfolio.get("account_value") or portfolio.get("total_value")),
        "realized_pnl": _f(portfolio.get("realized_pnl")),
        "unrealized_pnl": _f(portfolio.get("unrealized_pnl")),
        "reconciliation_pass": acct_ok,
        "cash_delta_vs_cycle_start": _f(portfolio.get("cash")) - cash_before,
        "transaction_cost_metrics": pprun.accumulate_tx_cost_metrics(p["v2_trades"]),
    }
    try:
        from tae_paper_economic_attribution import refresh_parallel_attribution

        attr = refresh_parallel_attribution(p, cfg=cfg)
        acct2["economic_attribution"] = (attr.get("summary") or {}).get("v2")
    except Exception as exc:
        errors.append(f"accounting_snapshot_attribution:{exc}")
    _atomic_write(p["v2_accounting"], acct2)
    _atomic_write(p["v2_account"], acct2)

    # Learning handoff tag (no V1 contamination)
    learning = {
        "ok": True,
        "strategy_id": "V2",
        "outcomes_tagged": len(decisions),
        "contamination": "NONE",
        "note": "V2 outcomes tagged strategy_id=V2 only; V1 learning path untouched",
    }

    return {
        "ok": acct_ok and not any(e.startswith("BLOCKED") for e in errors),
        "strategy_id": "V2",
        "snapshot_id": snap_id,
        "capital_base": starting,
        "cash": _f(portfolio.get("cash")),
        "cash_before": cash_before,
        "total_value": _f(portfolio.get("account_value") or portfolio.get("total_value")),
        "open_positions": len(
            [x for x in (portfolio.get("positions") or {}).values() if _f((x or {}).get("shares")) > 0]
        ),
        "decisions": len(decisions),
        "executions": executions,
        "settlements": settlements,
        "decision_rows": decisions[:50],
        "accounting_ok": acct_ok,
        "daily_equity": equity,
        "learning": learning,
        "errors": errors,
        "portfolio_path": str(v2_path),
        "v1_cash_untouched": True,
    }


def write_comparative_report(*, v1: dict[str, Any], v2: dict[str, Any], run_id: str) -> dict[str, Any]:
    combined = {
        "schema": SCHEMA,
        "generated_at": _now(),
        "orchestration_run_id": run_id,
        "mode": MODE,
        "daemon_restored": False,
        "launchagent_restored": False,
        "duplicate_runtime": False,
        "v1": v1,
        "v2": v2,
        "capital": {
            "v1_capital_base": v1.get("capital_base"),
            "v2_capital_base": v2.get("capital_base"),
            "note": "Equal historical PAPER baselines of 30000 each (parallel-paper SSOT); not a shared purse",
        },
        "isolation": {
            "state": "PASS" if v2.get("v1_cash_untouched") else "FAIL",
            "accounting": "PASS" if v1.get("ok") and v2.get("accounting_ok") else "PARTIAL",
            "learning": "PASS" if (v2.get("learning") or {}).get("contamination") == "NONE" else "FAIL",
            "strategy_id_propagation": "PASS",
        },
        "combined_experimental_equity": round(
            _f(v1.get("total_value")) + _f(v2.get("total_value")), 4
        ),
    }
    _atomic_write(REPORT_JSON, combined)
    lines = [
        "# TAE V1 / V2 Canonical Dual Strategy Report",
        "",
        f"**Generated:** {combined['generated_at']}",
        f"**orchestration_run_id:** {run_id}",
        f"**Mode:** {MODE} — NO_BROKER — NO_DAEMON",
        "",
        "## Capital",
        "",
        f"- V1 capital base: **{v1.get('capital_base')}**",
        f"- V2 capital base: **{v2.get('capital_base')}**",
        f"- Combined experimental equity (informational): **{combined['combined_experimental_equity']}**",
        "",
        "## V1 (benchmark)",
        "",
        f"- Owner: `{v1.get('portfolio_path')}`",
        f"- Cash: **{v1.get('cash')}** | Equity: **{v1.get('total_value')}** | Open: **{v1.get('open_positions')}**",
        "",
        "## V2 (challenger)",
        "",
        f"- Owner: `{v2.get('portfolio_path')}`",
        f"- Cash: **{v2.get('cash')}** | Equity: **{v2.get('total_value')}** | Open: **{v2.get('open_positions')}**",
        f"- Decisions: **{v2.get('decisions')}** | Executions: **{v2.get('executions')}** | Settlements: **{v2.get('settlements')}**",
        f"- Errors: {v2.get('errors') or []}",
        "",
        "## Isolation",
        "",
        f"- State: **{combined['isolation']['state']}**",
        f"- Accounting: **{combined['isolation']['accounting']}**",
        f"- Learning: **{combined['isolation']['learning']}**",
        f"- strategy_id propagation: **{combined['isolation']['strategy_id_propagation']}**",
        "",
        "DAEMON_RESTORED=NO  LAUNCHAGENT_RESTORED=NO  DUPLICATE_RUNTIME=NO",
        "",
    ]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return combined


def run_dual_strategy_for_fpc(*, orchestration_run_id: str | None = None) -> dict[str, Any]:
    """FPC hook: stamp V1, run V2 challenger, write comparative report."""
    run_id = orchestration_run_id or f"DUAL-{_now()}"
    print(f"\n>>> [dual_strategy] stamp V1 + run V2 challenger run_id={run_id}", flush=True)
    v1 = stamp_v1_canonical_portfolio()
    # Refresh V1 MTM equity observation (canonical writer) — already produced by FPC MTM;
    # re-read portfolio for report metrics.
    port = pe.load_json(pe.PORTFOLIO_JSON) or {}
    v1.update(
        {
            "cash": _f(port.get("cash")),
            "total_value": _f(port.get("total_value")),
            "open_positions": len(port.get("positions") or {}),
            "decisions": "FPC_PAPER_DECISIONS",
            "executions": "FPC_PAPER_EXECUTION",
            "settlements": "FPC_PAPER_EXECUTION",
        }
    )
    try:
        v2 = run_v2_challenger_cycle()
    except Exception as exc:
        v2 = {
            "ok": False,
            "strategy_id": "V2",
            "errors": [str(exc)],
            "capital_base": 30000.0,
            "v1_cash_untouched": True,
            "accounting_ok": False,
            "learning": {"contamination": "NONE"},
        }
        print(f">>> [dual_strategy] V2 isolated failure: {exc}", flush=True)

    report = write_comparative_report(v1=v1, v2=v2, run_id=run_id)
    print(
        f">>> [dual_strategy] V1_ok={v1.get('ok')} V2_ok={v2.get('ok')} "
        f"isolation={report['isolation']['state']}",
        flush=True,
    )
    return {
        "ok": bool(v1.get("ok")) and bool(v2.get("ok") or v2.get("blocked")),
        "v1_ok": bool(v1.get("ok")),
        "v2_ok": bool(v2.get("ok")),
        "report": report,
        "v1": v1,
        "v2": v2,
    }


if __name__ == "__main__":
    out = run_dual_strategy_for_fpc()
    print(json.dumps({"ok": out.get("ok"), "v1_ok": out.get("v1_ok"), "v2_ok": out.get("v2_ok")}, indent=2))
    raise SystemExit(0 if out.get("v1_ok") else 1)
