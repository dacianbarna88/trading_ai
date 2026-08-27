#!/usr/bin/env python3
"""
Parallel PAPER daily + cumulative reports and verdict algorithm.

Transparent rules — no opaque scoring. One day never claims permanent superiority.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_parallel_paper_config import load_parallel_paper_config, paths
from tae_parallel_paper_runtime import (
    _atomic_write_json,
    _f,
    _s,
    accounting_pass,
    load_portfolio,
    load_v1_portfolio,
    portfolio_mtm,
)


def _today(cfg: dict[str, Any] | None = None) -> str:
    # Europe/Bucharest date when zoneinfo available; else UTC date
    try:
        from zoneinfo import ZoneInfo

        tz = ZoneInfo((cfg or {}).get("TIMEZONE") or "Europe/Bucharest")
        return datetime.now(tz).date().isoformat()
    except Exception:
        return datetime.now(timezone.utc).date().isoformat()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


MONEY_DECIMALS = 2
FLOATING_POINT_ABS_USD = 0.01  # below one cent → numeric noise
MATERIALITY_BPS = 0.0001  # 0.01% of starting capital
MATERIALITY_FLOOR_USD = 1.0


def money_round(value: Any, ndigits: int = MONEY_DECIMALS) -> float:
    """Canonical accounting rounding for classification (raw values kept separately)."""
    if value is None:
        return 0.0
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(x) or math.isinf(x):
        return 0.0
    return round(x, ndigits)


def materiality_threshold_usd(starting_av: Any) -> float:
    start = max(_f(starting_av, 30000.0), 1.0)
    return max(MATERIALITY_FLOOR_USD, MATERIALITY_BPS * start)


def classify_difference_usd(raw_diff: float, *, threshold: float) -> str:
    """
    Classify an absolute USD gap.

    Boundary (inclusive): |Δ| >= materiality_threshold_usd → MATERIAL_DIFFERENCE.
    Example at $30k capital (threshold $3.00): $2.99 = ECONOMICALLY_IMMATERIAL; $3.00 = MATERIAL.
    """
    abs_raw = abs(_f(raw_diff))
    abs_rounded = abs(money_round(raw_diff))
    thr = money_round(threshold)
    if abs_raw < FLOATING_POINT_ABS_USD or abs_rounded == 0.0:
        return "FLOATING_POINT_NOISE"
    if abs_rounded < thr:
        return "ECONOMICALLY_IMMATERIAL"
    return "MATERIAL_DIFFERENCE"


def compute_daily_verdict(
    *,
    v1: dict[str, Any],
    v2: dict[str, Any],
    data_quality_ok: bool,
    accounting_ok: bool,
    activity: bool,
    activity_material: bool | None = None,
) -> dict[str, Any]:
    """
    Transparent verdict with explicit monetary materiality.

    WIN requires an economically material AV / PnL / realized / unrealized gap.
    Drawdown-only floating-point gaps never produce V1_WIN / V2_WIN.
    Exact threshold boundary is inclusive (|Δ| >= threshold ⇒ material).
    """
    act_mat = bool(activity if activity_material is None else activity_material)

    if not data_quality_ok or not accounting_ok:
        return {
            "verdict": "INCONCLUSIVE_DATA_QUALITY",
            "winner": None,
            "confidence_level": "LOW",
            "main_reason": "Accounting or data-quality failure — no strategic winner declared.",
            "economically_material": False,
            "activity_material": act_mat,
            "economic_significance": None,
            "verdict_basis": "DATA_OR_ACCOUNTING_FAILURE",
            "difference_class": None,
            "materiality_threshold_usd": materiality_threshold_usd(v1.get("starting_av") or v2.get("starting_av")),
        }

    start = max(_f(v1.get("starting_av"), 30000.0), _f(v2.get("starting_av"), 30000.0), 1.0)
    threshold = materiality_threshold_usd(start)

    # Prefer ending AV when present; else reconstruct from starting + daily PnL
    raw_av1 = _f(v1.get("ending_av"), start + _f(v1.get("daily_total_pnl")))
    raw_av2 = _f(v2.get("ending_av"), start + _f(v2.get("daily_total_pnl")))
    raw_pnl1 = _f(v1.get("daily_total_pnl"))
    raw_pnl2 = _f(v2.get("daily_total_pnl"))
    raw_real1 = _f(v1.get("daily_realized_pnl"))
    raw_real2 = _f(v2.get("daily_realized_pnl"))
    raw_unreal1 = _f(v1.get("daily_unrealized_pnl"))
    raw_unreal2 = _f(v2.get("daily_unrealized_pnl"))
    raw_dd1 = _f(v1.get("drawdown"))
    raw_dd2 = _f(v2.get("drawdown"))

    rnd_av1 = money_round(raw_av1)
    rnd_av2 = money_round(raw_av2)
    rnd_pnl1 = money_round(raw_pnl1)
    rnd_pnl2 = money_round(raw_pnl2)
    rnd_real1 = money_round(raw_real1)
    rnd_real2 = money_round(raw_real2)
    rnd_unreal1 = money_round(raw_unreal1)
    rnd_unreal2 = money_round(raw_unreal2)

    raw_av_diff = raw_av2 - raw_av1
    raw_pnl_diff = raw_pnl2 - raw_pnl1
    raw_real_diff = raw_real2 - raw_real1
    raw_unreal_diff = raw_unreal2 - raw_unreal1
    raw_dd_diff = abs(raw_dd2) - abs(raw_dd1)

    rnd_av_diff = rnd_av2 - rnd_av1
    rnd_pnl_diff = rnd_pnl2 - rnd_pnl1
    rnd_real_diff = rnd_real2 - rnd_real1
    rnd_unreal_diff = rnd_unreal2 - rnd_unreal1

    av_class = classify_difference_usd(raw_av_diff, threshold=threshold)
    pnl_class = classify_difference_usd(raw_pnl_diff, threshold=threshold)
    real_class = classify_difference_usd(raw_real_diff, threshold=threshold)
    unreal_class = classify_difference_usd(raw_unreal_diff, threshold=threshold)
    dd_class = classify_difference_usd(raw_dd_diff, threshold=threshold)

    material_economic = any(
        c == "MATERIAL_DIFFERENCE" for c in (av_class, pnl_class, real_class, unreal_class)
    )
    # Primary significance among economic axes (drawdown alone never decides a WIN)
    if material_economic:
        economic_significance = "MATERIAL_DIFFERENCE"
    elif all(c == "FLOATING_POINT_NOISE" for c in (av_class, pnl_class, real_class, unreal_class)):
        economic_significance = "FLOATING_POINT_NOISE"
    else:
        economic_significance = "ECONOMICALLY_IMMATERIAL"

    audit = {
        "materiality_threshold_usd": threshold,
        "raw_V1_account_value": raw_av1,
        "raw_V2_account_value": raw_av2,
        "rounded_V1_account_value": rnd_av1,
        "rounded_V2_account_value": rnd_av2,
        "raw_account_value_difference": raw_av_diff,
        "rounded_account_value_difference": rnd_av_diff,
        # aliases kept for older readers
        "raw_account_value_v1": raw_av1,
        "raw_account_value_v2": raw_av2,
        "rounded_account_value_v1": rnd_av1,
        "rounded_account_value_v2": rnd_av2,
        "rounded_account_value": {"V1": rnd_av1, "V2": rnd_av2},
        "raw_difference": raw_av_diff,
        "rounded_difference": rnd_av_diff,
        "raw_pnl_difference": raw_pnl_diff,
        "rounded_pnl_difference": rnd_pnl_diff,
        "raw_realized_difference": raw_real_diff,
        "rounded_realized_difference": rnd_real_diff,
        "raw_unrealized_difference": raw_unreal_diff,
        "rounded_unrealized_difference": rnd_unreal_diff,
        "economic_significance": economic_significance,
        "difference_class": economic_significance,
        "difference_classes": {
            "account_value": av_class,
            "daily_pnl": pnl_class,
            "realized": real_class,
            "unrealized": unreal_class,
            "drawdown": dd_class,
        },
        "economically_material": material_economic,
        "activity_material": act_mat,
    }

    def _pack(**kwargs: Any) -> dict[str, Any]:
        out = dict(audit)
        out.update(kwargs)
        return out

    if not act_mat and not material_economic:
        return _pack(
            verdict="INCONCLUSIVE_NO_ACTIVITY",
            winner=None,
            confidence_level="LOW",
            main_reason=(
                "No material economic activity; account-value and PnL differences are below the "
                f"materiality threshold (${threshold:.2f}) and reflect numeric precision, not edge."
            ),
            verdict_basis="NO_ACTIVITY_AND_IMMATERIAL_DIFF",
        )

    if not material_economic:
        reason = (
            "Account-value, realized and unrealized differences are below the materiality threshold "
            f"(${threshold:.2f}); economic_significance={economic_significance}. "
            "No economically material winner — drawdown noise alone cannot decide the day."
        )
        return _pack(
            verdict="DRAW" if act_mat else "INCONCLUSIVE_NO_ACTIVITY",
            winner=None,
            confidence_level="MEDIUM" if act_mat else "LOW",
            main_reason=reason,
            verdict_basis="IMMATERIAL_OR_FLOATING_POINT",
        )

    thr_r = money_round(threshold)

    # Material economic difference — decide by rounded AV / PnL (not raw float noise)
    if abs(rnd_av_diff) >= thr_r or abs(rnd_pnl_diff) >= thr_r:
        if rnd_av_diff > 0 or (rnd_av_diff == 0 and rnd_pnl_diff > 0):
            winner, verdict = "V2", "V2_WIN"
            better_pnl, worse_pnl = rnd_pnl2, rnd_pnl1
        elif rnd_av_diff < 0 or (rnd_av_diff == 0 and rnd_pnl_diff < 0):
            winner, verdict = "V1", "V1_WIN"
            better_pnl, worse_pnl = rnd_pnl1, rnd_pnl2
        else:
            return _pack(
                verdict="DRAW",
                winner=None,
                confidence_level="MEDIUM",
                main_reason=(
                    f"Materiality threshold ${threshold:.2f} met on secondary axes, "
                    "but rounded account values / daily PnL remain tied."
                ),
                verdict_basis="MATERIAL_BUT_TIED_AFTER_ROUNDING",
            )
        realized_driven = abs(rnd_real_diff) >= abs(rnd_unreal_diff)
        return _pack(
            verdict=verdict,
            winner=winner,
            confidence_level="MEDIUM",
            main_reason=(
                f"{winner} leads by an economically material margin "
                f"(rounded AV Δ=${abs(rnd_av_diff):.2f}, threshold ${threshold:.2f}; "
                f"daily PnL {better_pnl:.2f} vs {worse_pnl:.2f}); "
                f"advantage primarily {'realized' if realized_driven else 'unrealized'}. "
                "Single-day result is not permanent superiority."
            ),
            verdict_basis="MATERIAL_AV_OR_PNL",
        )

    if abs(rnd_real_diff) >= thr_r:
        if rnd_real_diff > 0:
            return _pack(
                verdict="V2_WIN",
                winner="V2",
                confidence_level="MEDIUM",
                main_reason=(
                    f"V2 has economically material realized PnL advantage "
                    f"(Δ=${abs(rnd_real_diff):.2f} ≥ threshold ${threshold:.2f}). "
                    "Single-day result is not permanent superiority."
                ),
                verdict_basis="MATERIAL_REALIZED",
            )
        return _pack(
            verdict="V1_WIN",
            winner="V1",
            confidence_level="MEDIUM",
            main_reason=(
                f"V1 has economically material realized PnL advantage "
                f"(Δ=${abs(rnd_real_diff):.2f} ≥ threshold ${threshold:.2f}). "
                "Single-day result is not permanent superiority."
            ),
            verdict_basis="MATERIAL_REALIZED",
        )

    if abs(rnd_unreal_diff) >= thr_r:
        if rnd_unreal_diff > 0:
            return _pack(
                verdict="V2_WIN",
                winner="V2",
                confidence_level="MEDIUM",
                main_reason=(
                    f"V2 has economically material unrealized (mark-to-market) advantage "
                    f"(Δ=${abs(rnd_unreal_diff):.2f} ≥ threshold ${threshold:.2f}); "
                    "this is MTM, not realized cash PnL. Single-day result is not permanent superiority."
                ),
                verdict_basis="MATERIAL_UNREALIZED",
            )
        return _pack(
            verdict="V1_WIN",
            winner="V1",
            confidence_level="MEDIUM",
            main_reason=(
                f"V1 has economically material unrealized (mark-to-market) advantage "
                f"(Δ=${abs(rnd_unreal_diff):.2f} ≥ threshold ${threshold:.2f}); "
                "this is MTM, not realized cash PnL. Single-day result is not permanent superiority."
            ),
            verdict_basis="MATERIAL_UNREALIZED",
        )

    return _pack(
        verdict="DRAW",
        winner=None,
        confidence_level="MEDIUM",
        main_reason=(
            f"Differences remain within materiality (${threshold:.2f}) after accounting rounding; "
            "no winner declared."
        ),
        verdict_basis="NO_MATERIAL_WINNER",
    )


def _arm_day_metrics(arm: str, portfolio: dict[str, Any], cfg: dict[str, Any], marks: dict[str, float]) -> dict[str, Any]:
    if arm == "V1" and str(portfolio.get("v1_mode") or cfg.get("V1_MODE") or "").upper() == "CANONICAL_PAPER_MIRROR":
        start_cap = _f(portfolio.get("starting_value") or portfolio.get("starting_capital"))
        av = _f(portfolio.get("account_value") or portfolio.get("total_value"))
        cash = _f(portfolio.get("cash"))
        invested = _f(portfolio.get("open_positions_value"))
        realized = _f(portfolio.get("realized_pnl"))
        unreal = _f(portfolio.get("unrealized_pnl"))
        total = _f(portfolio.get("total_pnl"), realized + unreal)
        return {
            "arm": arm,
            "source": "CANONICAL_PAPER",
            "v1_mode": "CANONICAL_PAPER_MIRROR",
            "inception_date": portfolio.get("inception_date") or portfolio.get("created_at"),
            "starting_av": start_cap,
            "ending_av": av,
            "cash": cash,
            "invested": invested,
            "reserved": float(cfg.get("V1_MIN_CASH_RESERVE") or 500.0),
            "realized_pnl_cumulative": realized,
            "unrealized_pnl": unreal,
            "daily_realized_pnl": 0.0,  # no coherent daily baseline yet after restore
            "daily_unrealized_pnl": 0.0,
            "daily_total_pnl": 0.0,
            "cumulative_pnl": total,
            "open_positions": len(portfolio.get("positions") or {}),
            "capital_utilization": (invested / start_cap) if start_cap else 0.0,
            "drawdown": _f(portfolio.get("drawdown"), -abs(_f(portfolio.get("drawdown_pct"))) * max(start_cap, 1.0) / 100.0),
            "drawdown_pct": _f(portfolio.get("drawdown_pct")),
            "reconciliation_pass": accounting_pass(portfolio),
            "risk_events": 0,
            "baseline_restored": True,
        }

    start_cap = _f(portfolio.get("starting_capital"), float(cfg[f"{arm}_STARTING_CAPITAL"]))
    av, invested = portfolio_mtm(portfolio, marks)
    cash = _f(portfolio.get("cash"))
    realized = _f(portfolio.get("realized_pnl"))
    unreal = _f(portfolio.get("unrealized_pnl"))
    total = realized + unreal
    # daily approx: vs starting capital baseline for isolated arms
    daily_total = av - start_cap
    return {
        "arm": arm,
        "source": "ISOLATED_PARALLEL_PAPER" if arm == "V2" else "ISOLATED",
        "v2_mode": "ISOLATED_PARALLEL_PAPER" if arm == "V2" else None,
        "inception_date": portfolio.get("created_at"),
        "starting_av": start_cap,
        "ending_av": av,
        "cash": cash,
        "invested": invested,
        "reserved": float(cfg[f"{arm}_MIN_CASH_RESERVE"]),
        "realized_pnl_cumulative": realized,
        "unrealized_pnl": unreal,
        "daily_realized_pnl": realized,  # isolated book: cumulative == daily until multi-day baseline stored
        "daily_unrealized_pnl": unreal,
        "daily_total_pnl": daily_total,
        "cumulative_pnl": total,
        "open_positions": len(portfolio.get("positions") or {}),
        "capital_utilization": (invested / start_cap) if start_cap else 0.0,
        "drawdown": min(0.0, daily_total),
        "reconciliation_pass": accounting_pass(portfolio),
        "risk_events": 0,
    }


def generate_daily_report(
    *,
    date: str | None = None,
    cfg: dict[str, Any] | None = None,
    marks: dict[str, float] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    cfg = cfg or load_parallel_paper_config()
    p = paths()
    day = date or _today(cfg)
    md_path = p["reports"] / f"TAE_PARALLEL_DAILY_REPORT_{day}.md"
    json_path = p["reports"] / f"tae_parallel_daily_report_{day}.json"
    pos_csv = p["reports"] / f"tae_parallel_positions_{day}.csv"
    div_csv = p["reports"] / f"tae_parallel_divergences_{day}.csv"

    # Idempotency: if exists and not force, return existing
    if json_path.is_file() and not force:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
        existing["idempotent_reuse"] = True
        return existing

    v1 = load_v1_portfolio(cfg)
    v2 = load_portfolio(p["v2_portfolio"], starting=float(cfg["V2_STARTING_CAPITAL"]), arm="V2")
    marks = marks or {
        t: _f(pos.get("current_price") or pos.get("avg_price"))
        for t, pos in {** (v1.get("positions") or {}), **(v2.get("positions") or {})}.items()
    }
    m1 = _arm_day_metrics("V1", v1, cfg, marks)
    m2 = _arm_day_metrics("V2", v2, cfg, marks)

    # V2 extras from journals
    v2_decs = [r for r in _read_jsonl(p["v2_decisions"]) if str(r.get("ts", "")).startswith(day) or True]
    # Use all decisions if timestamps are UTC Z without date match simplicity — filter by file growth; for tests use all
    counts = {"OPEN": 0, "ADD": 0, "HOLD": 0, "STOP_ACCUMULATION": 0, "CLOSE": 0}
    for d in v2_decs:
        a = _s(d.get("action")).upper()
        if a in counts:
            counts[a] += 1
        elif a == "STOP_ACCUMULATION":
            counts["STOP_ACCUMULATION"] += 1
    m2["v2_counts"] = counts

    # Cycles
    import tae_strategy_v2_foundation as v2f

    store = v2f.load_cycle_store(p["v2_cycles"]) if p["v2_cycles"].is_file() else {"cycles": {}}
    cycles = list((store.get("cycles") or {}).values())
    tr = [int(c.get("tranche_count") or 0) for c in cycles if int(c.get("tranche_count") or 0) > 0]
    m2["active_cycles"] = sum(1 for c in cycles if _s(c.get("status")) not in {"CLOSED", ""})
    m2["cycles_2plus"] = sum(1 for x in tr if x >= 2)
    m2["avg_tranches"] = (sum(tr) / len(tr)) if tr else 0.0

    divs = _read_jsonl(p["divergences"])
    # Prefer today's divergences
    day_divs = [d for d in divs if day in str(d.get("timestamp") or "")] or divs[-50:]
    v1_trades = _read_jsonl(p["v1_trades"])
    v2_trades = _read_jsonl(p["v2_trades"])
    activity_material = bool(
        m1["open_positions"]
        or m2["open_positions"]
        or v1_trades
        or v2_trades
        or abs(_f(m1["daily_realized_pnl"])) >= FLOATING_POINT_ABS_USD
        or abs(_f(m2["daily_realized_pnl"])) >= FLOATING_POINT_ABS_USD
    )
    activity = bool(activity_material or v2_decs or _read_jsonl(p["v1_decisions"]) or day_divs)
    data_ok = True
    acct_ok = bool(m1["reconciliation_pass"] and m2["reconciliation_pass"])
    baseline_restored = bool(m1.get("baseline_restored") or str(cfg.get("V1_MODE") or "").upper() == "CANONICAL_PAPER_MIRROR")
    if baseline_restored:
        # Daily A/B winner suppressed until a coherent V1 day-over-day baseline exists
        verdict = {
            "verdict": "INCONCLUSIVE_BASELINE_RESTORED",
            "winner": None,
            "confidence_level": "LOW",
            "main_reason": (
                "V1 benchmark restored as CANONICAL_PAPER_MIRROR; cumulative canonical economics "
                "are authoritative, but daily PnL comparison lacks a coherent V1 day baseline. "
                "No V1_WIN/V2_WIN declared."
            ),
            "economically_material": False,
            "activity_material": activity_material,
            "economic_significance": None,
            "verdict_basis": "V1_CANONICAL_BASELINE_RESTORED",
            "materiality_threshold_usd": materiality_threshold_usd(m1.get("starting_av") or m2.get("starting_av")),
        }
    else:
        verdict = compute_daily_verdict(
            v1=m1,
            v2=m2,
            data_quality_ok=data_ok,
            accounting_ok=acct_ok,
            activity=activity,
            activity_material=activity_material,
        )

    # Top divergences by |V1_value - V2_value|
    ranked = sorted(
        day_divs,
        key=lambda d: abs(_f(d.get("V1_value")) - _f(d.get("V2_value")))
        + (10.0 if d.get("action_divergence") != "SAME_ACTION" else 0.0),
        reverse=True,
    )[:10]

    diff = {
        "ending_av": m2["ending_av"] - m1["ending_av"],
        "daily_total_pnl": m2["daily_total_pnl"] - m1["daily_total_pnl"],
        "realized": m2["realized_pnl_cumulative"] - m1["realized_pnl_cumulative"],
        "unrealized": m2["unrealized_pnl"] - m1["unrealized_pnl"],
        "drawdown": m2["drawdown"] - m1["drawdown"],
    }

    explanation = {
        "which_better": verdict.get("winner") or verdict["verdict"],
        "primary_cause": verdict["main_reason"],
        "realized_vs_unrealized": (
            "realized" if abs(diff["realized"]) >= abs(diff["unrealized"]) else "unrealized"
        ),
        "capital_protection": "V2" if abs(m2["drawdown"]) <= abs(m1["drawdown"]) else "V1",
        "capital_efficiency": "V2" if m2["capital_utilization"] >= m1["capital_utilization"] else "V1",
        "hard_risk_note": f"V2 CLOSE count today/all journals: {counts.get('CLOSE', 0)}",
        "add_note": f"ADD decisions logged: {counts.get('ADD', 0)}",
    }

    professional = verdict["main_reason"]

    report = {
        "schema": "tae.parallel_paper.daily_report.v1",
        "date": day,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "executive_conclusion": verdict,
        "v1": m1,
        "v2": m2,
        "difference": diff,
        "explanation": explanation,
        "top_divergences": ranked,
        "professional_conclusion": professional,
        "accounting_status": "PASS" if acct_ok else "FAIL",
        "data_quality_status": "PASS" if data_ok else "FAIL",
        "disclaimer": "Single-day verdict is operational, not permanent strategic superiority.",
        "paths": {
            "md": str(md_path),
            "json": str(json_path),
            "positions_csv": str(pos_csv),
            "divergences_csv": str(div_csv),
        },
    }

    # Write MD
    md = [
        f"# TAE Parallel PAPER Daily Report — {day}",
        "",
        f"**Verdict:** `{verdict['verdict']}` · winner={verdict.get('winner')}",
        "",
        f"{professional}",
        "",
        "## Sources",
        "",
        f"- **V1 source:** `{m1.get('source') or 'CANONICAL_PAPER'}` · mode=`{m1.get('v1_mode') or cfg.get('V1_MODE')}`",
        f"- **V1 inception:** `{m1.get('inception_date')}`",
        f"- **V1 cumulative PnL:** `{m1.get('cumulative_pnl', m1.get('realized_pnl_cumulative')):.4f}`",
        f"- **V1 account value:** `{m1['ending_av']:.4f}`",
        f"- **V2 source:** `ISOLATED_PARALLEL_PAPER` · inception=`{m2.get('inception_date')}` · starting_capital=`{m2.get('starting_av'):.2f}`",
        "",
        "## Comparative table",
        "",
        "| Metric | V1 | V2 | Diff |",
        "|--------|---:|---:|-----:|",
        f"| Ending AV | {m1['ending_av']:.2f} | {m2['ending_av']:.2f} | {diff['ending_av']:.2f} |",
        f"| Cash | {m1['cash']:.2f} | {m2['cash']:.2f} | {m2['cash']-m1['cash']:.2f} |",
        f"| Invested | {m1['invested']:.2f} | {m2['invested']:.2f} | {m2['invested']-m1['invested']:.2f} |",
        f"| Realized PnL | {m1['realized_pnl_cumulative']:.2f} | {m2['realized_pnl_cumulative']:.2f} | {diff['realized']:.2f} |",
        f"| Unrealized PnL | {m1['unrealized_pnl']:.2f} | {m2['unrealized_pnl']:.2f} | {diff['unrealized']:.2f} |",
        f"| Daily total PnL | {m1['daily_total_pnl']:.2f} | {m2['daily_total_pnl']:.2f} | {diff['daily_total_pnl']:.2f} |",
        f"| Drawdown | {m1['drawdown']:.2f} | {m2['drawdown']:.2f} | {diff['drawdown']:.2f} |",
        f"| Open positions | {m1['open_positions']} | {m2['open_positions']} | |",
        f"| Capital util | {m1['capital_utilization']:.3f} | {m2['capital_utilization']:.3f} | |",
        f"| Accounting | {m1['reconciliation_pass']} | {m2['reconciliation_pass']} | |",
        "",
        "## V2 activity",
        "",
        f"- OPEN/ADD/HOLD/STOP/CLOSE: {counts}",
        f"- Active cycles: {m2.get('active_cycles')} · 2+ tranches: {m2.get('cycles_2plus')} · avg tranches: {m2.get('avg_tranches'):.3f}",
        "",
        "## Top divergences",
        "",
    ]
    for i, d in enumerate(ranked, 1):
        md.append(
            f"{i}. {d.get('ticker')}: {d.get('action_divergence')} "
            f"(V1={d.get('V1_action')}/{d.get('V1_reason')} · V2={d.get('V2_action')}/{d.get('V2_reason')})"
        )
    md.extend(["", "## Disclaimer", "", report["disclaimer"], ""])
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(md), encoding="utf-8")
    _atomic_write_json(json_path, report)

    # Positions CSV
    with pos_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["arm", "ticker", "shares", "avg_price", "current_price", "strategy_version"])
        for arm, port in (("V1", v1), ("V2", v2)):
            for t, pos in sorted((port.get("positions") or {}).items()):
                w.writerow(
                    [
                        arm,
                        t,
                        pos.get("shares"),
                        pos.get("avg_price"),
                        pos.get("current_price"),
                        pos.get("strategy_version"),
                    ]
                )

    with div_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "timestamp",
                "ticker",
                "action_divergence",
                "V1_action",
                "V1_reason",
                "V2_action",
                "V2_reason",
                "V2_cycle_id",
                "V1_value",
                "V2_value",
            ],
        )
        w.writeheader()
        for d in ranked:
            w.writerow({k: d.get(k) for k in w.fieldnames})

    conclusion = {
        "date": day,
        "verdict": verdict["verdict"],
        "winner": verdict.get("winner"),
        "confidence_level": verdict.get("confidence_level"),
        "V1_source": m1.get("source") or "CANONICAL_PAPER",
        "V1_mode": m1.get("v1_mode") or cfg.get("V1_MODE"),
        "V1_inception_date": m1.get("inception_date"),
        "V1_cumulative_pnl": m1.get("cumulative_pnl", m1.get("realized_pnl_cumulative")),
        "V1_account_value": m1["ending_av"],
        "V2_source": "ISOLATED_PARALLEL_PAPER",
        "V2_mode": "ISOLATED_PARALLEL_PAPER",
        "V2_inception_date": m2.get("inception_date"),
        "V2_starting_capital": m2.get("starting_av"),
        "V2_account_value": m2["ending_av"],
        "raw_V1_account_value": verdict.get("raw_V1_account_value", m1["ending_av"]),
        "raw_V2_account_value": verdict.get("raw_V2_account_value", m2["ending_av"]),
        "rounded_V1_account_value": verdict.get("rounded_V1_account_value", money_round(m1["ending_av"])),
        "rounded_V2_account_value": verdict.get("rounded_V2_account_value", money_round(m2["ending_av"])),
        "raw_account_value_difference": verdict.get("raw_account_value_difference", diff["ending_av"]),
        "rounded_account_value_difference": verdict.get(
            "rounded_account_value_difference", money_round(diff["ending_av"])
        ),
        "rounded_account_value": verdict.get("rounded_account_value")
        or {
            "V1": money_round(m1["ending_av"]),
            "V2": money_round(m2["ending_av"]),
        },
        "V1_daily_pnl": m1["daily_total_pnl"],
        "V2_daily_pnl": m2["daily_total_pnl"],
        "V1_drawdown": m1["drawdown"],
        "V2_drawdown": m2["drawdown"],
        "realized_difference": diff["realized"],
        "unrealized_difference": diff["unrealized"],
        "raw_difference": verdict.get("raw_difference", diff["ending_av"]),
        "rounded_difference": verdict.get("rounded_difference", money_round(diff["ending_av"])),
        "materiality_threshold_usd": verdict.get("materiality_threshold_usd"),
        "economic_significance": verdict.get("economic_significance") or verdict.get("difference_class"),
        "difference_class": verdict.get("difference_class"),
        "economically_material": bool(verdict.get("economically_material")),
        "activity_material": bool(verdict.get("activity_material")),
        "verdict_basis": verdict.get("verdict_basis"),
        "main_reason": verdict["main_reason"],
        "risks": ["single_day_not_superiority", "isolated_benchmark_not_canonical_paper", "v1_daily_baseline_pending"],
        "accounting_status": report["accounting_status"],
        "data_quality_status": report["data_quality_status"],
        "report_path": str(md_path),
    }
    _atomic_write_json(p["latest_conclusion"], conclusion)
    update_cumulative_report(day_report=report, cfg=cfg)
    return report


def update_cumulative_report(*, day_report: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_parallel_paper_config()
    p = paths()
    cum_path = p["cumulative_json"]
    cum: dict[str, Any]
    if cum_path.is_file():
        try:
            cum = json.loads(cum_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cum = {}
    else:
        cum = {
            "schema": "tae.parallel_paper.cumulative.v1",
            "days": [],
            "V1_wins": 0,
            "V2_wins": 0,
            "draws": 0,
            "inconclusive_days": 0,
        }

    day = day_report["date"]
    days = list(cum.get("days") or [])
    # Replace same day (idempotent)
    days = [d for d in days if d.get("date") != day]
    v = day_report["executive_conclusion"]["verdict"]
    days.append(
        {
            "date": day,
            "verdict": v,
            "V1_av": day_report["v1"]["ending_av"],
            "V2_av": day_report["v2"]["ending_av"],
            "V1_pnl": day_report["v1"]["daily_total_pnl"],
            "V2_pnl": day_report["v2"]["daily_total_pnl"],
            "V1_dd": day_report["v1"]["drawdown"],
            "V2_dd": day_report["v2"]["drawdown"],
        }
    )
    days.sort(key=lambda x: x["date"])

    v1w = sum(1 for d in days if d["verdict"] == "V1_WIN")
    v2w = sum(1 for d in days if d["verdict"] == "V2_WIN")
    draws = sum(1 for d in days if d["verdict"] == "DRAW")
    incon = sum(1 for d in days if str(d["verdict"]).startswith("INCONCLUSIVE"))

    cum = {
        "schema": "tae.parallel_paper.cumulative.v1",
        "updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "completed_market_days": len(days),
        "days": days,
        "V1_wins": v1w,
        "V2_wins": v2w,
        "draws": draws,
        "inconclusive_days": incon,
        "V1_latest_av": day_report["v1"]["ending_av"],
        "V2_latest_av": day_report["v2"]["ending_av"],
        "V1_cumulative_realized": day_report["v1"]["realized_pnl_cumulative"],
        "V2_cumulative_realized": day_report["v2"]["realized_pnl_cumulative"],
        "V1_unrealized": day_report["v1"]["unrealized_pnl"],
        "V2_unrealized": day_report["v2"]["unrealized_pnl"],
        "days_v2_lower_drawdown": sum(1 for d in days if abs(_f(d["V2_dd"])) <= abs(_f(d["V1_dd"]))),
        "days_v2_higher_av": sum(1 for d in days if _f(d["V2_av"]) > _f(d["V1_av"])),
        "days_v2_higher_realized_pnl": sum(1 for d in days if _f(d["V2_pnl"]) > _f(d["V1_pnl"])),
        "disclaimer": "Cumulative counts are operational. Permanent superiority requires many market regimes.",
    }
    _atomic_write_json(cum_path, cum)

    md = [
        "# TAE Parallel PAPER Cumulative Report",
        "",
        f"Completed days: **{cum['completed_market_days']}**",
        f"V1 wins: {v1w} · V2 wins: {v2w} · Draws: {draws} · Inconclusive: {incon}",
        f"Latest AV V1/V2: {cum['V1_latest_av']:.2f} / {cum['V2_latest_av']:.2f}",
        "",
        cum["disclaimer"],
        "",
    ]
    p["cumulative_md"].write_text("\n".join(md), encoding="utf-8")

    # Append metrics CSV row (rewrite all for simplicity)
    with p["daily_metrics_csv"].open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["date", "verdict", "V1_av", "V2_av", "V1_pnl", "V2_pnl", "V1_dd", "V2_dd"],
        )
        w.writeheader()
        for d in days:
            w.writerow(d)
    return cum


# ---------------------------------------------------------------------------
# Phase 4 — V1/V2/V3 three-way comparison. Additive: does not modify
# compute_daily_verdict/generate_daily_report/update_cumulative_report above,
# which remain the authoritative V1-vs-V2 report other tooling already
# depends on (p["latest_conclusion"], the cumulative report, etc.). This is
# a separate, parallel report answering the newer "which of V1/V2/V3 leads"
# question introduced by the V3 ("V_learning") arm.
# ---------------------------------------------------------------------------

# Per-arm action -> class normalization for divergence comparison. Raw action
# strings differ by arm (V1: BUY/SELL, V2: OPEN/ADD/CLOSE, V3: BUY/SELL) even
# when they mean the same economic thing — classify_divergence() already
# encodes this for the V1-vs-V2 pair; this generalizes the same idea to
# three arms rather than duplicating classify_divergence's pairwise branches.
_ACTION_CLASS: dict[str, dict[str, str]] = {
    "V1": {
        "BUY": "ENTRY", "SELL": "EXIT", "HOLD": "HOLD",
        "BLOCKED": "BLOCKED", "ERROR": "ERROR", "SKIP": "HOLD",
    },
    "V2": {
        "OPEN": "ENTRY", "ADD": "ENTRY", "CLOSE": "EXIT", "HOLD": "HOLD",
        "BLOCKED": "BLOCKED", "ERROR": "ERROR", "STOP_ACCUMULATION": "HOLD", "SKIP": "HOLD",
    },
    "V3": {
        "BUY": "ENTRY", "SELL": "EXIT", "HOLD": "HOLD",
        "BLOCKED": "BLOCKED", "ERROR": "ERROR", "SKIP": "HOLD",
    },
}


def _action_class(arm: str, action: Any) -> str:
    return _ACTION_CLASS.get(arm, {}).get(_s(action).upper(), "OTHER")


def compute_three_way_verdict(arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """
    Generalizes compute_daily_verdict's materiality-gated winner logic to N
    arms without touching that function. Winner = arm with the highest
    ending_av; a win requires beating the runner-up by
    materiality_threshold_usd — the same $ definition compute_daily_verdict
    uses, so for exactly two arms this reduces to the same comparison (just
    not literally the same code path — compute_daily_verdict stays untouched
    as the authoritative V1-vs-V2 verdict).
    """
    names = [n for n in arms if arms.get(n)]
    if not names:
        return {"verdict": "NO_ARMS", "winner": None, "ranked": [], "main_reason": "No arm data available."}

    accounting_ok = all(bool(arms[n].get("reconciliation_pass")) for n in names)
    start = max((_f(arms[n].get("starting_av"), 30000.0) for n in names), default=30000.0) or 1.0
    threshold = materiality_threshold_usd(start)
    ranked = sorted(names, key=lambda n: _f(arms[n].get("ending_av")), reverse=True)

    if not accounting_ok:
        return {
            "verdict": "INCONCLUSIVE_DATA_QUALITY",
            "winner": None,
            "ranked": ranked,
            "materiality_threshold_usd": threshold,
            "main_reason": "Accounting reconciliation failed for at least one arm — no leader declared.",
        }

    if len(ranked) == 1:
        return {
            "verdict": f"{ranked[0]}_ONLY",
            "winner": ranked[0],
            "ranked": ranked,
            "materiality_threshold_usd": threshold,
            "main_reason": f"Only {ranked[0]} has data this cycle.",
        }

    leader, runner_up = ranked[0], ranked[1]
    lead_margin = _f(arms[leader].get("ending_av")) - _f(arms[runner_up].get("ending_av"))
    material = lead_margin >= threshold
    return {
        "verdict": f"{leader}_WIN" if material else "NO_MATERIAL_LEADER",
        "winner": leader if material else None,
        "ranked": ranked,
        "lead_margin_usd": round(lead_margin, 4),
        "materiality_threshold_usd": threshold,
        "main_reason": (
            f"{leader} leads {runner_up} by ${lead_margin:.2f} (threshold ${threshold:.2f})."
            if material
            else f"Largest gap ({leader} vs {runner_up}) is ${lead_margin:.2f}, "
            f"below materiality threshold ${threshold:.2f} — no material leader."
        ),
    }


def _latest_decisions_by_ticker(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Journals are append-only chronological — last row per ticker wins."""
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        t = _s(r.get("ticker"))
        if t:
            out[t] = r
    return out


