#!/usr/bin/env python3
"""
TAE Paper Decision Engine — PAPER_ONLY / READ_ONLY / NO_BROKER.

Converts existing intelligence + learning-to-profit outputs into explicit PAPER decisions.
Does NOT execute trades, modify live paths, or promote to live.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tae_decision_event_bus import open_positions_from_portfolio, read_csv_rows, signals_by_ticker

SCHEMA = "tae_paper_decision_engine"
VERSION = "v1"
MODE = "PAPER_ONLY"

LTP_DIR = Path("runtime_outputs/learning_to_profit")
HYPOTHESES_JSON = LTP_DIR / "hypotheses.json"
QUEUE_JSONL = LTP_DIR / "paper_experiment_queue.jsonl"
EXPERIMENTS_JSON = LTP_DIR / "experiment_results.json"

GII_JSON = Path("tae_growth_intelligence.json")
PPG_JSON = Path("tae_portfolio_profit_governor.json")
APPE_JSON = Path("tae_adaptive_profit_policy_engine.json")
SHADOW_JSON = Path("tae_profit_protection_shadow.json")
SHADOW_VALIDATION_JSON = Path("tae_profit_protection_validation.json")
DPE_EVAL_JSON = Path("runtime_outputs/dpe/result_evaluator/evaluation.json")
DPE_ADAPTIVE_JSON = Path("runtime_outputs/dpe/adaptive/adaptive.json")
ACCOUNTING_JSON = Path("tae_accounting_snapshot.json")
CONFIDENCE_JSON = Path("tae_confidence_evolution.json")
REPLAY_JSON = Path("tae_decision_replay.json")
ADAPTATION_HINTS_JSON = Path("runtime_outputs/longitudinal_memory/adaptation_hints.json")
PATTERN_DISCOVERY_TXT = Path("pattern_discovery_summary.txt")
PORTFOLIO_CSV = Path("portfolio.csv")
SIGNALS_CSV = Path("live_signals.csv")

OUTPUT_DIR = Path("runtime_outputs/paper_decisions")
DECISIONS_JSON = OUTPUT_DIR / "paper_decisions.json"
DECISIONS_JSONL = OUTPUT_DIR / "paper_decisions.jsonl"
REPORT_MD = Path("TAE_PAPER_DECISION_ENGINE_REPORT.md")

PAPER_ACTIONS = frozenset(
    {
        "BUY_PAPER",
        "SELL_PAPER",
        "REDUCE_PAPER",
        "PROTECT_PAPER",
        "ROTATE_PAPER",
        "HOLD_PAPER",
        "SKIP_PAPER",
    }
)

FORBIDDEN_WRITE_PREFIXES = (
    "portfolio.csv",
    "live_signals.csv",
    "watchlist.txt",
    "live_bot.py",
    "core/",
    "research_core/",
)

HEALTHY_LIFECYCLE = frozenset({"SURVIVED", "EARLY_WINNER", "MATURE_WINNER", "PEAK_WINNER"})
WEAK_LIFECYCLE = frozenset({"PROFIT_DECAY", "COLLAPSED", "WEAKENING"})

HISTORICAL_INTELLIGENCE_CSV = Path("historical_intelligence.csv")
MULTI_HORIZON_BACKTEST_CSV = Path("multi_horizon_backtest.csv")
STRATEGIC_INTELLIGENCE_TXT = Path("strategic_intelligence_summary.txt")
HORIZON_VOTE_TXT = Path("horizon_vote_summary.txt")
INTRADAY_FADE_JSON = Path("tae_intraday_fade_intelligence.json")
CROSS_VALIDATION_JSON = Path("tae_cross_validation_report.json")
HISTORICAL_RESULTS_JSON = Path("tae_historical_results_analysis.json")
HORIZON_LABELS = ("7D", "1M", "1Y", "2Y", "5Y", "10Y", "20Y")


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


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def assert_safe_output_path(path: Path) -> None:
    resolved = str(path.resolve())
    output_root = OUTPUT_DIR.resolve()
    if path.resolve() != REPORT_MD.resolve() and output_root not in path.resolve().parents:
        raise RuntimeError(f"Unsafe output path outside paper_decisions/: {path}")
    for forbidden in FORBIDDEN_WRITE_PREFIXES:
        if forbidden.rstrip("/") in resolved:
            raise RuntimeError(f"Forbidden write target: {path}")


def index_gii(gii: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _s(t.get("ticker")).upper(): t for t in (gii or {}).get("tickers") or [] if t.get("ticker")
    }


def index_shadow(shadow: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        _s(p.get("ticker")).upper(): p for p in (shadow or {}).get("positions") or [] if p.get("ticker")
    }


def ppg_posture_by_ticker(ppg: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for key in ("top_5_risky_tickers", "top_5_keep_winners"):
        for row in (ppg or {}).get(key) or []:
            if isinstance(row, dict):
                ticker = _s(row.get("ticker")).upper()
                if ticker:
                    out[ticker] = row
    return out


def experiments_by_ticker(experiments: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for exp in experiments:
        tickers = exp.get("affected_tickers") or []
        if not tickers:
            out.setdefault("_PORTFOLIO", []).append(exp)
            continue
        for raw in tickers:
            ticker = _s(raw).upper()
            out.setdefault(ticker, []).append(exp)
    return out


def file_age_hours(path: Path) -> float | None:
    if not path.is_file():
        return None
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return round((datetime.now(timezone.utc) - mtime).total_seconds() / 3600, 1)


def market_proxy_ticker(ticker: str) -> str:
    ticker = ticker.upper()
    if ticker.endswith(".L"):
        return "EWU"
    if ticker.endswith((".DE", ".PA", ".AS", ".MI", ".SW", ".MC", ".BR")):
        return "VGK"
    if ticker in {"SPY", "QQQ", "DIA", "IWM", "VGK", "EWU", "FEZ"}:
        return ticker
    return "SPY"


def classify_trend(value: float | None, *, pos: float = 1.0, neg: float = -1.0) -> str:
    if value is None:
        return "UNKNOWN"
    if value >= pos:
        return "POSITIVE"
    if value <= neg:
        return "NEGATIVE"
    return "NEUTRAL"


def trend_polarity(trend: str) -> int:
    return {"POSITIVE": 1, "NEUTRAL": 0, "NEGATIVE": -1, "UNKNOWN": 0}.get(trend, 0)


def load_historical_horizon_returns(path: Path = HISTORICAL_INTELLIGENCE_CSV) -> dict[str, dict[str, float]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, float]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            ticker = _s(row.get("Ticker")).upper()
            horizon = _s(row.get("Horizon"))
            if not ticker or horizon not in {"2Y", "5Y", "10Y", "20Y"}:
                continue
            try:
                out.setdefault(ticker, {})[horizon] = float(row.get("Return_%") or 0)
            except (TypeError, ValueError):
                continue
    return out


def parse_strategic_market_returns(path: Path = STRATEGIC_INTELLIGENCE_TXT) -> dict[str, dict[str, float]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, float]] = {}
    pattern = re.compile(
        r"\|\s*([A-Z0-9._]+)\s*\|\s*1M\s*([-\d.]+)%?\s*\|\s*3M\s*([-\d.]+)%?\s*\|\s*6M\s*([-\d.]+)%?\s*\|\s*12M\s*([-\d.]+)%"
    )
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = pattern.search(line)
        if not match:
            continue
        proxy = match.group(1).upper()
        out[proxy] = {
            "1M": float(match.group(2)),
            "1Y": float(match.group(5)),
        }
    return out


def load_intraday_by_ticker(path: Path = INTRADAY_FADE_JSON) -> dict[str, dict[str, Any]]:
    doc = load_json(path) or {}
    return {
        _s(p.get("ticker")).upper(): p
        for p in (doc.get("positions") or [])
        if p.get("ticker")
    }


def load_horizon_ssot() -> dict[str, Any]:
    cross = load_json(CROSS_VALIDATION_JSON) or {}
    hist_results = load_json(HISTORICAL_RESULTS_JSON) or {}
    horizon_vote = HORIZON_VOTE_TXT.read_text(encoding="utf-8", errors="replace") if HORIZON_VOTE_TXT.is_file() else ""
    return {
        "historical_returns": load_historical_horizon_returns(),
        "strategic_returns": parse_strategic_market_returns(),
        "multi_horizon_backtest_present": MULTI_HORIZON_BACKTEST_CSV.is_file(),
        "intraday_by_ticker": load_intraday_by_ticker(),
        "cross_horizon_consistency": cross.get("cross_horizon_consistency_summary"),
        "horizon_vote_text": horizon_vote,
        "historical_results_horizons": list((hist_results.get("top_10_per_horizon") or {}).keys()),
        "freshness_hours": {
            "historical_intelligence.csv": file_age_hours(HISTORICAL_INTELLIGENCE_CSV),
            "strategic_intelligence_summary.txt": file_age_hours(STRATEGIC_INTELLIGENCE_TXT),
            "horizon_vote_summary.txt": file_age_hours(HORIZON_VOTE_TXT),
            "tae_intraday_fade_intelligence.json": file_age_hours(INTRADAY_FADE_JSON),
            "tae_cross_validation_report.json": file_age_hours(CROSS_VALIDATION_JSON),
        },
    }


def build_horizon_context(ticker: str, ctx: dict[str, Any]) -> dict[str, Any]:
    ticker = ticker.upper()
    ssot = ctx.get("horizon_ssot") or {}
    stale_paths = set(ctx.get("stale_source_paths") or [])
    hist_stale = "historical_intelligence.csv" in stale_paths
    strat_stale = "strategic_intelligence_summary.txt" in stale_paths
    gii = (ctx.get("gii_by") or {}).get(ticker) or {}
    intraday = (ssot.get("intraday_by_ticker") or {}).get(ticker) or {}
    hist = (ssot.get("historical_returns") or {}).get(ticker) or {}
    proxy = market_proxy_ticker(ticker)
    strategic = (ssot.get("strategic_returns") or {}).get(proxy) or {}

    short_pct = _f(intraday.get("current_pct") or gii.get("current_pct"))
    short_drawdown = abs(_f(intraday.get("drawdown_from_high_pct") or gii.get("drawdown")))

    ret_2y = hist.get("2Y") if not hist_stale else None
    ret_5y = hist.get("5Y") if not hist_stale else None
    ret_10y = hist.get("10Y") if not hist_stale else None
    ret_20y = hist.get("20Y") if not hist_stale else None

    ret_1m = strategic.get("1M") if not strat_stale else None
    ret_1y = strategic.get("1Y") if not strat_stale else None

    if ret_1y is None and ret_2y is not None:
        ret_1y = ret_2y / 2.0

    horizon_context: dict[str, dict[str, Any]] = {
        "7D": {
            "return_pct": round(short_pct, 2),
            "trend": classify_trend(short_pct, pos=0.5, neg=-0.5),
            "source": "tae_intraday_fade_intelligence.json|tae_growth_intelligence.json",
        },
        "1M": {
            "return_pct": ret_1m,
            "trend": "UNKNOWN" if strat_stale else classify_trend(ret_1m),
            "source": f"strategic_intelligence_summary.txt via {proxy}",
            "stale": strat_stale,
        },
        "1Y": {
            "return_pct": round(ret_1y, 2) if ret_1y is not None else None,
            "trend": "UNKNOWN" if strat_stale else classify_trend(ret_1y),
            "source": f"strategic_intelligence_summary.txt|historical_intelligence.csv via {proxy}",
            "stale": strat_stale or hist_stale,
        },
        "2Y": {
            "return_pct": ret_2y,
            "trend": "UNKNOWN" if hist_stale else classify_trend(ret_2y),
            "source": "historical_intelligence.csv",
            "stale": hist_stale,
        },
        "5Y": {
            "return_pct": ret_5y,
            "trend": "UNKNOWN" if hist_stale else classify_trend(ret_5y),
            "source": "historical_intelligence.csv",
            "stale": hist_stale,
        },
        "10Y": {
            "return_pct": ret_10y,
            "trend": "UNKNOWN" if hist_stale else classify_trend(ret_10y),
            "source": "historical_intelligence.csv",
            "stale": hist_stale,
        },
        "20Y": {
            "return_pct": ret_20y,
            "trend": "UNKNOWN" if hist_stale else classify_trend(ret_20y),
            "source": "historical_intelligence.csv",
            "stale": hist_stale,
        },
    }

    short_term_trend_7d = horizon_context["7D"]["trend"]
    monthly_trend = horizon_context["1M"]["trend"]
    yearly_trend = horizon_context["1Y"]["trend"]
    long_values = [ret_5y, ret_10y, ret_20y]
    long_avg = sum(v for v in long_values if v is not None) / max(1, len([v for v in long_values if v is not None]))
    long_term_trend = classify_trend(long_avg if long_values else None)

    polarities = [trend_polarity(horizon_context[h]["trend"]) for h in HORIZON_LABELS]
    alignment_score = round(50.0 + sum(polarities) * (50.0 / len(HORIZON_LABELS)), 1)
    alignment_score = max(0.0, min(100.0, alignment_score))

    short_pol = trend_polarity(short_term_trend_7d)
    medium_pol = trend_polarity(monthly_trend)
    long_pol = trend_polarity(long_term_trend)
    conflict = (short_pol < 0 and long_pol > 0) or (short_pol > 0 and long_pol < 0)

    parts: list[str] = []
    for label in HORIZON_LABELS:
        row = horizon_context[label]
        ret = row.get("return_pct")
        ret_txt = f"{ret:.1f}%" if isinstance(ret, (int, float)) else "n/a"
        parts.append(f"{label}={row['trend']}({ret_txt})")
    if conflict:
        parts.append("short-vs-long CONFLICT")
    else:
        parts.append("horizons aligned")
    if hist_stale:
        parts.append("STALE historical_intelligence.csv — 2Y-20Y not used")
    if strat_stale:
        parts.append("STALE strategic_intelligence_summary.txt — 1M/1Y not used")
    horizon_reason = "; ".join(parts)

    return {
        "horizon_context": horizon_context,
        "short_term_trend_7d": short_term_trend_7d,
        "monthly_trend": monthly_trend,
        "yearly_trend": yearly_trend,
        "long_term_trend": long_term_trend,
        "horizon_alignment_score": alignment_score,
        "horizon_conflict_flag": conflict,
        "horizon_reason": horizon_reason,
        "short_drawdown_pct": round(short_drawdown, 2),
        "market_proxy": proxy,
        "cross_horizon_consistency": ssot.get("cross_horizon_consistency"),
        "historical_stale": hist_stale,
        "strategic_stale": strat_stale,
    }


def apply_stale_source_penalty(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> float:
    penalty = _f((ctx.get("historical_runtime") or {}).get("confidence_penalty"))
    stale = (ctx.get("historical_runtime") or {}).get("stale_sources") or []
    if not stale and not penalty:
        return 0.0
    if stale:
        evidence.append(f"STALE sources: {', '.join(stale)} — confidence reduced")
    if penalty > 0:
        for action in scores:
            if action != "SKIP_PAPER":
                scores[action] *= max(0.5, 1.0 - penalty)
        scores["SKIP_PAPER"] += penalty * 40.0
    return penalty


def apply_learning_evidence_bias(
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
) -> None:
    confidence_doc = ctx.get("confidence_evolution") or {}
    replay_doc = ctx.get("decision_replay") or {}

    final_rec = _s(confidence_doc.get("final_recommendation")).upper()
    if "DO_NOT_PROMOTE" in final_rec or "INSUFFICIENT" in final_rec:
        scores["BUY_PAPER"] -= 12.0
        scores["SKIP_PAPER"] += 10.0
        evidence.append(f"confidence evolution: {final_rec or 'caution'}")

    for rec in replay_doc.get("recommendations") or []:
        if _s(rec) == "DO_NOT_PROMOTE_TO_LIVE":
            scores["BUY_PAPER"] -= 10.0
            scores["SKIP_PAPER"] += 8.0
            evidence.append("decision replay: DO_NOT_PROMOTE_TO_LIVE")
            break

    if ctx.get("pattern_discovery_present"):
        scores["ROTATE_PAPER"] += 3.0
        evidence.append("pattern discovery summary available")


def apply_horizon_action_bias(
    ticker: str,
    scores: dict[str, float],
    evidence: list[str],
    ctx: dict[str, Any],
    *,
    held: bool,
) -> dict[str, Any]:
    hz = build_horizon_context(ticker, ctx)
    short = trend_polarity(hz["short_term_trend_7d"])
    medium = trend_polarity(hz["monthly_trend"])
    long_t = trend_polarity(hz["long_term_trend"])
    alignment = _f(hz["horizon_alignment_score"])
    conflict = bool(hz["horizon_conflict_flag"])
    drawdown = _f(hz.get("short_drawdown_pct"))

    exps = (ctx.get("exp_by_ticker") or {}).get(ticker.upper(), [])
    override = ticker in (ctx.get("top_growth") or []) or any(
        e.get("verdict") == "PROMISING" for e in exps
    )

    if not override and (short < 0 or medium < 0):
        scores["BUY_PAPER"] -= 28.0
        scores["SKIP_PAPER"] += 18.0
        evidence.append(f"horizon BUY gate: short/medium not aligned — {hz['horizon_reason'][:120]}")
    elif short > 0 and medium > 0:
        scores["BUY_PAPER"] += 10.0
        evidence.append("horizon supports BUY (short+medium positive)")

    if short < 0 and long_t > 0:
        scores["SELL_PAPER"] += 14.0
        scores["REDUCE_PAPER"] += 12.0
        evidence.append("horizon: short weakness vs positive long-term trend")

    if held and short <= 0 and long_t > 0 and not conflict:
        scores["HOLD_PAPER"] += 16.0
        evidence.append("horizon: long-term positive — treat short weakness as pullback")

    if drawdown >= 2.5 and long_t > 0:
        scores["PROTECT_PAPER"] += 18.0
        evidence.append(f"horizon: short volatility elevated (drawdown {drawdown:.1f}%) with intact long trend")

    if held and alignment >= 65.0:
        scores["HOLD_PAPER"] += 6.0
    elif alignment <= 35.0:
        scores["ROTATE_PAPER"] += 10.0
        scores["SELL_PAPER"] += 6.0

    if ticker in (ctx.get("top_growth") or []):
        held_alignments = [
            _f(build_horizon_context(t, ctx).get("horizon_alignment_score"))
            for t in (ctx.get("live_positions") or {})
            if t != ticker
        ]
        if held_alignments and alignment > min(held_alignments) + 8.0:
            scores["ROTATE_PAPER"] += 14.0
            evidence.append("horizon: candidate alignment beats weakest held position")

    if conflict:
        scores["PROTECT_PAPER"] += 8.0
        scores["SKIP_PAPER"] += 5.0

    return hz


def build_context() -> dict[str, Any]:
    gii = load_json(GII_JSON)
    ppg = load_json(PPG_JSON)
    appe = load_json(APPE_JSON)
    shadow = load_json(SHADOW_JSON)
    shadow_val = load_json(SHADOW_VALIDATION_JSON)
    dpe_eval = load_json(DPE_EVAL_JSON)
    dpe_adaptive = load_json(DPE_ADAPTIVE_JSON)
    accounting = load_json(ACCOUNTING_JSON)
    hypotheses = load_json(HYPOTHESES_JSON)
    experiments_doc = load_json(EXPERIMENTS_JSON)
    confidence_evolution = load_json(CONFIDENCE_JSON)
    decision_replay = load_json(REPLAY_JSON)
    adaptation_hints = load_json(ADAPTATION_HINTS_JSON)

    portfolio_rows = read_csv_rows(PORTFOLIO_CSV) if PORTFOLIO_CSV.is_file() else []
    signal_rows = read_csv_rows(SIGNALS_CSV) if SIGNALS_CSV.is_file() else []
    live_positions = open_positions_from_portfolio(portfolio_rows)
    signals = signals_by_ticker(signal_rows)

    gii_by = index_gii(gii)
    shadow_by = index_shadow(shadow)
    ppg_by = ppg_posture_by_ticker(ppg)
    experiments = (experiments_doc or {}).get("experiments") or []
    exp_by_ticker = experiments_by_ticker(experiments)

    top_growth = [
        _s(t.get("ticker")).upper()
        for t in sorted((gii or {}).get("tickers") or [], key=lambda x: _f(x.get("growth_score")), reverse=True)[:5]
    ]

    latest_appe = (appe or {}).get("latest_observation") or {}
    portfolio_gii = (gii or {}).get("portfolio") or {}
    acct_cash_hint = _f((accounting or {}).get("cash_available")) or _f((accounting or {}).get("account_value_corrected")) * 0.1
    horizon_ssot = load_horizon_ssot()
    from tae_historical_runtime_refresh import load_runtime_state, stale_source_paths

    hist_runtime = load_runtime_state()

    return {
        "gii": gii,
        "gii_by": gii_by,
        "portfolio_gii": portfolio_gii,
        "ppg": ppg,
        "ppg_by": ppg_by,
        "appe": appe,
        "policy_state": _s(latest_appe.get("policy_state")),
        "suggested_policy": _s(latest_appe.get("suggested_shadow_policy")),
        "shadow_by": shadow_by,
        "shadow_validation": shadow_val,
        "dpe_eval": dpe_eval,
        "dpe_adaptive": dpe_adaptive,
        "preferred_philosophy": _s((dpe_adaptive or {}).get("preferred_philosophy")),
        "accounting": accounting,
        "cash_hint": acct_cash_hint,
        "hypotheses": hypotheses,
        "experiments": experiments,
        "exp_by_ticker": exp_by_ticker,
        "confidence_evolution": confidence_evolution,
        "decision_replay": decision_replay,
        "adaptation_hints": adaptation_hints,
        "pattern_discovery_present": PATTERN_DISCOVERY_TXT.is_file(),
        "live_positions": live_positions,
        "signals": signals,
        "top_growth": top_growth,
        "horizon_ssot": horizon_ssot,
        "historical_runtime": hist_runtime,
        "stale_source_paths": sorted(stale_source_paths()),
        "sources_loaded": {
            "hypotheses": HYPOTHESES_JSON.is_file(),
            "experiments": EXPERIMENTS_JSON.is_file(),
            "gii": GII_JSON.is_file(),
            "ppg": PPG_JSON.is_file(),
            "appe": APPE_JSON.is_file(),
            "shadow": SHADOW_JSON.is_file(),
            "shadow_validation": SHADOW_VALIDATION_JSON.is_file(),
            "dpe_eval": DPE_EVAL_JSON.is_file(),
            "dpe_adaptive": DPE_ADAPTIVE_JSON.is_file(),
            "portfolio": PORTFOLIO_CSV.is_file(),
            "signals": SIGNALS_CSV.is_file(),
            "accounting": ACCOUNTING_JSON.is_file(),
            "historical_intelligence": HISTORICAL_INTELLIGENCE_CSV.is_file(),
            "strategic_intelligence": STRATEGIC_INTELLIGENCE_TXT.is_file(),
            "horizon_vote": HORIZON_VOTE_TXT.is_file(),
            "intraday_fade": INTRADAY_FADE_JSON.is_file(),
            "cross_validation": CROSS_VALIDATION_JSON.is_file(),
            "confidence_evolution": CONFIDENCE_JSON.is_file(),
            "longitudinal_adaptation_hints": ADAPTATION_HINTS_JSON.is_file(),
            "decision_replay": REPLAY_JSON.is_file(),
            "pattern_discovery": PATTERN_DISCOVERY_TXT.is_file(),
        },
    }


def ticker_universe(ctx: dict[str, Any]) -> list[str]:
    held = set(ctx.get("live_positions") or {})
    signal_tickers = set(ctx.get("signals") or {})
    gii_tickers = set(ctx.get("gii_by") or {})
    top = set(ctx.get("top_growth") or [])
    universe = held | signal_tickers | (gii_tickers & top)
    return sorted(universe)


def experiment_boost(ticker: str, ctx: dict[str, Any]) -> tuple[float, list[str]]:
    exps = list(ctx.get("exp_by_ticker", {}).get(ticker.upper(), []))
    exps.extend(ctx.get("exp_by_ticker", {}).get("_PORTFOLIO", []))
    boost = 0.0
    notes: list[str] = []
    for exp in exps:
        verdict = _s(exp.get("verdict"))
        action = _s(exp.get("paper_experiment_action"))
        if verdict == "PROMISING":
            boost += 12.0
            notes.append(f"experiment {exp.get('hypothesis_id')} PROMISING")
        elif verdict == "CONTINUE_TESTING":
            boost += 5.0
        elif verdict == "REJECT":
            boost -= 20.0
            notes.append(f"experiment {exp.get('hypothesis_id')} REJECT")
        elif verdict == "NEEDS_MORE_DATA":
            boost -= 8.0
        if action:
            notes.append(action)
    return boost, notes


def estimate_deltas(ticker: str, action: str, ctx: dict[str, Any]) -> dict[str, float]:
    gii = (ctx.get("gii_by") or {}).get(ticker.upper()) or {}
    shadow = (ctx.get("shadow_by") or {}).get(ticker.upper()) or {}
    missed = _f(gii.get("missed_usd") or shadow.get("missed_opportunity_usd"))
    cap_eff = _f(gii.get("capital_efficiency"))
    collapse = _f(gii.get("collapse_probability"))

    exps = (ctx.get("exp_by_ticker") or {}).get(ticker.upper()) or []
    if exps and exps[0].get("deltas"):
        d = exps[0]["deltas"]
        return {
            "expected_profit_delta": _f(d.get("expected_profit_delta_usd")),
            "expected_risk_delta": _f(d.get("risk_delta")),
            "capital_efficiency_delta": _f(d.get("capital_efficiency_delta")),
        }

    if action == "BUY_PAPER":
        return {"expected_profit_delta": 15.0, "expected_risk_delta": 0.05, "capital_efficiency_delta": 5.0}
    if action == "SELL_PAPER":
        return {
            "expected_profit_delta": missed * 0.1,
            "expected_risk_delta": -collapse * 0.2,
            "capital_efficiency_delta": max(0.0, 50.0 - cap_eff) * 0.1,
        }
    if action == "REDUCE_PAPER":
        return {
            "expected_profit_delta": missed * 0.2,
            "expected_risk_delta": -0.12,
            "capital_efficiency_delta": 2.0,
        }
    if action == "PROTECT_PAPER":
        return {
            "expected_profit_delta": missed * 0.25,
            "expected_risk_delta": -0.15,
            "capital_efficiency_delta": -1.0,
        }
    if action == "ROTATE_PAPER":
        return {
            "expected_profit_delta": missed * 0.18,
            "expected_risk_delta": -0.06,
            "capital_efficiency_delta": max(0.0, 45.0 - cap_eff) * 0.08,
        }
    if action == "HOLD_PAPER":
        return {
            "expected_profit_delta": missed * 0.08,
            "expected_risk_delta": 0.03,
            "capital_efficiency_delta": 0.0,
        }
    return {"expected_profit_delta": 0.0, "expected_risk_delta": 0.0, "capital_efficiency_delta": 0.0}


def hypotheses_for_ticker(ticker: str, hypotheses_doc: dict[str, Any] | None) -> list[dict[str, Any]]:
    ticker = ticker.upper()
    matched: list[dict[str, Any]] = []
    for hyp in (hypotheses_doc or {}).get("hypotheses") or []:
        tickers = [_s(t).upper() for t in (hyp.get("affected_tickers") or [])]
        if not tickers or ticker in tickers:
            matched.append(hyp)
    return matched


def protection_validation_bias(
    ticker: str,
    validation: dict[str, Any] | None,
) -> tuple[float, float, float, bool]:
    """Return (protect_boost, reduce_boost, sell_penalty, gates_passed)."""
    if not validation:
        return 0.0, 0.0, 0.0, False
    gates = validation.get("gates") or {}
    gates_passed = bool(gates.get("gates_passed"))
    protect_boost = 15.0 if gates_passed else -5.0
    reduce_boost = 8.0 if gates_passed else 0.0
    sell_penalty = 0.0

    best = validation.get("best_strategy") or {}
    best_id = _s(best.get("strategy_id")).lower()
    if "trailing" in best_id:
        protect_boost += 12.0
    if "partial" in best_id or "sell" in best_id:
        reduce_boost += 10.0
    if _f(best.get("delta_vs_hold_total")) <= 0:
        sell_penalty += 6.0

    for row in validation.get("ticker_breakdown") or []:
        if _s(row.get("ticker")).upper() == ticker.upper():
            if _f(row.get("delta_vs_hold")) > 0:
                protect_boost += 8.0
            elif _f(row.get("delta_vs_hold")) < 0:
                sell_penalty += 5.0
    return protect_boost, reduce_boost, sell_penalty, gates_passed


def apply_hypothesis_rules(
    ticker: str,
    action: str,
    confidence: float,
    ctx: dict[str, Any],
) -> tuple[str, list[dict[str, Any]], str]:
    """Apply hypothesis validation/rejection rules; may force SKIP_PAPER."""
    hyps = hypotheses_for_ticker(ticker, ctx.get("hypotheses"))
    applied: list[dict[str, Any]] = []
    for hyp in hyps:
        applied.append(
            {
                "hypothesis_id": hyp.get("hypothesis_id"),
                "validation_rule": hyp.get("validation_rule"),
                "rejection_rule": hyp.get("rejection_rule"),
                "hypothesis_type": hyp.get("hypothesis_type"),
            }
        )

    exps = (ctx.get("exp_by_ticker") or {}).get(ticker.upper(), [])
    exps.extend((ctx.get("exp_by_ticker") or {}).get("_PORTFOLIO", []))
    if any(e.get("verdict") == "REJECT" for e in exps):
        return "SKIP_PAPER", applied, "hypothesis rejection_rule: linked experiment REJECT"

    promising = any(e.get("verdict") == "PROMISING" for e in exps)
    if action in {"BUY_PAPER", "ROTATE_PAPER"} and not promising and confidence < 0.5:
        return "SKIP_PAPER", applied, "hypothesis rejection_rule: no PROMISING validation for aggressive action"

    if action == "PROTECT_PAPER" and hyps and not promising and confidence < 0.42:
        return "SKIP_PAPER", applied, "hypothesis rejection_rule: protect action lacks validation evidence"

    return action, applied, ""


def compute_risk_score(ticker: str, ctx: dict[str, Any]) -> float:
    gii = (ctx.get("gii_by") or {}).get(ticker.upper()) or {}
    ppg_row = (ctx.get("ppg_by") or {}).get(ticker.upper()) or {}
    posture = _s(ppg_row.get("governor_posture"))
    score = _f(gii.get("collapse_probability")) * 50.0
    score += _f(gii.get("opportunity_score")) * 0.3
    if posture in {"PROTECT_SHADOW", "TRAIL_SHADOW"}:
        score += 20.0
    elif posture == "WATCH_SHADOW":
        score += 10.0
    if _s(gii.get("lifecycle_stage")) in WEAK_LIFECYCLE:
        score += 25.0
    return round(min(100.0, max(0.0, score)), 2)


def score_actions_for_ticker(ticker: str, ctx: dict[str, Any]) -> tuple[str, dict[str, float], list[str]]:
    ticker = ticker.upper()
    held = ticker in (ctx.get("live_positions") or {})
    gii = (ctx.get("gii_by") or {}).get(ticker) or {}
    shadow = (ctx.get("shadow_by") or {}).get(ticker) or {}
    ppg_row = (ctx.get("ppg_by") or {}).get(ticker) or {}
    signal = (ctx.get("signals") or {}).get(ticker) or {}

    strategy = _s(gii.get("recommended_shadow_strategy"))
    lifecycle = _s(gii.get("lifecycle_stage"))
    cap_eff = _f(gii.get("capital_efficiency"))
    growth_score = _f(gii.get("growth_score"))
    missed = _f(gii.get("missed_usd") or shadow.get("missed_opportunity_usd"))
    current_pct = _f(gii.get("current_pct") or shadow.get("current_pct"))
    opp_cat = _s(gii.get("opportunity_category"))
    posture = _s(ppg_row.get("governor_posture"))
    protect_signal = _s(shadow.get("protection_signal"))
    signal_name = _s(signal.get("signal")).upper()
    signal_score = _f(signal.get("score"))

    policy_state = _s(ctx.get("policy_state"))
    suggested_policy = _s(ctx.get("suggested_policy")).upper()
    exp_boost, exp_notes = experiment_boost(ticker, ctx)
    preferred = _s(ctx.get("preferred_philosophy"))

    scores: dict[str, float] = {a: 0.0 for a in PAPER_ACTIONS}
    evidence: list[str] = []

    if not gii and not shadow and not signal:
        scores["SKIP_PAPER"] = 80.0
        evidence.append("insufficient intelligence for ticker")
        hz = build_horizon_context(ticker, ctx)
        return "SKIP_PAPER", scores, evidence, [], False, hz

    if held:
        if posture in {"PROTECT_SHADOW"} and current_pct > 2.0 and missed >= 15.0:
            scores["REDUCE_PAPER"] += 45.0
            evidence.append(f"PPG posture={posture} missed=${missed:.2f}")
        if strategy == "REDUCE_EXPOSURE_SHADOW" or (cap_eff < 25.0 and posture not in {"PROTECT_SHADOW"}):
            scores["SELL_PAPER"] += 35.0 + max(0.0, 30.0 - cap_eff) * 0.5
            evidence.append(f"low capital_efficiency={cap_eff:.1f}")
        if lifecycle in WEAK_LIFECYCLE or _f(gii.get("collapse_probability")) > 0.55:
            scores["SELL_PAPER"] += 30.0
            evidence.append(f"weak lifecycle={lifecycle}")
        if opp_cat in {"CAPITAL_LOCKED", "CASH_CONSTRAINT"} and cap_eff < 45.0:
            scores["ROTATE_PAPER"] += 38.0
            evidence.append(f"opportunity_category={opp_cat}")
        if posture in {"TRAIL_SHADOW"} or "TRAILING" in protect_signal.upper():
            scores["PROTECT_PAPER"] += 40.0
            evidence.append(f"protection posture/signal={posture}/{protect_signal}")
        if strategy in {"TIGHTEN_TRAIL_SHADOW", "PROTECT_PROFIT_SHADOW"}:
            scores["PROTECT_PAPER"] += 25.0
            evidence.append(f"GII strategy={strategy}")
        if strategy == "KEEP_GROWING_SHADOW" and lifecycle in HEALTHY_LIFECYCLE:
            scores["HOLD_PAPER"] += 42.0 + growth_score * 0.1
            evidence.append(f"healthy winner lifecycle={lifecycle}")
        if strategy == "HOLD_AND_MONITOR_SHADOW":
            scores["HOLD_PAPER"] += 28.0
            evidence.append(f"monitor strategy={strategy}")
        if missed >= 30.0 and cap_eff < 40.0 and ticker not in (ctx.get("top_growth") or []):
            scores["ROTATE_PAPER"] += 20.0
        if not any(scores[a] > 20 for a in ("SELL_PAPER", "REDUCE_PAPER", "PROTECT_PAPER", "ROTATE_PAPER", "HOLD_PAPER")):
            scores["HOLD_PAPER"] += 20.0
            evidence.append("default hold for open position with partial evidence")
    else:
        if signal_score >= 90.0 and "STRONG BUY" in signal_name:
            scores["BUY_PAPER"] += 40.0
            evidence.append(f"signal={signal_name} score={signal_score}")
        elif signal_score >= 75.0 and "BUY" in signal_name:
            scores["BUY_PAPER"] += 25.0
            evidence.append(f"signal={signal_name}")
        if ticker in (ctx.get("top_growth") or []):
            scores["BUY_PAPER"] += 20.0 + growth_score * 0.15
            evidence.append(f"top_growth_candidate growth_score={growth_score:.1f}")
        if policy_state == "HIGH_RISK" or "PRESERVATION" in suggested_policy:
            scores["SKIP_PAPER"] += 15.0
            scores["BUY_PAPER"] -= 8.0
            evidence.append(f"policy={policy_state}/{ctx.get('suggested_policy')}")
        if _f(ctx.get("cash_hint")) < 1000.0:
            scores["SKIP_PAPER"] += 15.0
            scores["BUY_PAPER"] -= 10.0
            evidence.append("limited capital hint from accounting snapshot")
        if not signal and ticker not in (ctx.get("top_growth") or []):
            scores["SKIP_PAPER"] += 35.0
            evidence.append("no signal and not top growth candidate")

    if preferred == "COLLABORATIVE":
        scores["PROTECT_PAPER"] += 5.0
        scores["HOLD_PAPER"] += 3.0
    elif preferred == "COMPETITIVE":
        scores["ROTATE_PAPER"] += 4.0
        scores["SELL_PAPER"] += 3.0

    hz = apply_horizon_action_bias(ticker, scores, evidence, ctx, held=held)
    apply_stale_source_penalty(scores, evidence, ctx)
    apply_learning_evidence_bias(scores, evidence, ctx)

    prot_boost, reduce_boost, sell_penalty, gates_passed = protection_validation_bias(
        ticker, ctx.get("shadow_validation"),
    )
    scores["PROTECT_PAPER"] += prot_boost
    scores["REDUCE_PAPER"] += reduce_boost
    scores["SELL_PAPER"] -= sell_penalty
    if not gates_passed:
        evidence.append("protection validation gates not passed")
    else:
        evidence.append("protection validation gates passed")

    for action_key in scores:
        scores[action_key] += exp_boost * (
            0.15 if action_key in {"HOLD_PAPER", "PROTECT_PAPER", "BUY_PAPER"} else 0.1
        )
    evidence.extend(exp_notes)

    best = max(scores, key=lambda a: scores[a])
    if scores[best] < 18.0:
        best = "SKIP_PAPER"
        evidence.append("no action met minimum confidence threshold")

    confidence = round(min(0.95, max(0.25, scores[best] / 100.0)), 3)
    best, applied_hyps, rule_note = apply_hypothesis_rules(ticker, best, confidence, ctx)
    if rule_note:
        evidence.append(rule_note)

    return best, scores, evidence, applied_hyps, gates_passed, hz


def build_decision(ticker: str, ctx: dict[str, Any], *, seq: int) -> dict[str, Any]:
    action, scores, evidence_notes, applied_hypotheses, gates_passed, horizon = score_actions_for_ticker(ticker, ctx)
    gii = (ctx.get("gii_by") or {}).get(ticker.upper()) or {}
    deltas = estimate_deltas(ticker.upper(), action, ctx)
    risk_score = compute_risk_score(ticker.upper(), ctx)
    confidence = round(min(0.95, max(0.25, scores.get(action, 18.0) / 100.0)), 3)
    stale_penalty = _f((ctx.get("historical_runtime") or {}).get("confidence_penalty"))
    if stale_penalty > 0:
        confidence = round(max(0.25, confidence * (1.0 - stale_penalty)), 3)

    hints = ctx.get("adaptation_hints") or {}
    action_bias = _f((hints.get("action_confidence_bias") or {}).get(action))
    if action_bias:
        confidence = round(min(0.95, max(0.25, confidence + action_bias * 0.05)), 3)
        evidence_notes.append(f"longitudinal memory action bias {action_bias:+.3f}")

    sources: list[str] = []
    if gii:
        sources.append("tae_growth_intelligence.json")
    if ticker.upper() in (ctx.get("shadow_by") or {}):
        sources.append("tae_profit_protection_shadow.json")
    if ticker.upper() in (ctx.get("ppg_by") or {}):
        sources.append("tae_portfolio_profit_governor.json")
    if ctx.get("appe"):
        sources.append("tae_adaptive_profit_policy_engine.json")
    if (ctx.get("exp_by_ticker") or {}).get(ticker.upper()):
        sources.append("runtime_outputs/learning_to_profit/experiment_results.json")
    if applied_hypotheses:
        sources.append("runtime_outputs/learning_to_profit/hypotheses.json")
    if ctx.get("shadow_validation"):
        sources.append("tae_profit_protection_validation.json")
    if ctx.get("horizon_ssot", {}).get("historical_returns"):
        sources.append("historical_intelligence.csv")
    if STRATEGIC_INTELLIGENCE_TXT.is_file():
        sources.append("strategic_intelligence_summary.txt")
    if ctx.get("confidence_evolution"):
        sources.append("tae_confidence_evolution.json")
    if ctx.get("adaptation_hints"):
        sources.append("runtime_outputs/longitudinal_memory/adaptation_hints.json")
    if ctx.get("decision_replay"):
        sources.append("tae_decision_replay.json")
    if ctx.get("pattern_discovery_present"):
        sources.append("pattern_discovery_summary.txt")
    if ticker.upper() in (ctx.get("signals") or {}):
        sources.append("live_signals.csv")
    if ticker.upper() in (ctx.get("live_positions") or {}):
        sources.append("portfolio.csv")

    ts = _now()
    decision_id = f"PDEC-{ticker.upper()}-{seq:04d}"
    hyp_validation = applied_hypotheses[0].get("validation_rule") if applied_hypotheses else (
        "PAPER decision validated against GII/PPG/shadow evidence over validation_window."
    )
    hyp_rejection = applied_hypotheses[0].get("rejection_rule") if applied_hypotheses else (
        "Reject PAPER decision if 30-day shadow metrics regress: profit_capture_rate down, "
        "missed_usd up, or risk_score rises without offsetting profit gain."
    )

    return {
        "decision_id": decision_id,
        "timestamp": ts,
        "ticker": ticker.upper(),
        "action": action,
        "source_systems": sorted(set(sources)),
        "evidence": "; ".join(evidence_notes)[:500],
        "confidence": confidence,
        "risk_score": risk_score,
        "expected_profit_delta": round(deltas["expected_profit_delta"], 2),
        "expected_risk_delta": round(deltas["expected_risk_delta"], 4),
        "capital_efficiency_delta": round(deltas["capital_efficiency_delta"], 2),
        "validation_window": 30,
        "validation_rule": hyp_validation,
        "rejection_rule": hyp_rejection,
        "promotion_rule": (
            "PAPER validation must show PROMISING experiment verdict + non-negative profit delta "
            "before any advisory review; live promotion remains blocked (live_promotion_allowed=false)."
        ),
        "live_promotion_allowed": False,
        "mode": MODE,
        "action_scores": {k: round(v, 2) for k, v in scores.items() if v > 0},
        "hypothesis_rules_applied": applied_hypotheses,
        "protection_validation_gates_passed": gates_passed,
        "horizon_context": horizon.get("horizon_context"),
        "short_term_trend_7d": horizon.get("short_term_trend_7d"),
        "monthly_trend": horizon.get("monthly_trend"),
        "yearly_trend": horizon.get("yearly_trend"),
        "long_term_trend": horizon.get("long_term_trend"),
        "horizon_alignment_score": horizon.get("horizon_alignment_score"),
        "horizon_conflict_flag": horizon.get("horizon_conflict_flag"),
        "horizon_reason": horizon.get("horizon_reason"),
        "historical_sources_stale": bool((ctx.get("historical_runtime") or {}).get("stale_sources")),
        "confidence_penalty_stale": stale_penalty,
        "created_at": ts,
    }


def build_decisions(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    universe = ticker_universe(ctx)
    decisions = [build_decision(ticker, ctx, seq=i + 1) for i, ticker in enumerate(universe)]
    action_order = {
        "BUY_PAPER": 0,
        "SELL_PAPER": 1,
        "REDUCE_PAPER": 2,
        "PROTECT_PAPER": 3,
        "ROTATE_PAPER": 4,
        "HOLD_PAPER": 5,
        "SKIP_PAPER": 6,
    }
    decisions.sort(key=lambda d: (action_order.get(d["action"], 9), -d["confidence"], d["ticker"]))
    return decisions


def build_report_payload(decisions: list[dict[str, Any]], ctx: dict[str, Any]) -> dict[str, Any]:
    action_counts: dict[str, int] = {}
    for d in decisions:
        action_counts[d["action"]] = action_counts.get(d["action"], 0) + 1

    return {
        "schema": SCHEMA,
        "version": VERSION,
        "mode": MODE,
        "read_only": True,
        "no_broker": True,
        "no_live_execution": True,
        "no_execution": True,
        "live_promotion_allowed": False,
        "generated_at": _now(),
        "decision_count": len(decisions),
        "action_summary": action_counts,
        "sources_loaded": ctx.get("sources_loaded") or {},
        "policy_context": {
            "policy_state": ctx.get("policy_state"),
            "suggested_policy": ctx.get("suggested_policy"),
            "preferred_philosophy": ctx.get("preferred_philosophy"),
        },
        "decisions": decisions,
        "safety": {
            "mode": MODE,
            "PAPER_ONLY": True,
            "NO_BROKER": True,
            "NO_LIVE_CHANGE": True,
            "NO_EXECUTION": True,
            "live_promotion_allowed": False,
        },
    }


def write_outputs(report: dict[str, Any]) -> tuple[Path, Path, Path]:
    assert_safe_output_path(DECISIONS_JSON)
    assert_safe_output_path(DECISIONS_JSONL)
    assert_safe_output_path(REPORT_MD)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    DECISIONS_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with DECISIONS_JSONL.open("w", encoding="utf-8") as handle:
        for row in report.get("decisions") or []:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    summary = report.get("action_summary") or {}
    lines = [
        "# TAE Paper Decision Engine Report",
        "",
        f"**Generated:** {report['generated_at']}",
        "**Mode:** PAPER_ONLY — READ_ONLY — NO_BROKER — NO_LIVE_CHANGE — NO_EXECUTION",
        "**Live promotion allowed:** false",
        "",
        "> **PAPER_ONLY explicit decisions — no broker execution, no live promotion, no live file changes**",
        "",
        "## Executive summary",
        "",
        f"- Decisions generated: **{report.get('decision_count', 0)}**",
    ]
    for action in sorted(summary.keys()):
        lines.append(f"- **{action}**: {summary[action]}")
    lines.extend(
        [
            "",
            "## Decision table",
            "",
            "| ticker | action | confidence | risk | profit Δ | cap eff Δ | evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in (report.get("decisions") or [])[:25]:
        ev = _s(row.get("evidence"))[:60].replace("|", "/")
        lines.append(
            f"| {row.get('ticker')} | {row.get('action')} | {row.get('confidence')} | "
            f"{row.get('risk_score')} | {row.get('expected_profit_delta')} | "
            f"{row.get('capital_efficiency_delta')} | {ev} |"
        )

    lines.extend(
        [
            "",
            "## Closed intelligence loop",
            "",
            "- Consumes: learning-to-profit hypotheses + experiment results",
            "- Consumes: GII, PPG, APPE, profit protection, DPE adaptive/evaluation",
            "- Consumes: portfolio.csv + live_signals.csv (read-only)",
            "- Produces explicit PAPER BUY/SELL/HOLD/REDUCE/PROTECT/ROTATE/SKIP decisions",
            "- Applies hypothesis validation/rejection rules and protection validation scoring",
            "- Applies multi-horizon context (7D/1M/1Y/2Y/5Y/10Y/20Y) from existing SSOT artifacts",
            "",
            "## Safety confirmation",
            "",
            "| Rule | Status |",
            "| --- | --- |",
            "| PAPER_ONLY | ✅ |",
            "| NO_BROKER | ✅ |",
            "| NO_LIVE_CHANGE | ✅ |",
            "| NO_EXECUTION | ✅ |",
            "| live_promotion_allowed | **false** |",
            "| portfolio.csv modified | **false** |",
            "| live_bot.py modified | **false** |",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return DECISIONS_JSON, DECISIONS_JSONL, REPORT_MD


def print_summary(report: dict[str, Any]) -> None:
    summary = report.get("action_summary") or {}
    print("===== TAE PAPER DECISION ENGINE =====")
    print("Mode: PAPER_ONLY — NO_BROKER — NO_EXECUTION — no live change")
    print("Decisions:", report.get("decision_count", 0))
    print("Actions:", ", ".join(f"{k}={v}" for k, v in sorted(summary.items())))
    for row in (report.get("decisions") or [])[:5]:
        print(f"  {row['ticker']} → {row['action']} conf={row['confidence']} risk={row['risk_score']}")


def main() -> int:
    ctx = build_context()
    if not ctx.get("gii_by") and not ctx.get("live_positions"):
        print("paper-decision-engine: insufficient inputs — run growth-intelligence and ensure portfolio.csv", flush=True)
        return 1

    decisions = build_decisions(ctx)
    report = build_report_payload(decisions, ctx)
    paths = write_outputs(report)
    print_summary(report)
    print("Wrote:", *paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
