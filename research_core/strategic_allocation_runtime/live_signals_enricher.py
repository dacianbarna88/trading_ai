"""Live signals strategic allocation enricher — read-only from existing artifacts."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALLOCATION_COLUMNS = (
    "Allocation_Score",
    "Allocation_Confidence",
    "Allocation_Region",
    "Allocation_Sector",
    "Allocation_Macro",
    "Allocation_Bias",
    "Capital_Flow",
    "Regional_Strength",
    "Strategic_Portfolio_Score",
    "Allocation_Context",
)

ARTIFACT_FILES = {
    "strategic_allocation": "strategic_allocation.csv",
    "strategic_bias": "strategic_bias.csv",
    "regional_strength": "regional_strength.csv",
    "sector_rotation": "sector_rotation.csv",
    "adaptive_allocation": "adaptive_allocation.json",
    "allocation_gap": "allocation_gap_analysis.json",
    "allocator_health": "allocator_health.csv",
    "portfolio_score": "strategic_portfolio_score.csv",
    "capital_flow": "capital_flow_summary.txt",
    "horizon": "horizon_vote_summary.txt",
    "strategic_intel": "strategic_intelligence_summary.txt",
    "macro": "macro_committee_summary.txt",
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
        return float(str(value).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


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
        return "EUROPE"
    if market == "UK":
        return "UK"
    if market == "ASIA":
        return "ASIA"
    return "US"


def _parse_macro_verdict(text: str) -> str:
    match = re.search(r"FINAL MACRO VOTE:\s*(\S+)", text)
    return match.group(1) if match else "MACRO_UNKNOWN"


@dataclass
class AllocationContext:
    region_allocation: dict[str, float]
    region_bias: dict[str, str]
    region_strength: dict[str, float]
    adaptive_allocation: dict[str, float]
    allocation_gaps: dict[str, dict[str, Any]]
    sector_leader: str
    sector_score: float | None
    capital_flow_view: str
    horizon_vote: str
    macro_verdict: str
    strategic_bias_view: str
    portfolio_score: float | None
    allocator_health: float | None
    artifacts_loaded: dict[str, bool] = field(default_factory=dict)

    @classmethod
    def load(cls, root: Path | str = ".") -> AllocationContext:
        root = Path(root)
        artifacts_loaded = {
            name: (root / fname).is_file() for name, fname in ARTIFACT_FILES.items()
        }

        region_allocation: dict[str, float] = {}
        region_bias: dict[str, str] = {}
        for row in _load_csv_rows(root / ARTIFACT_FILES["strategic_allocation"]):
            region = str(row.get("Region") or "").upper()
            alloc = _parse_float(row.get("Normalized_Allocation_%"))
            bias = str(row.get("Strategic_Bias") or "NEUTRAL")
            if region and alloc is not None:
                region_allocation[region] = alloc
                region_bias[region] = bias

        for row in _load_csv_rows(root / ARTIFACT_FILES["strategic_bias"]):
            region = str(row.get("Region") or "").upper()
            bias = str(row.get("Strategic_Bias") or "NEUTRAL")
            if region:
                region_bias.setdefault(region, bias)

        region_strength: dict[str, float] = {}
        for row in _load_csv_rows(root / ARTIFACT_FILES["regional_strength"]):
            region = str(row.get("Region") or "").upper()
            strength = _parse_float(row.get("Regional_Strength"))
            if region and strength is not None:
                region_strength[region] = strength

        adaptive_payload = _load_json(root / ARTIFACT_FILES["adaptive_allocation"]) or {}
        raw_alloc = adaptive_payload.get("recommended_allocation") or {}
        adaptive_allocation = {
            str(k).upper(): float(v)
            for k, v in raw_alloc.items()
            if _parse_float(v) is not None
        }

        allocation_gaps = _load_json(root / ARTIFACT_FILES["allocation_gap"]) or {}

        sector_leader = "UNKNOWN"
        sector_score: float | None = None
        sector_rows = _load_csv_rows(root / ARTIFACT_FILES["sector_rotation"])
        if sector_rows:
            best = max(
                sector_rows,
                key=lambda r: _parse_float(r.get("Sector_Score")) or -999.0,
            )
            sector_leader = str(best.get("Sector") or "UNKNOWN")
            sector_score = _parse_float(best.get("Sector_Score"))

        capital_flow_view = "NO_DATA"
        cf_text = _read_text(root / ARTIFACT_FILES["capital_flow"])
        if "CAPITAL_FLOW_IN" in cf_text:
            capital_flow_view = "INFLOW_BIAS"
        elif "CAPITAL_FLOW_OUT" in cf_text:
            capital_flow_view = "OUTFLOW_BIAS"
        elif cf_text.strip():
            capital_flow_view = "STABLE"

        horizon_text = _read_text(root / ARTIFACT_FILES["horizon"])
        horizon_vote = "HORIZON_NEUTRAL"
        if "LONG_TERM_US" in horizon_text:
            horizon_vote = "LONG_TERM_US"
        elif "LONG_TERM_EUROPE" in horizon_text:
            horizon_vote = "LONG_TERM_EUROPE"
        elif "LONG_TERM_UK" in horizon_text:
            horizon_vote = "LONG_TERM_UK"

        macro_verdict = _parse_macro_verdict(_read_text(root / ARTIFACT_FILES["macro"]))
        intel_text = _read_text(root / ARTIFACT_FILES["strategic_intel"])
        strategic_bias_view = "NEUTRAL"
        if "OVERWEIGHT_US" in intel_text:
            strategic_bias_view = "OVERWEIGHT_US"
        elif "UNDERWEIGHT" in intel_text:
            strategic_bias_view = "DEFENSIVE_BIAS"

        portfolio_score: float | None = None
        score_rows = _load_csv_rows(root / ARTIFACT_FILES["portfolio_score"])
        if score_rows:
            portfolio_score = _parse_float(score_rows[0].get("Strategic_Portfolio_Score"))

        allocator_health: float | None = None
        health_rows = _load_csv_rows(root / ARTIFACT_FILES["allocator_health"])
        if health_rows:
            total_gap = sum(abs(_parse_float(r.get("Gap_%")) or 0) for r in health_rows)
            allocator_health = round(max(0.0, 100.0 - total_gap / 2), 1)

        return cls(
            region_allocation=region_allocation,
            region_bias=region_bias,
            region_strength=region_strength,
            adaptive_allocation=adaptive_allocation,
            allocation_gaps=allocation_gaps,
            sector_leader=sector_leader,
            sector_score=sector_score,
            capital_flow_view=capital_flow_view,
            horizon_vote=horizon_vote,
            macro_verdict=macro_verdict,
            strategic_bias_view=strategic_bias_view,
            portfolio_score=portfolio_score,
            allocator_health=allocator_health,
            artifacts_loaded=artifacts_loaded,
        )

    def enrich_ticker(self, ticker: str, signal: str = "", score: Any = None) -> dict[str, Any]:
        ticker = str(ticker).upper().strip()
        market = _infer_market(ticker)
        region = _region_key(market)

        region_alloc = self.region_allocation.get(region)
        if region_alloc is None and market == "EU":
            region_alloc = self.region_allocation.get("EUROPE")
        region_bias = self.region_bias.get(region, self.region_bias.get("EUROPE", "NEUTRAL"))
        strength = self.region_strength.get(region, self.region_strength.get("EUROPE"))
        adaptive_pct = self.adaptive_allocation.get(market, self.adaptive_allocation.get("US"))

        gap_info = self.allocation_gaps.get(market) or self.allocation_gaps.get(region)
        gap_action = gap_info.get("action") if isinstance(gap_info, dict) else None

        allocation_score = 50.0
        if region_alloc is not None:
            allocation_score += min(25.0, region_alloc * 0.4)
        if strength is not None:
            allocation_score += min(15.0, strength * 0.5)
        if self.portfolio_score is not None:
            allocation_score += self.portfolio_score * 0.15
        if region_bias == "OVERWEIGHT":
            allocation_score += 5.0
        elif region_bias == "UNDERWEIGHT":
            allocation_score -= 5.0
        allocation_score = round(min(100.0, max(0.0, allocation_score)), 2)

        sources = sum(1 for loaded in self.artifacts_loaded.values() if loaded)
        allocation_confidence = round(min(100.0, sources * 7.0 + (10 if gap_action else 0)), 1)

        allocation_region = (
            f"{region} alloc={region_alloc:.1f}% bias={region_bias} strength={strength}"
            if region_alloc is not None and strength is not None
            else f"{region} bias={region_bias}"
        )
        allocation_sector = (
            f"LEADER={self.sector_leader}({self.sector_score:.2f})"
            if self.sector_score is not None
            else f"LEADER={self.sector_leader}"
        )
        allocation_macro = f"{self.macro_verdict} adaptive={adaptive_pct}% gap={gap_action or 'N/A'}"
        capital_flow = self.capital_flow_view
        regional_strength = f"{strength:.2f}" if strength is not None else "N/A"
        portfolio_score = self.portfolio_score

        ctx_parts = [
            f"market={market}",
            f"region={allocation_region}",
            f"sector={allocation_sector}",
            f"macro={allocation_macro}",
            f"bias={self.strategic_bias_view}",
            f"capital_flow={capital_flow}",
            f"horizon={self.horizon_vote}",
            f"portfolio_score={portfolio_score}",
        ]
        if signal:
            ctx_parts.append(f"signal={signal}")
        if score is not None:
            ctx_parts.append(f"score={score}")

        return {
            "Allocation_Score": allocation_score,
            "Allocation_Confidence": allocation_confidence,
            "Allocation_Region": allocation_region,
            "Allocation_Sector": allocation_sector,
            "Allocation_Macro": allocation_macro,
            "Allocation_Bias": self.strategic_bias_view,
            "Capital_Flow": capital_flow,
            "Regional_Strength": regional_strength,
            "Strategic_Portfolio_Score": portfolio_score,
            "Allocation_Context": "; ".join(ctx_parts),
        }

    def advisory_summary(self) -> dict[str, Any]:
        return {
            "regional_allocation": self.region_allocation,
            "sector_allocation": {
                "leader": self.sector_leader,
                "score": self.sector_score,
            },
            "macro_allocation": {
                "verdict": self.macro_verdict,
                "adaptive": self.adaptive_allocation,
            },
            "capital_flow": self.capital_flow_view,
            "strategic_bias": self.strategic_bias_view,
            "allocation_confidence": round(
                sum(1 for v in self.artifacts_loaded.values() if v) * 7.0,
                1,
            ),
            "portfolio_score": self.portfolio_score,
            "allocator_health": self.allocator_health,
            "horizon_vote": self.horizon_vote,
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

    ctx = AllocationContext.load(root)
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return {"ok": False, "error": "Empty live_signals.csv", "rows": 0}

    fieldnames = list(rows[0].keys())
    for col in ALLOCATION_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    enriched = 0
    strong_buy_allocation: list[dict[str, Any]] = []
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
            strong_buy_allocation.append({"ticker": ticker, **enrichment})

    strong_buy_allocation.sort(
        key=lambda x: _parse_float(x.get("Allocation_Score")) or 0,
        reverse=True,
    )
    advisory = ctx.advisory_summary()
    advisory["top_allocation_candidates"] = [
        {
            "ticker": c["ticker"],
            "allocation_score": c.get("Allocation_Score"),
            "confidence": c.get("Allocation_Confidence"),
        }
        for c in strong_buy_allocation[:5]
    ]

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
        "strong_buy_allocation_summary": strong_buy_allocation[:10],
        "advisory_summary": advisory,
        "artifacts_loaded": ctx.artifacts_loaded,
    }