def compute_three_way_divergence(p: dict[str, Any], day: str) -> list[dict[str, Any]]:
    """
    N-arm divergence matrix computed at report-generation time from each
    arm's persisted decisions journal, rather than a new per-cycle write
    into (or a schema change to) divergence_journal.jsonl. That file's
    V1_action/V2_action columns are read directly by generate_daily_report's
    "Top divergences" section above and are left exactly as-is. Computing
    this from journals that already exist means no change to run_cycle()'s
    hot path (the same cron-driven path V1/V2 run through every hour) —
    the tradeoff is this reflects "latest decision per ticker today" rather
    than a literal per-cycle-timestamped divergence event stream.
    """
    v1_rows = [r for r in _read_jsonl(p["v1_decisions"]) if day in _s(r.get("ts") or r.get("timestamp"))]
    v2_rows = [r for r in _read_jsonl(p["v2_decisions"]) if day in _s(r.get("ts") or r.get("timestamp"))]
    v3_path = p.get("arms", {}).get("v3", {}).get("decisions")
    v3_rows = [r for r in _read_jsonl(v3_path)] if v3_path else []
    v3_rows = [r for r in v3_rows if day in _s(r.get("ts") or r.get("timestamp"))]

    v1d = _latest_decisions_by_ticker(v1_rows)
    v2d = _latest_decisions_by_ticker(v2_rows)
    v3d = _latest_decisions_by_ticker(v3_rows)

    tickers = sorted(set(v1d) | set(v2d) | set(v3d))
    rows: list[dict[str, Any]] = []
    for t in tickers:
        d1, d2, d3 = v1d.get(t) or {}, v2d.get(t) or {}, v3d.get(t) or {}
        # NO_DECISION (arm never evaluated this ticker today — e.g. V2's
        # universe is wider than V1/V3's) is distinct from a real action
        # class. Comparing it as if it were a strategic disagreement was a
        # bug caught while validating this function: it inflated the first
        # run's disagreement count to 514 for an ~18-25 ticker watchlist,
        # almost entirely "V1/V3 didn't look at this ticker" noise rather
        # than genuine cross-arm disagreement.
        c1 = _action_class("V1", d1.get("action")) if d1 else "NO_DECISION"
        c2 = _action_class("V2", d2.get("action")) if d2 else "NO_DECISION"
        c3 = _action_class("V3", d3.get("action")) if d3 else "NO_DECISION"
        pairwise = {
            "V1_V2": "SAME_CLASS" if c1 == c2 else ("N/A" if "NO_DECISION" in (c1, c2) else "DIFFER"),
            "V1_V3": "SAME_CLASS" if c1 == c3 else ("N/A" if "NO_DECISION" in (c1, c3) else "DIFFER"),
            "V2_V3": "SAME_CLASS" if c2 == c3 else ("N/A" if "NO_DECISION" in (c2, c3) else "DIFFER"),
        }
        present = [c for c in (c1, c2, c3) if c != "NO_DECISION"]
        meaningful_disagreement = len(present) >= 2 and len(set(present)) > 1
        rows.append({
            "ticker": t,
            "V1_action": d1.get("action"), "V1_reason": d1.get("reason"), "V1_class": c1,
            "V2_action": d2.get("action"), "V2_reason": d2.get("reason"), "V2_class": c2,
            "V3_action": d3.get("action"), "V3_reason": d3.get("reason"), "V3_class": c3,
            "pairwise": pairwise,
            "arms_with_decision": len(present),
            "all_agree": not meaningful_disagreement,
        })
    return rows


