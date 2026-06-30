"""
Live signals research enricher — read-only context from existing research artifacts.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RESEARCH_COLUMNS = (
    "Research_Momentum",
    "Research_Daily_Gainers",
    "Research_Threshold",
    "Research_Regional",
    "Research_Macro",
    "Research_Sector",
    "Research_ETF",
    "Research_Counterfactual",
    "Research_Confidence",
    "Research_Context",
)

ARTIFACT_FILES = {
    "momentum": "momentum_continuation_signals.csv",
    "daily_gainers": "daily_gainers_strategy_results.csv",
    "daily_gainers_filter": "daily_gainers_momentum_filter_results.csv",
    "threshold_virtual": "threshold_80_virtual_candidates.csv",
    "threshold_intel": "threshold_intelligence_summary.txt",
    "regional_strength": "regional_strength.csv",
    "regional_validation": "tae_regional_validation_kn_d5_00002.json",
    "sector_rotation": "sector_rotation.csv",
    "global_market": "global_market_scanner.csv",
    "adaptive": "adaptive_allocation.json",
    "macro": "macro_committee_summary.txt",
    "entry_cf": "tae_entry_counterfactual.json",
    "exit_cf": "tae_exit_counterfactual.json",
}


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return payload if isinstance(payload, dict) else None


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def _parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_market(ticker: str) -> str:
    try:
        from markets.market_hours import get_ticker_market

        return get_ticker_market(ticker)
    except Exception:
        ticker = ticker.upper()
        if ticker.endswith(".L"):
            return "UK"
        if ticker.endswith((".DE", ".PA", ".AS", ".MI", ".SW", ".MC", ".BR")):
            return "EU"
        return "US"


def _region_key(market: str) -> str:
    market = market.upper()
    if market in ("EU", "EUROPE", "EUROZONE"):
        return "EU"
    if market == "UK":
        return "UK"
    return "US"


def _parse_macro_verdict(text: str) -> str:
    match = re.search(r"FINAL MACRO VOTE:\s*(\S+)", text)
    return match.group(1) if match else "MACRO_UNKNOWN"


def _parse_macro_confidence(text: str) -> float | None:
    match = re.search(r"Confidence:\s*([\d.]+)%", text)
    return _parse_float(match.group(1)) if match else None


@dataclass
class ResearchContext:
    momentum_by_ticker: dict[str, dict[str, str]]
    threshold_tickers: set[str]
    regional_strength: dict[str, float]
    regional_validation_status: str
    sector_top: str
    sector_top_score: float | None
    etf_scores: dict[str, float]
    daily_gainers_by_region: dict[str, str]
    macro_verdict: str
    macro_confidence: float | None
    adaptive_allocation: dict[str, float]
    entry_cf_verdict: str
    entry_cf_best: str
    exit_cf_verdict: str
    threshold_policy: str
    top_momentum_candidates: list[dict[str, Any]] = field(default_factory=list)
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> ResearchContext:
        root = Path(root)
        artifacts_loaded = {
            name: (root / fname).is_file() for name, fname in ARTIFACT_FILES.items()
        }

        momentum_by_ticker: dict[str, dict[str, str]] = {}
        top_momentum: list[dict[str, Any]] = []
        for row in _load_csv_rows(root / ARTIFACT_FILES["momentum"]):
            ticker = str(row.get("Ticker") or "").upper()
            if not ticker:
                continue
            momentum_by_ticker[ticker] = row
            score = _parse_float(row.get("Momentum_Score"))
            if score is not None:
                top_momentum.append(
                    {
                        "ticker": ticker,
                        "momentum_score": score,
                        "edge": row.get("Research_Edge"),
                    }
                )
        top_momentum.sort(key=lambda x: x["momentum_score"], reverse=True)

        threshold_tickers = {
            str(r.get("Ticker") or "").upper()
            for r in _load_csv_rows(root / ARTIFACT_FILES["threshold_virtual"])
            if r.get("Ticker")
        }

        regional_strength: dict[str, float] = {}
        for row in _load_csv_rows(root / ARTIFACT_FILES["regional_strength"]):
            region = str(row.get("Region") or "").upper()
            strength = _parse_float(row.get("Regional_Strength"))
            if region and strength is not None:
                if region in ("EUROPE", "EUROZONE"):
                    regional_strength["EU"] = strength
                else:
                    regional_strength[region] = strength

        regional_validation = _load_json(root / ARTIFACT_FILES["regional_validation"]) or {}
        rv_status = str(
            regional_validation.get("readiness_projection")
            or (regional_validation.get("validation_summary") or {}).get("readiness_projection")
            or regional_validation.get("verdict")
            or "UNKNOWN"
        )

        sector_top = "UNKNOWN"
        sector_top_score: float | None = None
        sector_rows = _load_csv_rows(root / ARTIFACT_FILES["sector_rotation"])
        if sector_rows:
            best = max(
                sector_rows,
                key=lambda r: _parse_float(r.get("Sector_Score")) or -999.0,
            )
            sector_top = str(best.get("Sector") or "UNKNOWN")
            sector_top_score = _parse_float(best.get("Sector_Score"))

        etf_scores: dict[str, float] = {}
        for row in _load_csv_rows(root / ARTIFACT_FILES["global_market"]):
            ticker = str(row.get("Ticker") or "").upper()
            score = _parse_float(row.get("Strategic_Score"))
            if ticker and score is not None:
                etf_scores[ticker] = score

        daily_gainers_by_region: dict[str, str] = {}
        dg_rows = _load_csv_rows(root / ARTIFACT_FILES["daily_gainers"])
        for region in ("US", "EU", "UK"):
            region_rows = [
                r
                for r in dg_rows
                if str(r.get("Region") or "").upper() == region
                and (_parse_float(r.get("Num_Trades")) or 0) >= 10
            ]
            if not region_rows:
                continue
            best = max(region_rows, key=lambda r: _parse_float(r.get("Avg_Return_Pct")) or -999.0)
            avg = _parse_float(best.get("Avg_Return_Pct"))
            wr = _parse_float(best.get("Win_Rate_Pct"))
            if avg is not None:
                daily_gainers_by_region[region] = (
                    f"WR={wr:.1f}% AvgRet={avg:.2f}% hold={best.get('Hold_Days')}d"
                    if wr is not None
                    else f"AvgRet={avg:.2f}% hold={best.get('Hold_Days')}d"
                )

        macro_text = ""
        macro_path = root / ARTIFACT_FILES["macro"]
        if macro_path.is_file():
            try:
                macro_text = macro_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                macro_text = ""

        adaptive_payload = _load_json(root / ARTIFACT_FILES["adaptive"]) or {}
        raw_alloc = adaptive_payload.get("recommended_allocation") or {}
        adaptive_allocation = {
            str(k).upper(): float(v)
            for k, v in raw_alloc.items()
            if _parse_float(v) is not None
        }

        entry_cf = _load_json(root / ARTIFACT_FILES["entry_cf"]) or {}
        exit_cf = _load_json(root / ARTIFACT_FILES["exit_cf"]) or {}
        entry_verdict = str(entry_cf.get("verdict") or "UNKNOWN")
        exit_verdict = str(exit_cf.get("verdict") or "UNKNOWN")
        best_scenario = str(entry_cf.get("best_scenario_id") or "N/A")

        threshold_policy = "KEEP_THRESHOLD_90"
        intel_path = root / ARTIFACT_FILES["threshold_intel"]
        if intel_path.is_file():
            try:
                intel_text = intel_path.read_text(encoding="utf-8", errors="replace")
                if "KEEP_THRESHOLD" in intel_text:
                    match = re.search(r"(KEEP_THRESHOLD_\d+[^\n]*)", intel_text)
                    if match:
                        threshold_policy = match.group(1).strip()
            except OSError:
                pass

        return cls(
            momentum_by_ticker=momentum_by_ticker,
            threshold_tickers=threshold_tickers,
            regional_strength=regional_strength,
            regional_validation_status=rv_status,
            sector_top=sector_top,
            sector_top_score=sector_top_score,
            etf_scores=etf_scores,
            daily_gainers_by_region=daily_gainers_by_region,
            macro_verdict=_parse_macro_verdict(macro_text),
            macro_confidence=_parse_macro_confidence(macro_text),
            adaptive_allocation=adaptive_allocation,
            entry_cf_verdict=entry_verdict,
            entry_cf_best=best_scenario,
            exit_cf_verdict=exit_verdict,
            threshold_policy=threshold_policy,
            top_momentum_candidates=top_momentum[:5],
            artifacts_loaded=artifacts_loaded,
        )

    def enrich_ticker(self, ticker: str, signal: str = "", score: Any = None) -> dict[str, Any]:
        ticker = str(ticker).upper().strip()
        market = _infer_market(ticker)
        region = _region_key(market)

        mom_row = self.momentum_by_ticker.get(ticker)
        if mom_row:
            mom_score = mom_row.get("Momentum_Score")
            mom_edge = mom_row.get("Research_Edge") or "ACTIVE"
            research_momentum = f"SCORE={mom_score} EDGE={mom_edge}"
        else:
            research_momentum = "NO_MOMENTUM_SIGNAL"

        research_daily = self.daily_gainers_by_region.get(region, "NO_REGION_DATA")

        score_val = _parse_float(score)
        if ticker in self.threshold_tickers:
            research_threshold = "VIRTUAL_80_CANDIDATE"
        elif score_val is not None and score_val >= 90:
            research_threshold = f"SCORE_{int(score_val)}>{self.threshold_policy}"
        elif score_val is not None and score_val >= 80:
            research_threshold = f"SCORE_{int(score_val)}_WATCH"
        else:
            research_threshold = self.threshold_policy

        r_strength = self.regional_strength.get(region)
        if r_strength is not None:
            research_regional = f"{region}_STRENGTH={r_strength:.2f} RV={self.regional_validation_status}"
        else:
            research_regional = f"RV={self.regional_validation_status}"

        alloc_pct = self.adaptive_allocation.get(region)
        macro_conf = self.macro_confidence
        if alloc_pct is not None:
            research_macro = (
                f"{self.macro_verdict} alloc={alloc_pct:.1f}%"
                f"{f' conf={macro_conf:.0f}%' if macro_conf is not None else ''}"
            )
        else:
            research_macro = self.macro_verdict

        if self.sector_top_score is not None:
            research_sector = f"LEADER={self.sector_top}({self.sector_top_score:.2f})"
        else:
            research_sector = f"LEADER={self.sector_top}"

        etf_score = self.etf_scores.get(ticker)
        if etf_score is not None:
            research_etf = f"STRATEGIC={etf_score:.2f}"
        elif ticker in ("SPY", "QQQ", "IWM", "DIA"):
            research_etf = "BENCHMARK_ETF"
        else:
            research_etf = "N/A"

        research_counterfactual = (
            f"ENTRY={self.entry_cf_verdict} BEST={self.entry_cf_best} EXIT={self.exit_cf_verdict}"
        )

        sources = sum(1 for loaded in self.artifacts_loaded.values() if loaded)
        research_confidence = round(min(100.0, sources * 8.0 + (10 if mom_row else 0)), 1)

        ctx_parts = [
            f"market={market}",
            f"momentum={research_momentum}",
            f"sector={research_sector}",
            f"regional={research_regional}",
            f"macro={research_macro}",
            f"threshold={research_threshold}",
            f"counterfactual={research_counterfactual}",
        ]
        if signal:
            ctx_parts.append(f"signal={signal}")
        if score is not None:
            ctx_parts.append(f"score={score}")

        return {
            "Research_Momentum": research_momentum,
            "Research_Daily_Gainers": research_daily,
            "Research_Threshold": research_threshold,
            "Research_Regional": research_regional,
            "Research_Macro": research_macro,
            "Research_Sector": research_sector,
            "Research_ETF": research_etf,
            "Research_Counterfactual": research_counterfactual,
            "Research_Confidence": research_confidence,
            "Research_Context": "; ".join(ctx_parts),
        }

    def advisory_summary(self) -> dict[str, Any]:
        return {
            "top_research_candidates": self.top_momentum_candidates,
            "momentum_summary": (
                f"{len(self.momentum_by_ticker)} momentum signals; "
                f"top={[c['ticker'] for c in self.top_momentum_candidates[:3]]}"
            ),
            "sector_summary": (
                f"Leader {self.sector_top} score={self.sector_top_score}"
                if self.sector_top_score is not None
                else f"Leader {self.sector_top}"
            ),
            "regional_summary": (
                f"Strength {self.regional_strength} validation={self.regional_validation_status}"
            ),
            "macro_summary": (
                f"{self.macro_verdict} allocation={self.adaptive_allocation}"
            ),
            "counterfactual_summary": (
                f"entry={self.entry_cf_verdict} best={self.entry_cf_best} exit={self.exit_cf_verdict}"
            ),
            "threshold_policy": self.threshold_policy,
            "artifacts_loaded": self.artifacts_loaded,
        }


def enrich_live_signals_file(
    root: Path | str = ".",
    *,
    signals_path: str = "live_signals.csv",
) -> dict[str, Any]:
    root = Path(root)
    path = root / signals_path
    if not path.is_file():
        return {"ok": False, "error": f"Missing {signals_path}", "rows": 0}

    ctx = ResearchContext.load(root)
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"ok": False, "error": "Empty live_signals.csv", "rows": 0}

    fieldnames = list(rows[0].keys())
    for col in RESEARCH_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    enriched = 0
    strong_buy_research: list[dict[str, Any]] = []
    for row in rows:
        ticker = str(row.get("Ticker") or "").upper()
        enrichment = ctx.enrich_ticker(
            ticker,
            signal=str(row.get("Signal") or ""),
            score=row.get("Score"),
        )
        row.update(enrichment)
        enriched += 1
        if str(row.get("Signal", "")).upper() == "STRONG BUY":
            strong_buy_research.append(
                {
                    "ticker": ticker,
                    **{k: enrichment[k] for k in RESEARCH_COLUMNS},
                }
            )

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    strong_buy = sum(1 for r in rows if str(r.get("Signal", "")).upper() == "STRONG BUY")
    return {
        "ok": True,
        "rows": len(rows),
        "enriched": enriched,
        "strong_buy_count": strong_buy,
        "strong_buy_research_summary": strong_buy_research[:10],
        "advisory_summary": ctx.advisory_summary(),
        "artifacts_loaded": ctx.artifacts_loaded,
    }