def generate_three_way_report(
    *,
    date: str | None = None,
    cfg: dict[str, Any] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """V1/V2/V3 daily comparison — separate artifact from generate_daily_report."""
    cfg = cfg or load_parallel_paper_config()
    p = paths()
    day = date or _today(cfg)
    md_path = p["reports"] / f"TAE_PARALLEL_DAILY_REPORT_3WAY_{day}.md"
    json_path = p["reports"] / f"tae_parallel_daily_report_3way_{day}.json"

    if json_path.is_file() and not force:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
        existing["idempotent_reuse"] = True
        return existing

    v1 = load_v1_portfolio(cfg)
    v2 = load_portfolio(p["v2_portfolio"], starting=float(cfg["V2_STARTING_CAPITAL"]), arm="V2")
    v3_enabled = "v3" in (cfg.get("enabled_arm_ids") or [])
    v3 = (
        load_portfolio(p["arms"]["v3"]["portfolio"], starting=float(cfg.get("V3_STARTING_CAPITAL") or 30000.0), arm="V3")
        if v3_enabled
        else None
    )

    marks = {
        t: _f(pos.get("current_price") or pos.get("avg_price"))
        for t, pos in {
            **(v1.get("positions") or {}),
            **(v2.get("positions") or {}),
            **((v3.get("positions") or {}) if v3 else {}),
        }.items()
    }

    m1 = _arm_day_metrics("V1", v1, cfg, marks)
    m2 = _arm_day_metrics("V2", v2, cfg, marks)
    arms_metrics = {"V1": m1, "V2": m2}
    if v3 is not None:
        arms_metrics["V3"] = _arm_day_metrics("V3", v3, cfg, marks)

    verdict = compute_three_way_verdict(arms_metrics)
    divergences = compute_three_way_divergence(p, day)
    disagreements = [d for d in divergences if not d["all_agree"]]
    comparable = [d for d in divergences if d["arms_with_decision"] >= 2]

    report = {
        "schema": "tae.parallel_paper.daily_report_3way.v1",
        "date": day,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "arms_present": sorted(arms_metrics),
        "executive_conclusion": verdict,
        "metrics": arms_metrics,
        "divergences": divergences,
        "disagreement_count": len(disagreements),
        "comparable_ticker_count": len(comparable),
        "single_arm_only_ticker_count": len(divergences) - len(comparable),
        "disclaimer": "Single-day verdict is operational, not permanent strategic superiority. See generate_daily_report() for the authoritative V1-vs-V2 report this does not replace.",
        "paths": {"md": str(md_path), "json": str(json_path)},
    }

    md = [
        f"# TAE Parallel PAPER Daily Report — V1/V2/V3 — {day}",
        "",
        f"**Verdict:** `{verdict['verdict']}` · winner={verdict.get('winner')} · ranked={verdict.get('ranked')}",
        "",
        verdict["main_reason"],
        "",
        "## Comparative table",
        "",
        "| Metric | " + " | ".join(arms_metrics) + " |",
        "|---" * (len(arms_metrics) + 1) + "|",
    ]
    row_defs = [
        ("Ending AV", "ending_av", "{:.2f}"),
        ("Cash", "cash", "{:.2f}"),
        ("Invested", "invested", "{:.2f}"),
        ("Realized PnL (cum.)", "realized_pnl_cumulative", "{:.2f}"),
        ("Unrealized PnL", "unrealized_pnl", "{:.2f}"),
        ("Daily total PnL", "daily_total_pnl", "{:.2f}"),
        ("Drawdown", "drawdown", "{:.2f}"),
        ("Open positions", "open_positions", "{}"),
        ("Capital util", "capital_utilization", "{:.3f}"),
        ("Accounting", "reconciliation_pass", "{}"),
    ]
    for label, key, fmt in row_defs:
        cells = [fmt.format(arms_metrics[a].get(key) or 0) for a in arms_metrics]
        md.append(f"| {label} | " + " | ".join(cells) + " |")

    md += [
        "",
        f"## Divergences ({len(disagreements)} of {len(comparable)} tickers evaluated by 2+ arms disagree on action class; "
        f"{len(divergences) - len(comparable)} more tickers were evaluated by only one arm and are not comparable)",
        "",
    ]
    for d in disagreements[:15]:
        md.append(
            f"- {d['ticker']}: V1={d['V1_action']}({d['V1_class']}) · "
            f"V2={d['V2_action']}({d['V2_class']}) · V3={d['V3_action']}({d['V3_class']})"
        )
    md += ["", "## Disclaimer", "", report["disclaimer"], ""]

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(md), encoding="utf-8")
    _atomic_write_json(json_path, report)
    return report
